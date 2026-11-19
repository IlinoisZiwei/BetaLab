"""Opt-in five-account real queue rehearsal; separate schema, no production data."""
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from uuid import uuid4
from support import database as db_support

@unittest.skipUnless(os.getenv('BETALAB_REHEARSAL_TEST')=='1','Requires explicit five-account real rehearsal opt-in')
class RehearsalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_support.setup_database(cls)
        cls.previous={k:os.environ.get(k) for k in ('UPLOAD_DIR','COMPUTE_STORAGE_DIR','COMPUTE_MODE')}
        cls.output=Path('backend/compute/runs')/('phase5-rehearsal-'+uuid4().hex[:8]);cls.output.mkdir(parents=True)
        os.environ.update(UPLOAD_DIR=str(cls.videos.UPLOAD_DIR),COMPUTE_STORAGE_DIR=str(cls.output.resolve()),COMPUTE_MODE='real')
        from backend.db.manage import execute,DB
        execute('BEGIN;'+(DB/'seeds/catalog.sql').read_text()+'COMMIT;',direct=True)
        from starlette.testclient import TestClient
        cls.clients=[cls.alice,cls.bob]
        for index in range(2,5):
            client=TestClient(cls.api.app,headers={'origin':'http://localhost:8443'})
            response=client.post('/api/auth/register',json=dict(username=f'rehearsal{index}',password='phase5-local-test-only'))
            assert response.status_code==201,response.text
            client.headers['x-csrf-token']=response.json()['csrf_token'];cls.clients.append(client)
        cls.worker=None

    @classmethod
    def tearDownClass(cls):
        if cls.worker and cls.worker.poll() is None:
            cls.worker.terminate()
            try:cls.worker.wait(timeout=10)
            except subprocess.TimeoutExpired:cls.worker.kill();cls.worker.wait(timeout=5)
        for client in cls.clients[2:]:client.close()
        for key,old in cls.previous.items():
            if old is None:os.environ.pop(key,None)
            else:os.environ[key]=old
        db_support.teardown_database(cls)

    def submit(self,client,kind,body,key):
        response=client.post('/api/tasks/'+kind,json=body,headers={'Idempotency-Key':key})
        self.assertEqual(response.status_code,202,response.text)
        return response.json()

    def test_five_users_real_fifo_restart_retry_and_notifications(self):
        from backend.compute.preflight import check
        from backend.database import database
        preflight=check(database_check=True)
        (self.output/'preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
        self.assertTrue(preflight['environment_ready'],preflight)
        with (Path(os.environ['BETA_TRANSLATOR_ROOT'])/'videos/trial2.mp4').open('rb') as stream:
            video=self.alice.post('/api/videos',data=dict(route_id='r1',visibility='public',share_as_beta='true'),
                files={'video':('trial2.mp4',stream,'video/mp4')})
        self.assertEqual(video.status_code,201,video.text);video_id=video.json()['id']
        analysis=self.submit(self.alice,'analyze',dict(kind='analyze',video_id=video_id,route_id='r1',
            calibration=dict(version='trial2-grid143-v2',reference_frame=450,evidence_key='calibration/trial2-grid143-v2')),'phase5-analysis')
        started=time.monotonic()
        subprocess.run([sys.executable,'-m','backend.compute.worker','--once'],check=True,timeout=1800)
        analysis_seconds=time.monotonic()-started
        analysis=self.alice.get('/api/tasks/'+analysis['id']).json()
        self.assertEqual(analysis['state'],'succeeded',analysis)
        self.assertFalse(analysis['is_mock'])
        reference=self.bob.get('/api/tasks/source-analysis/'+video_id).json()
        dimensions=[(170,175),(175,180),(180,185),(165,170),(185,190)]
        def body(index):
            height,span=dimensions[index]
            return dict(kind='generate',video_id=video_id,source_analysis_id=reference['source_analysis_id'],
                source_analysis_version=reference['source_analysis_version'],target_body=dict(height_cm=height,arm_span_cm=span,provenance='user_input'),compare_techniques=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            submitted=list(pool.map(lambda i:self.submit(self.clients[i],'generate',body(i),f'phase5-user-{i}'),range(5)))
        ids=[t['id'] for t in submitted]
        with database() as db:
            queued=db.execute('SELECT id,state FROM compute_tasks WHERE id=ANY(%s::uuid[]) ORDER BY created_at,id',(ids,)).fetchall()
        self.assertEqual([r['state'] for r in queued],['queued']*5)
        expected_order=[str(r['id']) for r in queued]
        self.worker=subprocess.Popen([sys.executable,'-m','backend.compute.worker'],stdout=subprocess.DEVNULL)
        type(self).worker=self.worker
        snapshots=[];observed_order=[];started=time.monotonic();deadline=started+1200
        while time.monotonic()<deadline:
            with database() as db:
                rows=db.execute('SELECT id,state FROM compute_tasks WHERE id=ANY(%s::uuid[]) ORDER BY created_at,id',(ids,)).fetchall()
            running=[str(r['id']) for r in rows if r['state']=='running']
            self.assertLessEqual(len(running),1)
            if running and running[0] not in observed_order:observed_order.append(running[0])
            state={str(r['id']):r['state'] for r in rows}
            if not snapshots or state!=snapshots[-1]['states']:
                snapshots.append(dict(seconds=round(time.monotonic()-started,3),states=state))
            if all(r['state'] in ('succeeded','failed') for r in rows):break
            time.sleep(.1)
        else:self.fail('Five real jobs did not finish within the rehearsal budget')
        self.assertEqual(observed_order,expected_order)
        queue_seconds=time.monotonic()-started
        completed=[];skeleton_hashes=[]
        for i,(client,task) in enumerate(zip(self.clients,submitted)):
            final=client.get('/api/tasks/'+task['id']).json();completed.append(final)
            self.assertEqual(final['state'],'succeeded',final);self.assertFalse(final['is_mock'])
            result=final['result']
            self.assertEqual(result['frame_count'],976)
            self.assertEqual(result['target_body']['height_cm'],dimensions[i][0])
            self.assertFalse(result['quality']['physical_validation'])
            self.assertIn(result['baseline_status'],('failed','not_checked'))
            self.assertEqual(client.get('/api/tasks/'+task['id']+'/artifacts/video',headers={'Range':'bytes=0-31'}).status_code,206)
            self.assertEqual(self.clients[(i+1)%5].get('/api/tasks/'+task['id']).status_code,404)
            notes=client.get('/api/notifications').json()['items']
            self.assertEqual(sum(n['task_id']==task['id'] for n in notes),1)
            skeleton_hashes.append(result['artifacts']['skeleton']['sha256'])
            duplicate=client.post('/api/tasks/generate',json=body(i),headers={'Idempotency-Key':f'phase5-user-{i}'})
            self.assertEqual(duplicate.status_code,200);self.assertEqual(duplicate.json()['id'],task['id'])
        self.assertEqual(len(set(skeleton_hashes)),5)
        second=subprocess.run([sys.executable,'-m','backend.compute.worker','--once'],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(second.returncode,0);self.assertIn('Another compute worker',second.stderr)
        # Leave another real job queued when the running worker is forcibly stopped.
        interrupted=self.submit(self.clients[4],'generate',body(4),'phase5-interrupt')
        waiting=self.submit(self.clients[3],'generate',body(3),'phase5-waiting')
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            path=self.output/'work'/interrupted['id']/'progress.json'
            if path.exists() and json.loads(path.read_text())['stage']=='adapting':break
            time.sleep(.05)
        else:self.fail('Real job did not reach adaptation')
        self.worker.kill();self.worker.wait(timeout=5)
        with (self.output/'.algorithm.lock').open('a') as lock:
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_UN);break
                except BlockingIOError:time.sleep(.1)
            else:self.fail('Orphaned algorithm kept the compute lock')
        self.assertEqual(self.clients[3].get('/api/tasks/'+waiting['id']).json()['state'],'queued')
        subprocess.run([sys.executable,'-m','backend.compute.worker','--once'],check=True,timeout=1800)
        failed=self.clients[4].get('/api/tasks/'+interrupted['id']).json()
        self.assertEqual(failed['error']['code'],'INTERRUPTED')
        self.assertFalse((self.output/'published'/interrupted['id']).exists())
        self.assertEqual(self.clients[3].get('/api/tasks/'+waiting['id']).json()['state'],'succeeded')
        retry=self.clients[4].post('/api/tasks/'+interrupted['id']+'/retry',headers={'Idempotency-Key':'phase5-retry'})
        self.assertEqual(retry.status_code,202);self.assertEqual(retry.json()['attempt'],2)
        subprocess.run([sys.executable,'-m','backend.compute.worker','--once'],check=True,timeout=1800)
        retried=self.clients[4].get('/api/tasks/'+retry.json()['id']).json()
        self.assertEqual(retried['state'],'succeeded')
        notes=self.clients[4].get('/api/notifications').json()['items']
        for task_id in (submitted[4]['id'],interrupted['id'],retried['id']):
            self.assertEqual(sum(n['task_id']==task_id for n in notes),1)
        report=dict(analysis=analysis,generation=completed[0],generations=completed,users=5,
            analysis_seconds=analysis_seconds,queue_seconds=queue_seconds,expected_fifo=expected_order,
            observed_fifo=observed_order,max_running=1,snapshots=snapshots,
            duplicate_worker_rejected=True,interrupted=failed,retried=retried,waiting_task_survived=True)
        (self.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Five-account real rehearsal retained at',self.output,flush=True)

if __name__=='__main__':unittest.main()
