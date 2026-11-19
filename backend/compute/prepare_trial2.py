"""Rebuild Trial2 metric contact evidence at 14.3 cm without altering CIS5810.

Reference: CIS5810/Beta_Translator @ ff85726da2fbbd2616c409b01d6c03833ab62ce9,
beta_translator/trials.py, trial2_scene3d.py, body_regions.py, and
BetaLab local-server/prepare_quick.py. Calls the original calibrated scene
and episode projection; does not copy a saved 15 cm skeleton as a new result.
Run with Beta_Translator's Python 3.12 environment. No inference/solve occurs.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = 'trial2-grid143-v1'
SOURCE_COMMIT = 'ff85726da2fbbd2616c409b01d6c03833ab62ce9'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

def prepare(source, out):
    import numpy as np
    source, out = source.resolve(), out.resolve()
    if out.exists():
        raise ValueError('Use a new output directory; old calibration artifacts are never overwritten')
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != SOURCE_COMMIT:
        raise ValueError('Source commit changed; review compatibility before changing the pin')
    cfg = json.loads((source/'configs/trials/trial2.json').read_text())
    evidence = source/cfg['input_root']
    files = [source/cfg['video'], source/cfg['baseline'], source/'configs/trials/trial2.json',
             source/'configs/users/trial_user_175.json', source/'requirements.txt', evidence/'automatic/wholebody.npz']
    for folder in ('state', 'tables', 'automatic/predictions'):
        files.extend(p for p in (evidence/folder).iterdir() if p.is_file())
    files.extend((source/'data').glob('*.json'))
    files.extend((source/'beta_translator').glob('*.py'))
    hashes = {str(p.relative_to(source)): digest(p) for p in sorted(set(files))}
    sys.path.insert(0, str(source))
    from beta_translator.trials import load_trial
    # The source's pixels, masks, native timeline and labels remain read-only.
    # Only calibration JSON is copied and changed in this temporary view.
    with tempfile.TemporaryDirectory(prefix='betalab-calibration-') as temporary:
        project = Path(temporary)
        shutil.copytree(source/'data', project/'data')
        for folder in ('outputs', 'videos'):
            (project/folder).symlink_to(source/folder, target_is_directory=True)
        spec_path = project/'data/trial2_spatial_hypotheses.json'
        spec = json.loads(spec_path.read_text())
        spec['hole_spacing_cm'] = 14.3
        spec['spacing_status'] = 'User-confirmed adjacent hole center spacing'
        spec['grid_status'] = 'User-confirmed equal horizontal and vertical spacing'
        spec['spacing_evidence'] = 'User confirmed adjacent hole center spacing on both grid axes'
        write(spec_path, spec)
        cfg['scene']['spacing_cm'] = 14.3
        _, data, scene, regions, _ = load_trial(project, cfg, 175.)
        mapping = regions['mapping']
        contacts = np.full((*mapping.shape, 3), np.nan)
        evidence_frames = np.zeros(mapping.shape, dtype=int)
        for t, limb in np.ndindex(mapping.shape):
            if mapping[t, limb] >= 0:
                episode = regions['episodes'][int(mapping[t, limb])]
                contacts[t, limb] = scene.intersect(np.array(episode['anchor_px']), episode['panel'])
                evidence_frames[t, limb] = episode['evidence_frames']
        trusted = data['known'] & (evidence_frames > 0)
        holds = []
        for hid, record in data['records'].items():
            xy = np.array([record['cx_px'], record['cy_px']])
            panel = int(scene.panel(xy))
            holds.append(dict(id=hid, center_px=xy.tolist(), panel=panel,
                              center_cm=scene.intersect(xy, panel).tolist(),
                              review_status=record.get('review_status', 'unknown')))
        scene_report = scene.report()
    # Reject any concurrent modification of the evidence before publishing.
    if any(digest(source/name) != value for name, value in hashes.items()):
        raise RuntimeError('Source evidence changed while preparing')
    identity = dict(calibration_version=VERSION, grid_spacing_cm=14.3,
                    source_commit=commit, input_sha256=hashes, adapter_sha256=digest(Path(__file__)))
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    # Stage directory is promoted only after every artifact has been written.
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent, prefix='.trial2-stage-') as temporary:
        staging = Path(temporary)/'complete'
        staging.mkdir()
        np.savez_compressed(staging/'evidence.npz', contacts_cm=contacts,
            trusted=trusted, known=data['known'], evidence_frames=evidence_frames,
            labels=data['labels'], frames=data['frames'], confidence=data['confidence'],
            ground=data['ground'], observed_px=data['observed_px'], visibility=data['visibility'])
        write(staging/'scene.json', scene_report)
        write(staging/'holds.json', holds)
        write(staging/'trial-config.json', cfg)
        write(staging/'wall-evidence.json', spec)
        write(staging/'provenance.json', dict(**identity, cache_key=key,
              is_mock=False, artifact_kind='calibrated_evidence_only',
              skeleton_regenerated=False, physical_validation=False,
              frame_count=len(data['frames']), fps=float(data['fps']),
              source_body_status='unverified: loader assumes 173 cm; template uses 175 cm',
              geometry_status='assumed',
              warnings=['Angles, camera intrinsics, panel boundaries and floor remain assumptions.',
                        'Existing 15 cm fitted trajectories and quick caches are incompatible.',
                        'Zero-evidence contact proposals are retained as labels but not trusted.']))
        environment = dict(python=platform.python_version(), machine=platform.machine(),
            system=platform.system(), free_disk_gib=round(shutil.disk_usage(out.parent).free/2**30, 2),
            packages={name: importlib.metadata.version(name) for name in
                      ('numpy', 'scipy', 'pandas', 'matplotlib', 'opencv-python')},
            ffmpeg_available=bool(shutil.which('ffmpeg')), ffprobe_available=bool(shutil.which('ffprobe')))
        write(staging/'environment.json', environment)
        write(staging/'artifact-sha256.json', {p.name: digest(p) for p in sorted(staging.iterdir())})
        staging.rename(out)
    print(json.dumps(dict(output=str(out), cache_key=key, frames=len(data['frames']),
                          holds=len(holds), trusted_contacts=int(trusted.sum()), skeleton_regenerated=False)))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.out)
