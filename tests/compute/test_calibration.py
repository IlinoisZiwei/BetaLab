"""Optional real-data tests: run using CIS5810 Python and BETA_TRANSLATOR_ROOT."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[2]
SOURCE = os.environ.get('BETA_TRANSLATOR_ROOT')
OUT = Path(os.environ.get('BETA_CALIBRATION_OUTPUT', str(REPO/'backend/compute/runs/trial2-grid143-v1')))

@unittest.skipUnless(SOURCE and OUT.exists(), 'Requires explicit CIS5810 source and prepared output')
class CalibrationTest(unittest.TestCase):
    def test_real_projection_and_provenance(self):
        import numpy as np
        source = Path(SOURCE)
        sys.path.insert(0, str(source))
        from beta_translator.trial2_scene3d import Trial2Scene
        old = Trial2Scene(source, middle_deg=15, upper_deg=0, spacing_cm=15)
        holds = json.loads((OUT/'holds.json').read_text())
        delta = []
        for hold in holds:
            old_position = old.intersect(np.array(hold['center_px']), hold['panel'])
            delta.append(np.max(np.abs(np.array(hold['center_cm']) - old_position * (14.3/15))))
        self.assertLess(max(delta), .05)  # cm, small numerical camera fitting differences only
        config = json.loads((OUT/'trial-config.json').read_text())
        self.assertEqual(config['scene']['spacing_cm'], 14.3)
        self.assertEqual(json.loads((source/'configs/trials/trial2.json').read_text())['scene']['spacing_cm'], 15)
        spec = json.loads((OUT/'wall-evidence.json').read_text())
        self.assertEqual(spec['hole_spacing_cm'], 14.3)
        self.assertFalse(spec['all_geometry_measured'])
        with np.load(OUT/'evidence.npz', allow_pickle=False) as data:
            np.testing.assert_array_equal(data['frames'], np.arange(976))
            self.assertEqual(data['contacts_cm'].shape, (976, 4, 3))
            self.assertTrue(np.isfinite(data['contacts_cm'][data['trusted']]).all())
            self.assertFalse(data['trusted'][data['evidence_frames'] == 0].any())
        provenance = json.loads((OUT/'provenance.json').read_text())
        self.assertFalse(provenance['skeleton_regenerated'])
        identity = {k: provenance[k] for k in ('calibration_version', 'grid_spacing_cm', 'source_commit', 'input_sha256', 'adapter_sha256')}
        self.assertEqual(hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(), provenance['cache_key'])
        identity['grid_spacing_cm'] = 15
        self.assertNotEqual(hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(), provenance['cache_key'])
        for name, digest in json.loads((OUT/'artifact-sha256.json').read_text()).items():
            self.assertEqual(hashlib.sha256((OUT/name).read_bytes()).hexdigest(), digest)

if __name__ == '__main__':
    unittest.main()
