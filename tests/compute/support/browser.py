"""Local API/Vite environment with verified precomputed v5 source evidence."""
import copy
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from urllib.request import urlopen
from uuid import uuid4
from . import database as db_support

def setup_browser(cls):
    db_support.setup_database(cls)
    cls.old_env={k:os.environ.get(k) for k in ('UPLOAD_DIR','COMPUTE_STORAGE_DIR','APP_ORIGINS','BETALAB_API_TARGET')}
    cls.output=Path('backend/compute/runs')/('community-v5-'+uuid4().hex[:8]);cls.output.mkdir()
    os.environ.update(UPLOAD_DIR=str(cls.videos.UPLOAD_DIR),COMPUTE_STORAGE_DIR=str(cls.output.resolve()),
        COMPUTE_MODE='real',APP_ORIGINS='http://127.0.0.1:5177',BETALAB_API_TARGET='http://127.0.0.1:8797')
    from backend.database import database
    from backend.compute import service
    with database() as db:
        db.execute("INSERT INTO routes(id,gym_id,name,grade) VALUES ('r1','test-gym','Trial2','V3')")
    with (Path(os.environ['BETA_TRANSLATOR_ROOT'])/'videos/trial2.mp4').open('rb') as f:
        response=cls.alice.post('/api/videos',data=dict(route_id='r1',visibility='public',title='Verified Trial2 source'),files={'video':('trial2.mp4',f,'video/mp4')})
    assert response.status_code==201,response.text
    cls.source_id=response.json()['id']
    with cls.video.open('rb') as f:
        response=cls.alice.post('/api/videos',data=dict(route_id='r1',visibility='public',title='No analysis video'),files={'video':('other.mp4',f,'video/mp4')})
    cls.unsupported_id=response.json()['id']
    report=Path(os.environ.get('BETALAB_V5_REPORT','backend/compute/runs/phase3-real-62fc330f/validation.json'))
    saved=json.loads(report.read_text())['analysis']['result']
    from backend.compute.real_job import input_hashes
    from backend.compute.storage import digest
    provenance=json.loads((report.parent/saved['artifacts']['provenance']['storage_key']).read_text())
    current = input_hashes(Path(os.environ['BETA_TRANSLATOR_ROOT']))
    recorded = provenance['input_sha256']
    changed = {k for k in set(current) | set(recorded) if current.get(k) != recorded.get(k)}
    if changed:
        # These GUI-only suites display immutable historical diagnostics (before localization/presentation changes).
        # Do not relabel their provenance or permit new solver runs from them.
        assert getattr(cls, 'historical_display_only', False), sorted(changed)
        assert changed <= {'betalab/moments.py', 'betalab/geometry_scope.py', 'betalab/render_video.py'}, sorted(changed)
        import hashlib
        for key in changed:
            original = subprocess.check_output(['git','show','73a8daa:backend/compute/'+key.split('/')[-1]])
            assert hashlib.sha256(original).hexdigest() == recorded[key]
        (cls.output/'historical-fixture.json').write_text(json.dumps(dict(
            purpose='Display/input review only; no source fitting or target adaptation',
            recorded_source='73a8daa', changed_since_recording=sorted(changed)),indent=2))
    for artifact in saved['artifacts'].values():
        original=report.parent/artifact['storage_key'];assert digest(original)==artifact['sha256']
        target=cls.output/artifact['storage_key'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
    body=dict(kind='analyze',video_id=cls.source_id,route_id='r1',calibration=dict(version='trial2-grid143-v2',reference_frame=450,evidence_key='calibration/trial2-grid143-v2'))
    response=cls.alice.post('/api/tasks/analyze',json=body,headers={'Idempotency-Key':'verified-precomputed-source'})
    assert response.status_code==202,response.text
    source_task=response.json();result=copy.deepcopy(saved);result['source_video_id']=cls.source_id
    with database() as db:
        row=db.execute("UPDATE compute_tasks SET state='running' WHERE id=%s RETURNING *",(source_task['id'],)).fetchone()
        service.finish(db,row,result=result)
    cls.processes=[];cls.logs=[]
    node=os.environ.get('BETALAB_NODE','node')
    for name,cmd in [('api',[sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8797']),('vite',[node,'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5177'])]:
        cls.start(name,cmd)
    for url in ('http://127.0.0.1:8797/api/health','http://127.0.0.1:5177'):
        for _ in range(100):
            try:
                with urlopen(url) as r:
                    if r.status==200:break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Server failed: '+url)

def start(cls,name,cmd):
    log=(cls.output/(name+'.log')).open('w');cls.logs.append(log)
    cls.processes.append(subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True))

def teardown_browser(cls):
    for p in reversed(cls.processes):
        if p.poll() is None:
            os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=8)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
    for f in cls.logs:f.close()
    for k,v in cls.old_env.items():
        if v is None:os.environ.pop(k,None)
        else:os.environ[k]=v
    db_support.teardown_database(cls)
