import json,sys
from pathlib import Path
import numpy as np
import pandas as pd
root=Path(__file__).parent/'benchmarks'
a=json.loads((root/'baseline/benchmark.json').read_text());b=json.loads((root/'optimized/benchmark.json').read_text())
p=Path(a['output_dir']);q=Path(b['output_dir'])
with np.load(p/'steady/trajectory.npz') as x,np.load(q/'steady/trajectory.npz') as y:
    differences={k:float(np.max(np.abs(x[k]-y[k]),initial=0)) for k in ('joints','anatomical_q','parameters','contact_gaps_cm','audit_forces_bw')}
m=pd.read_csv(p/'steady/metrics.csv');n=pd.read_csv(q/'steady/metrics.csv')
flags=[c for c in m if c.endswith('_failed') or m[c].dtype==bool]
checks={c:dict(before=int(m[c].sum()),after=int(n[c].sum()),identical=bool(m[c].equals(n[c]))) for c in flags}
s=json.loads((p/'steady/summary.json').read_text())['solver'];t=json.loads((q/'steady/summary.json').read_text())['solver']
report=dict(baseline=a,optimized=b,speedup=a['pipeline_seconds']/b['pipeline_seconds'],reduction_percent=100*(1-b['pipeline_seconds']/a['pipeline_seconds']),trajectory_max_absolute_differences=differences,checks=checks,solver_before=s,solver_after=t,profile_identical=json.loads((p/'user_profile.json').read_text())==json.loads((q/'user_profile.json').read_text()))
(root/'comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('checks','solver_before','solver_after')},indent=2))
print('All constraint flag columns identical:',all(c['identical'] for c in checks.values()),'columns:',len(checks))
