"""Disposable database, authenticated accounts and sample upload fixtures."""
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

def setup_database(cls):
    cls.old_mode = os.environ.get('COMPUTE_MODE')
    os.environ['COMPUTE_MODE'] = 'mock'
    from backend.database import connect
    from psycopg import sql
    cls.schema = 'compute_test_' + uuid4().hex
    cls.previous_options = os.environ.get('PGOPTIONS')
    with connect() as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
    os.environ['PGOPTIONS'] = '-c search_path=' + cls.schema
    from backend.db.manage import migrate
    migrate(direct=True)
    migrate(direct=True)  # Replay verifies checksum/idempotence.
    cls.directory = tempfile.TemporaryDirectory()
    cls.video = Path(cls.directory.name)/'sample.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x64:d=1',
                    '-c:v','libx264','-pix_fmt','yuv420p',str(cls.video)],check=True)
    import backend.app as api
    from backend import auth
    from backend.routes import videos
    cls.auth = auth
    cls.videos = videos
    # Each disposable schema gets its own in-memory login throttle state.
    cls.old_attempts = auth.attempts
    auth.attempts = type(auth.attempts)(auth.attempts.default_factory)
    cls.old_upload = videos.UPLOAD_DIR
    videos.UPLOAD_DIR = (Path(cls.directory.name)/'uploads').resolve()
    cls.api = api
    from starlette.testclient import TestClient
    cls.alice = TestClient(api.app,headers={'origin':'http://localhost:8443'})
    cls.bob = TestClient(api.app,headers={'origin':'http://localhost:8443'})
    for client,name in ((cls.alice,'phase2alice'),(cls.bob,'phase2bob')):
        response = client.post('/api/auth/register',json=dict(username=name,password='phase2-local-test-only'))
        assert response.status_code==201, response.text
        client.headers['x-csrf-token'] = response.json()['csrf_token']
    cls.alice_id = cls.alice.get('/api/auth/me').json()['user']['id']
    cls.bob_id = cls.bob.get('/api/auth/me').json()['user']['id']
    with connect() as db:
        db.execute("INSERT INTO gyms(id,name) VALUES ('test-gym','Test Gym')")
        db.execute("INSERT INTO routes(id,gym_id,name,grade) VALUES ('test-route','test-gym','Test Route','V0')")

def teardown_database(cls):
    from backend.database import connect
    from psycopg import sql
    if cls.old_mode is None:
        os.environ.pop('COMPUTE_MODE',None)
    else:
        os.environ['COMPUTE_MODE'] = cls.old_mode
    cls.alice.close()
    cls.bob.close()
    cls.videos.UPLOAD_DIR = cls.old_upload
    cls.auth.attempts = cls.old_attempts
    cls.directory.cleanup()
    if cls.previous_options is None:
        os.environ.pop('PGOPTIONS',None)
    else:
        os.environ['PGOPTIONS'] = cls.previous_options
    with connect() as db:
        db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))

def upload_sample(self):
    from backend.database import database
    with database() as db:
        db.execute('TRUNCATE compute_tasks CASCADE')
    with self.video.open('rb') as stream:
        response = self.alice.post('/api/videos',data=dict(route_id='test-route',visibility='public'),
            files={'video':('sample.mp4',stream,'video/mp4')})
    self.assertEqual(response.status_code,201,response.text)
    self.video_id = response.json()['id']
    self.request = dict(kind='analyze',video_id=self.video_id,route_id='test-route',
        calibration=dict(version='trial2-grid143-v1',reference_frame=450,evidence_key='calibration/trial2-grid143-v1'))
