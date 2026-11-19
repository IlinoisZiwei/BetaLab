"""Fit source motion to image observations and unchanged contact candidates.

Uses CIS5810 Beta_Translator ff85726da2fbbd2616c409b01d6c03833ab62ce9:
body_legs bounds/kinematics and Trial2Scene pixels/wall_clearance. The temporal
least-squares objective here is a BetaLab adapter, not the original full-force
solver. Wall angles, contact evidence and body measurements are not inferred.
"""
import numpy as np
from scipy.optimize import least_squares
from beta_translator.body_legs import bounds_and_rates
from .preview_math import geometry
from .geometry_scope import wall_contacts,known_wall_clearance


def fit_source(reference,evidence,profile,scene,progress,max_nfev=200,initial=None):
    """Fit known-wall contacts with dense IK, rate-limited warm start and a
    block-tridiagonal temporal solve. Ground candidates remain in raw evidence.
    Every temporal result is projected onto the ORIGINAL joint/rate limits and
    must then be checked again for contact and wall errors.
    """
    from .preview_math import adapt
    from .trajectory_solver import solve
    n=len(reference);lo,hi,speed,_=bounds_and_rates();scale=np.r_[np.full(3,40.),np.ones(29)]
    mask=wall_contacts(evidence)
    observed=np.nan_to_num(evidence['observed_px'])
    visible=(evidence['visibility']>.5)&np.isfinite(evidence['observed_px']).all(-1)
    if initial is None:
        dense=initialize_source(reference,evidence,profile,scene,progress)
        initial=adapt(dense,{**dict(evidence),'trusted':mask},profile,progress)[0]
    stages=[];q=initial
    for contact_weight,wall_scale,iterations in [(1.,.5,min(100,max_nfev)),(2.,.2,max_nfev),(10.,.02,max_nfev)]:
        def local(q):
            g=geometry(q,profile)
            contact=contact_weight*((g['contact_points']-evidence['contacts_cm'])*mask[...,None]).reshape(n,-1)
            pixels=((scene.pixels(g['joints'])-observed)*visible[...,None]/12).reshape(n,-1)
            clearance=known_wall_clearance(scene,g['joints'])
            wall=np.where(clearance.real<0,clearance,0).reshape(n,-1)/wall_scale
            return np.c_[contact,pixels,wall,.02*(q-reference)/scale]
        q,info=solve(local,q,lo,hi,speed/30,progress,iterations=iterations)
        q,projection=project_rates(q)
        stages.append(dict(**info,projection=projection,contact_weight=contact_weight,wall_scale_cm=wall_scale))
    return q,dict(method='wall_source_observation_fit_v3',stages=stages,
        success=all(stage['success'] for stage in stages),
        contact_order_preserved=True,contact_timing_preserved=True,
        scope='Known upper/middle walls only; ground retained but not optimized or certified',
        note='Stopping and rate projection do not certify contact, collision or mechanics; inspect independent diagnostics.')


def adapt_body(reference,evidence,source_profile,target_profile,scene,progress,max_iterations=200):
    """Preserve identical bodies exactly; otherwise fit the whole target trajectory.

    New BetaLab adaptation using the attributed Beta Translator chain and original
    limits. Source image pixels describe the original person, so are not target
    observations. No contact labels, anchors or timing are changed.
    """
    if source_profile == target_profile:
        return reference.copy(),dict(method='identical_body_identity',success=True)
    from .trajectory_solver import solve
    lo,hi,speed,_=bounds_and_rates();mask=wall_contacts(evidence)
    scale=np.r_[np.full(3,40.),np.ones(29)];n=len(reference)
    def local(q):
        g=geometry(q,target_profile)
        contacts=(10*(g['contact_points']-evidence['contacts_cm'])*mask[...,None]).reshape(n,-1)
        clearance=known_wall_clearance(scene,g['joints'])
        wall=np.where(clearance.real<0,clearance,0).reshape(n,-1)/.02
        return np.c_[contacts,wall,(q-reference)/scale]
    q,info=solve(local,reference.copy(),lo,hi,speed/30,progress,iterations=max_iterations)
    q,projection=project_rates(q)
    return q,dict(method='wall_target_temporal_fit_v1',solver=info,projection=projection,
                  success=info['success'],contact_order_preserved=True,contact_timing_preserved=True)


def initialize_source(reference,evidence,profile,scene,progress):
    """Dense per-frame IK before temporal fitting; prevents a bad sequential branch
    from becoming a full-trajectory prior. Complex-step Jacobians reuse the actual
    Beta Translator chain, not the old 22-variable initializer's geometry.
    """
    lo,hi,_,_=bounds_and_rates();poses=[];scale=np.r_[np.full(3,40.),np.ones(29)]
    previous=None
    for t,ref in enumerate(reference):
        mask=wall_contacts(evidence)[t]
        visibility=evidence['visibility'][t]
        observed=np.nan_to_num(evidence['observed_px'][t])
        visible=(visibility>.5)&np.isfinite(evidence['observed_px'][t]).all(-1)
        def values(q):
            q=np.atleast_2d(q);g=geometry(q,profile)
            contact=((g['contact_points']-evidence['contacts_cm'][t])*mask[None,:,None]).reshape(len(q),-1)
            pixels=((scene.pixels(g['joints'])-observed)*visible[None,...,None]/12).reshape(len(q),-1)
            clearance=known_wall_clearance(scene,g['joints'])
            wall=np.where(clearance.real<0,clearance,0).reshape(len(q),-1)/2
            prior=.02*(q-ref)/scale
            smooth=.03*(q-(ref if previous is None else previous))/scale
            return np.c_[contact,pixels,wall,prior,smooth]
        def jacobian(q):
            batch=np.tile(q,(32,1)).astype(complex)
            batch[np.arange(32),np.arange(32)]+=1e-25j
            return (values(batch).imag/1e-25).T
        def solve(seed):
            return least_squares(lambda q:values(q)[0],np.clip(seed,lo+1e-8,hi-1e-8),
                jac=jacobian,bounds=(lo,hi),x_scale=scale,max_nfev=100,ftol=1e-5,xtol=1e-5,gtol=1e-5)
        best=solve(ref if previous is None else previous)
        # Retry the independent observed pose only when the previous branch is poor.
        if previous is not None and best.cost>20:
            alternate=solve(ref)
            if alternate.cost<best.cost:best=alternate
        previous=best.x;poses.append(previous.copy())
        if (t+1)%100==0:progress('source_skeleton',f'Observed source IK {t+1}/{len(reference)}')
    return np.stack(poses)


def project_rates(q,max_iterations=10000):
    """Dykstra projection onto joint boxes and adjacent-frame speed slabs.

    Uses the unchanged Beta Translator bounds/rates. This deterministic numerical
    projection is new BetaLab code; contacts must be rechecked after projection.
    """
    lo,hi,speed,_=bounds_and_rates();step=speed/30
    result=q.copy();corrections=[np.zeros_like(q) for _ in range(3)]
    for iteration in range(max_iterations):
        before=result.copy()
        for group in range(3):
            candidate=result+corrections[group]
            projected=candidate.copy()
            if group==2:projected=np.clip(candidate,lo,hi)
            else:
                left=np.arange(group,len(q)-1,2);right=left+1
                delta=candidate[right]-candidate[left]
                excess=(delta-np.clip(delta,-step,step))/2
                projected[left]+=excess;projected[right]-=excess
            corrections[group]=candidate-projected;result=projected
        if np.max(np.abs(result-before))<1e-10 and np.all(np.abs(np.diff(result,axis=0))<=step+1e-10):
            break
    if not np.all(np.abs(np.diff(result,axis=0))*30<=speed+1e-7):
        raise RuntimeError('Rate projection did not converge; do not publish it as a passed trajectory')
    return result,dict(method='dykstra_joint_box_and_speed_slabs',iterations=iteration+1)
