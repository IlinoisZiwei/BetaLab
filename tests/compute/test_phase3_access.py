"""Fast media authorization tests. Fixtures are synthetic, not algorithm validation."""
import json
import os
from pathlib import Path
import shutil
import unittest
from uuid import uuid4
from support import database as db_support

@unittest.skipUnless(os.getenv('BETALAB_TEST_DB')=='1','Requires explicit PostgreSQL test opt-in')
class MediaAccessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_support.setup_database(cls)
        cls.old_storage=os.environ.get('COMPUTE_STORAGE_DIR')
        os.environ['COMPUTE_STORAGE_DIR']=str(Path(cls.directory.name)/'compute')

    @classmethod
    def tearDownClass(cls):
        if cls.old_storage is None:
            os.environ.pop('COMPUTE_STORAGE_DIR',None)
        else:
            os.environ['COMPUTE_STORAGE_DIR']=cls.old_storage
        db_support.teardown_database(cls)

    def setUp(self):
        db_support.upload_sample(self)
        from backend.compute import service,storage
        from backend.database import database
        from backend.compute.contracts import SourceRequest
        self.task,_=service.submit(SourceRequest.model_validate(self.request).model_dump(),self.alice_id,uuid4().hex)
        self.published=storage.root()/'published'/self.task['id']
        self.published.mkdir(parents=True)
        shutil.copyfile(self.video,self.published/'video.mp4')
        (self.published/'fixture.json').write_text(json.dumps({'purpose':'synthetic access-control test only'}))
        def artifact(name,mime):
            return dict(storage_key=f"published/{self.task['id']}/{name}",media_type=mime,sha256=storage.digest(self.published/name))
        assets={name:artifact('fixture.json','application/json') for name in ('holds','skeleton','alignment','contacts')}
        assets['video']=artifact('video.mp4','video/mp4')
        result=dict(kind='analyze',is_mock=False,algorithm_version='synthetic-access-test',
            source_analysis_version='test-version',calibration_version='test-calibration',source_video_id=self.video_id,
            frame_count=25,fps=25,quality=dict(evidence='low_confidence',geometry_status='assumed'),
            artifacts=assets,baseline_status='not_requested',technique_status='not_requested')
        with database() as db:
            row=db.execute("UPDATE compute_tasks SET is_mock=false,state='running' WHERE id=%s RETURNING *",(self.task['id'],)).fetchone()
            service.finish(db,row,result=result)

    def test_shared_source_preview_does_not_expose_private_task_or_raw_artifacts(self):
        source='/api/tasks/source-analysis/'+self.video_id+'/artifacts/'
        own='/api/tasks/'+self.task['id']+'/artifacts/'
        # Historical media remains viewable; it cannot seed a new-engine generation.
        self.assertEqual(self.bob.get('/api/tasks/source-analysis/'+self.video_id).status_code,409)
        self.assertEqual(self.bob.get(source+'video').status_code,200)
        self.assertEqual(self.bob.get(own+'video').status_code,404)
        self.assertEqual(self.bob.get(source+'skeleton').status_code,404)
        self.alice.patch('/api/videos/'+self.video_id,json={'visibility':'private'})
        self.assertEqual(self.bob.get(source+'video').status_code,404)
        self.assertEqual(self.alice.get(own+'video').status_code,200)
        self.alice.delete('/api/videos/'+self.video_id)
        self.assertEqual(self.alice.get(own+'video').status_code,404)

    def test_file_integrity_and_path_escape_fail_closed(self):
        url='/api/tasks/'+self.task['id']+'/artifacts/video'
        self.assertEqual(self.alice.get(url,headers={'Range':'bytes=-0'}).status_code,416)
        self.assertEqual(self.alice.get(url,headers={'Range':'bytes='+'9'*5000+'-'}).status_code,416)
        path=self.published/'video.mp4'
        saved=path.read_bytes()
        path.write_bytes(saved+b'corrupt')
        self.assertEqual(self.alice.get(url).status_code,409)
        path.unlink()
        path.symlink_to(self.video)
        self.assertEqual(self.alice.get(url).status_code,404)

    def test_old_engine_job_fails_before_starting_a_scientific_process(self):
        from backend.compute import service,storage
        from backend.compute.contracts import SourceRequest
        from backend.compute.worker import Worker
        from backend.database import database
        from psycopg.types.json import Jsonb
        task,_=service.submit(SourceRequest.model_validate(self.request).model_dump(),self.alice_id,uuid4().hex)
        with database() as db:
            db.execute('UPDATE compute_tasks SET is_mock=false,execution=%s WHERE id=%s',
                       (Jsonb(dict(mode='real',engine='obsolete-engine')),task['id']))
        with Worker() as worker:
            self.assertTrue(worker.run_one())
        failed=self.alice.get('/api/tasks/'+task['id']).json()
        self.assertEqual(failed['error']['code'],'STALE_ANALYSIS')
        self.assertFalse(failed['error']['retryable'])
        self.assertFalse((storage.root()/'work'/task['id']).exists())

    def test_unknown_video_is_rejected_before_queueing_real_work(self):
        old_upload=os.environ.get('UPLOAD_DIR')
        os.environ['UPLOAD_DIR']=str(self.videos.UPLOAD_DIR)
        os.environ['COMPUTE_MODE']='real'
        try:
            response=self.alice.post('/api/tasks/analyze',json=self.request,headers={'Idempotency-Key':'unsupported-recording'})
            self.assertEqual(response.status_code,422,response.text)
            self.assertIn('Trial 2',response.json()['error']['message'])
        finally:
            os.environ['COMPUTE_MODE']='mock'
            if old_upload is None:
                os.environ.pop('UPLOAD_DIR',None)
            else:
                os.environ['UPLOAD_DIR']=old_upload

    def test_upload_and_artifact_range_transport_preserves_endpoint_policies(self):
        data=self.video.read_bytes()
        upload='/api/videos/'+self.video_id+'/content'
        artifact='/api/tasks/'+self.task['id']+'/artifacts/video'
        for url in (upload,artifact):
            for header,expected in [('bytes=0-9',data[:10]),('bytes=10-',data[10:]),('bytes=-12',data[-12:])]:
                response=self.alice.get(url,headers={'Range':header})
                self.assertEqual(response.status_code,206)
                self.assertEqual(response.content,expected)
                self.assertEqual(int(response.headers['content-length']),len(expected))
                self.assertEqual(response.headers['cache-control'],'no-store')  # API middleware policy
            for header in ('bytes=-0','bytes=99-2','bytes=99999999-','bytes=0-1,3-4','invalid'):
                response=self.alice.get(url,headers={'Range':header})
                self.assertEqual(response.status_code,416,header)
                self.assertEqual(response.headers['content-range'],f'bytes */{len(data)}')
        self.assertEqual(self.alice.get(upload,headers={'Range':'bytes=-'}).status_code,206)
        self.assertEqual(self.alice.get(artifact,headers={'Range':'bytes=-'}).status_code,416)
        self.assertEqual(self.alice.get(upload).headers['content-disposition'],'inline')
        self.assertNotIn('content-disposition',self.alice.get(artifact).headers)

if __name__=='__main__':
    unittest.main()
