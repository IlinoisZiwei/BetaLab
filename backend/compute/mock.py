"""Deterministic in-memory executor for B's fixtures, NOT an authenticated API."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .contracts import SourceRequest, GenerationRequest, Task, Result, Quality, Error, Notification

def now():
    return datetime.now(timezone.utc).isoformat()

class MockExecutor:
    def __init__(self):
        self.tasks = {}
        self.requests = {}
        self.notifications = {}

    def submit(self, request, owner_id, retry_of=None):
        request = (SourceRequest if request.get('kind') == 'analyze' else GenerationRequest).model_validate(request)
        previous = self.tasks.get(retry_of) if retry_of else None
        if retry_of and (previous is None or previous.owner_id != owner_id or previous.state != 'failed'
                         or not previous.error.retryable or request != self.requests[retry_of]):
            raise ValueError('Retry requires the same request and an owned retryable failed task')
        task = Task(id='mock-' + uuid4().hex, owner_id=owner_id, source_video_id=request.video_id,
                    kind=request.kind, state='queued', stage='queued', is_mock=True,
                    created_at=now(), updated_at=now(), retry_of=retry_of,
                    attempt=previous.attempt + 1 if previous else 1)
        self.tasks[task.id], self.requests[task.id] = task, request
        return task

    def advance(self, task_id, outcome='success'):
        if outcome not in ('success', 'failure', 'insufficient'):
            raise ValueError('Unknown mock outcome')
        task = self.tasks[task_id]
        if task.state in ('succeeded', 'failed'):
            return task  # No duplicate terminal notification.
        payload = task.model_dump()
        payload['updated_at'] = now()
        if task.state == 'queued':
            payload.update(state='running', stage='mock_analysis' if task.kind == 'analyze' else 'mock_baseline')
        elif outcome == 'failure':
            payload.update(state='failed', stage='failed', error=Error(code='WORKER_FAILED',
                message='Example worker failure; no real computation ran.', retryable=True))
        else:
            req = self.requests[task_id]
            enough = outcome != 'insufficient'
            generate = task.kind == 'generate'
            payload.update(state='succeeded', stage='complete', result=Result(
                kind=task.kind, is_mock=True, algorithm_version='mock-v1',
                source_analysis_version=req.source_analysis_version if generate else 'mock-source-v1',
                calibration_version='trial2-grid143-v1' if generate else req.calibration.version,
                source_video_id=req.video_id, frame_count=976, fps=30,
                original_body=None if generate else req.uploader_body,
                target_body=req.target_body if generate else None,
                quality=Quality(evidence='sufficient' if enough else 'insufficient', geometry_status='assumed',
                    warnings=['SIMULATION: no skeleton or video was generated.']),
                baseline_status=('passed' if enough else 'insufficient_evidence') if generate else 'not_requested',
                technique_status=('no_improvement' if enough else 'blocked') if generate and req.compare_techniques else 'not_requested'))
        updated = Task.model_validate(payload)
        self.tasks[task_id] = updated
        if updated.state in ('succeeded', 'failed'):
            self.notifications.setdefault(task_id, Notification(id='mock-notification-' + task_id,
                owner_id=task.owner_id, task_id=task_id, event='task_' + updated.state,
                created_at=now(), is_mock=True))
        return updated

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--outcome', choices=['success', 'failure', 'insufficient'], default='success')
    args = parser.parse_args()
    executor = MockExecutor()
    task = executor.submit(json.loads(args.request.read_text()), 'mock-user')
    history = [task.model_dump(mode='json')]
    for _ in range(2):
        task = executor.advance(task.id, args.outcome)
        history.append(task.model_dump(mode='json'))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'history.json').write_text(json.dumps(history, indent=2) + '\n')
    (args.out/'notifications.json').write_text(json.dumps([n.model_dump() for n in executor.notifications.values()], indent=2) + '\n')
    print(f'MOCK ONLY: {task.state}; fixtures saved to {args.out}')

if __name__ == '__main__':
    main()
