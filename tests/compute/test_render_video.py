"""Presentation-only regression; no Trial2 fitting or technique comparison."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec('cv2'), 'Requires scientific Python/OpenCV')
class StackedPreviewTest(unittest.TestCase):
    def test_full_width_order_and_only_supported_contact_holds(self):
        import cv2
        import numpy as np
        from backend.compute.render_video import render, focus_transform

        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'original.mp4'
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 30, (960, 540))
            for _ in range(2):
                writer.write(np.full((540, 960, 3), (220, 30, 30), np.uint8))
            writer.release()
            joints = np.ones((2, 4, 3, 3))
            joints[..., :2] = 800
            labels = np.array([['used', 'untrusted', '', '']] * 2)
            trusted = np.array([[True, False, False, False]] * 2)
            holds = [{'id': name, 'center_px': [x, 200]} for name, x in
                     [('used', 200), ('untrusted', 400), ('unused', 600)]]
            scene = {'camera': {'R': np.eye(3), 'K': np.eye(3), 't_cm': [0, 0, 0]},
                     'assumptions': {'wall_polygons_px': {}}}
            output = folder / 'stacked.mp4'
            probe = render(source, joints, scene, holds, labels, trusted, output,
                           'Personal skeleton', lambda *_: None, geometry_failed=True)
            self.assertEqual(int(probe['streams'][0]['nb_read_frames']), 2)
            poster = cv2.imread(str(output.with_suffix('.png')))
            self.assertEqual(poster.shape, (1180, 960, 3))
            # Supported hold appears in top panel; other candidates remain blank.
            origin, scale = focus_transform(joints[..., :2], holds[:1])
            self.assertGreater(scale, .5)
            for hold, color in zip(holds, ([40, 140, 240], [245]*3, [245]*3)):
                x, y = ((np.asarray(hold['center_px']) - origin) * scale).astype(int)
                np.testing.assert_array_equal(poster[y + 35, x], color)
            projected = (joints[..., :2] - origin) * scale
            self.assertTrue((projected >= 0).all())
            self.assertTrue((projected <= [960, 540]).all())
            # The original occupies the bottom panel at the same full width.
            self.assertGreater(int(poster[800, 800, 0]), 200)
            self.assertLess(int(poster[800, 800, 1]), 50)
            np.testing.assert_array_equal(labels[0], ['used', 'untrusted', '', ''])
