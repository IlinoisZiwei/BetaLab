"""Immutable human hold corrections; automatic artifacts are never overwritten."""
import hashlib
import json
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.database import database
from . import input_review, service, storage

class HoldCorrection(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    hold_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')
    cx_px: float = Field(ge=0)
    cy_px: float = Field(ge=0)
    note: str = Field(min_length=1, max_length=500)

class HoldReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_version: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    reference_frame: int = Field(ge=0, strict=True)
    corrections: list[HoldCorrection] = Field(max_length=500)
    notes: str = Field(min_length=1, max_length=3000)

def normalize(review, summary, original):
    if review.reference_frame != summary['reference_frame']:
        raise ValueError('Use the original analysis reference frame')
    ids = [h.hold_id for h in review.corrections]
    if len(set(ids)) != len(ids): raise ValueError('Duplicate hold IDs')
    holds = {h['hold_id']: dict(h) for h in original}
    for h in review.corrections:
        if h.cx_px >= summary['width'] or h.cy_px >= summary['height']:
            raise ValueError('Hold center is outside the reference image')
        if h.hold_id not in holds and not h.hold_id.startswith('manual-'):
            raise ValueError('New holds must use a manual- ID')
        # A corrected center does not invent a segmentation mask or hold size.
        holds[h.hold_id] = dict(hold_id=h.hold_id, cx_px=h.cx_px, cy_px=h.cy_px,
                               review_status='human_corrected', note=h.note)
    return list(holds.values())

def source_inputs(task_id, owner_id):
    result = input_review.prepared(task_id, owner_id)
    hashes = {n: result['artifacts'][n]['sha256'] for n in ('input_summary','holds')}
    content = {n: json.loads(storage.resolve(result['artifacts'][n]['storage_key']).read_text()) for n in hashes}
    return result, hashes, content

def document(task_id, version):
    if len(version) != 64 or any(c not in '0123456789abcdef' for c in version):
        raise HTTPException(422, 'Invalid hold review version')
    path = storage.root()/'hold-reviews'/str(task_id)/(version+'.json')
    if not path.is_file(): raise HTTPException(404, 'Hold review version unavailable')
    doc = json.loads(path.read_text())
    if hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest() != version:
        raise HTTPException(409, 'Hold review changed')
    return dict(version=version, **doc)

def read(task_id, owner_id, version=None, latest=True):
    _, hashes, content = source_inputs(task_id, owner_id)
    pointer = storage.root()/'hold-reviews'/str(task_id)/'latest.json'
    if version is None and latest and pointer.exists(): version = json.loads(pointer.read_text())['version']
    if version is None:
        return dict(version=None, review=None, holds=content['holds'], summary=content['input_summary'])
    doc = document(task_id, version)
    if doc['input_sha256'] != hashes: raise HTTPException(409, 'Hold source inputs changed')
    return dict(**doc, summary=content['input_summary'])

def save(task_id, owner_id, review):
    result, hashes, content = source_inputs(task_id, owner_id)
    try: holds = normalize(review, content['input_summary'], content['holds'])
    except ValueError as error: raise HTTPException(422, str(error))
    doc = dict(task_id=str(task_id), source_video_id=result['source_video_id'], input_sha256=hashes,
               review=review.model_dump(mode='json'), holds=holds, generation_ready=False)
    version = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    from .contact_review import atomic_json
    with database() as db:
        service.source(db, result['source_video_id'], owner_id, lock=True)
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('hold-review:'+str(task_id),))
        current = read(task_id, owner_id)
        if current['version'] == version: return current
        if current['version'] != review.base_version: raise HTTPException(409, 'Hold review changed; reload before saving')
        root = storage.root()/'hold-reviews'/str(task_id); root.mkdir(parents=True, exist_ok=True)
        atomic_json(root/(version+'.json'), doc); atomic_json(root/'latest.json', dict(version=version))
    return read(task_id, owner_id, version)
