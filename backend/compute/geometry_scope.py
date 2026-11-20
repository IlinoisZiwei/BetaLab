"""Known two-panel scope; never turn an unmeasured floor into a verified contact.

Panel intersection convention: CIS5810 Beta_Translator trial2_scene3d.py,
ff85726da2fbbd2616c409b01d6c03833ab62ce9. Raw labels/timing remain unchanged.
"""
import numpy as np

def wall_contacts(evidence):
    return evidence['trusted'] & ~evidence['ground']

def known_wall_clearance(scene,points):
    """Check only the two user-confirmed climbing planes; zero outside this scope."""
    if not hasattr(scene,'normals'):return scene.wall_clearance(points)
    signed=[]
    for i in (0,1):
        distance=((points-scene.origins[i])*scene.normals[i]).sum(-1)
        surface=points-distance[...,None]*scene.normals[i]
        applies=scene.panel(scene.pixels(surface).real)==i
        signed.append(np.where(applies,distance,np.inf))
    clearance=np.min(np.stack(signed),axis=0)
    return np.where(np.isfinite(clearance.real),clearance,0)

def diagnostic_moments(evidence,gaps):
    from .moments import build_moments,runs,LIMBS
    ground=evidence['ground'];trusted=wall_contacts(evidence)
    moments=build_moments((evidence['known']&~ground).tolist(),trusted.tolist(),gaps.tolist())
    for limb,name in enumerate(LIMBS):
        for first,last in runs(ground[:,limb].tolist()):
            moments.append(dict(id=f'ground-{name}-{first}',kind='unconfirmed_contact',
                frame=first,end_frame=last,at_seconds=first/30,limb=name,media='video',gap_cm=None,
                title='Ground geometry not verified',explanation='The original foot-ground candidates are kept. The lower wall corner is unknown, so the estimated ground coordinates are not used as a verified constraint.'))
    return sorted(moments,key=lambda m:(m['frame'],m['limb']))

def contact_transitions(evidence):
    """Keep abrupt candidate switches reviewable; do not rewrite their timing."""
    from .moments import LIMBS
    trusted=wall_contacts(evidence);labels=evidence['labels'];rows=[]
    for limb,name in enumerate(LIMBS):
        switches=trusted[1:,limb]&trusted[:-1,limb]&(labels[1:,limb]!=labels[:-1,limb])
        for frame in np.flatnonzero(switches)+1:
            distance=float(np.linalg.norm(evidence['contacts_cm'][frame,limb]-evidence['contacts_cm'][frame-1,limb]))
            rows.append(dict(limb=name,previous_frame=int(frame-1),frame=int(frame),at_seconds=float(frame/30),
                previous_hold=str(labels[frame-1,limb]),hold=str(labels[frame,limb]),anchor_jump_cm=distance,
                implied_same_point_speed_cm_s=distance*30,
                note='Candidate switch under the fixed contact-point model; review evidence, not a claim of human motion.'))
    return rows
