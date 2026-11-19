"""Main-page upload/analysis orchestration, without rerunning source diagnostics.

Real uploads and queued jobs; explicit interruption and previously verified v5
completion fixtures exercise failure/retry UI. No fresh source fitting is claimed.
"""
import copy
import json
import os
from pathlib import Path
import re
import unittest
from support import browser as community

@unittest.skipUnless(os.getenv('BETALAB_UPLOAD_BROWSER_TEST')=='1','Requires upload browser opt-in')
class UploadBrowserTest(unittest.TestCase):
    @classmethod
    def start(cls,name,cmd): community.start(cls,name,cmd)
    @classmethod
    def setUpClass(cls):community.setup_browser(cls)
    @classmethod
    def tearDownClass(cls):community.teardown_browser(cls)

    def test_upload_failure_analysis_retry_and_refresh(self):
        from playwright.sync_api import sync_playwright,expect
        from backend.database import database
        from backend.compute import service
        with sync_playwright() as p:
            browser=p.chromium.launch();context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page()
            page.goto('http://127.0.0.1:5177')
            page.get_by_label('Username',exact=True).fill('phase2bob');page.get_by_label('Password',exact=True).fill('phase2-local-test-only')
            page.get_by_role('button',name='Sign in',exact=True).last.click()
            def open_route():
                page.get_by_role('button',name=re.compile('^Go Climbing')).last.click()
                page.locator('.gym-card').filter(has_text='Test Gym').click()
                page.locator('.route-open').filter(has_text='Trial2').click()
            open_route();page.get_by_role('button',name='Add my video',exact=True).click()
            page.locator('input[type=file]').set_input_files(str(Path(os.environ['BETA_TRANSLATOR_ROOT'])/'videos/trial2.mp4'))
            page.get_by_label('Title',exact=True).fill('Upload analysis acceptance')
            page.get_by_role('radio',name='Private',exact=True).check()
            page.route('**/api/videos',lambda route:route.abort('failed') if route.request.method=='POST' else route.continue_(),times=1)
            page.get_by_role('button',name='Upload video',exact=True).click()
            expect(page.get_by_role('button',name='Retry upload',exact=True)).to_be_visible()
            # Upload succeeds, then analysis submission loses its connection before acceptance.
            page.route('**/api/tasks/upload-analysis/*',lambda route:route.abort('failed') if route.request.method=='POST' else route.continue_())
            with page.expect_response(lambda r:r.url.endswith('/api/videos') and r.request.method=='POST') as uploaded:
                page.get_by_role('button',name='Retry upload',exact=True).click()
            video_id=uploaded.value.json()['id']
            panel=page.get_by_label('Upload analysis status',exact=True)
            expect(panel).to_contain_text('Video saved')
            expect(panel.get_by_role('button',name='Start analysis',exact=True)).to_be_enabled()
            self.assertEqual(page.request.get('http://127.0.0.1:5177/api/videos/'+video_id).status,200)
            page.screenshot(path=str(self.output/'upload-analysis-submit-failure.png'),full_page=True)
            page.unroute('**/api/tasks/upload-analysis/*')
            with page.expect_response(lambda r:'/tasks/upload-analysis/' in r.url and r.request.method=='POST') as submitted:
                panel.get_by_role('button',name='Start analysis',exact=True).click()
            first=submitted.value.json();self.assertEqual(first['source_video_id'],video_id)
            expect(panel).to_contain_text('Analysis queued')
            with database() as db:
                row=db.execute("UPDATE compute_tasks SET state='running' WHERE id=%s RETURNING *",(first['id'],)).fetchone()
                service.finish(db,row,error=dict(code='INTERRUPTED',message='Explicit test interruption; the video is saved',retryable=True))
            expect(panel.get_by_role('button',name='Retry analysis',exact=True)).to_be_visible(timeout=10000)
            with page.expect_response(lambda r:r.url.endswith('/retry') and r.request.method=='POST') as retried:
                panel.get_by_role('button',name='Retry analysis',exact=True).click()
            latest=retried.value.json();self.assertEqual(latest['retry_of'],first['id'])
            self.assertEqual(page.request.get('http://127.0.0.1:5177/api/videos?owned=true').json()['items'][0]['id'],video_id)
            # Attach verified prior v5 output solely as an explicit completion fixture.
            saved=json.loads(Path('backend/compute/runs/phase3-real-62fc330f/validation.json').read_text())['analysis']['result']
            result=copy.deepcopy(saved);result['source_video_id']=video_id
            with database() as db:
                row=db.execute("UPDATE compute_tasks SET state='running' WHERE id=%s RETURNING *",(latest['id'],)).fetchone();service.finish(db,row,result=result)
            expect(panel).to_contain_text('Analysis completed',timeout=10000)
            expect(panel).to_contain_text('Baseline: failed')
            page.screenshot(path=str(self.output/'upload-analysis-completed.png'),full_page=True)
            page.reload();page.get_by_role('button',name='My skeletons',exact=True).click()
            page.get_by_role('button',name=re.compile('Source analysis · Completed')).click()
            expect(page.get_by_label('Source analysis video',exact=True)).to_be_visible()
            self.assertEqual(self.alice.get('/api/tasks/upload-analysis/'+video_id).status_code,404)
            # A new unsupported video on the very same route must not inherit Trial2 inputs.
            open_route();page.get_by_role('button',name='Add my video',exact=True).click()
            page.locator('input[type=file]').set_input_files(str(self.video))
            page.get_by_label('Title',exact=True).fill('Unsupported upload acceptance')
            page.get_by_role('radio',name='Private',exact=True).check()
            with page.expect_response(lambda r:r.url.endswith('/api/videos') and r.request.method=='POST') as second:
                page.get_by_role('button',name='Upload video',exact=True).click()
            other_id=second.value.json()['id']
            expect(panel).to_contain_text('Analysis queued',timeout=10000)
            state=page.request.get('http://127.0.0.1:5177/api/tasks/upload-analysis/'+other_id).json()
            self.assertEqual(state['task']['state'],'queued');self.assertFalse(state['task']['is_mock'])
            self.assertEqual(page.request.get('http://127.0.0.1:5177/api/videos/'+other_id+'/content').status,200)
            page.screenshot(path=str(self.output/'upload-analysis-unavailable.png'),full_page=True)
            # Supported upload normally triggers the queue without an extra click.
            open_route();page.get_by_role('button',name='Add my video',exact=True).click()
            page.locator('input[type=file]').set_input_files(str(Path(os.environ['BETA_TRANSLATOR_ROOT'])/'videos/trial2.mp4'))
            page.get_by_label('Title',exact=True).fill('Automatic source analysis acceptance')
            page.get_by_role('radio',name='Private',exact=True).check()
            with page.expect_response(lambda r:'/tasks/upload-analysis/' in r.url and r.request.method=='POST') as automatic:
                page.get_by_role('button',name='Upload video',exact=True).click()
            auto_task=automatic.value.json();self.assertEqual(automatic.value.status,202)
            expect(panel).to_contain_text('Analysis queued')
            page.reload();page.get_by_role('button',name='My skeletons',exact=True).click()
            expect(page.get_by_role('button',name=re.compile('Source analysis · Queued')).first).to_be_visible()
            (self.output/'upload-validation.json').write_text(json.dumps(dict(
                source_diagnostics_rerun=False,completion='verified precomputed v5 fixture',
                checks=['upload failure preserves selection','post-upload automatic analysis attempted','submission failure preserves upload','real queue','explicit failure and retry','completion baseline label','refresh recovery','owner-only','new same-route video independently queued','supported upload automatically queued'],
                uploaded_video_id=video_id,first_task_id=first['id'],retry_task_id=latest['id']),indent=2))
            browser.close()
        print('Upload browser validation:',self.output)
