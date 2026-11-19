"""Real PostgreSQL + authenticated HTTP integration tests in a disposable schema.

Run only with BETALAB_TEST_DB=1 and an explicitly configured test database.
No production schema/data is reset; a random schema is created and removed.
"""
import concurrent.futures
import os
import subprocess
import sys
import time
import unittest
from uuid import uuid4

from support import database as support

ENABLED = os.getenv('BETALAB_TEST_DB') == '1'

@unittest.skipUnless(ENABLED, 'Requires BETALAB_TEST_DB=1 and configured PostgreSQL')
class PhaseTwoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): support.setup_database(cls)
    @classmethod
    def tearDownClass(cls): support.teardown_database(cls)
    def setUp(self): support.upload_sample(self)

    def submit(self, client=None, body=None, key=None):
        client = client or self.alice
        body = body or self.request
        response = client.post('/api/tasks/'+body['kind'],json=body,headers={'Idempotency-Key':key or uuid4().hex})
        self.assertEqual(response.status_code,202,response.text)
        return response.json()

    def run_worker(self,outcome='success'):
        from backend.compute.worker import Worker
        with Worker(outcome) as worker:
            self.assertTrue(worker.run_one())

    def test_authenticated_mock_roundtrip_and_cross_user_generation(self):
        task = self.submit()
        self.assertEqual(self.alice.get('/api/tasks/'+task['id']+'/result').status_code,409)
        self.run_worker()
        result = self.alice.get('/api/tasks/'+task['id']+'/result').json()
        self.assertTrue(result['is_mock'])
        self.assertEqual(result['artifacts'],{})
        self.assertEqual(self.bob.get('/api/tasks/'+task['id']).status_code,404)
        reference = self.bob.get('/api/tasks/source-analysis/'+self.video_id)
        self.assertEqual(reference.status_code,200,reference.text)
        self.assertEqual(reference.json()['source_analysis_id'],task['id'])
        body = dict(kind='generate',video_id=self.video_id,source_analysis_id=task['id'],
            source_analysis_version=result['source_analysis_version'],
            target_body=dict(height_cm=170,arm_span_cm=175,provenance='user_input'),compare_techniques=True)
        generated = self.submit(self.bob,body)
        self.run_worker()
        self.assertEqual(self.bob.get('/api/tasks/'+generated['id']).json()['state'],'succeeded')
        self.assertEqual(self.alice.get('/api/tasks/'+generated['id']).status_code,404)
        notes = self.bob.get('/api/notifications').json()
        self.assertEqual(notes['unread_count'],1)
        note_id = notes['items'][0]['id']
        first = self.bob.patch('/api/notifications/'+note_id+'/read').json()['read_at']
        self.assertEqual(self.bob.patch('/api/notifications/'+note_id+'/read').json()['read_at'],first)
        self.assertEqual(self.bob.get('/api/notifications').json()['unread_count'],0)
        self.assertEqual(self.alice.patch('/api/notifications/'+note_id+'/read').status_code,404)

    def test_auth_csrf_origin_and_private_source(self):
        from starlette.testclient import TestClient
        with TestClient(self.api.app) as anonymous:
            self.assertEqual(anonymous.get('/api/tasks').status_code,401)
        self.assertEqual(self.alice.post('/api/tasks/analyze',json=self.request,headers={'x-csrf-token':'wrong'}).status_code,403)
        self.assertEqual(self.alice.post('/api/tasks/analyze',json=self.request,headers={'origin':'https://other.invalid'}).status_code,403)
        self.assertEqual(self.alice.patch('/api/videos/'+self.video_id,json={'visibility':'private'}).status_code,200)
        self.assertEqual(self.bob.get('/api/videos/'+self.video_id+'/content').status_code,404)
        self.assertEqual(self.bob.get('/api/tasks/source-analysis/'+self.video_id).status_code,404)
        self.assertEqual(self.bob.post('/api/tasks/analyze',json=self.request,headers={'Idempotency-Key':'private'}).status_code,404)
        self.submit(self.alice)

    def test_concurrent_idempotency_and_conflicts(self):
        from backend.compute.service import submit
        from backend.compute.contracts import SourceRequest
        body = SourceRequest.model_validate(self.request).model_dump()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _:submit(body,self.alice_id,'same-key'),range(6)))
        self.assertEqual(len({r[0]['id'] for r in results}),1)
        self.assertEqual(sum(r[1] for r in results),1)
        changed = {**self.request,'uploader_body':dict(height_cm=175,arm_span_cm=176,provenance='user_input')}
        self.assertEqual(self.alice.post('/api/tasks/analyze',json=changed,headers={'Idempotency-Key':'same-key'}).status_code,409)

    def test_retry_and_pagination(self):
        task = self.submit()
        self.run_worker('failure')
        url = '/api/tasks/'+task['id']+'/retry'
        self.assertEqual(self.bob.post(url,headers={'Idempotency-Key':'retry'}).status_code,404)
        response = self.alice.post(url,headers={'Idempotency-Key':'retry'})
        self.assertEqual(response.status_code,202,response.text)
        self.assertEqual(response.json()['attempt'],2)
        self.assertEqual(self.alice.post(url,headers={'Idempotency-Key':'retry'}).status_code,200)
        self.run_worker()
        page = self.alice.get('/api/tasks?limit=1').json()
        self.assertIsNotNone(page['next_cursor'])
        page2 = self.alice.get('/api/tasks',params={'limit':1,'cursor':page['next_cursor']}).json()
        self.assertNotEqual(page['items'][0]['id'],page2['items'][0]['id'])
        self.assertEqual(self.alice.get('/api/notifications').json()['unread_count'],2)

    def test_private_change_and_deletion_invalidate_live_access(self):
        task = self.submit(self.bob)
        self.alice.patch('/api/videos/'+self.video_id,json={'visibility':'private'})
        self.run_worker()
        self.assertEqual(self.bob.get('/api/tasks/'+task['id']).status_code,404)
        self.assertEqual(self.bob.get('/api/tasks').json()['items'],[])
        notes = self.bob.get('/api/notifications').json()['items']
        self.assertEqual(notes[0]['event'],'task_failed')
        self.assertNotIn('title',notes[0])
        self.alice.patch('/api/videos/'+self.video_id,json={'visibility':'public'})
        task2 = self.submit()
        self.assertEqual(self.alice.delete('/api/videos/'+self.video_id).status_code,204)
        self.run_worker()
        self.assertEqual(self.alice.get('/api/tasks/'+task2['id']).status_code,404)

    def test_source_version_and_insufficient_evidence(self):
        task = self.submit()
        self.run_worker('insufficient')
        result = self.alice.get('/api/tasks/'+task['id']+'/result').json()
        body = dict(kind='generate',video_id=self.video_id,source_analysis_id=task['id'],
            source_analysis_version=result['source_analysis_version'],target_body=dict(height_cm=170,arm_span_cm=175,provenance='user_input'))
        self.assertEqual(self.bob.post('/api/tasks/generate',json=body,headers={'Idempotency-Key':'insufficient'}).status_code,409)
        task2 = self.submit()
        self.run_worker()
        body['source_analysis_id'] = task2['id']
        self.assertEqual(self.bob.post('/api/tasks/generate',json=body,headers={'Idempotency-Key':'stale'}).status_code,409)

    def test_singleton_worker(self):
        from backend.compute.worker import Worker
        with Worker() as first:
            with self.assertRaisesRegex(RuntimeError,'Another compute worker'):
                with Worker():
                    pass
            self.assertFalse(first.run_one())

    def test_process_crash_recovery_and_restart_persistence(self):
        task = self.submit()
        process = subprocess.Popen([sys.executable,'-m','backend.compute.worker','--once','--delay','30'],stdout=subprocess.DEVNULL)
        try:
            deadline = time.monotonic()+10
            while time.monotonic()<deadline:
                if self.alice.get('/api/tasks/'+task['id']).json()['state']=='running':
                    break
                time.sleep(.05)
            else:
                self.fail('Worker did not claim persisted task')
            process.kill()
            process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        subprocess.run([sys.executable,'-m','backend.compute.worker','--once'],check=True,stdout=subprocess.DEVNULL)
        recovered = self.alice.get('/api/tasks/'+task['id']).json()
        self.assertEqual(recovered['error']['code'],'INTERRUPTED')
        retry = self.alice.post('/api/tasks/'+task['id']+'/retry',headers={'Idempotency-Key':'restart-retry'}).json()
        subprocess.run([sys.executable,'-m','backend.compute.worker','--once'],check=True,stdout=subprocess.DEVNULL)
        self.assertEqual(self.alice.get('/api/tasks/'+retry['id']).json()['state'],'succeeded')
        self.assertEqual(self.alice.get('/api/notifications').json()['unread_count'],2)

    def test_terminal_transaction_rolls_back_together(self):
        from backend.database import database
        from backend.compute.service import finish
        task = self.submit()
        with database() as db:
            row = db.execute("UPDATE compute_tasks SET state='running' WHERE id=%s RETURNING *",(task['id'],)).fetchone()
        with self.assertRaisesRegex(RuntimeError,'force rollback'):
            with database() as db:
                finish(db,row,error=dict(code='WORKER_FAILED',message='Test failure',retryable=True))
                raise RuntimeError('force rollback')
        self.assertEqual(self.alice.get('/api/tasks/'+task['id']).json()['state'],'running')
        self.assertEqual(self.alice.get('/api/notifications').json()['unread_count'],0)

if __name__=='__main__':
    unittest.main()
