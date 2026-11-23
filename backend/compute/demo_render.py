"""Render existing CIS5810 trajectories only; never fit or compare techniques.

Reads full_sequence_pipeline / trial1_refinement_pipeline trajectory conventions
from Beta_Translator @ ff85726da2fbbd2616c409b01d6c03833ab62ce9.
The top pane is a planar schematic, not a recovered 3D wall/camera.
"""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from .render_video import render
from .prepare_trial2 import digest


def prepare(source, run, destination):
    source, run, destination = Path(source), Path(run), Path(destination)
    summary = json.loads((run / 'summary.json').read_text())
    inputs = summary['provenance']['inputs']
    video_key = next(k for k in inputs if k.startswith('videos/') and k.endswith('.mp4'))
    video = source / video_key
    if digest(video) != inputs[video_key]:
        raise ValueError('Original recording does not match saved provenance')
    for name in ('trajectory.npz', summary['video_name']):
        if digest(run / name) != summary['output_sha256'][name]:
            raise ValueError('Saved output checksum mismatch: ' + name)
    destination.mkdir(parents=True, exist_ok=False)
    with np.load(run / 'trajectory.npz', allow_pickle=False) as data:
        joints = data['joints_cm']; labels = data['decoded_labels']
        known = data['known'] if 'known' in data else data['active']
        trusted = known & (data['supported'] if 'supported' in data else data['in_coverage'])
        if 'contact_type' in data:
            trusted = trusted & (data['contact_type'] == 'hold')
        if not np.array_equal(data['frames'], np.arange(summary['frame_count'])):
            raise ValueError('A full native-frame trajectory is required')
        holds = []
        for label in sorted(set(str(x) for x in labels[trusted])):
            positions = data['targets_cm'][(labels == label) & trusted]
            center = np.median(positions, axis=0) * [1, -1]
            holds.append(dict(id=label, center_px=center.tolist()))
        xyz = np.concatenate([joints * [1, -1], np.ones(joints.shape[:-1] + (1,))], axis=-1)
        scene = dict(camera=dict(R=np.eye(3), K=np.eye(3), t_cm=[0, 0, 0]),
                     assumptions=dict(wall_polygons_px={}))
        render(video, xyz, scene, holds, labels, trusted, destination / 'video.mp4',
               f"Pre-generated {summary['body']['height_cm']:g} cm | 2D schematic, not 3D", lambda *_: None,
               geometry_failed=True)
    cap = cv2.VideoCapture(str(video))
    if int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) != summary['frame_count'] or abs(cap.get(cv2.CAP_PROP_FPS) - 30) > .01:
        raise ValueError('Original/trajectory timeline mismatch')
    cap.set(cv2.CAP_PROP_POS_FRAMES, summary.get('reference_frame', summary['frame_count'] // 2))
    ok, frame = cap.read(); cap.release()
    if not ok:
        raise ValueError('Reference frame unavailable')
    cv2.imwrite(str(destination / 'wall.jpg'), frame)
    (destination / 'summary.json').write_text(json.dumps(summary, indent=2))
    (destination / 'presentation.json').write_text(json.dumps(dict(
        source_video_sha256=digest(video), source_summary_sha256=digest(run/'summary.json'),
        trajectory_sha256=digest(run/'trajectory.npz'), renderer_sha256=digest(Path(__file__)),
        shared_renderer_sha256=digest(Path(__file__).with_name('render_video.py')),
        source_run=str(run.relative_to(source)), source_commit='ff85726da2fbbd2616c409b01d6c03833ab62ce9',
        precomputed=True, scientific_algorithm_rerun=False, coordinate_view='planar_schematic'), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path); parser.add_argument('run', type=Path); parser.add_argument('destination', type=Path)
    args = parser.parse_args(); prepare(args.source, args.run, args.destination)
