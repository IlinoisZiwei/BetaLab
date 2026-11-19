"""Conservative necessary contact-distance bounds, NOT a feasibility certificate.

Derived from CIS5810 Beta_Translator ff85726da2fbbd2616c409b01d6c03833ab62ce9
body_legs.local_chain/knee_translation and body_user.body_lengths. Cubic spline
extrema bound the knee translation over its declared coordinate range. Triangle
inequalities deliberately overestimate reach; exceeding them proves inconsistent
contact constraints only UNDER the assumed body and wall, not human inability.
"""
import numpy as np
from beta_translator.body_legs import source,spline_coefficients,bounds_and_rates
from beta_translator.body_user import body_lengths
from .source_diagnostics import LIMBS


def spline_range(spec,lower,upper):
    x,y=np.asarray(spec['x']),np.asarray(spec['y'])
    b,c,d,end=spline_coefficients(tuple(x),tuple(y))
    values=[]
    for i in range(len(x)-1):
        a,z=max(lower,x[i]),min(upper,x[i+1])
        if a>z:continue
        candidates=[a-x[i],z-x[i]]
        roots=np.polynomial.polynomial.polyroots([b[i],2*c[i],3*d[i]])
        candidates.extend(float(r.real) for r in roots if abs(r.imag)<1e-9 and a-x[i]<=r.real<=z-x[i])
        values.extend(y[i]+v*(b[i]+v*(c[i]+v*d[i])) for v in candidates)
    if lower<x[0]:values.extend([y[0]+(lower-x[0])*b[0],y[0]+(min(upper,x[0])-x[0])*b[0]])
    if upper>x[-1]:values.extend([y[-1]+(max(lower,x[-1])-x[-1])*end,y[-1]+(upper-x[-1])*end])
    return min(values),max(values)


def contact_distance_bounds(profile):
    from beta_translator.body_legs import knee_translation
    lengths=body_lengths(profile);d=profile['dimensions_cm'];lo,hi,_,_=bounds_and_rates()
    arm=lengths['upper_arm']+lengths['forearm']+np.hypot(d['hand_patch_distance'],d['hand_patch_depth'])
    radii=[arm,arm]
    for side,offset in [('l',20),('r',26)]:
        axes=source()['joints']['knee_'+side]['axes'][3:]
        maxima=[]
        for axis in axes:
            if not axis['coordinate']:maxima.append(0.);continue
            a,b=spline_range(axis['function'],-hi[offset+3],-lo[offset+3]);maxima.append(max(abs(a),abs(b)))
        knee_bound=np.linalg.norm(maxima)*lengths['thigh']/np.linalg.norm(knee_translation(np.asarray(0.),side))
        ankle_offset=np.linalg.norm(source()['joints']['subtalar_'+side]['parent']['translation'])*(profile['height_cm']/180*100)
        radii.append(knee_bound+lengths['shank']+ankle_offset+np.hypot(.65*d['foot_length'],d['foot_depth']))
    roots=np.array([[-lengths['shoulder_w']/2,lengths['torso'],0],[lengths['shoulder_w']/2,lengths['torso'],0],
                    [-lengths['hip_w']/2,0,0],[lengths['hip_w']/2,0,0]])
    return np.array(radii)[:,None]+np.array(radii)[None,:]+np.linalg.norm(roots[:,None]-roots[None,:],axis=-1)


def audit_reach(evidence,profile,tolerance_cm=5.):
    bounds=contact_distance_bounds(profile);violations=[]
    for a in range(4):
        for b in range(a+1,4):
            distance=np.linalg.norm(evidence['contacts_cm'][:,a]-evidence['contacts_cm'][:,b],axis=-1)
            mask=evidence['trusted'][:,a]&evidence['trusted'][:,b]&(distance>bounds[a,b]+2*tolerance_cm)
            for frame in np.flatnonzero(mask):
                violations.append(dict(frame=int(frame),at_seconds=float(frame/30),limbs=[LIMBS[a],LIMBS[b]],
                    holds=[str(evidence['labels'][frame,a]),str(evidence['labels'][frame,b])],
                    distance_cm=float(distance[frame]),conservative_max_cm=float(bounds[a,b]),
                    unavoidable_max_endpoint_error_cm=float((distance[frame]-bounds[a,b])/2)))
    return dict(scope='Necessary condition under assumed calibration/body; passing is NOT sufficient.',
        tolerance_cm=tolerance_cm,pair_bounds_cm=bounds.tolist(),
        inconsistent_frames=len({v['frame'] for v in violations}),violations=violations)
