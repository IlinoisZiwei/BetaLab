"""Owner-only immutable global geometry, pinned to calibration/contact versions."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from fastapi import HTTPException
from backend.database import database
from . import contact_review, service, storage
from .input_schema import CalibrationReview
from .world_schema import WorldReview

ENGINE = 'global-wall-v1'

def hash_json(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def dependencies(task_id, owner_id, review):
    result, summary, holds, paths, hashes = contact_review.inputs(task_id,owner_id)
    for name in ('pose','identity','alignment'):
        a = result['artifacts'][name]; p = storage.resolve(a['storage_key'])
        if storage.digest(p) != a['sha256']: raise HTTPException(409,'Input artifact changed: '+name)
        paths[name],hashes[name] = p,a['sha256']
    calibration_path = storage.root()/'reviews'/str(task_id)/(review.calibration_version+'.json')
    if not calibration_path.is_file(): raise HTTPException(409,'Save the referenced wall calibration first')
    calibration = json.loads(calibration_path.read_text())
    expected = hash_json(dict(task=str(task_id),input_sha=hashes['input_summary'],review=calibration['review']))
    if expected != review.calibration_version: raise HTTPException(409,'Calibration version or inputs changed')
    CalibrationReview.model_validate(calibration['review'])
    hold_version = calibration['review'].get('hold_review_version')
    from . import hold_review
    holds = hold_review.read(task_id, owner_id, hold_version, latest=False)['holds']
    if contact_review.pinned_holds(task_id, review.contact_version) != hold_version:
        raise HTTPException(409, 'Calibration and contacts must use the same hold review version')
    if hold_version: hashes['hold_review_version'] = hold_version
    contacts = contact_review.export(task_id,owner_id,review.contact_version)
    hashes['calibration_document'] = storage.digest(calibration_path)
    hashes['contact_version'] = review.contact_version
    return result,dict(review=review.model_dump(mode='json'),calibration=calibration,
        summary=summary,holds=holds,contacts=contacts,paths={k:str(v) for k,v in paths.items()}),hashes

def folder(task_id):
    return storage.root()/'world-reviews'/str(task_id)

def document(task_id, version=None):
    root = folder(task_id)
    if version is None:
        if not (root/'latest.json').exists(): return None
        version = json.loads((root/'latest.json').read_text())['version']
    if len(version)!=64 or any(c not in '0123456789abcdef' for c in version):
        raise HTTPException(422,'Invalid global review version')
    path = root/(version+'.json')
    if not path.is_file(): raise HTTPException(404,'Global review version unavailable')
    doc = json.loads(path.read_text())
    if hash_json(doc)!=version: raise HTTPException(409,'Global review changed')
    return dict(version=version,**doc)

def public(doc):
    return dict(version=doc['version'],review=doc['review'],summary=doc['aligned']['summary'],
                panels=doc['aligned']['panels'],seams=doc['aligned']['seams'],
                cameras=doc['aligned']['cameras'],warnings=doc['aligned']['warnings'])

def read(task_id,owner_id,version=None,export=False):
    contact_review.inputs(task_id,owner_id)
    doc = document(task_id,version)
    if doc is None: return dict(version=None,review=None,summary=None)
    _,_,hashes = dependencies(task_id,owner_id,WorldReview.model_validate(doc['review']))
    if hashes!=doc['input_sha256']: raise HTTPException(409,'Global review dependencies changed')
    return doc if export else public(doc)

def save(task_id,owner_id,review: WorldReview):
    result,payload,hashes = dependencies(task_id,owner_id,review)
    source = os.getenv('BETA_TRANSLATOR_ROOT')
    if not source: raise HTTPException(503,'Scientific environment is not configured')
    python = os.getenv('BETA_TRANSLATOR_PYTHON',str(Path(source)/'.venv/bin/python'))
    try:
        process = subprocess.run([python,'-m','backend.compute.world_job'],input=json.dumps(payload),
            text=True,capture_output=True,timeout=90,cwd=Path(__file__).resolve().parents[2])
    except (OSError,subprocess.TimeoutExpired):
        raise HTTPException(503,'Global calibration validator unavailable')
    if process.returncode: raise HTTPException(422,'Global alignment rejected: '+process.stderr[-1000:])
    aligned = json.loads(process.stdout)
    code = {name:storage.digest(Path(__file__).with_name(name)) for name in
            ('world_schema.py','world_geometry.py','world_job.py','world_review.py','input_calibration.py')}
    doc = dict(engine=ENGINE,task_id=str(task_id),source_video_id=result['source_video_id'],
               input_sha256=hashes,code_sha256=code,review=review.model_dump(mode='json'),aligned=aligned)
    version = hash_json(doc)
    with database() as db:
        service.source(db,result['source_video_id'],owner_id,lock=True)
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('world-review:'+str(task_id),))
        current = document(task_id)
        if current and current['version']==version: return public(dict(version=version,**doc))
        if (current['version'] if current else None)!=review.base_version:
            raise HTTPException(409,'Global review changed; reload before saving')
        root = folder(task_id);root.mkdir(parents=True,exist_ok=True)
        contact_review.atomic_json(root/(version+'.json'),doc)
        contact_review.atomic_json(root/'latest.json',dict(version=version))
    return public(dict(version=version,**doc))
