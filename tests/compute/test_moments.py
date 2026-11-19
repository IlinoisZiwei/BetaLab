import unittest
from pydantic import ValidationError
from backend.compute.moments import build_moments
from backend.compute.contracts import Result, Moment

class MomentsTest(unittest.TestCase):
    def test_peak_times_and_unknown_support_are_distinct(self):
        known=[[True,False,False,True]]*4
        trusted=[[True,False,False,False]]*4
        gaps=[[0,0,0,0],[6,0,0,0],[9,0,0,0],[1,0,0,0]]
        result=build_moments(known,trusted,gaps,30)
        self.assertEqual(result[0]['kind'],'unconfirmed_contact')
        self.assertEqual(result[1]['frame'],2)
        self.assertEqual(result[1]['at_seconds'],2/30)
        self.assertEqual(result[1]['gap_cm'],9)
        self.assertEqual(result[1]['end_frame'],2)

    def test_invalid_or_absent_evidence_is_not_a_recommendation(self):
        self.assertEqual(build_moments([[False]*4],[[False]*4],[[float('nan')]*4]),[])
        for moment in build_moments([[True]*4],[[False]*4]):
            self.assertEqual(moment['kind'],'unconfirmed_contact')
            self.assertIsNone(moment['gap_cm'])

    def test_result_rejects_wrong_native_timestamp_and_end_frame(self):
        base=dict(kind='analyze',is_mock=True,algorithm_version='test',source_analysis_version='test',
            calibration_version='test',source_video_id='test',frame_count=4,fps=30,
            quality=dict(evidence='insufficient',geometry_status='assumed'),
            baseline_status='not_requested',technique_status='not_requested')
        m=dict(id='m',kind='unconfirmed_contact',frame=3,end_frame=3,at_seconds=.1,
            limb='left_hand',title='Evidence unavailable',explanation='No recommendation')
        Result(**base,moments=[m])
        for change in ({'at_seconds':.2},{'end_frame':4},{'frame':4},{'at_seconds':float('nan')}):
            with self.assertRaises(ValidationError):
                Result(**base,moments=[{**m,**change}])

if __name__=='__main__':
    unittest.main()
