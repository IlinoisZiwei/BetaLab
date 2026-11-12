"""Prepare video-dependent evidence once, independently of the requesting user."""
import os,sys,json
from pathlib import Path
import numpy as np
ROOT=Path(os.environ.get('BETA_TRANSLATOR_ROOT','/Users/ziwei/Desktop/2026 Fall/CIS 5810/Beta_Translator'));sys.path.insert(0,str(ROOT))
from beta_translator.trials import load_trial
cfg,d,scene,regions,legacy=load_trial(ROOT,'trial2',175)
out=Path(__file__).parent/'prepared';out.mkdir(exist_ok=True)
ix=np.arange(cfg['frame_count'])
source=ROOT/'outputs/trial2/shared_body/target_175cm_0000_0975_3cd414e63797/initialization.npz'
with np.load(source) as z:q=z['q'][ix].copy()
# This is a source-motion initialization, not a validated target trajectory.
contacts=np.zeros((len(ix),4,3));mapping=regions['mapping'][ix]
for t in range(len(ix)):
 for limb in range(4):
  e=int(mapping[t,limb])
  if e>=0:
   ep=regions['episodes'][e];contacts[t,limb]=scene.intersect(np.array(ep['anchor_px']),ep['panel'])
route_ids=sorted(set(e['hold'] for e in regions['episodes'] if e['hold'] in d['records']))
holds=[]
for hid in route_ids:
 r=d['records'][hid];xy=np.array([[r['x_min'],r['y_min']],[r['x_max'],r['y_min']],[r['x_max'],r['y_max']],[r['x_min'],r['y_max']]],float)
 center=np.array([r['cx_px'],r['cy_px']]);panel=int(scene.panel(center))
 holds.append(dict(id=hid,polygon=scene.intersect(xy,panel).tolist(),center=scene.intersect(center,panel).tolist(),review_status=r.get('review_status','unknown')))
evidence_frames=np.zeros(mapping.shape,dtype=int)
for t in range(len(ix)):
 for limb in range(4):
  episode=int(mapping[t,limb])
  if episode>=0:evidence_frames[t,limb]=regions['episodes'][episode]['evidence_frames']
np.savez_compressed(out/'trial2.npz',q=q,contacts=contacts,known=d['known'][ix],labels=d['labels'][ix],frames=ix,confidence=d['confidence'][ix],ground=d['ground'][ix],evidence_frames=evidence_frames)
(out/'contact_review.json').write_text(json.dumps(dict(reviewed_segment=[239,253],limb='right_foot',original_label='H109',decision='unconfirmed_excluded_from_quick_objective',reason='Video shows H109 held by hands above torso; right foot not there. Episode has zero supporting evidence frames. No replacement hold assigned.',canonical_evidence_unchanged=True),indent=2))
(out/'scene.json').write_text(json.dumps(scene.report()))
(out/'holds.json').write_text(json.dumps(holds))
(out/'provenance.json').write_text(json.dumps(dict(source_initialization=str(source),source_height_cm=175,frames=[0,int(ix[-1])],fps=30,notes='Fixed prepared source pose seed; inferred route holds/contact anchors and assumed wall calibration, not expert-verified beta.'),indent=2))
print('Prepared',len(ix),'frames and',len(holds),'route holds')
