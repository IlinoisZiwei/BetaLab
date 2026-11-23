"""Main-page acceptance: imported verified v5 source, fresh real target generation.

Uses disposable PostgreSQL schema, two actual accounts, API and Vite. Source
analysis is explicitly precomputed; this does not rerun or modify source fitting.
"""
import json
import os
import re
import sys
import time
import unittest

from support import browser as browser_support

@unittest.skipUnless(os.getenv('BETALAB_COMMUNITY_TEST')=='1','Requires explicit main-page real browser opt-in')
class CommunityBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): browser_support.setup_browser(cls)
    @classmethod
    def tearDownClass(cls): browser_support.teardown_browser(cls)
    @classmethod
    def start(cls,name,cmd): browser_support.start(cls,name,cmd)

    def test_community_to_private_skeleton(self):
        from playwright.sync_api import sync_playwright,expect
        with sync_playwright() as p:
            browser=p.chromium.launch();context=browser.new_context(viewport={'width':390,'height':844})
            page=context.new_page();page.goto('http://127.0.0.1:5177')
            page.get_by_label('Username',exact=True).fill('phase2bob');page.get_by_label('Password',exact=True).fill('phase2-local-test-only')
            page.get_by_role('button',name='Sign in',exact=True).last.click()
            expect(page.get_by_role('button',name='My Skeletons',exact=True)).to_have_count(0)
            def community(video_id):
                page.get_by_role('button',name=re.compile(r'^Community(?: |$)')).last.click()
                page.locator('.community-feed-card').filter(has_text='Verified Trial2 source' if video_id==self.source_id else 'No analysis video').click()
                page.locator('#community-video-'+video_id).get_by_role('button',name='Generate beta',exact=True).click()
            community(self.unsupported_id)
            dialog=page.get_by_role('dialog',name='Generate personal skeleton')
            expect(dialog).to_contain_text('Source analysis not ready')
            self.assertEqual(page.request.get('http://127.0.0.1:5177/api/tasks').json()['items'],[])
            dialog.get_by_role('button',name='Close',exact=True).click()
            page.get_by_role('button',name='Back',exact=True).first.click()
            community(self.source_id)
            expect(dialog.get_by_role('button',name='Generate my skeleton')).to_be_visible()
            dialog.get_by_label('Height (cm)',exact=True).fill('170');dialog.get_by_label('Arm span (cm)',exact=True).fill('175')
            captured=[]
            def lose_response(route):
                response=route.fetch();captured.append(response.json());route.abort('failed')
            page.route('**/api/tasks/generate',lose_response,times=1)
            dialog.get_by_role('button',name='Generate my skeleton').click()
            expect(dialog.get_by_role('alert')).to_contain_text('Cannot connect')
            dialog.get_by_role('button',name='Generate my skeleton').click()
            expect(page.get_by_test_id('main-task-state')).to_contain_text('Queued')
            task_id=captured[0]['id'];self.assertEqual(captured[0]['source_video_id'],self.source_id)
            self.assertEqual(len(page.request.get('http://127.0.0.1:5177/api/tasks').json()['items']),1)
            page.screenshot(path=str(self.output/'queued-mobile.png'),full_page=True)
            # The user can leave, reload, and find the server-owned task again.
            page.get_by_role('button',name=re.compile(r'^Community(?: |$)')).last.click();page.reload()
            self.start('worker',[sys.executable,'-m','backend.compute.worker','--once'])
            started=time.monotonic()
            deadline=started+300
            while time.monotonic()<deadline:
                task=page.request.get('http://127.0.0.1:5177/api/tasks/'+task_id).json()
                if task['state'] in ('succeeded','failed'):break
                page.wait_for_timeout(1000)
            self.assertEqual(task['state'],'succeeded',task)
            generation_seconds=time.monotonic()-started
            page.get_by_role('button',name='Notifications',exact=False).click()
            notes=page.get_by_role('dialog',name='Task notifications')
            expect(notes.get_by_role('button',name='Unread · Task completed')).to_be_visible(timeout=15000)
            notes.get_by_role('button',name='Unread · Task completed').click()
            expect(page.get_by_test_id('main-task-state')).to_contain_text('Completed')
            expect(page.get_by_label('Selected skeleton task')).to_contain_text('170 cm height')
            expect(page.get_by_label('Selected skeleton task')).to_contain_text('Baseline: failed')
            video=page.get_by_label('Personal skeleton video',exact=True)
            video.evaluate('(v)=>{v.muted=true;return v.play()}');page.wait_for_timeout(500)
            self.assertGreater(video.evaluate('(v)=>v.currentTime'),0)
            video.evaluate('(v)=>{v.pause();v.currentTime=10}')
            expect(video).to_have_js_property('paused',True)
            page.screenshot(path=str(self.output/'result-mobile.png'),full_page=True)
            page.reload();page.get_by_role('button',name=re.compile(r'^My Page(?: |$)')).click();page.get_by_role('button',name='My Skeletons',exact=True).click()
            page.get_by_role('button',name='Personal skeleton · Completed',exact=False).click()
            expect(page.get_by_label('Personal skeleton video',exact=True)).to_be_visible()
            self.assertEqual(self.alice.get('/api/tasks/'+task_id).status_code,404)
            self.alice.patch('/api/videos/'+self.source_id,json={'visibility':'private'})
            expect(page.get_by_label('Selected skeleton task')).to_have_count(0,timeout=15000)
            self.assertEqual(page.request.get('http://127.0.0.1:5177/api/tasks/'+task_id+'/artifacts/video').status,404)
            (self.output/'validation.json').write_text(json.dumps(dict(source='verified precomputed v5; not reanalyzed',generation=task,generation_seconds=generation_seconds,
                checks=['real source ID','unsupported source blocked','lost-response idempotency','leave/reload','notifications/read','private result playback','refresh recovery','revoked source'],viewport=[390,844]),indent=2))
            browser.close()
        print('Main-page validation:',self.output)

    def test_retry_and_account_isolation(self):
        from playwright.sync_api import sync_playwright,expect
        from backend.database import database
        from backend.compute import service
        self.alice.patch('/api/videos/'+self.source_id,json={'visibility':'public'})
        reference=self.bob.get('/api/tasks/source-analysis/'+self.source_id).json()
        body=dict(kind='generate',video_id=self.source_id,source_analysis_id=reference['source_analysis_id'],source_analysis_version=reference['source_analysis_version'],
            target_body=dict(height_cm=170,arm_span_cm=175,provenance='user_input'))
        response=self.bob.post('/api/tasks/generate',json=body,headers={'Idempotency-Key':'failure-fixture'})
        self.assertEqual(response.status_code,202,response.text);task=response.json()
        with database() as db:
            row=db.execute("UPDATE compute_tasks SET state='running' WHERE id=%s RETURNING *",(task['id'],)).fetchone()
            service.finish(db,row,error=dict(code='INTERRUPTED',message='Test interruption; retry is available',retryable=True))
        with sync_playwright() as p:
            browser=p.chromium.launch();context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page()
            page.goto('http://127.0.0.1:5177')
            page.get_by_label('Username',exact=True).fill('phase2bob');page.get_by_label('Password',exact=True).fill('phase2-local-test-only')
            page.get_by_role('button',name='Sign in',exact=True).last.click()
            page.get_by_role('button',name=re.compile(r'^My Page(?: |$)')).click();page.get_by_role('button',name='My Skeletons',exact=True).click()
            page.get_by_role('button',name='Personal skeleton · Failed',exact=False).click()
            expect(page.get_by_label('Selected skeleton task')).to_contain_text('Test interruption')
            with page.expect_response(lambda r:'/retry' in r.url and r.request.method=='POST') as retried:
                page.get_by_role('button',name='Retry generation',exact=True).click()
            new_task=retried.value.json();self.assertNotEqual(task['id'],new_task['id'])
            self.assertEqual(new_task['retry_of'],task['id'])
            expect(page.get_by_test_id('main-task-state')).to_contain_text('Queued')
            page.screenshot(path=str(self.output/'retry-mobile.png'),full_page=True)
            # Switch the authenticated browser session, then restore the main app.
            me=page.request.get('http://127.0.0.1:5177/api/auth/me').json()
            page.request.post('http://127.0.0.1:5177/api/auth/logout',headers={'Origin':'http://127.0.0.1:5177','X-CSRF-Token':me['csrf_token']})
            page.reload();expect(page.get_by_role('button',name='My Skeletons',exact=True)).to_have_count(0)
            page.get_by_label('Username',exact=True).fill('phase2alice');page.get_by_label('Password',exact=True).fill('phase2-local-test-only')
            page.get_by_role('button',name='Sign in',exact=True).last.click();page.get_by_role('button',name=re.compile(r'^My Page(?: |$)')).click();page.get_by_role('button',name='My Skeletons',exact=True).click()
            expect(page.get_by_role('button',name=re.compile('Personal skeleton'))).to_have_count(0)
            self.assertEqual(page.request.get('http://127.0.0.1:5177/api/tasks/'+new_task['id']).status,404)
            browser.close()
        (self.output/'retry-validation.json').write_text(json.dumps(dict(retry_created=True,account_isolation=True,fixture='Explicit failed task; no solver run'),indent=2))
