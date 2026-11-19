"""Verify and package real precomputed examples, never fabricate a live task.

Validates the Beta Translator provenance recorded by real_job.py (CIS5810
ff85726da2fbbd2616c409b01d6c03833ab62ce9); this module does not alter motion.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile
from .contracts import Result
from .storage import ENGINE,TRIAL2_SHA256,digest
from .real_job import input_hashes

PAGE='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BetaLab 真实备用结果</title><style>body{font:16px system-ui;background:#edf3f6;color:#163044;max-width:1100px;margin:auto;padding:24px}section{background:white;padding:20px;border-radius:12px;margin:20px 0}video{width:100%}button{padding:10px;margin:5px;border-radius:6px;border:1px solid #759aae}p{line-height:1.5}.warning{border-left:4px solid #bb7510;padding:12px;background:#fff4d9}</style>
<h1>BetaLab · 真实预生成备用结果</h1><p class="warning">这是已完成的真实计算，不是现场新任务。几何检查仍未通过；未完成全力学验证，不作为攀爬建议。</p>
<div id="content"></div><script>
const data=__DATA__;
for(const role of ['analysis','generation']){
 const item=data.examples[role],section=document.createElement('section');
 const h=document.createElement('h2');h.textContent=role==='analysis'?'源分析':'目标身材诊断预览';section.append(h);
 const p=document.createElement('p');p.textContent=`${item.frame_count}帧 / ${item.fps}fps · ${item.algorithm_version} · 基线：${item.baseline_status} · ${item.created_at}`;section.append(p);
 const dims=document.createElement('p');dims.textContent='身体参数：'+JSON.stringify(item.target_body||item.original_body);section.append(dims);
 const video=document.createElement('video');video.controls=true;video.preload='metadata';video.src=item.video;section.append(video);
 for(const m of item.moments){const b=document.createElement('button');b.textContent=`查看 ${m.at_seconds.toFixed(2)} 秒 · ${m.limb} · ${m.title}`;
 b.onclick=()=>{const seek=()=>{video.pause();video.currentTime=Math.max(0,Math.min(m.at_seconds,(item.frame_count-1)/item.fps,video.duration));};if(video.readyState>=1)seek();else{video.addEventListener('loadedmetadata',seek,{once:true});video.load();}};section.append(b);}
 const note=document.createElement('p');note.textContent=item.quality.warnings.join(' ');section.append(note);document.getElementById('content').append(section);
}
</script></html>'''

def within(base,key):
    path=(base/key).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file() or (base/key).is_symlink():
        raise ValueError('File outside the verified bundle')
    return path

def verify(bundle):
    bundle=Path(bundle)
    manifest=json.loads((bundle/'manifest.json').read_text())
    if manifest.get('schema_version')!=1 or manifest.get('prerecorded') is not True or manifest.get('is_mock') is not False:
        raise ValueError('Not a labelled real standby bundle')
    entries=manifest.get('sha256',{})
    if not {'index.html','metadata.json','README.txt'}.issubset(entries):
        raise ValueError('Incomplete bundle manifest')
    for name,expected in entries.items():
        if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):
            raise ValueError('Invalid manifest checksum')
        if digest(within(bundle,name))!=expected:raise ValueError('Bundle checksum mismatch: '+name)
    metadata=json.loads((bundle/'metadata.json').read_text())
    if metadata.get('prerecorded') is not True or metadata.get('is_mock') is not False:
        raise ValueError('Missing prerecorded/real labels')
    if set(metadata.get('examples',{}))!={'analysis','generation'}:
        raise ValueError('Both source and target examples are required')
    for example in metadata['examples'].values():
        referenced=set(example['artifacts'].values()) | {example['video']}
        if not referenced.issubset(entries):
            raise ValueError('Unverified example artifact')
    return manifest

def probe(path,expected):
    stream=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=codec_name,pix_fmt,nb_read_frames,avg_frame_rate','-of','json',str(path)],text=True))['streams'][0]
    numerator,denominator=map(int,stream['avg_frame_rate'].split('/'))
    if stream['codec_name']!='h264' or stream['pix_fmt']!='yuv420p' or int(stream['nb_read_frames'])!=expected.frame_count or numerator/denominator!=expected.fps:
        raise ValueError('Video encoding/time axis mismatch')

def pack(report_path,destination,source):
    report_path,destination,source=Path(report_path).resolve(),Path(destination).resolve(),Path(source).resolve()
    archive=destination.with_suffix('.zip')
    if destination.exists() or archive.exists():raise FileExistsError('Choose a new standby version; existing backups are preserved')
    report=json.loads(report_path.read_text());source_inputs=input_hashes(source)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.standby-') as temp:
        staging=Path(temp)/'bundle';staging.mkdir()
        metadata=dict(schema_version=1,prerecorded=True,is_mock=False,packaged_at=datetime.now(timezone.utc).isoformat(),
            original_recording_sha256=TRIAL2_SHA256,examples={})
        for role in ('analysis','generation'):
            task=report[role]
            result=Result.model_validate(task['result'])
            if task['state']!='succeeded' or result.is_mock or result.algorithm_version!=ENGINE:
                raise ValueError('Only complete, current, real results may be packaged')
            if result.kind!=('analyze' if role=='analysis' else 'generate'):
                raise ValueError('Wrong example type')
            out=staging/role;out.mkdir()
            files={}
            for name,artifact in result.artifacts.items():
                if not re.fullmatch('[a-z][a-z0-9_]*',name):raise ValueError('Invalid artifact name')
                original=within(report_path.parent,artifact.storage_key)
                if digest(original)!=artifact.sha256:raise ValueError('Original artifact changed: '+name)
                target=out/(name+original.suffix)
                shutil.copyfile(original,target);files[name]=target.relative_to(staging).as_posix()
            provenance=json.loads((staging/files['provenance']).read_text())
            if provenance['video_sha256']!=TRIAL2_SHA256 or provenance['input_sha256']!=source_inputs:
                raise ValueError('Source evidence/algorithm changed; regenerate the example')
            probe(staging/files['video'],result)
            metadata['examples'][role]=dict(algorithm_version=result.algorithm_version,baseline_status=result.baseline_status,
                created_at=task['created_at'],frame_count=result.frame_count,fps=result.fps,
                original_body=result.original_body.model_dump() if result.original_body else None,
                target_body=result.target_body.model_dump() if result.target_body else None,
                quality=result.quality.model_dump(),moments=[m.model_dump() for m in result.moments],
                video=files['video'],artifacts=files)
        if report['analysis']['result']['source_analysis_version']!=report['generation']['result']['source_analysis_version']:
            raise ValueError('Examples do not share the same source analysis')
        (staging/'metadata.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+'\n')
        embedded=json.dumps(metadata,ensure_ascii=False).replace('<','\\u003c')
        (staging/'index.html').write_text(PAGE.replace('__DATA__',embedded))
        (staging/'README.txt').write_text('真实预生成诊断备用包；不是现场新任务。\n打开 index.html 查看。几何基线仍失败，不能声称动作可行。\n不包含账号、会话、原始上传文件或私有worker日志。视频内含原录像画面；仅按原录像授权范围使用。\n')
        manifest=dict(schema_version=1,prerecorded=True,is_mock=False,
            sha256={p.relative_to(staging).as_posix():digest(p) for p in sorted(staging.rglob('*')) if p.is_file()})
        (staging/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');verify(staging)
        zip_path=Path(temp)/'bundle.zip'
        with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(staging.rglob('*')):
                if path.is_file():zipped.write(path,path.relative_to(staging).as_posix())
        staging.rename(destination);zip_path.rename(archive)
    return dict(bundle=str(destination),archive=str(archive),archive_sha256=digest(archive),file_count=len(manifest['sha256']))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    create=commands.add_parser('pack');create.add_argument('--report',type=Path,required=True)
    create.add_argument('--out',type=Path,required=True);create.add_argument('--source',type=Path,required=True)
    check=commands.add_parser('verify');check.add_argument('bundle',type=Path)
    args=parser.parse_args()
    result=pack(args.report,args.out,args.source) if args.command=='pack' else verify(args.bundle)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
