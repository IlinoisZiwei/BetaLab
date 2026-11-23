"""Latest My Page/Community lifecycle with explicit mock compute, two accounts.
No Trial2 refit, technique comparison or claim of scientific correctness.
"""
import os
import re
import unittest
from support import browser as support

@unittest.skipUnless(os.getenv('BETALAB_CURRENT_FLOW')=='1','Requires isolated browser test')
class CurrentFlowTest(unittest.TestCase):
    historical_display_only=True
    @classmethod
    def start(cls,name,cmd): support.start(cls,name,cmd)
    @classmethod
    def setUpClass(cls): support.setup_browser(cls)
    @classmethod
    def tearDownClass(cls): support.teardown_browser(cls)

    def test_two_accounts_generate_notify_reopen_and_revoke(self):
        from backend.compute.worker import Worker
        from backend.database import database
        from playwright.sync_api import sync_playwright,expect
        # This suite uses a labeled mock source; historical fixture is not reused.
        os.environ['COMPUTE_MODE']='mock'
        with database() as db: db.execute('TRUNCATE compute_tasks CASCADE')
        request=dict(kind='analyze',video_id=self.source_id,route_id='r1',calibration=dict(version='test',reference_frame=0,evidence_key='test'))
        response=self.alice.post('/api/tasks/analyze',json=request,headers={'Idempotency-Key':'new-ui-source'})
        self.assertEqual(response.status_code,202,response.text)
        with Worker() as worker: self.assertTrue(worker.run_one())
        # API process started in real mode; switch just its launch configuration.
        import signal
        for process in self.processes:
            os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=10)
        self.processes=[]
        import sys
        self.start('mock-api',[sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8797'])
        self.start('mock-vite',[os.environ['BETALAB_NODE'],'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5177'])
        from urllib.request import urlopen
        import time
        for _ in range(100):
            try:
                urlopen('http://127.0.0.1:5177');urlopen('http://127.0.0.1:8797/api/health');break
            except OSError: time.sleep(.1)
        with sync_playwright() as p:
            browser=p.chromium.launch();page=browser.new_page(viewport={'width':390,'height':844})
            page.goto('http://127.0.0.1:5177')
            page.get_by_label('Username',exact=True).fill('phase2bob');page.get_by_label('Password',exact=True).fill('phase2-local-test-only')
            page.get_by_role('button',name='Sign in',exact=True).last.click()
            page.get_by_role('button',name=re.compile(r'^Community(?: |$)')).click()
            page.locator('.community-feed-card').filter(has_text='Verified Trial2 source').click()
            page.locator('#community-video-'+self.source_id).get_by_role('button',name='Generate beta',exact=True).click()
            dialog=page.get_by_role('dialog',name='Generate personal skeleton')
            expect(dialog).to_contain_text('Mock analysis')
            dialog.get_by_label('Height (cm)',exact=True).fill('170');dialog.get_by_label('Arm span (cm)',exact=True).fill('175')
            dialog.get_by_role('button',name='Generate my skeleton',exact=True).click()
            expect(page.get_by_test_id('main-task-state')).to_contain_text('Queued')
            expect(page.get_by_label('Task progress',exact=True)).to_contain_text('includes queue time')
            with Worker() as worker:self.assertTrue(worker.run_one())
            expect(page.get_by_test_id('main-task-state')).to_contain_text('Completed',timeout=15000)
            page.get_by_role('button',name=re.compile('^Notifications,')).click()
            page.get_by_role('button',name='Unread · Task completed',exact=True).click()
            expect(page.get_by_label('Selected skeleton task')).to_contain_text('170 cm height')
            page.reload();page.get_by_role('button',name=re.compile(r'^My Page(?: |$)')).click()
            page.get_by_role('button',name='My Skeletons',exact=True).click()
            page.get_by_role('button',name=re.compile('Personal skeleton · Completed')).click()
            expect(page.get_by_label('Selected skeleton task')).to_contain_text('Mock task')
            expect(page.get_by_role('button',name='Browse routes',exact=True)).to_have_count(0)
            page.screenshot(path=str(self.output/'latest-mock-flow.png'),full_page=True)
            response=self.alice.patch('/api/videos/'+self.source_id,json={'visibility':'private'})
            self.assertEqual(response.status_code,200,response.text)
            expect(page.get_by_label('Selected skeleton task')).to_have_count(0,timeout=15000)
            browser.close()
