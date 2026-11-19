"""Scientific known-truth acceptance, independent of Trial2."""
import copy
import unittest
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

@unittest.skipUnless(cv2 is not None,'Requires scientific Python OpenCV')
class WorldGeometryTest(unittest.TestCase):
    def setUp(self):
        from support.world_fixture import fixture
        self.data = fixture()

    def align(self):
        from backend.compute.world_geometry import align
        d = self.data
        return align(*(d[k] for k in ['review','calibration','summary','contacts','pose','identity','alignment']))

    def test_join_camera_hold_ray_and_contact_agree(self):
        out = self.align()
        self.assertLess(out['seams'][0]['seam_gap_cm'],1e-8)
        np.testing.assert_allclose(out['cameras'][0]['center_cm'] if 0 in out['cameras'] else out['cameras']['0']['center_cm'],self.data['center'],atol=1e-3)
        np.testing.assert_allclose(out['holds'][0]['xyz_cm'],[40,-50,0],atol=1e-3)
        ray = np.array(out['pose_rays'][0]['directions'][0])
        expected = self.data['point']-self.data['center'];expected /= np.linalg.norm(expected)
        np.testing.assert_allclose(ray,expected,atol=1e-6)
        self.assertIsNone(out['pose_rays'][0]['joint_xyz_cm'])
        self.assertTrue(all(d is None for d in out['pose_rays'][2]['directions']))
        self.assertEqual(out['contacts'][0]['target_xyz_cm'],out['holds'][0]['xyz_cm'])
        self.assertFalse(out['summary']['generation_ready'])

    def test_handheld_does_not_reuse_reference_camera(self):
        self.data['review']['fixed_camera_confirmed'] = False
        out = self.align()
        self.assertEqual(out['summary']['missing_camera_frames'],[1,2,3])
        self.assertIsNone(out['pose_rays'][1]['origin_cm'])
        controls = copy.deepcopy(self.data['review']['cameras'][0])
        controls['frame'] = 1
        for o in controls['observations']:
            o['pixel'] = self.data['project']([self.data['xyz'](o['plane_id'],o['uv_cm'])],offset=10)[0].tolist()
        self.data['review']['cameras'].append(controls)
        out = self.align()
        np.testing.assert_allclose(out['cameras']['1']['center_cm'],self.data['center']+[10,0,0],atol=1e-3)
        self.assertEqual(out['summary']['camera_aligned_frames'],2)

    def test_motion_invalidates_fixed_camera_reuse(self):
        self.data['alignment']['matrices'][1,0,2] = 10
        self.assertIn(1,self.align()['summary']['missing_camera_frames'])

    def test_bad_geometry_intrinsics_and_check_points_rejected(self):
        original = copy.deepcopy(self.data)
        edits = [
            lambda d: d['review']['joins'][0].update(fold_deg=0),
            lambda d: d['review']['joins'][0].update(child='a'),
            lambda d: d['review']['joins'][0].update(child_edge_cm=[[0,0],[0,80]]),
            lambda d: d['review']['intrinsics'].update(width=1080),
            lambda d: d['review']['cameras'][0]['observations'][-1].update(pixel=[10,10]),
            lambda d: d['contacts']['frames'][0].update(hold_id='missing'),
            lambda d: d['calibration']['review'].update(identity_confirmed=False),
        ]
        for edit in edits:
            self.data = copy.deepcopy(original);edit(self.data)
            with self.assertRaises(ValueError): self.align()
