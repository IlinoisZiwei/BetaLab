"""Loopback-only prototype API, one solver worker at a time."""
import os,json,math,uuid,subprocess,threading,queue,sys,hashlib
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(os.environ.get('BETA_TRANSLATOR_ROOT','/Users/ziwei/Desktop/2026 Fall/CIS 5810/Beta_Translator'))
HERE=Path(__file__).resolve().parent; JOBS=HERE/'jobs';JOBS.mkdir(exist_ok=True)
work=queue.Queue(); detailed_work=queue.Queue()
def profile_for(height,span):
    if not all(math.isfinite(x) for x in (height,span)) or not 100<=height<=230 or not 80<=span<=260:raise ValueError('Use height 100–230 cm and arm span 80–260 cm for this prototype.')
    p=json.loads((ROOT/'configs/users/trial_user_175.json').read_text());scale=height/p['height_cm']
    p['dimensions_cm']={k:v*scale for k,v in p['dimensions_cm'].items()};d=p['dimensions_cm']
    factor=(span-d['shoulder_w'])/(2*(d['upper_arm']+d['forearm']+d['hand_length']))
    for k in ('upper_arm','forearm','hand_length','hand_patch_distance','hand_patch_depth'):d[k]*=factor
    p.update(height_cm=height,arm_span_cm=span,user_id='local_preview')
    p['biomechanics']['capsule_radii_cm']=[v*scale for v in p['biomechanics']['capsule_radii_cm']]
    p['evidence'].update(height='user_input',arm_span='user_input',geometry='assumed template ratios scaled to height; arm segments scaled to match measured bilateral span')
    return p
def engine_key():
    config=ROOT/'configs/trials/trial2.json';cfg=json.loads(config.read_text());evidence=ROOT/cfg['input_root']
    files=[*sorted((ROOT/'beta_translator').glob('*.py')),*sorted((ROOT/'data').glob('*.json')),config,ROOT/cfg['video'],ROOT/cfg['baseline'],evidence/'automatic/wholebody.npz',HERE/'worker.py',HERE/'quick_worker.py',HERE/'render_preview.py',HERE/'server.py',*sorted((HERE/'prepared').glob('*'))]
    for folder in ('state','tables','automatic/predictions'):
        files.extend(sorted(f for f in (evidence/folder).iterdir() if f.is_file()))
    digest=hashlib.sha256()
    for file in files:
        digest.update(str(file).encode())
        with file.open('rb') as stream:
            while chunk:=stream.read(1024*1024):digest.update(chunk)
    return digest.hexdigest()
def run(detailed=False):
    tasks=detailed_work if detailed else work
    while True:
        job=tasks.get()
        try:
            with (job/('worker.log' if detailed else 'quick.log')).open('w') as log:
                result=subprocess.run([str(ROOT/'.venv/bin/python'),str(HERE/('worker.py' if detailed else 'quick_worker.py')),str(job)],env={**os.environ,'BETA_TRANSLATOR_ROOT':str(ROOT),'PYTHONUNBUFFERED':'1'},stdout=log,stderr=subprocess.STDOUT)
            data=json.loads((job/'status.json').read_text())
            if result.returncode:raise RuntimeError('Worker stopped')
            if not detailed and data['state']=='ready':detailed_work.put(job)
        except Exception:
            data=json.loads((job/'status.json').read_text())
            if detailed:data.update(detail_state='failed',detail_message='Detailed analysis stopped. Quick preview remains available.')
            else:data.update(state='failed',message='Quick worker stopped. Please retry.')
            tmp=job/'server-status.tmp';tmp.write_text(json.dumps(data));tmp.replace(job/'status.json')
        finally:tasks.task_done()
class Handler(BaseHTTPRequestHandler):
    def reply(self,code,data):
        body=json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        if self.path!='/api/skeleton-jobs':return self.reply(404,{'error':'Not found'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size>4096:raise ValueError('Request too large')
            d=json.loads(self.rfile.read(size))
            if d.get('source_id')!='trial2':raise ValueError('Only the prepared Trial 2 recording is supported locally.')
            h=float(d['height_cm']);s=float(d['arm_span_cm']);p=profile_for(h,s)
        except (ValueError,KeyError,TypeError):return self.reply(400,{'error':'Provide Trial 2, height 100–230 cm and arm span 80–260 cm.'})
        key=engine_key()
        for old in JOBS.glob('*/request.json'):
            previous=json.loads(old.read_text());state=json.loads((old.parent/'status.json').read_text())
            if previous.get('engine_key')==key and previous.get('profile')==p and state['state'] in ('queued','fitting','rendering','ready'):
                return self.reply(200,state)
        job=JOBS/uuid.uuid4().hex;job.mkdir();(job/'request.json').write_text(json.dumps(dict(source_id='trial2',height_cm=h,arm_span_cm=s,profile=p,engine_key=key),indent=2))
        data=dict(id=job.name,state='queued',message='Waiting for the local solver');(job/'status.json').write_text(json.dumps(data));work.put(job);self.reply(202,data)
    def do_GET(self):
        if self.path=='/api/health':return self.reply(200,{'ready':True,'source_id':'trial2'})
        parts=self.path.split('/')
        if len(parts) not in (4,5) or parts[1:3]!=['api','skeleton-jobs'] or len(parts[3])!=32 or any(c not in '0123456789abcdef' for c in parts[3]):return self.reply(404,{'error':'Not found'})
        job=JOBS/parts[3]
        if not (job/'status.json').exists():return self.reply(404,{'error':'Unknown job'})
        if len(parts)==4:return self.reply(200,json.loads((job/'status.json').read_text()))
        if parts[4] not in ('preview.mp4','quick.mp4') or not (job/parts[4]).exists():return self.reply(404,{'error':'Video not ready'})
        body=(job/parts[4]).read_bytes();self.send_response(200);self.send_header('Content-Type','video/mp4');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
if __name__ == '__main__':
    # Interrupted tasks remain inspectable and can be retried as a new job.
    for path in JOBS.glob('*/status.json'):
        data=json.loads(path.read_text())
        if data.get('detail_state') in ('queued','fitting','rendering'):
            data.update(detail_state='failed',detail_message='Server restarted; quick preview is still available.');path.write_text(json.dumps(data))
        if data['state'] not in ('ready','failed'):
            data.update(state='failed',message='Local server restarted. Please retry.');path.write_text(json.dumps(data))
    threading.Thread(target=run,daemon=True).start()
    threading.Thread(target=run,args=(True,),daemon=True).start()
    print('BetaLab local API: http://127.0.0.1:8787',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8787),Handler).serve_forever()
