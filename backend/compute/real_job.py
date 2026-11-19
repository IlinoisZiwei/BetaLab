"""Isolated scientific process for real, full-timeline Trial2 previews.

References CIS5810 Beta_Translator @ ff85726da2fbbd2616c409b01d6c03833ab62ce9:
trial2_spatial_data.load_trial2/seed_pose, body_regions.episode_regions,
body_contacts.foot_frames, body_legs.initialize and ik3d.kinematics.
Existing reviewed observations are reused ONLY after exact video hash matching.
No technique or full mechanics pass is inferred from a playable preview.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from .prepare_trial2 import SOURCE_COMMIT, digest, write
from .calibration import VERSION,scene_for
from .fit_trial2 import profile_for

ENGINE='trial2-source-fit-v5'
VIDEO_HASH='9964d27ca051953d77cf10ee94a1772bd73e30d7e23fa09a54983c3630e8a068'

def input_hashes(source):
    files=list((source/'beta_translator').glob('*.py'))+list((source/'data').glob('*.json'))
    files += [source/'configs/users/trial_user_175.json',source/'configs/trials/trial2.json']
    for folder in ('state','tables','automatic/predictions'):
        files += [p for p in (source/'outputs/trial2'/folder).iterdir() if p.is_file()]
    files += [source/'outputs/trial2/automatic/wholebody.npz']
    hashes={str(p.relative_to(source)):digest(p) for p in sorted(set(files))}
    for name in ('real_job.py','preview_math.py','render_video.py','fit_trial2.py','moments.py','source_fit.py','source_diagnostics.py','reachability.py','calibration.py','geometry_scope.py','trajectory_solver.py'):
        hashes['betalab/'+name]=digest(Path(__file__).with_name(name))
    return hashes

def process(job, progress):
    import numpy as np
    started=time.monotonic()
    source=Path(job['source']).resolve()
    storage=Path(job['storage']).resolve()
    directory=Path(job['directory'])
    video=Path(job['video'])
    request=job['request']
    if digest(video)!=VIDEO_HASH or digest(source/'videos/trial2.mp4')!=VIDEO_HASH:
        raise ValueError('Video differs from the calibrated Trial2 dataset')
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=SOURCE_COMMIT:
        raise ValueError('Beta Translator version changed')
    hashes=input_hashes(source)
    sys.path.insert(0,str(source))
    from beta_translator.trial2_spatial_data import load_trial2,seed_pose
    from beta_translator.trial2_scene3d import Trial2Scene
    from beta_translator.body_regions import episode_regions
    from beta_translator.body_contacts import foot_frames
    from beta_translator.body_legs import initialize
    from beta_translator.body_user import body_lengths
    from beta_translator.ik3d import kinematics
    from .preview_math import adapt,geometry
    from .source_fit import fit_source,adapt_body
    from .source_diagnostics import evaluate
    from .geometry_scope import wall_contacts,diagnostic_moments,contact_transitions
    from .reachability import audit_reach
    from .render_video import render
    from .moments import build_moments
    output=directory/'output'
    output.mkdir()
    is_source=request['kind']=='analyze'
    warnings=['Geometry preview only: forces, balance and full mechanical feasibility have not been checked.',
              'Wall angles are user-reported; camera intrinsics/boundaries remain assumed and uncertain contacts unresolved.',
              'Prepared Trial2 observations are reused for this exact recording; this is not fresh generic-video inference.']
    warnings.append('Scope: known upper/middle wall contacts only. Ground geometry and full body collision/mechanics remain unverified; raw ground proposals are retained.')
    if is_source:
        body=request['uploader_body'] or dict(height_cm=173.,arm_span_cm=176.,provenance='estimated')
        if request['uploader_body'] is None:
            warnings.append('Source height is approximately 173 cm per user; 176 cm arm span is explicitly assumed, with template proportions.')
        profile=profile_for(source,body['height_cm'],body['arm_span_cm'])
        progress('calibrating','Rebuilding the 14.3 cm wall scene')
        with tempfile.TemporaryDirectory(dir=directory,prefix='scene-') as temporary:
            project=Path(temporary)
            shutil.copytree(source/'data',project/'data')
            for name in ('videos','outputs'):
                (project/name).symlink_to(source/name,target_is_directory=True)
            spec_path=project/'data/trial2_spatial_hypotheses.json'
            spec=json.loads(spec_path.read_text())
            spec.update(hole_spacing_cm=14.3,spacing_status='User-confirmed adjacent hole centers',
                        grid_status='User-confirmed equal horizontal/vertical spacing')
            write(spec_path,spec)
            data=load_trial2(project)
            scene=scene_for(project)
            regions=episode_regions(data,scene,body['height_cm'])
            for episode in regions['episodes']:
                episode['evidence_frames']=int(episode['evidence_frames'])
            seed=seed_pose(data,scene,body['height_cm'])
            joints,_,_=kinematics(seed,body_lengths(profile))
            progress('source_skeleton','Initializing anatomical joints from original pixel observations')
            q=initialize(dict(joints=joints,values=seed),body_lengths(profile),body['height_cm'],
                         foot_frames(data,scene,regions,body['height_cm'])[0])
            mapping=regions['mapping']
            contacts=np.zeros((*mapping.shape,3))
            counts=np.zeros(mapping.shape,dtype=int)
            for t,limb in np.ndindex(mapping.shape):
                if mapping[t,limb]>=0:
                    episode=regions['episodes'][int(mapping[t,limb])]
                    contacts[t,limb]=scene.intersect(np.array(episode['anchor_px']),episode['panel'])
                    counts[t,limb]=episode['evidence_frames']
            evidence=dict(contacts_cm=contacts,known=data['known'],trusted=data['known']&(counts>0),
                evidence_frames=counts,labels=data['labels'],frames=data['frames'],confidence=data['confidence'],
                ground=data['ground'],visibility=data['visibility'],observed_px=data['observed_px'])
            holds=[dict(id=hid,center_px=[record['cx_px'],record['cy_px']],panel=int(scene.panel([record['cx_px'],record['cy_px']])))
                   for hid,record in data['records'].items()]
            report=scene.report()
            np.savez_compressed(output/'initializer.npz',anatomical_q=q)
            before,_=evaluate(q,evidence,profile,scene)
            reach=audit_reach(evidence,profile)
            wall_reach=audit_reach({**evidence,'trusted':wall_contacts(evidence)},profile)
            q,solver=fit_source(q,evidence,profile,scene,progress)
            after,g=evaluate(q,evidence,profile,scene)
            write(output/'source_audit.json',dict(before=before,after=after,
                necessary_reach_check=reach,wall_reach_check=wall_reach,solver=solver,episodes=regions['episodes'],
                correction_status='No contact labels, times, anchors or unmeasured body/wall values edited.'))
            write(output/'reachability.json',reach)
            write(output/'contact_transitions.json',contact_transitions(evidence))
            metrics=after['summary']
            diagnostics=dict(check_scope='geometry_only',mechanics_checked=False,physical_validation=False,
                initialization_only=False,source_fit=solver,source_metrics=metrics,
                supported_max_gap_cm=metrics['wall_max_gap_cm'],supported_frames_over_5cm=metrics['wall_frames_over_5cm'],
                joint_bounds_pass=metrics['joint_bounds_pass'],coordinate_rate_pass=metrics['coordinate_rate_pass'],
                joint_centers_behind_wall_frames=metrics['known_wall_penetration_frames'],
                unconfirmed_contact_samples=metrics['unconfirmed_samples'],
                necessary_reach_inconsistent_frames=wall_reach['inconsistent_frames'],
                deferred_ground_samples=metrics['deferred_ground_samples'],geometry_scope='upper_and_middle_walls',
                raw_ground_inclusive_reach_inconsistent_frames=reach['inconsistent_frames'])
            if reach['inconsistent_frames']:
                warnings.append(f"Including unvalidated ground proposals yields {reach['inconsistent_frames']} inconsistent frames. These ground coordinates are not enforced or certified by the known-wall fit.")
            if not solver['success']:
                warnings.append('Source fitting reached its iteration limit; the published motion remains a diagnostic estimate.')
        np.savez_compressed(output/'contacts.npz',**evidence)
        with np.load(source/'outputs/trial2/state/alignment_cache.npz',allow_pickle=False) as z:
            np.savez_compressed(output/'alignment.npz',frames=z['frames'],matrices=z['matrices'])
        write(output/'scene.json',report)
        write(output/'holds.json',holds)
        source_version=hashlib.sha256(json.dumps(dict(inputs=hashes,body=body,calibration=VERSION,video=VIDEO_HASH),sort_keys=True).encode()).hexdigest()
        original_body=body
        target_body=None

    else:
        original=job['source_result']
        if original['baseline_status']!='passed':
            warnings.append('Source motion has not passed baseline checks; this target is diagnostic only.')
        def load_artifact(name):
            artifact=original['artifacts'][name]
            path=(storage/artifact['storage_key']).resolve()
            if not path.is_relative_to(storage) or digest(path)!=artifact['sha256']:
                raise ValueError('Source artifact missing or changed')
            return path
        provenance=json.loads(load_artifact('provenance').read_text())
        if provenance['input_sha256']!=hashes or provenance['video_sha256']!=VIDEO_HASH:
            raise ValueError('Source evidence or adapter changed; analyze the recording again')
        source_version=original['source_analysis_version']
        original_body=original['original_body']
        target_body=request['target_body']
        profile=profile_for(source,target_body['height_cm'],target_body['arm_span_cm'])
        with np.load(load_artifact('skeleton'),allow_pickle=False) as z:
            reference=z['anatomical_q'].copy()
        with np.load(load_artifact('contacts'),allow_pickle=False) as z:
            evidence={k:z[k].copy() for k in z.files}
        report=json.loads(load_artifact('scene').read_text())
        holds=json.loads(load_artifact('holds').read_text())
        progress('adapting','Adapting full native contact sequence to target dimensions')
        source_profile=profile_for(source,original_body['height_cm'],original_body['arm_span_cm'])
        scene=scene_for(source)
        q,solver=adapt_body(reference,evidence,source_profile,profile,scene,progress)
        target_audit,g=evaluate(q,evidence,profile,scene)
        metrics=target_audit['summary']
        diagnostics=dict(check_scope='geometry_only',mechanics_checked=False,physical_validation=False,
            target_fit=solver,geometry_scope='upper_and_middle_walls',
            supported_max_gap_cm=metrics['wall_max_gap_cm'],supported_frames_over_5cm=metrics['wall_frames_over_5cm'],
            joint_bounds_pass=metrics['joint_bounds_pass'],coordinate_rate_pass=metrics['coordinate_rate_pass'],
            unconfirmed_contact_samples=metrics['unconfirmed_samples'],
            contact_order_preserved=True,contact_timing_preserved=True,
            deferred_ground_samples=metrics['deferred_ground_samples'],
            joint_centers_behind_wall_frames=metrics['known_wall_penetration_frames'])
        write(output/'target_audit.json',target_audit)
        if request['compare_techniques']:
            warnings.append('Technique comparison blocked: full baseline mechanics have not passed.')
    if not np.array_equal(evidence['frames'],np.arange(976)) or q.shape!=(976,32) or not np.isfinite(q).all():
        raise ValueError('Incomplete or non-finite native trajectory')
    np.savez_compressed(output/'skeleton.npz',anatomical_q=q,joints_cm=g['joints'],frames=evidence['frames'],
                        known=wall_contacts(evidence),raw_known=evidence['known'],ground=evidence['ground'],labels=evidence['labels'],visibility=evidence['visibility'])
    geometry_failed = (diagnostics['supported_frames_over_5cm'] > 0
        or not diagnostics['joint_bounds_pass'] or not diagnostics['coordinate_rate_pass']
        or diagnostics.get('joint_centers_behind_wall_frames',0)>0)
    if geometry_failed:
        warnings.append(f"Geometry check failed: {diagnostics['supported_frames_over_5cm']} frames exceed the 5 cm contact-gap threshold; maximum gap {diagnostics['supported_max_gap_cm']:.1f} cm.")
    moments=diagnostic_moments(evidence,np.linalg.norm(g['contact_points']-evidence['contacts_cm'],axis=-1))
    write(output/'moments.json',moments)
    # Sparse/zero-visibility poses remain estimates, never relabelled as observations.
    progress('rendering','Rendering original recording beside reconstructed wall motion')
    dimensions=original_body if is_source else target_body
    title=('Source estimate' if is_source else 'Target')+f" {dimensions['height_cm']:g} cm / span {dimensions['arm_span_cm']:g} cm"
    probe=render(video,g['joints'],report,holds,evidence['labels'],wall_contacts(evidence),output/'video.mp4',title,progress,geometry_failed=geometry_failed)
    diagnostics.update(media=probe,elapsed_seconds=time.monotonic()-started,
                       source_body=original_body,target_body=target_body,source_video_sha256=VIDEO_HASH)
    write(output/'diagnostics.json',diagnostics)
    write(output/'provenance.json',dict(engine=ENGINE,source_commit=SOURCE_COMMIT,video_sha256=VIDEO_HASH,
        calibration_version=VERSION,input_sha256=hashes,source_analysis_version=source_version,
        body=dimensions,source_body=original_body,mechanics_checked=False))
    if digest(video)!=VIDEO_HASH or input_hashes(source)!=hashes:
        raise ValueError('Inputs changed during generation')
    types={'.mp4':'video/mp4','.png':'image/png','.json':'application/json','.npz':'application/octet-stream'}
    artifacts={p.stem:dict(storage_key=f"published/{job['id']}/{p.name}",media_type=types[p.suffix],sha256=digest(p))
               for p in sorted(output.iterdir())}
    # PNG and MP4 share a stem; give the image its own name.
    artifacts['video']=dict(storage_key=f"published/{job['id']}/video.mp4",media_type='video/mp4',sha256=digest(output/'video.mp4'))
    artifacts['poster']=dict(storage_key=f"published/{job['id']}/video.png",media_type='image/png',sha256=digest(output/'video.png'))
    result=dict(schema_version=1,kind=request['kind'],is_mock=False,algorithm_version=ENGINE,
        source_analysis_version=source_version,calibration_version=VERSION,source_video_id=request['video_id'],
        frame_count=976,fps=30.,quality=dict(evidence='low_confidence',geometry_status='assumed',
        physical_validation=False,check_scope='geometry_only',warnings=warnings),
        original_body=original_body,target_body=target_body,artifacts=artifacts,
        baseline_status='failed' if geometry_failed else 'not_checked',
        technique_status='blocked' if request.get('compare_techniques') else 'not_requested',suggestions=[],moments=moments)
    write(directory/'result.json',result)
    progress('verifying','Artifacts complete; awaiting permission and publication checks')

def main():
    path=Path(sys.argv[1]).resolve()
    job=json.loads(path.read_text())
    directory=Path(job['directory'])
    def progress(stage,message):
        temporary=directory/'progress.tmp'
        write(temporary,dict(stage=stage,message=message))
        temporary.replace(directory/'progress.json')
    parent=job.get('parent_pid')
    if parent:
        def watchdog():
            while True:
                if os.getppid()!=parent:
                    # The worker starts a dedicated process session. Kill its encoder too.
                    if os.getsid(0)==os.getpid():
                        os.killpg(os.getpgrp(),signal.SIGKILL)
                    os._exit(130)
                time.sleep(.2)
        threading.Thread(target=watchdog,daemon=True).start()
    # Also excludes an orphaned scientific process during database worker recovery.
    with (Path(job['storage'])/'.algorithm.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        process(job,progress)

if __name__=='__main__':
    main()
