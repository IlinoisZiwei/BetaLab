"""Opt-in full-recording integration; keeps generated artifacts in ignored runs/."""
import json
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from uuid import uuid4
from support import database as db_support

@unittest.skipUnless(os.getenv('BETALAB_REAL_TEST')=='1', 'Requires explicit real Trial2 integration opt-in')
class RealPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_support.setup_database(cls)
        cls.old_upload_env=os.environ.get('UPLOAD_DIR')
        cls.old_storage=os.environ.get('COMPUTE_STORAGE_DIR')
        os.environ['UPLOAD_DIR']=str(cls.videos.UPLOAD_DIR)
        cls.output=Path('backend/compute/runs')/('phase3-real-'+uuid4().hex[:8])
        cls.output.mkdir(parents=True)
        os.environ['COMPUTE_STORAGE_DIR']=str(cls.output.resolve())
        os.environ['COMPUTE_MODE']='real'
        from backend.database import database
        with database() as db:
            db.execute("INSERT INTO routes(id,gym_id,name,grade) VALUES ('r1','test-gym','Trial2','V0') ON CONFLICT DO NOTHING")

    @classmethod
    def tearDownClass(cls):
        for key,old in [('UPLOAD_DIR',cls.old_upload_env),('COMPUTE_STORAGE_DIR',cls.old_storage)]:
            if old is None:
                os.environ.pop(key,None)
            else:
                os.environ[key]=old
        db_support.teardown_database(cls)

    def worker(self, task, client):
        started=time.monotonic()
        subprocess.run([sys.executable,'-m','backend.compute.worker','--once'],check=True,timeout=1800)
        response=client.get('/api/tasks/'+task['id'])
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual(result['state'],'succeeded',json.dumps(result))
        self.assertFalse(result['is_mock'])
        return result,time.monotonic()-started

    def test_full_recording_analysis_generation_and_protected_playback(self):
        original=Path(os.environ['BETA_TRANSLATOR_ROOT'])/'videos/trial2.mp4'
        with original.open('rb') as stream:
            uploaded=self.alice.post('/api/videos',data=dict(route_id='r1',visibility='public'),files={'video':('trial2.mp4',stream,'video/mp4')})
        self.assertEqual(uploaded.status_code,201,uploaded.text)
        video_id=uploaded.json()['id']
        body=dict(kind='analyze',video_id=video_id,route_id='r1',calibration=dict(version='trial2-grid143-v2',reference_frame=450,evidence_key='calibration/trial2-grid143-v2'))
        response=self.alice.post('/api/tasks/analyze',json=body,headers={'Idempotency-Key':'real-source'})
        self.assertEqual(response.status_code,202,response.text)
        analysis,analysis_seconds=self.worker(response.json(),self.alice)
        source=analysis['result']
        self.assertEqual(source['frame_count'],976)
        self.assertEqual(source['original_body']['provenance'],'estimated')
        self.assertEqual(source['quality']['check_scope'],'geometry_only')
        self.assertIn(source['baseline_status'],('failed','not_checked'))
        audit=json.loads((self.output/source['artifacts']['source_audit']['storage_key']).read_text())
        self.assertIn('inconsistent_frames',audit['necessary_reach_check'])
        self.assertEqual(source['calibration_version'],'trial2-grid143-v2')
        self.assertLess(audit['after']['summary']['wall_max_gap_cm'],audit['before']['summary']['wall_max_gap_cm'])
        self.assertTrue(audit['solver']['contact_timing_preserved'])
        self.assertEqual(audit['after']['summary']['deferred_ground_samples'],78)
        self.assertEqual(audit['wall_reach_check']['inconsistent_frames'],0)
        self.assertTrue(audit['after']['summary']['coordinate_rate_pass'])
        reference=self.bob.get('/api/tasks/source-analysis/'+video_id).json()
        generation=dict(kind='generate',video_id=video_id,source_analysis_id=reference['source_analysis_id'],
            source_analysis_version=reference['source_analysis_version'],target_body=dict(height_cm=170,arm_span_cm=175,provenance='user_input'),compare_techniques=True)
        submitted=self.bob.post('/api/tasks/generate',json=generation,headers={'Idempotency-Key':'real-target'})
        self.assertEqual(submitted.status_code,202,submitted.text)
        self.assertEqual(self.bob.post('/api/tasks/generate',json=generation,headers={'Idempotency-Key':'real-target'}).status_code,200)
        generated,generation_seconds=self.worker(submitted.json(),self.bob)
        result=generated['result']
        self.assertIn(result['baseline_status'],('failed','not_checked'))
        if result['baseline_status']=='failed':
            self.assertTrue(any('Geometry check failed' in warning for warning in result['quality']['warnings']))
        self.assertEqual(result['technique_status'],'blocked')
        self.assertFalse(result['quality']['physical_validation'])
        self.assertEqual(result['target_body']['height_cm'],170)
        self.assertEqual(result['source_analysis_version'],source['source_analysis_version'])
        base='/api/tasks/'+generated['id']+'/artifacts/'
        self.assertEqual(self.alice.get(base+'video').status_code,404)
        from starlette.testclient import TestClient
        with TestClient(self.api.app) as anonymous:
            self.assertEqual(anonymous.get(base+'video').status_code,401)
        content=self.bob.get(base+'video')
        self.assertEqual(content.status_code,200)
        self.assertEqual(content.headers['content-type'],'video/mp4')
        first=self.bob.get(base+'video',headers={'Range':'bytes=0-31'})
        self.assertEqual(first.status_code,206)
        self.assertEqual(first.content,content.content[:32])
        suffix=self.bob.get(base+'video',headers={'Range':'bytes=-32'})
        self.assertEqual(suffix.content,content.content[-32:])
        for header in ('bytes=-0','bytes=-','bytes=999999999-','bytes=0-2,4-6','bytes=40-20'):
            self.assertEqual(self.bob.get(base+'video',headers={'Range':header}).status_code,416)
        self.assertEqual(self.bob.get(base+'worker.log').status_code,404)
        notes=self.bob.get('/api/notifications').json()
        self.assertEqual(notes['unread_count'],1)
        self.assertFalse(notes['items'][0]['is_mock'])
        self.bob.patch('/api/notifications/'+notes['items'][0]['id']+'/read')
        self.assertEqual(self.bob.get('/api/notifications').json()['unread_count'],0)
        # A corrupted artifact must not be streamed. Restore it after checking.
        path=self.output/result['artifacts']['diagnostics']['storage_key']
        saved=path.read_bytes()
        path.write_bytes(saved+b' ')
        self.assertEqual(self.bob.get(base+'diagnostics').status_code,409)
        path.write_bytes(saved)
        self.alice.patch('/api/videos/'+video_id,json={'visibility':'private'})
        self.assertEqual(self.bob.get(base+'video').status_code,404)
        self.assertEqual(self.bob.get('/api/tasks/'+generated['id']+'/result').status_code,404)
        self.alice.patch('/api/videos/'+video_id,json={'visibility':'public'})
        self.assertEqual(self.bob.get(base+'poster').status_code,200)
        # Kill a REAL scientific job's parent; its watchdog must release the compute lock.
        interrupted=self.alice.post('/api/tasks/analyze',json=body,headers={'Idempotency-Key':'real-interrupt'}).json()
        parent=subprocess.Popen([sys.executable,'-m','backend.compute.worker','--once'],stdout=subprocess.DEVNULL)
        work=self.output/'work'/interrupted['id']
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if (work/'progress.json').exists():
                    break
                time.sleep(.1)
            else:
                self.fail('Real scientific process did not report progress')
            self.assertEqual(self.alice.get('/api/tasks/'+interrupted['id']+'/artifacts/video').status_code,409)
            parent.kill()
            parent.wait(timeout=5)
            released=False
            with (self.output/'.algorithm.lock').open('a') as lock:
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    try:
                        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        released=True
                        fcntl.flock(lock,fcntl.LOCK_UN)
                        break
                    except BlockingIOError:
                        time.sleep(.1)
            self.assertTrue(released,'Orphaned scientific process still holds compute lock')
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=5)
        subprocess.run([sys.executable,'-m','backend.compute.worker','--once'],check=True,stdout=subprocess.DEVNULL)
        self.assertEqual(self.alice.get('/api/tasks/'+interrupted['id']).json()['error']['code'],'INTERRUPTED')
        self.assertFalse((self.output/'published'/interrupted['id']).exists())
        # Unrelated uploads must not accidentally inherit Trial2 masks/calibration.
        with self.video.open('rb') as stream:
            other=self.alice.post('/api/videos',data=dict(route_id='r1',visibility='public'),
                files={'video':('other.mp4',stream,'video/mp4')}).json()
        rejected=self.alice.post('/api/tasks/analyze',json={**body,'video_id':other['id']},headers={'Idempotency-Key':'unrelated'})
        self.assertEqual(rejected.status_code,422,rejected.text)
        self.alice.delete('/api/videos/'+video_id)
        self.assertEqual(self.bob.get(base+'video').status_code,404)
        report=dict(analysis=analysis,generation=generated,analysis_seconds=analysis_seconds,generation_seconds=generation_seconds)
        (self.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'Real artifacts and timings retained at {self.output}',flush=True)

if __name__=='__main__':
    unittest.main()
