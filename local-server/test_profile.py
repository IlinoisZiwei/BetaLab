import unittest
from server import profile_for
class ProfileTest(unittest.TestCase):
    def test_span_and_height_are_independent(self):
        a=profile_for(168,170);b=profile_for(168,180)
        for p in (a,b):
            d=p['dimensions_cm'];self.assertAlmostEqual(d['shoulder_w']+2*(d['upper_arm']+d['forearm']+d['hand_length']),p['arm_span_cm'])
        self.assertEqual(a['dimensions_cm']['thigh'],b['dimensions_cm']['thigh'])
        self.assertGreater(b['dimensions_cm']['upper_arm'],a['dimensions_cm']['upper_arm'])
        self.assertEqual(a['evidence']['arm_span'],'user_input')
    def test_bad_measurements(self):
        for h,s in [(0,170),(168,float('nan')),(168,float('inf')),(240,170)]:
            with self.assertRaises(ValueError):profile_for(h,s)
if __name__=='__main__':unittest.main()
