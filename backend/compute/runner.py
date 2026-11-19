"""Supervise the scientific process; publish validated artifacts atomically."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from fastapi import HTTPException
from backend.database import database
from .contracts import Result
from . import service, storage

class Interrupted(RuntimeError):
    pass

def stop_process(process):
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=5)

def discard(task_id):
    # Retain work/logs for diagnosis; unpublished artifacts are never accessible.
    path=storage.root()/'published'/str(task_id)
    if path.exists():
        shutil.rmtree(path)

def validate_source_result(source, result):
    for artifact in result['artifacts'].values():
        if storage.digest(storage.resolve(artifact['storage_key']))!=artifact['sha256']:
            raise HTTPException(409,'Source analysis artifacts changed; analyze the recording again')
    from .real_job import input_hashes
    provenance=json.loads(storage.resolve(result['artifacts']['provenance']['storage_key']).read_text())
    if provenance['input_sha256']!=input_hashes(source):
        raise HTTPException(409,'Source evidence or algorithm changed; analyze the recording again')


def execute(task, worker):
    if task['execution'].get('engine') not in (storage.ENGINE,storage.INPUT_ENGINE):
        raise HTTPException(409,'Algorithm version changed; submit a new task')
    root=storage.root()
    directory=root/'work'/str(task['id'])
    directory.mkdir(parents=True,exist_ok=False)
    source_env=os.getenv('BETA_TRANSLATOR_ROOT')
    if not source_env:
        raise RuntimeError('Set BETA_TRANSLATOR_ROOT to the verified CIS5810 project')
    source=Path(source_env).resolve()
    python=Path(os.getenv('BETA_TRANSLATOR_PYTHON',str(source/'.venv/bin/python')))
    with database() as db:
        video=service.check_request(db,task['request'],task['owner_id'])
        source_result=None
        if task['kind']=='generate':
            source_result=db.execute('SELECT payload FROM compute_results WHERE task_id=%s',
                (task['request']['source_analysis_id'],)).fetchone()['payload']
    if source_result is not None:
        validate_source_result(source,source_result)
    video_path=storage.video_path(video)
    if storage.digest(video_path)!=task['execution']['video_sha256']:
        raise HTTPException(409,'Source video changed')
    job=dict(id=str(task['id']),request=task['request'],source=str(source),storage=str(root),
             directory=str(directory),video=str(video_path),source_result=source_result,parent_pid=os.getpid())
    request_path=directory/'job.json'
    request_path.write_text(json.dumps(job,indent=2)+'\n')
    timeout=float(os.getenv('COMPUTE_TIMEOUT_SECONDS','1800'))
    if timeout<=0:
        raise ValueError('COMPUTE_TIMEOUT_SECONDS must be positive')
    with (directory/'worker.log').open('w') as log:
        process=subprocess.Popen([str(python),'-m',('backend.compute.input_job' if task['execution']['engine']==storage.INPUT_ENGINE else 'backend.compute.real_job'),str(request_path)],
            cwd=Path(__file__).resolve().parents[2],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
            env={**os.environ,'PYTHONUNBUFFERED':'1','MPLBACKEND':'Agg'})
        (directory/'process.json').write_text(json.dumps(dict(pid=process.pid,process_group=process.pid))+'\n')
        started=time.monotonic()
        try:
            while process.poll() is None:
                if worker.stopping:
                    raise Interrupted('Worker stopped during scientific computation')
                if time.monotonic()-started>timeout:
                    raise TimeoutError('Scientific process exceeded configured timeout')
                worker.lock.execute('SELECT 1')
                with database() as db:
                    service.check_request(db,task['request'],task['owner_id'])
                    progress=directory/'progress.json'
                    stage=json.loads(progress.read_text())['stage'] if progress.exists() else 'starting_algorithm'
                    db.execute("UPDATE compute_tasks SET stage=%s,updated_at=now() WHERE id=%s AND state='running'",(stage,task['id']))
                time.sleep(.5)
            if process.returncode:
                raise RuntimeError(f'Scientific process failed with exit code {process.returncode}; see private worker.log')
        finally:
            stop_process(process)
    result=Result.model_validate_json((directory/'result.json').read_text()).model_dump(mode='json')
    if result['source_video_id']!=str(task['source_video_id']) or result['kind']!=task['kind'] or result['is_mock']:
        raise ValueError('Scientific result identity mismatch')
    prefix=f"published/{task['id']}/"
    for artifact in result['artifacts'].values():
        key=artifact['storage_key']
        if not key.startswith(prefix) or '/' in key[len(prefix):]:
            raise ValueError('Artifact outside task publication directory')
        path=directory/'output'/key[len(prefix):]
        if path.is_symlink() or not path.is_file() or storage.digest(path)!=artifact['sha256']:
            raise ValueError('Incomplete or changed output artifact')
    # Second, independent media validation before publication.
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames',
        '-show_entries','stream=codec_name,pix_fmt,nb_read_frames,avg_frame_rate','-of','json',str(directory/'output/video.mp4')],text=True))['streams'][0]
    numerator,denominator=map(int,probe['avg_frame_rate'].split('/'))
    if (probe['codec_name']!='h264' or probe['pix_fmt']!='yuv420p' or int(probe['nb_read_frames'])!=result['frame_count']
            or numerator/denominator!=result['fps']):
        raise ValueError('Playback validation failed')
    if storage.digest(video_path)!=task['execution']['video_sha256']:
        raise HTTPException(409,'Source video changed while computing')
    destination=root/'published'/str(task['id'])
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        raise FileExistsError('Task already has a publication directory')
    (directory/'output').rename(destination)
    return result
