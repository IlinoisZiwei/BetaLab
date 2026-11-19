"""Publish labeled synthetic geometry to exercise API/GUI, without model inference."""
import json
import os
from pathlib import Path
import subprocess
from backend.compute import service, storage
from backend.database import database

def prepare(client, video_id, output):
    task = client.post('/api/tasks/upload-analysis/'+video_id).json()
    root = Path(output)/'published'/task['id'];root.mkdir(parents=True)
    source = Path(os.environ['BETA_TRANSLATOR_ROOT'])
    env = {**os.environ,'PYTHONPATH':'tests/compute:.'}
    subprocess.run([str(source/'.venv/bin/python'),'-m','support.world_fixture',str(root)],env=env,check=True)
    artifacts = {}
    names = dict(input_summary='summary.json',holds='holds.json',pose='pose.npz',identity='identity.npz',
        alignment='alignment.npz',contacts='contacts.csv',contact_events='contact_events.csv',
        frame_map='frame_map.csv',reference='reference.jpg',hold_preview='reference.jpg')
    for name,file in names.items():
        path = root/file
        artifacts[name] = dict(storage_key=str(path.relative_to(Path(output))),sha256=storage.digest(path),
            media_type='image/jpeg' if file.endswith('.jpg') else 'application/json' if file.endswith('.json') else 'application/octet-stream')
    result = dict(kind='analyze',is_mock=False,algorithm_version=storage.INPUT_ENGINE,
        source_analysis_version='SYNTHETIC-WORLD-TEST',calibration_version='SYNTHETIC',
        source_video_id=video_id,frame_count=4,fps=2,quality=dict(evidence='insufficient',geometry_status='assumed',
        warnings=['SYNTHETIC GEOMETRY TEST; not a reconstruction of this video']),artifacts=artifacts,
        baseline_status='insufficient_evidence',technique_status='not_requested')
    with database() as db:
        row = db.execute("UPDATE compute_tasks SET state='running',is_mock=false WHERE id=%s RETURNING *",(task['id'],)).fetchone()
        service.finish(db,row,result=result)
    path = '/api/tasks/'+task['id']
    calibration = client.post(path+'/input-review',json=json.loads((root/'calibration.json').read_text()))
    assert calibration.status_code==200,calibration.text
    contacts = client.post(path+'/contact-review',json=dict(intervals=[
        dict(limb='left_hand',state='hold',hold_id='H1',start_frame=0,release_frame=4)],
        confirmed=True,notes='SYNTHETIC geometry integration test'))
    assert contacts.status_code==200,contacts.text
    review = json.loads((root/'review.json').read_text())
    review.update(calibration_version=calibration.json()['version'],contact_version=contacts.json()['version'])
    return task,review
