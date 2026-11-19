"""Task/notification routes; authentication is injected from A's API."""
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, Request
from .contracts import SourceRequest, GenerationRequest
from . import service, upload_analysis, input_review, contact_review, world_review
from .input_schema import CalibrationReview
from .contact_schema import ContactReview
from .world_schema import WorldReview
from .media import artifact_response, source_artifact_response

def create_router(current_session):
    router = APIRouter(prefix='/api', tags=['compute'])

    def create(body, session, response, key):
        task, created = service.submit(body.model_dump(), session['id'], key)
        response.status_code = 202 if created else 200
        return task

    @router.post('/tasks/analyze')
    def analyze(body: SourceRequest, response: Response, idempotency_key: str = Header(default=''), session=Depends(current_session)):
        return create(body, session, response, idempotency_key)

    @router.post('/tasks/generate')
    def generate(body: GenerationRequest, response: Response, idempotency_key: str = Header(default=''), session=Depends(current_session)):
        return create(body, session, response, idempotency_key)

    @router.get('/tasks/upload-analysis/{video_id}')
    def upload_status(video_id: UUID, session=Depends(current_session)):
        return upload_analysis.status(video_id, session['id'])

    @router.post('/tasks/upload-analysis/{video_id}')
    def upload_start(video_id: UUID, response: Response, session=Depends(current_session)):
        task, created = upload_analysis.start(video_id, session['id'])
        response.status_code = 202 if created else 200
        return task

    @router.get('/tasks')
    def tasks(cursor: UUID | None = None, limit: int = Query(20,ge=1,le=100), session=Depends(current_session)):
        return service.list_tasks(session['id'], cursor, limit)

    @router.get('/tasks/source-analysis/{video_id}')
    def source_analysis(video_id: UUID, session=Depends(current_session)):
        return service.source_analysis(video_id, session['id'])

    @router.get('/tasks/source-analysis/{video_id}/artifacts/{name}')
    def source_artifact(video_id: UUID, name: str, request: Request, session=Depends(current_session)):
        return source_artifact_response(video_id,name,session['id'],request)

    @router.get('/tasks/{task_id}/input-review')
    def get_input_review(task_id: UUID, session=Depends(current_session)):
        return input_review.read(task_id,session['id'])

    @router.post('/tasks/{task_id}/input-review')
    def save_input_review(task_id: UUID, body: CalibrationReview, session=Depends(current_session)):
        return input_review.save(task_id,session['id'],body)

    @router.get('/tasks/{task_id}/contact-review')
    def get_contact_review(task_id: UUID, version: str | None = Query(default=None, pattern=r'^[a-f0-9]{64}$'), session=Depends(current_session)):
        return contact_review.read(task_id, session['id'], version)

    @router.post('/tasks/{task_id}/contact-review')
    def save_contact_review(task_id: UUID, body: ContactReview, session=Depends(current_session)):
        return contact_review.save(task_id, session['id'], body)

    @router.get('/tasks/{task_id}/contact-review/export')
    def export_contacts(task_id: UUID, version: str = Query(pattern=r'^[a-f0-9]{64}$'), session=Depends(current_session)):
        return contact_review.export(task_id, session['id'], version)

    @router.get('/tasks/{task_id}/world-review')
    def get_world_review(task_id: UUID, version: str | None = Query(default=None, pattern=r'^[a-f0-9]{64}$'), session=Depends(current_session)):
        return world_review.read(task_id,session['id'],version)

    @router.post('/tasks/{task_id}/world-review')
    def save_world_review(task_id: UUID, body: WorldReview, session=Depends(current_session)):
        return world_review.save(task_id,session['id'],body)

    @router.get('/tasks/{task_id}/world-review/export')
    def export_world_review(task_id: UUID, version: str = Query(pattern=r'^[a-f0-9]{64}$'), session=Depends(current_session)):
        return world_review.read(task_id,session['id'],version,export=True)

    @router.get('/tasks/{task_id}')
    def task(task_id: UUID, session=Depends(current_session)):
        return service.get_task(task_id, session['id'])

    @router.get('/tasks/{task_id}/result')
    def result(task_id: UUID, session=Depends(current_session)):
        task = service.get_task(task_id, session['id'])
        if task['state'] != 'succeeded':
            raise HTTPException(409, 'Result not ready')
        return task['result']

    @router.get('/tasks/{task_id}/artifacts/{name}')
    def artifact(task_id: UUID, name: str, request: Request, session=Depends(current_session)):
        return artifact_response(task_id,name,session['id'],request)

    @router.post('/tasks/{task_id}/retry')
    def retry(task_id: UUID, response: Response, idempotency_key: str = Header(default=''), session=Depends(current_session)):
        task, created = service.retry(task_id, session['id'], idempotency_key)
        response.status_code = 202 if created else 200
        return task

    @router.get('/notifications')
    def notifications(cursor: UUID | None = None, limit: int = Query(20,ge=1,le=100), session=Depends(current_session)):
        return service.notifications(session['id'], cursor, limit)

    @router.patch('/notifications/{notification_id}/read')
    def read(notification_id: UUID, session=Depends(current_session)):
        return service.mark_read(notification_id, session['id'])

    return router
