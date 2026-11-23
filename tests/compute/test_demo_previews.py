"""Demo visibility, immutable media verification and non-compute saves."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from support import database as support


class DemoAlgorithmGateTest(unittest.TestCase):
    def test_default_gate_precedes_any_scientific_access(self):
        from backend.compute.demo_algorithm import run
        with patch.dict(os.environ, {'BETALAB_DEMO_COMPUTE_ENABLED': '0'}):
            with self.assertRaisesRegex(ValueError, 'disabled'):
                run('/nonexistent', 'trial1', execute=True)
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                run('/nonexistent', 'trial2')


@unittest.skipUnless(os.getenv('BETALAB_TEST_DB') == '1', 'Requires isolated PostgreSQL test schema')
class DemoPreviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.setup_database(cls)
        cls.old_storage = os.environ.get('COMPUTE_STORAGE_DIR')
        os.environ['COMPUTE_STORAGE_DIR'] = cls.directory.name

    @classmethod
    def tearDownClass(cls):
        if cls.old_storage is None: os.environ.pop('COMPUTE_STORAGE_DIR', None)
        else: os.environ['COMPUTE_STORAGE_DIR'] = cls.old_storage
        support.teardown_database(cls)

    def setUp(self):
        support.upload_sample(self)
        from backend.database import database
        from backend.compute.storage import digest
        from psycopg.types.json import Jsonb
        self.path = '/api/demo-previews/' + self.video_id
        payload = dict(title='Prepared test',target_height_cm=180,target_arm_span_cm=None,
            frame_count=30,fps=30,limitations=['Diagnostic only'],artifacts={
                'video': dict(storage_key='sample.mp4',media_type='video/mp4',sha256=digest(self.video)),
                'wall': dict(storage_key='sample.mp4',media_type='video/mp4',sha256=digest(self.video))})
        with database() as db:
            db.execute('INSERT INTO demo_previews(video_id,payload) VALUES (%s,%s)', (self.video_id, Jsonb(payload)))

    def test_save_is_personal_idempotent_and_not_computation(self):
        from backend.database import database
        for _ in range(2): self.assertEqual(self.bob.post(self.path+'/save').status_code,200)
        self.assertEqual(len(self.bob.get('/api/demo-previews/saved').json()['items']),1)
        self.assertEqual(self.alice.get('/api/demo-previews/saved').json()['items'],[])
        value=self.bob.get(self.path).json()
        self.assertTrue(value['precomputed']);self.assertFalse(value['live_generation_enabled'])
        self.assertNotIn('artifacts',value)
        with database() as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM compute_tasks').fetchone()['n'],0)
        self.assertEqual(self.alice.post('/api/tasks/upload-analysis/'+self.video_id).status_code,409)
        self.assertEqual(self.alice.post('/api/tasks/analyze',json=self.request,headers={'Idempotency-Key':'demo'}).status_code,409)

    def test_revocation_covers_saved_list_and_media(self):
        self.bob.post(self.path+'/save')
        response=self.bob.get(self.path+'/media/video',headers={'Range':'bytes=0-31'})
        self.assertEqual(response.status_code,206);self.assertEqual(len(response.content),32)
        self.assertEqual(self.alice.patch('/api/videos/'+self.video_id,json={'visibility':'private'}).status_code,200)
        self.assertEqual(self.bob.get(self.path).status_code,404)
        self.assertEqual(self.bob.get(self.path+'/media/video').status_code,404)
        self.assertEqual(self.bob.post(self.path+'/save').status_code,404)
        self.assertEqual(self.bob.get('/api/demo-previews/saved').json()['items'],[])
        self.assertEqual(self.alice.get(self.path).status_code,200)

    def test_corrupt_artifact_and_csrf(self):
        with patch('backend.compute.storage.digest',return_value='changed'):
            self.assertEqual(self.bob.get(self.path+'/media/video').status_code,409)
        token=self.bob.headers.pop('x-csrf-token')
        try:self.assertEqual(self.bob.post(self.path+'/save').status_code,403)
        finally:self.bob.headers['x-csrf-token']=token
