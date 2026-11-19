"""C's launch checks; reads the database without running migrations or jobs.

Source checks use Beta Translator's anatomy verifiers and Trial2 inputs,
CIS5810 commit ff85726da2fbbd2616c409b01d6c03833ab62ce9. No solver is run.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from .prepare_trial2 import SOURCE_COMMIT
from .storage import ENGINE, TRIAL2_SHA256, digest, root
from backend.database import connect

REPO=Path(__file__).resolve().parents[2]

def check(source=None, database_check=False):
    checks=[]
    def record(name,ok,detail):
        checks.append(dict(name=name,ok=bool(ok),detail=detail))
    versions={}
    for name in ('fastapi','uvicorn','psycopg','pydantic','python-dotenv','pwdlib','python-multipart'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]='missing'
    record('api_dependencies','missing' not in versions.values(),versions)
    mode=os.getenv('COMPUTE_MODE','real')
    record('mode',mode in ('real','mock'),dict(mode=mode,note='Mock is test-only; never present it as live algorithm output.'))
    for tool in ('ffmpeg','ffprobe'):
        executable=shutil.which(tool)
        if executable:
            try:
                version=subprocess.check_output([executable,'-version'],text=True,timeout=10).splitlines()[0]
                record(tool,True,version)
            except (OSError,subprocess.SubprocessError):record(tool,False,'Executable failed')
        else:record(tool,False,'Not found on PATH')
    try:
        directory=root()
        if directory.is_relative_to((REPO/'public').resolve()):
            raise ValueError('Private compute storage cannot be inside public/')
        directory.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryFile(dir=directory) as probe:
            probe.write(b'BetaLab write check');probe.flush();os.fsync(probe.fileno())
        free=shutil.disk_usage(directory).free
        record('storage',free>=2*1024**3,dict(free_gib=round(free/1024**3,2),minimum_free_gib=2,writable=True))
    except (OSError,ValueError):record('storage',False,'Check private directory location, write access and free space')
    source=source or os.getenv('BETA_TRANSLATOR_ROOT')
    if source:
        source=Path(source).resolve()
        try:
            commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL,timeout=10).strip()
            record('source_revision',commit==SOURCE_COMMIT,dict(actual=commit,expected=SOURCE_COMMIT))
            record('recording',digest(source/'videos/trial2.mp4')==TRIAL2_SHA256,dict(expected_sha256=TRIAL2_SHA256))
            from .real_job import input_hashes
            inputs=input_hashes(source)
            fingerprint=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
            record('prepared_evidence',True,dict(file_count=len(inputs),sha256=fingerprint))
        except (OSError,ValueError,subprocess.SubprocessError):record('prepared_evidence',False,'Pinned source/video/prepared inputs missing or unreadable')
        scientific=os.getenv('BETA_TRANSLATOR_PYTHON',str(source/'.venv/bin/python'))
        script='''import json,platform
from importlib.metadata import version
from beta_translator.body_reference import verify_chain
from beta_translator.body_leg_reference import verify_leg_chain
import cv2,numpy,scipy,pandas,matplotlib
print(json.dumps(dict(python=platform.python_version(),machine=platform.machine(),
packages={k:version(k) for k in ['numpy','scipy','pandas','matplotlib','opencv-python']},
arm_chain=bool(verify_chain()['rotational_chain_pass']),leg_chain=bool(verify_leg_chain()['passed']))))'''
        try:
            result=json.loads(subprocess.check_output([scientific,'-c',script],cwd=source,text=True,stderr=subprocess.PIPE,timeout=60))
            record('scientific_environment',result['python'].startswith('3.12.') and result['arm_chain'] and result['leg_chain'],result)
        except (OSError,ValueError,subprocess.SubprocessError):record('scientific_environment',False,'Use the verified Python 3.12 environment; dependency or anatomy verification failed')
    else:record('scientific_environment',False,'Set BETA_TRANSLATOR_ROOT')
    if database_check:
        try:
            with connect(connect_timeout=3) as db:
                applied={r['version']:r['checksum'] for r in db.execute('SELECT version,checksum FROM schema_migrations')}
                migrations=list((REPO/'backend/db/migrations').glob('*.sql'))
                mismatch=[p.name for p in migrations if applied.get(p.name)!=hashlib.sha256(p.read_bytes()).hexdigest()]
                record('database_migrations',not mismatch,dict(expected=len(migrations),mismatched_or_missing=mismatch))
                rows=db.execute('SELECT state,count(*) AS count FROM compute_tasks GROUP BY state').fetchall()
                record('queue_readable',True,{r['state']:r['count'] for r in rows})
                found=db.execute("SELECT EXISTS(SELECT 1 FROM routes WHERE id='r1' AND NOT archived) AS present").fetchone()['present']
                record('demo_route',found,'Active route r1 is required for the calibrated recording')
        except Exception as error:
            # Never echo a DSN, password, session token or raw driver exception.
            record('database',False,f'Database check failed ({type(error).__name__}); check connection and migrations')
    return dict(schema_version=1,engine=ENGINE,environment_ready=all(c['ok'] for c in checks),
                algorithm_feasibility='not_certified',checks=checks)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('check','run'),default='check',nargs='?')
    parser.add_argument('--source',type=Path)
    parser.add_argument('--database',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.source:os.environ['BETA_TRANSLATOR_ROOT']=str(args.source.resolve())
    result=check(args.source,args.database or args.command=='run')
    output=json.dumps(result,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(output)
    print(output,flush=True)
    if not result['environment_ready']:sys.exit(1)
    if args.command=='run':
        os.chdir(REPO)
        os.execv(sys.executable,[sys.executable,'-m','backend.compute.worker'])

if __name__=='__main__':main()
