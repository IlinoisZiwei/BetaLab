"""Upload-to-analysis orchestration; no changes to the v5 scientific pipeline.

The supported recording uses its existing reviewed calibration. Never assign that
calibration to a different recording merely because it shares a route.
"""
from fastapi import HTTPException
from . import service, storage
from .calibration import VERSION
from .contracts import SourceRequest
from backend.database import database


def request_for(video):
    import os
    new_video = os.getenv('COMPUTE_MODE','real')!='mock' and storage.digest(storage.video_path(video)) != storage.TRIAL2_SHA256
    version = storage.INPUT_CALIBRATION if new_video else VERSION
    return SourceRequest(video_id=str(video['id']), route_id=video['route_id'],
        calibration=dict(version=version,reference_frame=0 if new_video else 450,evidence_key='calibration/'+version)).model_dump()


def status(video_id, owner_id):
    with database() as db:
        video = service.source(db, video_id, owner_id)
        if str(video['owner_id']) != str(owner_id):
            raise HTTPException(404, 'Only the uploader can manage source analysis')
        row = db.execute(service.SELECT + "WHERE t.source_video_id=%s AND t.owner_id=%s AND t.kind='analyze' "
                         'ORDER BY t.created_at DESC,t.id DESC LIMIT 1', (video_id, owner_id)).fetchone()
    if row:
        return dict(task=service.task_payload(row), can_start=False, reason=None)
    try:
        request = request_for(video)
        storage.execution_config(video, request)
    except HTTPException as error:
        if error.status_code not in (404, 409, 422, 503):
            raise
        return dict(task=None, can_start=False, reason=error.detail)
    return dict(task=None, can_start=True, reason=None)


def start(video_id, owner_id):
    state = status(video_id, owner_id)
    if state['task']:
        # Retries are explicit attempts through the existing retry API.
        return state['task'], False
    if not state['can_start']:
        raise HTTPException(409, state['reason'])
    with database() as db:
        video = service.source(db, video_id, owner_id)
    request = request_for(video)
    return service.submit(request, owner_id, f'upload-analysis:{storage.ENGINE}:{video_id}')
