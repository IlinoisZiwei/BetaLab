"""Export the actual Pydantic schemas and reproducible frontend sample payloads."""
import json
from pathlib import Path
from .contracts import SourceRequest, GenerationRequest, Task, Result, Notification
from .mock import MockExecutor

def export(out):
    out.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (out/name).write_text(json.dumps(value, indent=2) + '\n')
    for model in (SourceRequest, GenerationRequest, Task, Result, Notification):
        save(model.__name__ + '.schema.json', model.model_json_schema())
    source = SourceRequest(video_id='demo-trial2', route_id='r1', calibration=dict(
        version='trial2-grid143-v1', reference_frame=450, evidence_key='calibration/trial2-grid143-v1'),
        uploader_body=None)
    target = GenerationRequest(video_id='demo-trial2', source_analysis_id='mock-analysis',
        source_analysis_version='mock-source-v1', target_body=dict(height_cm=170, arm_span_cm=175,
        provenance='user_input'), compare_techniques=True)
    for name, request in [('analysis', source), ('generation', target)]:
        save(name + '-request.json', request.model_dump())
        for outcome in ('success', 'failure', 'insufficient'):
            executor = MockExecutor()
            task = executor.submit(request.model_dump(), 'mock-user')
            history = [task.model_dump()]
            for _ in range(2):
                task = executor.advance(task.id, outcome)
                history.append(task.model_dump())
            save(f'{name}-{outcome}.json', dict(history=history,
                notifications=[n.model_dump() for n in executor.notifications.values()]))

if __name__ == '__main__':
    export(Path('docs/compute/examples'))
