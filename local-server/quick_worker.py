"""Geometry-only, bounded per-frame IK. Detailed mechanics run separately."""
import os,sys,json,time
from pathlib import Path
started=time.perf_counter()
ROOT=Path(os.environ['BETA_TRANSLATOR_ROOT']);sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.optimize import least_squares
from beta_translator.body_legs import kinematics,bounds_and_rates
from beta_translator.body_user import body_lengths,validate_user
from render_preview import render
job=Path(sys.argv[1]);here=Path(__file__).parent;req=json.loads((job/'request.json').read_text());p=req['profile'];validate_user(p)
def update(**kw):
    data=json.loads((job/'status.json').read_text());data.update(kw);tmp=job/'quick-status.tmp';tmp.write_text(json.dumps(data));tmp.replace(job/'status.json')
try:
    update(state='fitting',message='Building quick body-proportion preview')
    with np.load(here/'prepared/trial2.npz',allow_pickle=False) as z:e={k:z[k] for k in z.files}
    scene=json.loads((here/'prepared/scene.json').read_text());holds=json.loads((here/'prepared/holds.json').read_text())
    lengths=body_lengths(p);d=p['dimensions_cm'];lo,hi,speed,_=bounds_and_rates();reference=e['q'];poses=[];prev=None
    def geometry(q):
        g=kinematics(np.atleast_2d(q),lengths,p['height_cm'])
        hands=[]
        for side in range(2):
            H=g['orientations'][:,3+side*3];hands.append(g['joints'][:,side,2]-d['hand_patch_distance']*H[:,:,1]-d['hand_patch_depth']*H[:,:,2])
        F=g['foot_frames'];local=np.array([.65*d['foot_length'],0.,-d['foot_depth']])
        foot=g['foot_origins']+np.einsum('tsij,j->tsi',F,local)
        g['contact_points']=np.concatenate([np.stack(hands,1),foot],axis=1)
        g['foot_heel']=g['foot_origins']-d['foot_depth']*F[:,:,:,2];g['foot_toe']=g['foot_heel']+d['foot_length']*F[:,:,:,0]
        return g
    # Preserve raw observations for audit; zero-support episodes are unresolved,
    # not silently relabelled as another hold or counted as solved contacts.
    trusted=e['known'] & (e['evidence_frames']>0)
    confidence=np.clip(e['confidence'],0,1)
    weight=np.where(trusted,np.where(confidence<.45,.35,1.),0.)
    # Smooth approach to the next supported target, only while unanchored.
    # Actual contact activation/timing is not moved earlier.
    reference_points=geometry(reference)['contact_points']
    guide_target=np.zeros_like(e['contacts']);guide_weight=np.zeros_like(weight)
    horizon=15
    for limb in range(4):
        for arrival in range(1,len(reference)):
            if not trusted[arrival,limb] or trusted[arrival-1,limb]:continue
            start=arrival-1
            while start>0 and not trusted[start-1,limb] and arrival-start<horizon:start-=1
            origin=reference_points[start,limb]
            for frame in range(start,arrival):
                u=(frame-start+1)/(arrival-start+1);blend=u*u*(3-2*u)
                guide_target[frame,limb]=(1-blend)*origin+blend*e['contacts'][arrival,limb]
                guide_weight[frame,limb]=.8*blend
    fit_started=time.perf_counter()
    for t,ref in enumerate(reference):
        low=lo.copy();high=hi.copy()
        if prev is not None:low=np.maximum(low,prev-speed/30);high=np.minimum(high,prev+speed/30)
        target=e['contacts'][t];known=weight[t];anchor=ref if prev is None else prev
        def values(q):
            q=np.atleast_2d(q);g=geometry(q)
            contact=((g['contact_points']-target)*known[None,:,None]/2).reshape(len(q),-1)
            approach=((g['contact_points']-guide_target[t])*guide_weight[t][None,:,None]/2).reshape(len(q),-1)
            prior=(q-ref)/np.r_[np.full(3,40.),np.full(29,2.)]
            continuity=(q-anchor)/np.r_[np.full(3,20.),np.full(29,1.)]*.15
            return np.c_[contact,approach,prior,continuity]
        def fun(q):return values(q)[0]
        def jac(q):
            batch=np.broadcast_to(q,(32,32)).astype(complex).copy();batch[np.arange(32),np.arange(32)]+=1e-25j
            return (values(batch).imag/1e-25).T
        seed=ref if prev is None else prev+(ref-reference[t-1])
        solution=least_squares(fun,np.clip(seed,low+1e-10,high-1e-10),jac=jac,bounds=(low,high),max_nfev=8,ftol=1e-3,xtol=1e-3,gtol=1e-3)
        prev=solution.x;poses.append(prev.copy())
        if (t+1)%100==0:update(message=f'Adapting movement · {t+1}/{len(reference)} frames')
    poses=np.stack(poses);g=geometry(poses);gap=np.linalg.norm(g['contact_points']-e['contacts'],axis=-1)
    g.update(frames=e['frames'],known=trusted,raw_known=e['known'],contact_weight=weight,anticipation_weight=guide_weight,labels=e['labels'],contacts=e['contacts'],contact_gaps_cm=gap,shoe_width_cm=d['foot_width'])
    np.savez_compressed(job/'quick_trajectory.npz',anatomical_q=poses,**{k:v for k,v in g.items() if isinstance(v,np.ndarray)})
    fitting_seconds=time.perf_counter()-fit_started
    update(message='Rendering quick preview')
    render(g,scene,holds,job/'quick.mp4')
    diagnostics=dict(max_contact_gap_cm=float(gap[e['known']].max()),supported_max_contact_gap_cm=float(gap[trusted].max()),unconfirmed_contacts=int((e['known'] & ~trusted).sum()),supported_frames_over_5cm=int((np.where(trusted,gap,0).max(1)>5).sum()),raw_frames_over_5cm=int((np.where(e['known'],gap,0).max(1)>5).sum()),joint_bounds_pass=bool(np.all(poses>=lo-1e-7)&np.all(poses<=hi+1e-7)),coordinate_rate_pass=bool(np.all(abs(np.diff(poses,axis=0))*30<=speed+1e-7)),physical_validation=False,hold_count=len(holds),fitting_seconds=fitting_seconds,quick_seconds=time.perf_counter()-started)
    (job/'quick_diagnostics.json').write_text(json.dumps(diagnostics,indent=2))
    update(state='ready',mode='quick',message='Quick preview ready',detail_state='queued',video_url=f'/api/skeleton-jobs/{job.name}/quick.mp4',height_cm=p['height_cm'],arm_span_cm=p['arm_span_cm'],source_id='trial2',quality='quick_geometry_only',first_frame=int(e['frames'][0]),last_frame=int(e['frames'][-1]),fps=30,**diagnostics)
except Exception as ex:
    import traceback;traceback.print_exc();update(state='failed',message='Quick preview failed. Please retry.',error=str(ex));sys.exit(1)
