"""Checks the real Trial 2 quick output, not a mock video."""
import unittest,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).parent
class QuickResult(unittest.TestCase):
    def test_real_result(self):
        job=HERE/'jobs/e1fe9be8d8184e868bbc20a74aeebdf5'
        p=json.loads((job/'request.json').read_text())['profile'];d=p['dimensions_cm']
        with np.load(job/'quick_trajectory.npz') as z:
            self.assertEqual(len(z['frames']),46)
            joints=z['joints']
            np.testing.assert_allclose(np.linalg.norm(joints[:,:2,1]-joints[:,:2,0],axis=-1),d['upper_arm'],atol=1e-10)
            np.testing.assert_allclose(np.linalg.norm(joints[:,:2,2]-joints[:,:2,1],axis=-1),d['forearm'],atol=1e-10)
            np.testing.assert_allclose(np.linalg.norm(joints[:,1,0]-joints[:,0,0],axis=-1),d['shoulder_w'],atol=1e-10)
            self.assertTrue(np.isfinite(z['anatomical_q']).all())
            targets=set(str(x) for x in z['labels'][z['known']])
            holds={h['id'] for h in json.loads((HERE/'prepared/holds.json').read_text())}
            self.assertTrue(targets<=holds)
        diag=json.loads((job/'quick_diagnostics.json').read_text())
        self.assertTrue(diag['joint_bounds_pass']);self.assertTrue(diag['coordinate_rate_pass'])
        self.assertFalse(diag['physical_validation'])
if __name__=='__main__':unittest.main()
