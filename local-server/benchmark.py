import sys,json,time
from pathlib import Path
root=Path(sys.argv[1]);out=Path(sys.argv[2]);request=Path(sys.argv[3]);sys.path.insert(0,str(root))
from beta_translator.body_model import BodyModel
out.mkdir(parents=True,exist_ok=True)
profile=json.loads(request.read_text())['profile'];start=time.perf_counter()
r=BodyModel(user_profile=profile).fit('trial2',project=root,frames=[550,595],iterations=15,candidates=('steady',),output_root=out,render=False)
(out/'benchmark.json').write_text(json.dumps(dict(output_dir=r['output_dir'],wall_seconds=time.perf_counter()-start,pipeline_seconds=r['seconds']),indent=2))
print((out/'benchmark.json').read_text())
