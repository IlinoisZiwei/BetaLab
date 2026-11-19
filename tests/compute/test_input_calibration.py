"""Synthetic metric checks, not a claim that any wall was measured."""
import unittest
from backend.compute.input_calibration import transform_points
from types import SimpleNamespace
def CalibrationReview(**data):
    return SimpleNamespace(**{**data, "planes": [SimpleNamespace(**p) for p in data["planes"]]})
try:
    import cv2
except ImportError:
    cv2=None

@unittest.skipUnless(cv2 is not None,'Requires scientific Python OpenCV')
class CalibrationTest(unittest.TestCase):
    def test_known_rectangle_and_ambiguous_membership(self):
        p=dict(id='p',polygon=[[0,0],[100,0],[100,100],[0,100]],grid_corners=[[0,0],[100,0],[100,100],[0,100]],horizontal_steps=2,vertical_steps=3,note='synthetic')
        data=dict(reference_frame=0,selected_hold_ids=['H1'],planes=[p],notes='synthetic')
        summary=dict(reference_frame=0,width=101,height=101)
        holds=[dict(hold_id='H1',cx_px=50,cy_px=50)]
        out=transform_points(CalibrationReview(**data),summary,holds)
        self.assertAlmostEqual(out['holds'][0]['uv_cm'][0],14.3,places=5)
        self.assertAlmostEqual(out['holds'][0]['uv_cm'][1],21.45,places=5)
        self.assertFalse(out['world_3d_aligned']);self.assertFalse(out['generation_ready'])
        data['planes'].append(dict(p,id='overlap'))
        out=transform_points(CalibrationReview(**data),summary,holds)
        self.assertEqual(out['holds'][0]['status'],'unassigned_or_ambiguous')
