"""Versioned manual contact corrections for new-video inputs only.

Interval convention follows CIS5810 Beta_Translator contact_decoding.py /
contact_matching.py @ ff85726da2fbbd2616c409b01d6c03833ab62ce9:
upstream end_frame is inclusive; end_sec is (end_frame + 1) / fps.
The editor uses an exclusive release_frame. Validation, version storage and
dense review export are new BetaLab code; no Trial2 solver is invoked.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import tempfile
from fastapi import HTTPException
from backend.database import database
from . import input_review, service, storage
from .contact_schema import ContactReview, LIMBS

INPUTS = ('input_summary', 'holds', 'contacts', 'contact_events', 'frame_map')

def inputs(task_id, owner_id):
    result = input_review.prepared(task_id, owner_id)
    paths, hashes = {}, {}
    for name in INPUTS:
        artifact = result['artifacts'][name]
        path = storage.resolve(artifact['storage_key'])
        if storage.digest(path) != artifact['sha256']:
            raise HTTPException(409, 'Contact input artifact changed: ' + name)
        paths[name], hashes[name] = path, artifact['sha256']
    summary = json.loads(paths['input_summary'].read_text())
    holds = json.loads(paths['holds'].read_text())
    return result, summary, holds, paths, hashes

def normalize(review: ContactReview, summary, holds):
    count, fps = summary['frame_count'], summary['fps']
    if count < 1 or not math.isfinite(fps) or fps <= 0:
        raise ValueError('Invalid analysis timeline')
    known = {h['hold_id'] for h in holds}
    intervals = sorted((i.model_dump() for i in review.intervals),
                       key=lambda i: (LIMBS.index(i['limb']), i['start_frame']))
    ends = {}
    for item in intervals:
        if item['release_frame'] > count:
            raise ValueError('Contact interval exceeds analysis frame count')
        if item['state'] == 'hold' and item['hold_id'] not in known:
            raise ValueError('Unknown hold ID: ' + item['hold_id'])
        if item['start_frame'] < ends.get(item['limb'], 0):
            raise ValueError('Overlapping intervals for ' + item['limb'])
        ends[item['limb']] = item['release_frame']
        item.update(start_sec=item['start_frame']/fps, release_sec=item['release_frame']/fps)
    known_rows = sum(i['release_frame']-i['start_frame'] for i in intervals if i['state'] != 'unknown')
    return dict(intervals=intervals, unknown_limb_frames=4*count-known_rows,
                frame_count=count, fps=fps, generation_ready=False,
                time_axis='analysis_frames', interval_convention='start inclusive, release exclusive')

def folder(task_id):
    return storage.root()/'contact-reviews'/str(task_id)

def read_document(task_id, hashes, version=None):
    root = folder(task_id)
    latest = root/'latest.json'
    if version is None:
        if not latest.exists(): return None
        version = json.loads(latest.read_text())['version']
    if len(version) != 64 or any(c not in '0123456789abcdef' for c in version):
        raise HTTPException(422, 'Invalid contact review version')
    path = root/(version+'.json')
    if not path.exists(): raise HTTPException(404, 'Contact review version unavailable')
    doc = json.loads(path.read_text())
    actual = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    if actual != version or doc['input_sha256'] != hashes:
        raise HTTPException(409, 'Contact review or its source inputs changed')
    return dict(version=version, **doc)

def read(task_id, owner_id, version=None):
    _, summary, holds, paths, hashes = inputs(task_id, owner_id)
    doc = read_document(task_id, hashes, version)
    candidates = []
    with paths['contact_events'].open() as stream:
        for row in csv.DictReader(stream):
            if row['limb'] in LIMBS and row['hold_id'] in {h['hold_id'] for h in holds}:
                candidates.append(dict(limb=row['limb'], state='hold', hold_id=row['hold_id'],
                    start_frame=int(row['start_frame']), release_frame=int(row['end_frame'])+1,
                    note='Automatic candidate; check against the video'))
    return dict(version=doc['version'] if doc else None, saved=doc,
                summary=summary, holds=holds, candidates=candidates)

def atomic_json(path, value):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        temporary = Path(stream.name)
    temporary.replace(path)

def save(task_id, owner_id, review: ContactReview):
    result, summary, holds, _, hashes = inputs(task_id, owner_id)
    try:
        normalized = normalize(review, summary, holds)
    except ValueError as error:
        raise HTTPException(422, str(error))
    doc = dict(schema_version='contact-review-v1', task_id=str(task_id),
               source_video_id=result['source_video_id'], input_sha256=hashes,
               review=review.model_dump(mode='json'), normalized=normalized)
    version = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    with database() as db:
        service.source(db, result['source_video_id'], owner_id, lock=True)
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('contact-review:'+str(task_id),))
        current = read_document(task_id, hashes)
        if current and current['version'] == version: return current
        if (current['version'] if current else None) != review.base_version:
            raise HTTPException(409, 'Contact review changed; reload before saving')
        root = folder(task_id)
        root.mkdir(parents=True, exist_ok=True)
        atomic_json(root/(version+'.json'), doc)
        atomic_json(root/'latest.json', dict(version=version))
    return dict(version=version, **doc)

def export(task_id, owner_id, version):
    """Pinned, integrity-checked input for a future reconstruction consumer.

    Unannotated frames stay unknown. Confirmation never implies geometry passes.
    Original timestamps are retained from the immutable sampling map.
    """
    _, summary, _, paths, hashes = inputs(task_id, owner_id)
    doc = read_document(task_id, hashes, version)
    if not doc['review']['confirmed']:
        raise HTTPException(409, 'Confirm the contact review before exporting it for computation')
    with paths['frame_map'].open() as stream:
        mapping = list(csv.DictReader(stream))
    count = summary['frame_count']
    if len(mapping) != count or any(int(row['frame']) != i for i, row in enumerate(mapping)):
        raise HTTPException(409, 'Frame map does not match analysis timeline')
    rows = [dict(frame=i, time_sec=i/summary['fps'], limb=limb, state='unknown', hold_id=None,
                 source_frame=int(mapping[i]['source_frame']),
                 source_time_sec=float(mapping[i]['source_time_sec']))
            for limb in LIMBS for i in range(count)]
    for interval in doc['normalized']['intervals']:
        offset = LIMBS.index(interval['limb'])*count
        for i in range(interval['start_frame'], interval['release_frame']):
            rows[offset+i].update(state=interval['state'], hold_id=interval['hold_id'])
    return dict(version=version, task_id=str(task_id), schema_version=doc['schema_version'],
                input_sha256=hashes, normalized=doc['normalized'], frames=rows,
                generation_ready=False)
