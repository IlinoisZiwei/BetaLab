"""Opt-in browser acceptance on actual media, API, database and real worker.

Uses a separate schema and ports 8794/5176. Leaves reports/artifacts in ignored runs/.
Requires: pip install -r backend/requirements-browser.txt; playwright install chromium.
"""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import unittest
from urllib.request import urlopen
from uuid import uuid4
from support import database as db_support

@unittest.skipUnless(os.getenv('BETALAB_BROWSER_TEST')=='1','Requires explicit real browser test opt-in')
class BrowserReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_support.setup_database(cls)
        cls.old_env={k:os.environ.get(k) for k in ('UPLOAD_DIR','COMPUTE_STORAGE_DIR','COMPUTE_MODE','APP_ORIGINS','BETALAB_API_TARGET')}
        cls.output=Path('backend/compute/runs')/('phase4-browser-'+uuid4().hex[:8])
        cls.output.mkdir(parents=True)
        os.environ.update(UPLOAD_DIR=str(cls.videos.UPLOAD_DIR),COMPUTE_STORAGE_DIR=str(cls.output.resolve()),
            COMPUTE_MODE='real',APP_ORIGINS='http://127.0.0.1:5176',BETALAB_API_TARGET='http://127.0.0.1:8794')
        from backend.database import database
        with database() as db:
            db.execute("INSERT INTO routes(id,gym_id,name,grade) VALUES ('r1','test-gym','Trial2','V0') ON CONFLICT DO NOTHING")
        node=os.environ.get('BETALAB_NODE','node')
        commands=[
            [sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8794'],
            [node,'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5176'],
            [sys.executable,'-m','backend.compute.worker']]
        cls.processes=[];cls.logs=[]
        for name,cmd in zip(('api','vite','worker'),commands):
            log=(cls.output/(name+'.log')).open('w');cls.logs.append(log)
            cls.processes.append(subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True))
        for url in ('http://127.0.0.1:8794/api/health','http://127.0.0.1:5176/compute.html'):
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                try:
                    with urlopen(url) as response:
                        if response.status==200:break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('Test server did not start: '+url)

    @classmethod
    def tearDownClass(cls):
        for process in reversed(cls.processes):
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
        for log in cls.logs:log.close()
        for key,old in cls.old_env.items():
            if old is None:os.environ.pop(key,None)
            else:os.environ[key]=old
        db_support.teardown_database(cls)

    def test_real_submission_play_pause_seek_and_access(self):
        from playwright.sync_api import sync_playwright,expect
        with sync_playwright() as p:
            browser=p.chromium.launch()
            context=browser.new_context(base_url='http://127.0.0.1:5176',viewport={'width':1280,'height':900})
            page=context.new_page()
            page.goto('http://127.0.0.1:5176/compute.html')
            page.get_by_label('用户名',exact=True).fill('phase4review')
            page.get_by_label('密码',exact=True).fill('phase4-browser-local')
            page.get_by_role('button',name='注册测试账号').click()
            expect(page.get_by_text('当前用户：phase4review')).to_be_visible()
            page.get_by_label('Trial 2 视频').set_input_files(str(Path(os.environ['BETA_TRANSLATOR_ROOT'])/'videos/trial2.mp4'))
            started=time.monotonic()
            with page.expect_response(lambda r:r.url.endswith('/api/tasks/analyze') and r.request.method=='POST') as created:
                page.get_by_role('button',name='上传并分析').click()
            analysis_id=created.value.json()['id']
            # Reload proves the job does not depend on the initiating page remaining open.
            page.reload()
            page.get_by_role('button',name=re.compile('源分析 ·')).first.click()
            expect(page.get_by_test_id('task-state')).to_contain_text('analyze · succeeded',timeout=180000)
            analysis_seconds=time.monotonic()-started
            analysis=page.request.get('/api/tasks/'+analysis_id).json()
            page.get_by_label('目标身高',exact=True).fill('170')
            page.get_by_label('目标臂展',exact=True).fill('175')
            started=time.monotonic()
            with page.expect_response(lambda r:r.url.endswith('/api/tasks/generate') and r.request.method=='POST') as created:
                page.get_by_role('button',name='生成我的预览').click()
            task_id=created.value.json()['id']
            expect(page.get_by_test_id('task-state')).to_contain_text('generate · succeeded',timeout=180000)
            generation_seconds=time.monotonic()-started
            task=page.request.get('/api/tasks/'+task_id).json();result=task['result']
            self.assertFalse(result['is_mock']);self.assertEqual(result['baseline_status'],'failed')
            player=page.get_by_label('生成结果',exact=True)
            player.evaluate('(v)=>new Promise((resolve,reject)=>{if(v.readyState>=2)return resolve(true);v.addEventListener("loadeddata",()=>resolve(true),{once:true});v.addEventListener("error",()=>reject(new Error("decode failed")),{once:true});})')
            player.evaluate('(v)=>v.play()')
            page.wait_for_timeout(500)
            self.assertGreater(player.evaluate('(v)=>v.currentTime'),.1)
            player.evaluate('(v)=>v.pause()')
            paused=player.evaluate('(v)=>v.currentTime');page.wait_for_timeout(250)
            self.assertAlmostEqual(player.evaluate('(v)=>v.currentTime'),paused,places=2)
            moments=[]
            for moment in result['moments']:
                button=page.locator(f'button[data-frame="{moment["frame"]}"]').first
                button.click()
                expect(page.get_by_text(re.compile('已定位'))).to_be_visible()
                actual=player.evaluate('(v)=>v.currentTime')
                self.assertAlmostEqual(actual,moment['at_seconds'],places=3)
                moments.append(dict(frame=moment['frame'],expected=moment['at_seconds'],actual=actual))
            # Repeating the same button must seek again, even after playback moved away.
            moment=result['moments'][-1];button=page.locator(f'button[data-frame="{moment["frame"]}"]').first
            player.evaluate('(v)=>{v.currentTime=1;}');button.click()
            self.assertAlmostEqual(player.evaluate('(v)=>v.currentTime'),moment['at_seconds'],places=3)
            # A fresh media element exercises the before-loadedmetadata path and bounds.
            bounds=page.evaluate('''async ({url,last})=>{
                const {seekToMoment}=await import('/src/compute/seek.ts');
                const v=document.createElement('video');v.preload='none';v.src=url;
                const before=v.readyState;
                const high=await seekToMoment(v,999,last);
                const low=await seekToMoment(v,-10,last);
                let invalid=false;try{await seekToMoment(v,NaN,last)}catch{invalid=true}
                v.removeAttribute('src');v.load();
                return {before,high,low,invalid};
            }''',dict(url='/api/tasks/'+task_id+'/artifacts/video',last=(result['frame_count']-1)/result['fps']))
            self.assertEqual(bounds['before'],0);self.assertEqual(bounds['high'],32.5)
            self.assertEqual(bounds['low'],0);self.assertTrue(bounds['invalid'])
            page.get_by_role('button',name='未读 · 计算完成',exact=True).first.click()
            expect(page.get_by_role('button',name='已读 · 计算完成',exact=True).first).to_be_visible()
            page.screenshot(path=str(self.output/'desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
            page.screenshot(path=str(self.output/'mobile.png'),full_page=True)
            csrf=page.request.get('/api/auth/me').json()['csrf_token']
            headers={'Origin':'http://127.0.0.1:5176','X-CSRF-Token':csrf}
            video_id=task['source_video_id']
            self.assertEqual(page.request.patch('/api/videos/'+video_id,data={'visibility':'public'},headers=headers).status,200)
            other=browser.new_context(base_url='http://127.0.0.1:5176')
            login=other.request.post('/api/auth/login',data={'username':'phase2bob','password':'phase2-local-test-only'},headers={'Origin':'http://127.0.0.1:5176'})
            self.assertEqual(login.status,200)
            self.assertEqual(other.request.get('/api/tasks/source-analysis/'+video_id+'/artifacts/video').status,200)
            self.assertEqual(other.request.get('/api/tasks/'+task_id+'/artifacts/video').status,404)
            page.request.patch('/api/videos/'+video_id,data={'visibility':'private'},headers=headers)
            self.assertEqual(other.request.get('/api/tasks/source-analysis/'+video_id+'/artifacts/video').status,404)
            page.request.delete('/api/videos/'+video_id,headers=headers)
            self.assertEqual(page.request.get('/api/tasks/'+task_id+'/artifacts/video').status,404)
            (self.output/'validation.json').write_text(json.dumps(dict(analysis=analysis,generation=task,
                analysis_seconds=analysis_seconds,generation_seconds=generation_seconds,moments=moments,
                seek_bounds=bounds,browser=browser.version),indent=2)+'\n')
            other.close();context.close();browser.close()
            print('Browser evidence retained at',self.output,flush=True)

if __name__=='__main__':unittest.main()
