"""Private compute storage. Only authenticated artifact routes expose published files."""
import hashlib
import os
from pathlib import Path
from fastapi import HTTPException
from .calibration import VERSION

TRIAL2_SHA256 = '9964d27ca051953d77cf10ee94a1772bd73e30d7e23fa09a54983c3630e8a068'
ENGINE = 'trial2-source-fit-v5'
INPUT_ENGINE = 'video-inputs-v1'
INPUT_CALIBRATION = 'new-video-unreviewed-v1'

def root():
    return Path(os.getenv('COMPUTE_STORAGE_DIR','./data/compute')).resolve()

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()

def resolve(key, base=None):
    base = root() if base is None else Path(base).resolve()
    path = (base/key).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(404,'Artifact unavailable')
    return path

def video_path(video):
    return resolve(video['storage_key'],Path(os.getenv('UPLOAD_DIR','./data/uploads')))

def execution_config(video, request):
    mode = os.getenv('COMPUTE_MODE','real')
    if mode not in ('real','mock'):
        raise HTTPException(503,'Compute mode misconfigured')
    if mode == 'mock':
        return dict(mode='mock')
    video_hash = digest(video_path(video))
    if video_hash != TRIAL2_SHA256:
        if request['kind']!='analyze' or request['calibration']['version']!=INPUT_CALIBRATION:
            raise HTTPException(422,'New videos have no Trial 2 evidence; prepare their own inputs before adaptation.')
        return dict(mode='real',engine=INPUT_ENGINE,video_sha256=video_hash)
    if request['kind']=='analyze':
        c = request['calibration']
        if (request['route_id']!='r1' or c['version']!=VERSION or c['reference_frame']!=450
                or c['geometry_status']!='assumed'):
            raise HTTPException(422,f'Trial 2 requires route r1 and {VERSION} calibration (frame 450, partially assumed geometry)')
    return dict(mode='real',engine=ENGINE,video_sha256=TRIAL2_SHA256)
