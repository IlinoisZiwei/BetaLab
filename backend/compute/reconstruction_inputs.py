"""Pinned input packages for a future reconstruction worker, never a skeleton result."""
import hashlib
import json
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.database import database
from .contracts import Body
from . import contact_review, service, storage, world_review

class Preparation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_body: Body | None = None
    world_version: str = Field(pattern=r'^[a-f0-9]{64}$')

def prepare(task_id, owner_id, request):
    world = world_review.read(task_id, owner_id, request.world_version, export=True)
    contacts = contact_review.export(task_id, owner_id, world['review']['contact_version'])
    manifest = dict(schema_version='reconstruction-inputs-v1', task_id=str(task_id),
        source_video_id=world['source_video_id'], world_version=request.world_version,
        calibration_version=world['review']['calibration_version'],
        contact_version=contacts['version'], input_sha256=world['input_sha256'],
        world_code_sha256=world['code_sha256'], generation_ready=False,
        source_body=request.source_body.model_dump(mode='json') if request.source_body else None,
        coverage=world['aligned']['summary'],
        blockers=['New-video body-depth reconstruction and adaptation are not implemented'],
        unknown_limb_frames=contacts['normalized']['unknown_limb_frames'])
    version = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with database() as db:
        service.source(db, manifest['source_video_id'], owner_id, lock=True)
        root = storage.root()/'reconstruction-inputs'/str(task_id); root.mkdir(parents=True, exist_ok=True)
        contact_review.atomic_json(root/(version+'.json'), manifest)
    return dict(version=version, **manifest)

def read(task_id, owner_id, version):
    # Check ownership/source before revealing whether the package exists.
    service.get_task(task_id, owner_id)
    if len(version) != 64 or any(c not in '0123456789abcdef' for c in version):
        raise HTTPException(422, 'Invalid input package version')
    path = storage.root()/'reconstruction-inputs'/str(task_id)/(version+'.json')
    if not path.is_file(): raise HTTPException(404, 'Input package unavailable')
    doc = json.loads(path.read_text())
    if hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest() != version:
        raise HTTPException(409, 'Input package changed')
    world = world_review.read(task_id, owner_id, doc['world_version'], export=True)
    if world['input_sha256'] != doc['input_sha256'] or world['code_sha256'] != doc['world_code_sha256']:
        raise HTTPException(409, 'Input package dependencies changed')
    return dict(version=version, **doc)
