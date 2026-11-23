"""Owner-only immutable calibration review versions for prepared new-video inputs.

Review does not rewrite predictions or enable source adaptation. The scientific
validator projects selected holds into plane-local coordinates only.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from fastapi import HTTPException
from backend.database import database
from . import service,storage
from .input_schema import CalibrationReview


def prepared(task_id,owner_id):
    task=service.get_task(task_id,owner_id)
    result=task.get('result')
    if task['state']!='succeeded' or not result or result['algorithm_version']!=storage.INPUT_ENGINE:
        raise HTTPException(409,'Only completed new-video input tasks can be reviewed')
    for name in ('input_summary','holds'):
        artifact=result['artifacts'][name]
        if storage.digest(storage.resolve(artifact['storage_key']))!=artifact['sha256']:raise HTTPException(409,'Input artifact changed')
    return result


def read(task_id,owner_id):
    result=prepared(task_id,owner_id)
    folder=storage.root()/'reviews'/str(task_id)
    latest=folder/'latest.json'
    return dict(version=None,review=None,calibrated=None) if not latest.exists() else json.loads(latest.read_text())


def save(task_id,owner_id,review):
    result=prepared(task_id,owner_id)
    source_env=os.getenv('BETA_TRANSLATOR_ROOT')
    if not source_env:raise HTTPException(503,'Local scientific environment is not configured')
    source=Path(source_env).resolve()
    python=Path(os.getenv('BETA_TRANSLATOR_PYTHON',str(source/'.venv/bin/python')))
    summary=storage.resolve(result['artifacts']['input_summary']['storage_key'])
    holds=storage.resolve(result['artifacts']['holds']['storage_key'])
    from . import hold_review
    corrected = hold_review.read(task_id, owner_id, review.hold_review_version, latest=False)['holds']
    payload=review.model_dump(mode='json')
    # Pass only validated JSON through stdin; never interpolate user text in a shell.
    try:
        process=subprocess.run([str(python),'-m','backend.compute.input_calibration',str(summary),str(holds)],
            input=json.dumps({**payload, '_holds': corrected}),text=True,capture_output=True,timeout=60,cwd=Path(__file__).resolve().parents[2])
    except (OSError,subprocess.TimeoutExpired):
        raise HTTPException(503,'Calibration validator unavailable; retry after checking the local worker environment')
    if process.returncode:raise HTTPException(422,'Invalid panel calibration: '+process.stderr[-800:])
    calibrated=json.loads(process.stdout)
    version=hashlib.sha256(json.dumps(dict(task=str(task_id),input_sha=result['artifacts']['input_summary']['sha256'],review=payload),sort_keys=True).encode()).hexdigest()
    doc=dict(version=version,review=payload,calibrated=calibrated,input_sha256=result['artifacts']['input_summary']['sha256'])
    with database() as db:
        service.source(db,result['source_video_id'],owner_id,lock=True)
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('input-review:'+str(task_id),))
        current=read(task_id,owner_id)
        if current['version']==version:return current
        if current['version']!=review.base_version:raise HTTPException(409,'Review changed; reload the latest version')
        folder=storage.root()/'reviews'/str(task_id);folder.mkdir(parents=True,exist_ok=True)
        for path in (folder/(version+'.json'),folder/'latest.json'):
            with tempfile.NamedTemporaryFile(mode='w',dir=folder,delete=False) as f:
                json.dump(doc,f,indent=2,allow_nan=False);temporary=Path(f.name)
            temporary.replace(path)
    return doc
