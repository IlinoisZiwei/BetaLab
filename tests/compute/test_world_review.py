"""Real HTTP/DB/scientific boundary with synthetic known-truth geometry."""
import copy
import os
from pathlib import Path
import unittest
from support import database as support

@unittest.skipUnless(os.getenv('BETALAB_WORLD_TEST')=='1','Requires explicit scientific API opt-in')
class WorldReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.setup_database(cls)
        cls.old_storage = os.environ.get('COMPUTE_STORAGE_DIR')
        os.environ['COMPUTE_STORAGE_DIR'] = str(Path(cls.directory.name)/'compute')
    @classmethod
    def tearDownClass(cls):
        if cls.old_storage is None: os.environ.pop('COMPUTE_STORAGE_DIR',None)
        else: os.environ['COMPUTE_STORAGE_DIR'] = cls.old_storage
        support.teardown_database(cls)
    def setUp(self):
        from support.world_api import prepare
        support.upload_sample(self)
        task,self.review = prepare(self.alice,self.video_id,os.environ['COMPUTE_STORAGE_DIR'])
        self.task_id = task['id'];self.path = '/api/tasks/'+task['id']+'/world-review'

    def test_save_versions_export_access_and_conflicts(self):
        self.assertIsNone(self.alice.get(self.path).json()['version'])
        self.assertEqual(self.bob.post(self.path,json=self.review).status_code,404)
        self.assertEqual(self.alice.post(self.path,json=self.review,headers={'x-csrf-token':'wrong'}).status_code,403)
        response = self.alice.post(self.path,json=self.review)
        self.assertEqual(response.status_code,200,response.text)
        first = response.json()['version']
        self.assertEqual(response.json()['summary']['camera_aligned_frames'],4)
        self.assertEqual(self.alice.post(self.path,json=self.review).json()['version'],first)
        changed = copy.deepcopy(self.review);changed['notes'] = 'Another synthetic observation'
        self.assertEqual(self.alice.post(self.path,json=changed).status_code,409)
        changed['base_version'] = first
        second = self.alice.post(self.path,json=changed)
        self.assertEqual(second.status_code,200,second.text)
        self.assertNotEqual(second.json()['version'],first)
        self.assertEqual(self.alice.get(self.path,params={'version':first}).json()['version'],first)
        export = self.alice.get(self.path+'/export',params={'version':first})
        self.assertEqual(export.status_code,200,export.text)
        aligned = export.json()['aligned']
        self.assertEqual(len(aligned['pose_rays']),4)
        self.assertIsNone(aligned['pose_rays'][0]['joint_xyz_cm'])
        self.assertFalse(aligned['summary']['generation_ready'])
        self.assertEqual(self.bob.get(self.path+'/export',params={'version':first}).status_code,404)
        self.assertEqual(self.alice.get(self.path+'/export').status_code,422)
        self.alice.delete('/api/videos/'+self.video_id)
        self.assertEqual(self.alice.get(self.path).status_code,404)

    def test_bad_missing_and_tampered_inputs(self):
        for change in [
            {'measurements_confirmed':False},
            {'calibration_version':'f'*64},
            {'intrinsics':{**self.review['intrinsics'],'width':1080}},
        ]:
            response = self.alice.post(self.path,json={**self.review,**change})
            self.assertIn(response.status_code,(409,422),response.text)
        saved = self.alice.post(self.path,json=self.review).json()
        from backend.compute import storage
        pose = storage.root()/'published'/self.task_id/'pose.npz'
        pose.write_bytes(b'changed')
        self.assertEqual(self.alice.get(self.path,params={'version':saved['version']}).status_code,409)
