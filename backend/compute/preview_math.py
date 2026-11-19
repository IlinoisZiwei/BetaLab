"""Geometry-only adaptation; no claim of force/balance feasibility.

Adapted from BetaLab local-server/quick_worker.py and CIS5810 Beta_Translator
ff85726da2fbbd2616c409b01d6c03833ab62ce9: body_legs.kinematics/bounds_and_rates,
body_user.body_lengths. Preserves the source frame/contact schedule exactly.
"""
import numpy as np
from scipy.optimize import least_squares
from beta_translator.body_legs import kinematics, bounds_and_rates
from beta_translator.body_user import body_lengths

def geometry(q, profile):
    d=profile['dimensions_cm']
    g=kinematics(np.atleast_2d(q),body_lengths(profile),profile['height_cm'])
    hands=[]
    for side in range(2):
        orientation=g['orientations'][:,3+side*3]
        hands.append(g['joints'][:,side,2]-d['hand_patch_distance']*orientation[:,:,1]-d['hand_patch_depth']*orientation[:,:,2])
    feet=g['foot_origins']+np.einsum('tsij,j->tsi',g['foot_frames'],[.65*d['foot_length'],0.,-d['foot_depth']])
    g['contact_points']=np.concatenate([np.stack(hands,1),feet],axis=1)
    return g

def adapt(reference, evidence, profile, progress):
    lo,hi,speed,_=bounds_and_rates()
    trusted=evidence['trusted']
    target=np.where(trusted[...,None],evidence['contacts_cm'],0.)
    confidence=np.clip(evidence['confidence'],0,1)
    weight=np.where(trusted,np.where(confidence<.45,.35,1.),0.)
    # Tentative approach only without a trusted anchor; never label it a new contact.
    # Adapted from the look-ahead in local-server/quick_worker.py (15 -> 30 frames).
    points=geometry(reference,profile)['contact_points']
    guide=np.zeros_like(target)
    guide_weight=np.zeros_like(weight)
    for limb in range(4):
        for arrival in range(1,len(reference)):
            if not trusted[arrival,limb] or trusted[arrival-1,limb]:
                continue
            start=arrival-1
            while start>0 and not trusted[start-1,limb] and arrival-start<30:
                start-=1
            for frame in range(start,arrival):
                u=(frame-start+1)/(arrival-start+1)
                blend=u*u*(3-2*u)
                guide[frame,limb]=(1-blend)*points[start,limb]+blend*target[arrival,limb]
                guide_weight[frame,limb]=2*blend
    poses=[]
    previous=None
    converged=0
    for t,ref in enumerate(reference):
        low,high=lo.copy(),hi.copy()
        if previous is not None:
            low=np.maximum(low,previous-speed/30)
            high=np.minimum(high,previous+speed/30)
        anchor=ref if previous is None else previous
        def values(q):
            q=np.atleast_2d(q)
            endpoints=geometry(q,profile)['contact_points']
            contact=((endpoints-target[t])*weight[t][None,:,None]/2).reshape(len(q),-1)
            prior=(q-ref)/np.r_[np.full(3,40.),np.full(29,2.)]
            smooth=.15*(q-anchor)/np.r_[np.full(3,20.),np.full(29,1.)]
            approach=((endpoints-guide[t])*guide_weight[t][None,:,None]/2).reshape(len(q),-1)
            return np.c_[contact,approach,prior,smooth]
        def jacobian(q):
            batch=np.broadcast_to(q,(32,32)).astype(complex).copy()
            batch[np.arange(32),np.arange(32)]+=1e-25j
            return (values(batch).imag/1e-25).T
        seed=ref if previous is None else previous+(ref-reference[t-1])
        solution=least_squares(lambda q:values(q)[0],np.clip(seed,low+1e-10,high-1e-10),
            jac=jacobian,bounds=(low,high),max_nfev=80 if t==0 else 20,ftol=1e-3,xtol=1e-3,gtol=1e-3)
        previous=solution.x
        poses.append(previous.copy())
        converged+=int(solution.success)
        if (t+1)%100==0:
            progress('adapting',f'{t+1}/{len(reference)} frames')
    q=np.stack(poses)
    g=geometry(q,profile)
    gaps=np.linalg.norm(g['contact_points']-target,axis=-1)
    g['contact_gaps_cm']=np.where(trusted,gaps,np.nan)
    diagnostics=dict(check_scope='geometry_only',mechanics_checked=False,physical_validation=False,
        frames=len(q),solver_converged_frames=converged,
        trusted_contact_samples=int(trusted.sum()),unconfirmed_contact_samples=int((evidence['known']&~trusted).sum()),
        supported_max_gap_cm=float(gaps[trusted].max()) if trusted.any() else None,
        supported_frames_over_5cm=int((np.where(trusted,gaps,0).max(1)>5).sum()),
        joint_bounds_pass=bool(np.all(q>=lo-1e-7)&np.all(q<=hi+1e-7)),
        coordinate_rate_pass=bool(np.all(abs(np.diff(q,axis=0))*30<=speed+1e-7)),
        contact_order_preserved=True,contact_timing_preserved=True)
    return q,g,diagnostics
