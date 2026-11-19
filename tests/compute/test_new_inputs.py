"""New-video real worker acceptance; deliberately no Trial2 fit/optimization."""
import copy
import json
import os
from pathlib import Path
import unittest
from support import database as db_support

@unittest.skipUnless(os.getenv('BETALAB_TEST_INPUTS')=='1','Requires real local models and disposable DB')
class NewInputsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_support.setup_database(cls)
        cls.previous={k:os.environ.get(k) for k in ('UPLOAD_DIR','COMPUTE_STORAGE_DIR')}
        cls.output=Path('backend/compute/runs/new-inputs-acceptance').resolve();cls.output.mkdir(exist_ok=True)
        os.environ['UPLOAD_DIR']=str(cls.videos.UPLOAD_DIR)
        os.environ['COMPUTE_STORAGE_DIR']=str(cls.output)
        cls.video=Path('backend/compute/runs/new-inputs-probe/new-video.mp4')
    @classmethod
    def tearDownClass(cls):
        for k,v in cls.previous.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        db_support.teardown_database(cls)
    def setUp(self):db_support.upload_sample(self)
    def test_real_pipeline_and_review(self):
        from backend.compute.worker import Worker
        os.environ['COMPUTE_MODE']='real'
        response=self.alice.post('/api/tasks/upload-analysis/'+self.video_id)
        self.assertEqual(response.status_code,202,response.text)
        task=response.json();path='/api/tasks/'+task['id']
        with Worker() as worker:self.assertTrue(worker.run_one())
        task=self.alice.get(path).json();self.assertEqual(task['state'],'succeeded',task)
        result=task['result'];self.assertEqual(result['algorithm_version'],'video-inputs-v1')
        summary=self.alice.get(path+'/artifacts/input_summary').json()
        self.assertGreater(summary['hold_count'],0);self.assertEqual(summary['contact_rows'],4*summary['frame_count'])
        self.assertFalse(summary['generation_ready']);self.assertEqual(self.bob.get(path+'/artifacts/pose').status_code,404)
        self.assertEqual(self.bob.get(path+'/input-review').status_code,404)
        self.assertEqual(self.alice.get('/api/tasks/source-analysis/'+self.video_id).status_code,409)
        holds=self.alice.get(path+'/artifacts/holds').json()
        # Synthetic rectangle tests API math/storage ONLY; these are not measured wall holes.
        w,h=summary['width']-1,summary['height']-1
        quad=[[0,0],[w,0],[w,h],[0,h]]
        review=dict(reference_frame=summary['reference_frame'],selected_hold_ids=[holds[0]['hold_id']],
            planes=[dict(id='test-panel',polygon=quad,grid_corners=quad,horizontal_steps=1,vertical_steps=1,
                         note='Synthetic API fixture, not an actual measurement')],notes='TEST ONLY')
        self.assertEqual(self.bob.post(path+'/input-review',json=review).status_code,404)
        saved=self.alice.post(path+'/input-review',json=review)
        self.assertEqual(saved.status_code,200,saved.text)
        saved=saved.json();self.assertFalse(saved['calibrated']['generation_ready'])
        self.assertEqual(self.alice.get(path+'/input-review').json()['version'],saved['version'])
        bad=copy.deepcopy(review);bad['notes']='stale version';self.assertEqual(self.alice.post(path+'/input-review',json=bad).status_code,409)
        bad=copy.deepcopy(review);bad['reference_frame']+=1;self.assertEqual(self.alice.post(path+'/input-review',json=bad).status_code,422)
        bad=copy.deepcopy(review);bad['planes'][0]['grid_corners']=[[0,0]]*4;self.assertEqual(self.alice.post(path+'/input-review',json=bad).status_code,422)
        bad=copy.deepcopy(review);bad['selected_hold_ids']=['missing'];self.assertEqual(self.alice.post(path+'/input-review',json=bad).status_code,422)
        (self.output/'validation.json').write_text(json.dumps(dict(task=task,summary=summary,checks=['real worker','private artifacts','review version','stale conflict','invalid geometry','wrong frame','unknown hold','generation blocked']),indent=2))
        self.assertEqual(self.alice.delete('/api/videos/'+self.video_id).status_code,204)
        self.assertEqual(self.alice.get(path+'/input-review').status_code,404)

    def test_no_person_fails_without_fake_results_and_keeps_upload(self):
        from backend.compute.worker import Worker
        with (Path(self.directory.name)/'sample.mp4').open('rb') as f:
            response=self.alice.post('/api/videos',data=dict(route_id='test-route',visibility='private'),files={'video':('empty.mp4',f,'video/mp4')})
        video_id=response.json()['id'];os.environ['COMPUTE_MODE']='real'
        task=self.alice.post('/api/tasks/upload-analysis/'+video_id).json()
        with Worker() as worker:self.assertTrue(worker.run_one())
        state=self.alice.get('/api/tasks/'+task['id']).json()
        self.assertEqual(state['state'],'failed');self.assertIsNone(state['result'])
        self.assertEqual(self.alice.get('/api/videos/'+video_id+'/content').status_code,200)
        self.assertEqual(self.alice.get('/api/tasks/'+task['id']+'/input-review').status_code,409)
        self.assertEqual(self.alice.get('/api/tasks/'+task['id']+'/artifacts/pose').status_code,409)
