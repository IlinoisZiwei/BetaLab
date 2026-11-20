"""Opt-in scientific regressions: source audit and observed-motion fit."""
import os
from pathlib import Path
import sys
import unittest

@unittest.skipUnless(os.getenv('BETALAB_SOURCE_TEST')=='1','Requires the Beta Translator scientific environment')
class SourceReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,os.environ['BETA_TRANSLATOR_ROOT'])
        import numpy as np
        from backend.compute.fit_trial2 import profile_for
        cls.np=np
        cls.profile=profile_for(Path(os.environ['BETA_TRANSLATOR_ROOT']),173,176)

    def fixture(self):
        np=self.np
        from backend.compute.preview_math import geometry
        from beta_translator.body_legs import bounds_and_rates
        lo,hi,_,_=bounds_and_rates()
        q=np.tile((lo+hi)/2,(4,1));q[:,:3]=[0,150,40]
        g=geometry(q,self.profile)
        class Camera:
            def pixels(self,p):return p[...,:2]*2
            def wall_clearance(self,p):return p[...,2]+1000
        scene=Camera()
        e=dict(contacts_cm=g['contact_points'].copy(),trusted=np.ones((4,4),bool),known=np.ones((4,4),bool),
            labels=np.full((4,4),'fixture'),evidence_frames=np.full((4,4),4),ground=np.zeros((4,4),bool),
            confidence=np.ones((4,4)),observed_px=scene.pixels(g['joints']),visibility=np.ones((4,4,3)))
        return q,e,scene

    def test_same_body_adaptation_preserves_fitted_motion_exactly(self):
        from backend.compute.source_fit import adapt_body
        q,e,scene=self.fixture();q[1,0]+=.5
        result,info=adapt_body(q,e,self.profile,self.profile,scene,lambda *a:None)
        self.np.testing.assert_array_equal(result,q)
        self.assertIsNot(result,q)
        self.assertEqual(info['method'],'identical_body_identity')

    def test_changed_body_temporal_fit_keeps_evidence_and_limits(self):
        from backend.compute.source_fit import adapt_body
        from backend.compute.source_diagnostics import evaluate
        from backend.compute.fit_trial2 import profile_for
        q,e,scene=self.fixture();snapshot={k:v.copy() for k,v in e.items()}
        target=profile_for(Path(os.environ['BETA_TRANSLATOR_ROOT']),170,175)
        result,_=adapt_body(q,e,self.profile,target,scene,lambda *a:None,max_iterations=30)
        summary=evaluate(result,e,target,scene)[0]['summary']
        self.assertTrue(summary['wall_contact_check_pass'])
        self.assertTrue(summary['joint_bounds_pass'])
        self.assertTrue(summary['coordinate_rate_pass'])
        self.assertEqual(summary['known_wall_penetration_frames'],0)
        for k,v in snapshot.items():self.np.testing.assert_array_equal(e[k],v)

    def test_identical_motion_passes_only_checked_geometry(self):
        from backend.compute.source_diagnostics import evaluate
        q,e,scene=self.fixture();d,_=evaluate(q,e,self.profile,scene)
        self.assertTrue(d['summary']['contact_check_pass'])
        self.assertFalse(d['summary']['physical_validation'])
        self.assertFalse(d['summary']['collision_validation'])
        e['contacts_cm'][2,1,0]+=20
        d,_=evaluate(q,e,self.profile,scene)
        self.assertEqual(d['summary']['frames_over_5cm'],1)
        self.assertEqual(d['episodes'][1]['peak_frame'],2)
        self.assertAlmostEqual(d['summary']['max_gap_cm'],20)

    def test_unconfirmed_evidence_cannot_become_a_pass(self):
        from backend.compute.source_diagnostics import evaluate
        q,e,scene=self.fixture();e['trusted'][:]=False
        d,_=evaluate(q,e,self.profile,scene)
        self.assertFalse(d['summary']['contact_check_pass'])
        self.assertIsNone(d['summary']['max_gap_cm'])
        self.assertEqual(d['summary']['unconfirmed_samples'],16)

    def test_fit_reduces_known_offset_without_changing_evidence(self):
        from backend.compute.source_fit import fit_source
        from backend.compute.source_diagnostics import evaluate
        q,e,scene=self.fixture();initial=q.copy();initial[:,0]+=4
        snapshot={k:v.copy() for k,v in e.items()}
        before=evaluate(initial,e,self.profile,scene)[0]['summary']['max_gap_cm']
        fitted,info=fit_source(initial,e,self.profile,scene,lambda *a:None,max_nfev=25)
        after=evaluate(fitted,e,self.profile,scene)[0]['summary']['max_gap_cm']
        self.assertLess(after,before/2)
        for k,v in snapshot.items():self.np.testing.assert_array_equal(e[k],v)
        self.assertTrue(info['contact_timing_preserved'])

    def test_user_angles_convert_and_legacy_geometry_is_reproduced(self):
        from backend.compute.calibration import scene_for
        from beta_translator.trial2_scene3d import Trial2Scene
        source=Path(os.environ['BETA_TRANSLATOR_ROOT']);np=self.np
        for middle,upper in [(15,0),(30,15),(45,0)]:
            actual=scene_for(source,middle,upper)
            expected=Trial2Scene(source,middle_deg=middle,upper_deg=upper,spacing_cm=14.3)
            np.testing.assert_allclose(actual.t,expected.t,atol=1e-9)
            np.testing.assert_allclose(actual.origins,expected.origins,atol=1e-9)
        corrected=scene_for(source)
        self.assertEqual(corrected.angles,(62.,20.))
        np.testing.assert_allclose(corrected.C,-corrected.R.T@corrected.t,atol=1e-9)
        self.assertFalse(corrected.spec['all_geometry_measured'])

    def test_ground_is_deferred_without_erasing_raw_labels(self):
        from backend.compute.geometry_scope import wall_contacts
        from backend.compute.source_diagnostics import evaluate
        q,e,scene=self.fixture();e['ground'][:,2]=True;e['contacts_cm'][:,2,0]+=1000
        d,_=evaluate(q,e,self.profile,scene)
        self.assertEqual(d['summary']['deferred_ground_samples'],4)
        self.assertTrue(d['summary']['wall_contact_check_pass'])
        self.assertFalse(d['summary']['contact_check_pass'])
        self.assertFalse(d['summary']['full_geometry_certified'])
        self.assertTrue(e['trusted'][:,2].all())
        self.assertFalse(wall_contacts(e)[:,2].any())

    def test_rate_projection_enforces_existing_limits_without_clipping_time(self):
        from backend.compute.source_fit import project_rates
        from beta_translator.body_legs import bounds_and_rates
        np=self.np;lo,hi,speed,_=bounds_and_rates()
        q=np.tile((lo+hi)/2,(30,1));q[15:,6]+=1
        result,info=project_rates(q)
        self.assertEqual(result.shape,q.shape)
        self.assertTrue(np.all(np.abs(np.diff(result,axis=0))*30<=speed+1e-7))
        self.assertTrue(np.all(result>=lo)&np.all(result<=hi))
        again,_=project_rates(result);np.testing.assert_allclose(again,result,atol=1e-8)

    def test_temporal_solver_decreases_objective_and_respects_boxes(self):
        from backend.compute.trajectory_solver import solve
        np=self.np;target=np.linspace(0,.4,8)[:,None]*np.ones((1,3))
        fitted,info=solve(lambda q:q-target,np.zeros_like(target),np.full(3,-1.),np.ones(3),
            np.full(3,.1),lambda *a:None,iterations=20)
        self.assertLess(info['final_cost'],info['initial_cost']/10)
        self.assertTrue(np.all(np.diff(info['cost_history'])<0))
        self.assertTrue(np.all(abs(fitted)<=1))

    def test_ground_moment_does_not_claim_missing_pose_evidence(self):
        from backend.compute.geometry_scope import diagnostic_moments
        q,e,scene=self.fixture();e['ground'][:,2]=True
        moments=diagnostic_moments(e,self.np.zeros((4,4)))
        self.assertEqual(len(moments),1)
        self.assertEqual(moments[0]['title'],'Ground geometry not verified')
        self.assertEqual(moments[0]['end_frame'],3)

    def test_reach_bound_contains_generated_contact_distances(self):
        from backend.compute.reachability import contact_distance_bounds,spline_range
        from backend.compute.preview_math import geometry
        from beta_translator.body_legs import bounds_and_rates
        np=self.np;lo,hi,_,_=bounds_and_rates()
        q=np.random.default_rng(5120).uniform(lo,hi,(300,32))
        contacts=geometry(q,self.profile)['contact_points']
        distances=np.linalg.norm(contacts[:,:,None]-contacts[:,None,:],axis=-1)
        self.assertTrue(np.all(distances<=contact_distance_bounds(self.profile)+1e-8))
        a,b=spline_range({'x':[0,1,2,3],'y':[0,1,2,3]},-.5,3.5)
        self.assertAlmostEqual(a,-.5);self.assertAlmostEqual(b,3.5)

    def test_inconsistent_contact_pair_is_not_hidden_by_solver(self):
        from backend.compute.reachability import audit_reach
        q,e,scene=self.fixture();e['contacts_cm'][:,0,0]+=1000
        d=audit_reach(e,self.profile)
        self.assertEqual(d['inconsistent_frames'],4)
        self.assertTrue(all(v['unavoidable_max_endpoint_error_cm']>5 for v in d['violations']))

if __name__=='__main__':unittest.main()
