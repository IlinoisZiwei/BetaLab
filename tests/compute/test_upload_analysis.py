"""Upload orchestration tests; mock worker outcomes are explicitly synthetic."""
import concurrent.futures
import os
import unittest
from support import database as db_support

@unittest.skipUnless(os.getenv('BETALAB_TEST_DB')=='1','Requires disposable PostgreSQL schema')
class UploadAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):db_support.setup_database(cls)
    @classmethod
    def tearDownClass(cls):db_support.teardown_database(cls)
    def setUp(self):db_support.upload_sample(self)

    @property
    def url(self):return '/api/tasks/upload-analysis/'+self.video_id

    def test_start_is_owner_only_and_idempotent_across_concurrent_calls(self):
        self.assertEqual(self.bob.get(self.url).status_code,404)
        self.assertEqual(self.bob.post(self.url).status_code,404)
        self.assertTrue(self.alice.get(self.url).json()['can_start'])
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            responses=list(pool.map(lambda _:self.alice.post(self.url),range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,202])
        self.assertEqual(responses[0].json()['id'],responses[1].json()['id'])
        self.assertEqual(self.alice.get(self.url).json()['task']['state'],'queued')
        self.assertEqual(len(self.alice.get('/api/tasks').json()['items']),1)
        self.assertEqual(self.alice.post(self.url).json()['id'],responses[0].json()['id'])

    def test_failed_analysis_preserves_video_and_requires_explicit_retry(self):
        from backend.compute.worker import Worker
        task=self.alice.post(self.url).json()
        with Worker('failure') as worker:worker.run_one()
        state=self.alice.get(self.url).json();self.assertEqual(state['task']['state'],'failed')
        self.assertEqual(self.alice.get('/api/videos/'+self.video_id+'/content').status_code,200)
        self.assertEqual(self.alice.post(self.url).json()['id'],task['id'])
        response=self.alice.post('/api/tasks/'+task['id']+'/retry',json={},headers={'Idempotency-Key':'upload-retry:'+task['id']})
        self.assertEqual(response.status_code,202,response.text)
        with Worker() as worker:worker.run_one()
        latest=self.alice.get(self.url).json()['task']
        self.assertEqual(latest['state'],'succeeded');self.assertEqual(latest['retry_of'],task['id'])
        self.assertEqual(self.alice.get('/api/notifications').json()['unread_count'],2)

    def test_new_real_video_queues_independent_input_preparation(self):
        previous=os.environ.get('UPLOAD_DIR');os.environ['UPLOAD_DIR']=str(self.videos.UPLOAD_DIR);os.environ['COMPUTE_MODE']='real'
        try:
            state=self.alice.get(self.url).json()
            self.assertTrue(state['can_start']);self.assertIsNone(state['task'])
            response=self.alice.post(self.url);self.assertEqual(response.status_code,202,response.text)
            self.assertFalse(response.json()['is_mock'])
            self.assertEqual(response.json()['state'],'queued')
            self.assertEqual(self.alice.get('/api/videos/'+self.video_id+'/content').status_code,200)
        finally:
            os.environ['COMPUTE_MODE']='mock'
            if previous is None:os.environ.pop('UPLOAD_DIR',None)
            else:os.environ['UPLOAD_DIR']=previous

    def test_deleted_source_cannot_be_started_or_retried(self):
        task=self.alice.post(self.url).json()
        self.assertEqual(self.alice.delete('/api/videos/'+self.video_id).status_code,204)
        self.assertEqual(self.alice.get(self.url).status_code,404)
        self.assertEqual(self.alice.post(self.url).status_code,404)
        self.assertEqual(self.alice.post('/api/tasks/'+task['id']+'/retry',json={},headers={'Idempotency-Key':'deleted'}).status_code,404)
