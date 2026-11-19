"""Authenticated range delivery; artifact selection/permissions happen before streaming."""
from fastapi import HTTPException, Request
from backend.media import ranged_file
from . import service, storage


def artifact_response(task_id, name, user_id, request: Request):
    task = service.get_task(task_id,user_id)
    if task['state']!='succeeded':
        raise HTTPException(409,'Result not ready')
    return stream_artifact(task['result'],name,request)

def source_artifact_response(video_id,name,user_id,request):
    if name not in ('video','poster'):
        raise HTTPException(404,'Source preview not found')
    reference=service.source_analysis(video_id,user_id,current_only=False)
    from backend.database import database
    with database() as db:
        service.source(db,video_id,user_id,lock=True)
        result=db.execute('SELECT payload FROM compute_results WHERE task_id=%s',
                          (reference['source_analysis_id'],)).fetchone()['payload']
    return stream_artifact(result,name,request)

def stream_artifact(result,name,request):
    artifact = result['artifacts'].get(name)
    if not artifact:
        raise HTTPException(404,'Artifact not found')
    path = storage.resolve(artifact['storage_key'])
    # Never serve a corrupt/replaced file even if an old DB manifest is still present.
    if storage.digest(path)!=artifact['sha256']:
        raise HTTPException(409,'Artifact integrity check failed')
    return ranged_file(path, request, artifact['media_type'])
