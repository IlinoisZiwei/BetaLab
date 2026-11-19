"""Source-fit evidence audit, using Beta Translator body_legs/Trial2Scene.

Reference: CIS5810 Beta_Translator ff85726da2fbbd2616c409b01d6c03833ab62ce9.
Candidate contacts are not human-confirmed contacts. Never change their schedule.
"""
import numpy as np
from beta_translator.body_legs import bounds_and_rates
from .preview_math import geometry
from .geometry_scope import wall_contacts,known_wall_clearance

LIMBS=('left_hand','right_hand','left_foot','right_foot')

def evaluate(q,evidence,profile,scene):
    g=geometry(q,profile)
    gaps=np.linalg.norm(g['contact_points']-evidence['contacts_cm'],axis=-1)
    trusted=evidence['trusted'].astype(bool)
    lo,hi,speed,_=bounds_and_rates()
    projected=scene.pixels(g['joints'])
    pixel_error=np.linalg.norm(projected-evidence['observed_px'],axis=-1)
    visible=(evidence['visibility']>.5)&np.isfinite(pixel_error)
    rate=np.abs(np.diff(q,axis=0))*30
    # Joint-center clearance is a diagnostic, NOT a capsule/collision certificate.
    clearance=scene.wall_clearance(g['joints'])
    rows=[];episodes=[]
    for limb,name in enumerate(LIMBS):
        labels=evidence['labels'][:,limb]
        starts=np.flatnonzero(np.r_[True,labels[1:]!=labels[:-1]])
        for a,b in zip(starts,np.r_[starts[1:],len(q)]):
            known=evidence['known'][a:b,limb]
            if not known.any():continue
            mask=trusted[a:b,limb];valid=gaps[a:b,limb][mask]
            indices=np.flatnonzero(mask)+a
            peak=int(indices[np.argmax(valid)]) if len(valid) else None
            episode=dict(limb=name,hold=str(labels[a]),start_frame=int(a),end_frame=int(b-1),
                evidence_frames=int(evidence['evidence_frames'][a,limb]),
                ground_proposal=bool(evidence['ground'][a,limb]),expert_confirmed=False,
                checked_samples=int(mask.sum()),max_gap_cm=float(valid.max()) if len(valid) else None,
                frames_over_5cm=int((valid>5).sum()),peak_frame=peak,
                interior_frames_over_5cm=int(((gaps[a:b,limb]>5)&mask&(np.arange(b-a)>=5)&(np.arange(b-a)<b-a-5)).sum()))
            episodes.append(episode)
            for f in range(a,b):
                rows.append(dict(frame=f,at_seconds=f/30,limb=name,hold=str(labels[f]),
                    phase='arrival' if f-a<5 else ('departure' if b-f<=5 else 'interior'),
                    checked=bool(trusted[f,limb]),gap_cm=float(gaps[f,limb]) if trusted[f,limb] else None))
    valid=gaps[trusted]
    stats=dict(frames=len(q),checked_samples=int(trusted.sum()),unconfirmed_samples=int((evidence['known']&~trusted).sum()),
        max_gap_cm=float(valid.max()) if len(valid) else None,
        p95_gap_cm=float(np.percentile(valid,95)) if len(valid) else None,
        frames_over_5cm=int(np.any((gaps>5)&trusted,axis=1).sum()),
        joint_bounds_pass=bool(np.all(q>=lo-1e-7)&np.all(q<=hi+1e-7)),
        coordinate_rate_pass=bool(np.all(rate<=speed+1e-7)),
        rate_violation_frames=int(np.any(rate>speed+1e-7,axis=1).sum()),
        max_rate_ratio=float(np.max(rate/speed)) if len(q)>1 else 0.,
        observed_joint_rmse_px=float(np.sqrt(np.mean(pixel_error[visible]**2))) if visible.any() else None,
        observed_joint_samples=int(visible.sum()),
        joint_centers_behind_wall_frames=int(np.any(clearance< -1,axis=(1,2)).sum()),
        min_joint_wall_clearance_cm=float(np.min(clearance)),
        physical_validation=False,collision_validation=False)
    wall_mask=wall_contacts(evidence)
    wall_gaps=gaps[wall_mask]
    wall_clearance=known_wall_clearance(scene,g['joints'])
    stats.update(wall_checked_samples=int(wall_mask.sum()),
        deferred_ground_samples=int((trusted&evidence['ground']).sum()),
        wall_max_gap_cm=float(wall_gaps.max()) if wall_gaps.size else None,
        wall_frames_over_5cm=int(np.any((gaps>5)&wall_mask,axis=1).sum()),
        known_wall_penetration_frames=int(np.any(wall_clearance< -1,axis=(1,2)).sum()),
        known_wall_min_clearance_cm=float(wall_clearance.min()),
        ground_geometry_status='unknown: lower-panel angle not measured',
        full_geometry_certified=False)
    stats['wall_contact_check_pass']=bool(wall_gaps.size and not stats['wall_frames_over_5cm'])
    stats['contact_check_pass']=bool(len(valid)>0 and not stats['frames_over_5cm'])
    return dict(summary=stats,episodes=episodes,frame_contacts=rows),g
