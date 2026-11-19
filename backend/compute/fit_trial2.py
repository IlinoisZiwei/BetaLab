"""Independent real Trial2 solver entry, with fresh 14.3 cm initialization.

References: CIS5810 Beta_Translator @ ff85726da2fbbd2616c409b01d6c03833ab62ce9:
body_model.BodyModel, trial2_spatial_data.seed_pose, ik3d.kinematics,
trial2_scene3d.Trial2Scene; profile scaling adapted from BetaLab's earlier
local-server/server.py and Beta_Translator/configs/users/trial_user_175.json.
No old 15 cm optimized skeleton or prepared q is reused. Source observations
and contact schedules still come from the prepared Trial2 dataset, not a new upload.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from .prepare_trial2 import SOURCE_COMMIT, VERSION, digest, write

def profile_for(source, height, span):
    if not all(math.isfinite(v) for v in (height,span)) or not 100<=height<=230 or not 80<=span<=260:
        raise ValueError('Height must be 100–230 cm and arm span 80–260 cm')
    profile = json.loads((source/'configs/users/trial_user_175.json').read_text())
    scale = height/profile['height_cm']
    dimensions = {k:v*scale for k,v in profile['dimensions_cm'].items()}
    arm_scale = (span-dimensions['shoulder_w'])/(2*(dimensions['upper_arm']+dimensions['forearm']+dimensions['hand_length']))
    for key in ('upper_arm','forearm','hand_length','hand_patch_distance','hand_patch_depth'):
        dimensions[key] *= arm_scale
    profile.update(height_cm=height,arm_span_cm=span,dimensions_cm=dimensions,user_id='betalab_target')
    profile['biomechanics']['capsule_radii_cm'] = [v*scale for v in profile['biomechanics']['capsule_radii_cm']]
    profile['evidence'].update(height='user_input',arm_span='user_input',geometry='Template proportions; not a measured full-body scan')
    return profile

def fit(source, out, height, span, frames, iterations, render=False):
    import numpy as np
    source, out = source.resolve(), out.resolve()
    if out.exists():
        raise ValueError('Use a new output directory; incomplete/old runs remain inspectable')
    commit = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if commit != SOURCE_COMMIT:
        raise ValueError('Review source version before changing the pinned commit')
    profile = profile_for(source,height,span)
    sys.path.insert(0,str(source))
    from beta_translator.body_model import BodyModel
    from beta_translator.body_user import body_lengths
    from beta_translator.trial2_scene3d import Trial2Scene
    from beta_translator.trial2_spatial_data import load_trial2, seed_pose
    from beta_translator.ik3d import kinematics
    out.mkdir(parents=True)
    project = out/'project'
    project.mkdir()
    shutil.copytree(source/'data',project/'data')
    shutil.copytree(source/'configs',project/'configs')
    for name in ('outputs','videos','beta_translator'):
        (project/name).symlink_to(source/name,target_is_directory=True)
    spec_path = project/'data/trial2_spatial_hypotheses.json'
    spec = json.loads(spec_path.read_text())
    spec.update(hole_spacing_cm=14.3,spacing_status='User-confirmed adjacent hole centers',
                grid_status='User-confirmed equal horizontal and vertical spacing')
    write(spec_path,spec)
    cfg = json.loads((project/'configs/trials/trial2.json').read_text())
    cfg['scene']['spacing_cm'] = 14.3
    cfg['baseline'] = 'data/betalab_observation_seed.npz'
    write(project/'configs/trials/trial2.json',cfg)
    data = load_trial2(project)
    scene = Trial2Scene(project,**cfg['scene'])
    # Reconstruct an initializer from original pixel observations in the NEW scene.
    # It is a starting estimate, not a measured or feasible source skeleton.
    seed = seed_pose(data,scene,height)
    joints,_,_ = kinematics(seed,body_lengths(profile))
    np.savez_compressed(project/cfg['baseline'],joints=joints,values=seed)
    write(out/'adapter-provenance.json',dict(source_commit=commit,calibration_version=VERSION,
        adapter_sha256=digest(Path(__file__)),height_cm=height,arm_span_cm=span,
        initialization='Fresh original-pixel seed in 14.3 cm scene; no saved optimized q',
        preserve_contact_order=True,preserve_contact_timing=True,techniques='not yet ported',
        geometry_status='assumed',physical_validation=False))
    result = BodyModel(user_profile=profile).fit('trial2',project=project,frames=frames,
        iterations=iterations,candidates=('steady',),output_root=out/'fit',render=render)
    write(out/'result.json',result)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--height',type=float,required=True)
    parser.add_argument('--arm-span',type=float,required=True)
    interval = parser.add_mutually_exclusive_group()
    interval.add_argument('--frames',nargs=2,type=int,default=[550,552])
    interval.add_argument('--all',action='store_true')
    parser.add_argument('--iterations',type=int,default=15)
    parser.add_argument('--render',action='store_true')
    args = parser.parse_args()
    if args.iterations<1:
        parser.error('iterations must be positive')
    result = fit(args.source,args.out,args.height,args.arm_span,'all' if args.all else args.frames,args.iterations,args.render)
    print(json.dumps(dict(output=result['output_dir'],selection_status=result['selection_status'],
                          physical_validation=result['physical_validation'],seconds=result['seconds'])))

if __name__ == '__main__':
    main()
