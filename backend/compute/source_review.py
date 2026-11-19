"""Reproducible Trial2 source audit; never overwrites historical runs or labels.

References CIS5810 Beta_Translator ff85726da2fbbd2616c409b01d6c03833ab62ce9:
Trial2Scene, load_trial2, episode_regions and contact_regions3d.homography.
This reviews existing real artifacts; it does not treat them as fresh inference.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from .prepare_trial2 import SOURCE_COMMIT,digest,write
from .fit_trial2 import profile_for


def load_npz(path):
    import numpy as np
    with np.load(path,allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}


def review(source,report_path,out,max_nfev=200,reuse_fit=False):
    import subprocess
    import numpy as np
    source,report_path,out=source.resolve(),report_path.resolve(),out.resolve()
    if out.exists():raise FileExistsError('Choose a new review output directory')
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=SOURCE_COMMIT:
        raise ValueError('Review the pinned Beta Translator revision first')
    sys.path.insert(0,str(source))
    from beta_translator.trial2_scene3d import Trial2Scene
    from beta_translator.trial2_spatial_data import load_trial2
    from beta_translator.body_regions import episode_regions
    from .preview_math import adapt
    from .geometry_scope import wall_contacts
    from .source_fit import fit_source
    from .source_diagnostics import evaluate
    from .reachability import audit_reach
    report=json.loads(report_path.read_text());result=report['analysis']['result']
    if result['is_mock'] or report['analysis']['state']!='succeeded':raise ValueError('Real complete analysis required')
    def artifact(result,name):
        entry=result['artifacts'][name];path=(report_path.parent/entry['storage_key']).resolve()
        if not path.is_relative_to(report_path.parent) or digest(path)!=entry['sha256']:
            raise ValueError('Source artifact path/checksum mismatch')
        return path
    provenance=json.loads(artifact(result,'provenance').read_text())
    from .real_job import VIDEO_HASH as TRIAL2_SHA256
    if digest(source/'videos/trial2.mp4')!=TRIAL2_SHA256 or provenance['video_sha256']!=TRIAL2_SHA256:
        raise ValueError('Wrong recording')
    # Match upstream evidence to the historical run; adapter changes are expected.
    for name,expected in provenance['input_sha256'].items():
        if name.startswith('betalab/'):continue
        path=(source/name).resolve()
        if not path.is_relative_to(source) or digest(path)!=expected:raise ValueError('Upstream inputs changed: '+name)
    body=result['original_body'];profile=profile_for(source,body['height_cm'],body['arm_span_cm'])
    evidence=load_npz(artifact(result,'contacts'));q=load_npz(artifact(result,'initializer' if 'initializer' in result['artifacts'] else 'skeleton'))['anatomical_q']
    if not np.array_equal(evidence['frames'],np.arange(976)):raise ValueError('Native timeline mismatch')
    from .calibration import VERSION,scene_for
    scene=scene_for(source) if result['calibration_version']==VERSION else Trial2Scene(source,middle_deg=15,upper_deg=0,spacing_cm=14.3)
    # Scene spacing is explicitly overridden; never write the upstream 15 cm file.
    data=load_trial2(source);regions=episode_regions(data,scene,body['height_cm'])
    for episode in regions['episodes']:
        episode['evidence_frames']=int(episode['evidence_frames'])
    for ep in regions['episodes']:
        a,b,l=ep['start_frame'],ep['end_frame']+1,ep['limb_index']
        anchor=scene.intersect(np.array(ep['anchor_px']),ep['panel'])
        if not np.allclose(evidence['contacts_cm'][a:b,l],anchor,atol=1e-7):
            raise ValueError('Review scene does not reproduce source anchors')
    out.mkdir(parents=True)
    write(out/'reachability.json',audit_reach(evidence,profile))
    write(out/'input-review.json',dict(source_body=body,spacing_cm=14.3,angles_measured=False,
        camera=scene.report()['camera'],episodes=regions['episodes'],evidence=regions['evidence'],
        raw_schedule_unchanged=bool(np.array_equal(data['labels'],evidence['labels'])),
        trusted_rule='Legacy known & episode evidence_frames>0; candidates, NOT manual confirmation.',
        correction_status='No unverified measurement, anchor, label or contact time was edited.'))
    np.savez_compressed(out/'evidence.npz',**evidence)
    summaries={}
    def save(name,pose,p,extra=None):
        diagnostic,g=evaluate(pose,evidence,p,scene)
        if extra:diagnostic.update(extra)
        write(out/(name+'.json'),diagnostic);np.savez_compressed(out/(name+'.npz'),q=pose)
        summaries[name]=diagnostic['summary'];print(name,summaries[name],flush=True)
        return diagnostic,g
    initial,_=save('initializer',q,profile)
    same=adapt(q,{**evidence,'trusted':wall_contacts(evidence)},profile,lambda *a:None)[0];save('same_body_control',same,profile)
    target=report['generation']['result'];target_body=target['target_body']
    save('target_generated',load_npz(artifact(target,'skeleton'))['anatomical_q'],
         profile_for(source,target_body['height_cm'],target_body['arm_span_cm']))
    start=time.monotonic()
    if reuse_fit:
        from .real_job import input_hashes
        if provenance['input_sha256']!=input_hashes(source):raise ValueError('Fit reuse requires the current algorithm/evidence fingerprint')
        fitted=load_npz(artifact(result,'skeleton'))['anatomical_q']
        solver=json.loads(artifact(result,'source_audit').read_text())['solver']
    else:
        fitted,solver=fit_source(q,evidence,profile,scene,lambda *a:print(*a,flush=True),max_nfev)
    final,g=save('source_fitted',fitted,profile,dict(solver=solver,reused_verified_fit=reuse_fit,
        elapsed_seconds=None if reuse_fit else time.monotonic()-start))
    from .source_fit import adapt_body
    same_fitted=adapt_body(fitted,evidence,profile,profile,scene,lambda *a:None)[0]
    save('same_body_from_fitted',same_fitted,profile)
    write(out/'summary.json',dict(source_commit=SOURCE_COMMIT,input_report_sha256=digest(report_path),
        algorithm_sha256={name:digest(Path(__file__).with_name(name)) for name in
            ('source_review.py','source_fit.py','source_diagnostics.py','reachability.py','preview_math.py','calibration.py','geometry_scope.py','trajectory_solver.py')},
        source_body=body,results=summaries,physical_validation=False,
        all_contact_labels_and_times_preserved=True))
    make_review_images(source,out,evidence,scene,profile,q,fitted,initial,final)
    import html
    import os
    media=[]
    for kind,title in [('analysis','源动作诊断视频'),('generation','目标体型诊断视频')]:
        task=report.get(kind)
        if not task:continue
        result=task['result']
        for name,entry in result['artifacts'].items():
            if entry['storage_key'].endswith('.mp4'):
                path=artifact(result,name)
                url=html.escape(os.path.relpath(path,out),quote=True)
                media.append(f'<h2>{title}（非可行动作认证）</h2><video controls preload="metadata" style="width:100%" src="{url}"></video>')
                break
    with (out/'review.html').open('a') as stream:stream.write(''.join(media))
    return summaries


def make_review_images(source,out,evidence,scene,profile,before,after,initial,final):
    import cv2
    import numpy as np
    from beta_translator.contact_regions3d import homography
    from .preview_math import geometry
    alignment=load_npz(source/'outputs/trial2/state/alignment_cache.npz')['matrices']
    cap=cv2.VideoCapture(str(source/'videos/trial2.mp4'))
    joints=[scene.pixels(geometry(q,profile)['joints']) for q in (before,after)]
    peaks=[e['peak_frame'] for e in sorted(final['episodes'],key=lambda x:x['max_gap_cm'] or 0,reverse=True)[:6]]
    frames=sorted(set([0,78,175,178,239,298,299,474,931]+[f for f in peaks if f is not None]))
    images=[]
    for f in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,raw=cap.read()
        if not ok:raise ValueError('Cannot read review frame')
        panels=[]
        anchors=homography(scene.pixels(evidence['contacts_cm'][f]),alignment[f])
        for title,pixels in zip(('Initializer','Source fit'),joints):
            image=raw.copy();p=homography(pixels[f],alignment[f])
            for limb in range(4):
                for a,b in zip(p[limb,:-1],p[limb,1:]):cv2.line(image,tuple(a.astype(int)),tuple(b.astype(int)),(0,190,255),3)
                if evidence['known'][f,limb]:
                    point=tuple(anchors[limb].astype(int));cv2.circle(image,point,9,(0,255,0),2)
                    cv2.putText(image,str(evidence['labels'][f,limb]),point,cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,0),2)
            cv2.rectangle(image,(0,0),(1920,58),(20,20,20),-1)
            cv2.putText(image,f'{title} | frame {f} / {f/30:.2f}s | yellow: model joints; green: candidate anchor',
                (20,38),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2)
            panels.append(cv2.resize(image,(960,540)))
        name=f'frame-{f:04d}.jpg';cv2.imwrite(str(out/name),np.hstack(panels));images.append(name)
    cap.set(cv2.CAP_PROP_POS_FRAMES,450);ok,image=cap.read();cap.release()
    if not ok:raise ValueError('Cannot read calibration frame')
    for name,color in [('upper_hinge_px',(0,255,255)),('lower_hinge_px',(0,255,255)),('floor_edge_px',(255,255,0))]:
        a,b=np.asarray(scene.spec[name],int);cv2.line(image,tuple(a),tuple(b),color,3)
        cv2.putText(image,name,tuple(a),cv2.FONT_HERSHEY_SIMPLEX,.7,color,2)
    for i,point in enumerate(scene.spec['upper_grid_px']):
        point=tuple(np.array(point,int));cv2.circle(image,point,6,(0,0,255),2)
        cv2.putText(image,str(i),point,cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,255),2)
    cv2.imwrite(str(out/'calibration-review.jpg'),image)
    summaries=[('原初始化',initial['summary']),('源联合拟合',final['summary'])]
    table='<table border="1" cellpadding="10"><tr><th>结果</th><th>已知墙最大误差cm</th><th>已知墙超5cm帧数</th><th>速率违规帧对</th><th>投影RMSE px</th></tr>'
    for label,stats in summaries:
        table+=f"<tr><td>{label}</td><td>{stats['wall_max_gap_cm']:.2f}</td><td>{stats['wall_frames_over_5cm']}</td><td>{stats['rate_violation_frames']}</td><td>{stats['observed_joint_rmse_px']:.2f}</td></tr>"
    table+='</table><p><a href="reachability.json">输入矛盾详细记录</a> · <a href="input-review.json">接触片段及墙面证据</a></p>'
    (out/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Trial2 source review</title>'
        '<style>body{font:18px system-ui;max-width:1500px;margin:30px auto}img{width:100%}</style>'
        '<h1>Trial2 源动作核查</h1><p>黄色为模型关节，绿色为候选接触锚点；不等于人工确认。'
        '同一原生帧左为初始化、右为拟合。两面攀爬墙角和边界已确认；源身材含估计值，完整碰撞/力学仍未验证。</p>'
        '<p><strong>全程基线尚未通过验证，不能作为可行攀爬动作。</strong>已采用约173 cm / 假设臂展176 cm、28°/70°相对水平的墙角和已确认边界。地面78个样本保留为未验证，表格单独统计已知墙面。</p>'+table+
        '<h2>标定位置存档（折线与地面线位置已确认）</h2><img src="calibration-review.jpg">'+
        ''.join(f'<h2>{name}</h2><img src="{name}">' for name in images))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--max-nfev',type=int,default=200)
    parser.add_argument('--reuse-fit',action='store_true',help='Audit an existing current source fit without solving it again')
    args=parser.parse_args()
    if args.max_nfev<1:parser.error('--max-nfev must be positive')
    review(args.source,args.report,args.out,args.max_nfev,args.reuse_fit)

if __name__=='__main__':main()
