"""Independent new-video input preparation; no Trial2 fit or technique comparison.

Calls CIS5810 Beta_Translator @ ff85726da2fbbd2616c409b01d6c03833ab62ce9:
trial_pipeline.prepare_video/track_climber/build_scene/select_route/infer_contacts,
wholebody_pose.WholebodyExtractor. Their automatic candidates remain unreviewed.
All outputs are in this task's directory; no upstream trial outputs are reused.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ENGINE='video-inputs-v1'
COMMIT='ff85726da2fbbd2616c409b01d6c03833ab62ce9'

def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,allow_nan=False));tmp.replace(path)

def run(job):
    import numpy as np
    import cv2
    import shutil
    source=Path(job['source']);directory=Path(job['directory']);out=directory/'output';out.mkdir()
    root=directory/'inputs';root.mkdir();started=time.monotonic()
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=COMMIT:raise ValueError('Review changed Beta Translator revision first')
    sys.path.insert(0,str(source))
    from beta_translator import trial_pipeline as pipeline
    from beta_translator.wholebody_pose import WholebodyExtractor
    from beta_translator.project_io import load_reviewed_holds
    cache=source/'training_data/model_cache'
    models=[source/'models/model_final.pth',source/'models/pose_landmarker.task',source/'models/experiment_config.yml',source/'models/contact_v1/deployment.json']
    models+=list((source/'models/contact_v1').glob('model_*.pt'))+list(cache.rglob('*.onnx'))
    if len(list(cache.rglob('*.onnx')))<2:raise ValueError('Install the pinned local RTMW and detector models before preparing inputs')
    hashes={str(p.relative_to(source)):digest(p) for p in models}
    # Hash all imported upstream algorithm modules and this adapter, not only the models.
    hashes.update({str(p.relative_to(source)):digest(p) for p in (source/'beta_translator').glob('*.py')})
    def progress(stage):write(directory/'progress.json',dict(stage=stage))
    progress('preparing_input_video')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',job['video']],text=True))
    times=np.asarray([float(f['best_effort_timestamp_time']) for f in probe['frames']])
    if len(times)<2 or not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('Video needs at least two strictly ordered frame timestamps')
    fps=min(15.,float(1/np.max(np.diff(times))))
    if fps<1:raise ValueError('Frame gaps exceed supported input sampling interval')
    fps=float(max(1, int(np.floor(fps + 1e-6))))
    video=root/'analysis.mp4'
    info=pipeline.prepare_video(job['video'],video,root,fps=fps,width=720)
    progress('detecting_body_pose')
    extractor=WholebodyExtractor(cache,device='cpu',threads=2)
    extractor.extract(video,root/'automatic/wholebody.npz')
    track=pipeline.track_climber(source,video,root)
    progress('detecting_wall_holds')
    scene=pipeline.build_scene(source,video,root,track['reference_frame'])
    pipeline.select_route(video,root)
    progress('predicting_contacts')
    prediction,contacts=pipeline.infer_contacts(source,video,root)
    records,masks,run_id,selected=load_reviewed_holds(root/'state/reviewed_hold_map.npz',video)
    # Publish only review inputs, not any pre-existing source motion or optimized q.
    copies={'video':video,'reference':root/'images/wall_reference.jpg','hold_preview':root/'images/selected_route.png',
        'hold_masks':root/'state/reviewed_hold_map.npz','pose':root/'automatic/wholebody.npz',
        'identity':root/'state/identity_guard.npz','alignment':root/'state/alignment_cache.npz',
        'frame_map':root/'tables/source_frame_map.csv','contacts':root/'automatic/predictions/limb_contacts.csv',
        'contact_events':root/'automatic/predictions/contact_events.csv'}
    artifacts={}
    for name,path in copies.items():
        if not path.exists():raise ValueError('Required input missing: '+name)
        target=out/(name+path.suffix);shutil.copyfile(path,target)
        media={'.mp4':'video/mp4','.jpg':'image/jpeg','.png':'image/png','.csv':'text/csv'}.get(path.suffix,'application/octet-stream')
        artifacts[name]=dict(storage_key=f"published/{job['id']}/{target.name}",sha256=digest(target),media_type=media)
    summary=dict(engine=ENGINE,source_video_sha256=digest(job['video']),analysis_video_sha256=digest(video),
        reference_frame=track['reference_frame'],frame_count=info['frame_count'],fps=info['fps'],width=info['width'],height=info['height'],
        hold_count=len(records),candidate_run_id=run_id,identity_confirmed=False,contacts_human_reviewed=False,
        contact_rows=len(contacts),alignment_valid_frames=scene['alignment_valid_frames'],
        geometry_status='needs_user_calibration',generation_ready=False,seconds=time.monotonic()-started,
        time_axis='Analysis frames; frame_map preserves original source indices and timestamps',
        blockers=['Confirm climber identity','Select route holds and review contact candidates','Mark panel polygons and 14.3 cm hole-grid corners; supply wall angles','Global 3D joins/camera and source adaptation remain separate'])
    # JSON-safe record projection excludes upstream numpy masks and scalars.
    holds=[dict(hold_id=str(r['hold_id']),cx_px=float(r['cx_px']),cy_px=float(r['cy_px']),bbox=[int(x) for x in r['bbox']],review_status='unreviewed') for r in records]
    provenance=dict(source_commit=COMMIT,source_video_sha256=summary['source_video_sha256'],inputs_sha256=hashes,
        adapter_sha256=digest(__file__),cache_policy='Fresh task directory; upstream trial output caches are never read',
        pose_metadata=extractor.provenance)
    for name,data in [('input_summary',summary),('holds',holds),('provenance',provenance)]:
        path=out/(name+'.json');write(path,data)
        artifacts[name]=dict(storage_key=f"published/{job['id']}/{path.name}",sha256=digest(path),media_type='application/json')
    result=dict(kind='analyze',is_mock=False,algorithm_version=ENGINE,source_analysis_version=digest(out/'provenance.json'),
        calibration_version='new-video-unreviewed-v1',source_video_id=job['request']['video_id'],frame_count=info['frame_count'],fps=info['fps'],
        quality=dict(evidence='insufficient',geometry_status='assumed',check_scope='none',warnings=[
            'Input preparation only: this video is not an adapted skeleton or a feasible movement.',
            'Automatic holds, tracking and contacts require review. Global homography can fail on parallax/folded walls.',
            'Wall measurements and global 3D alignment are not inferred from body proportions.']),
        artifacts=artifacts,baseline_status='insufficient_evidence',technique_status='not_requested',suggestions=[],moments=[])
    write(directory/'result.json',result);progress('verifying_input_artifacts')
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('job',type=Path);args=parser.parse_args()
    run(json.loads(args.job.read_text()))
