"""Run the existing CIS 5810 solver; never mutate its source or saved runs."""
import os,sys,json,subprocess
from pathlib import Path
ROOT=Path(os.environ['BETA_TRANSLATOR_ROOT']); sys.path.insert(0,str(ROOT))
import numpy as np
from beta_translator.body_model import BodyModel
from render_preview import render
import matplotlib.pyplot as plt
import cv2
job=Path(sys.argv[1]); request=json.loads((job/'request.json').read_text())
def status(stage,message,**extra):
    data=json.loads((job/'status.json').read_text())
    data.update(detail_state=stage,detail_message=message)
    if stage=='ready':
        extra['detailed_video_url']=extra.pop('video_url')
        extra['detailed_quality']=extra.pop('quality')
        extra['detailed_seconds']=extra.pop('seconds')
        extra.pop('height_cm',None);extra.pop('arm_span_cm',None)
    data.update(extra)
    tmp=job/'detail-status.tmp';tmp.write_text(json.dumps(data));tmp.replace(job/'status.json')
try:
    status('fitting','Fitting Trial 2 · full video · 976 frames. Detailed analysis may take over an hour.')
    result=BodyModel(user_profile=request['profile']).fit('trial2',project=ROOT,frames='all',iterations=15,candidates=('steady',),output_root=job/'runs',render=False)
    status('rendering','Rendering your skeleton preview')
    out=Path(result['output_dir']); candidate=result['selected_candidate']
    with np.load(out/candidate/'trajectory.npz',allow_pickle=False) as z: fit={k:z[k] for k in z.files}
    fit['shoe_width_cm']=request['profile']['dimensions_cm']['foot_width']
    scene=json.loads((out/'scene.json').read_text())
    holds=json.loads((Path(__file__).parent/'prepared/holds.json').read_text())
    render(fit,scene,holds,job/'preview.mp4')
    solver=json.loads((out/candidate/'summary.json').read_text())['solver']
    status('ready','Preview generated · diagnostic result, not validated climbing advice.',video_url=f'/api/skeleton-jobs/{job.name}/preview.mp4',height_cm=request['height_cm'],arm_span_cm=request['arm_span_cm'],source_id='trial2',first_frame=result['first_frame'],last_frame=result['last_frame'],fps=30,quality=result['selection_status'],physical_validation=result['physical_validation'],solver_converged=solver.get('success',solver.get('converged',False)),seconds=result['seconds'])
except Exception as e:
    import traceback;traceback.print_exc();status('failed','Generation failed. Retry or inspect the local worker log.',error=str(e));sys.exit(1)
