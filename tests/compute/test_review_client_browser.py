"""Review-page shared-client regression using verified v5 artifacts, no solver run."""
import os
from pathlib import Path
import unittest
from support import browser as support

@unittest.skipUnless(os.getenv('BETALAB_REVIEW_CLIENT_TEST')=='1','Requires review browser opt-in')
class ReviewClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): support.setup_browser(cls)
    @classmethod
    def tearDownClass(cls): support.teardown_browser(cls)
    @classmethod
    def start(cls,name,cmd): support.start(cls,name,cmd)

    def test_shared_client_login_upload_notifications_and_playback(self):
        from playwright.sync_api import sync_playwright,expect
        with sync_playwright() as p:
            browser=p.chromium.launch();page=browser.new_page()
            page.goto('http://127.0.0.1:5177/compute.html')
            page.get_by_label('用户名',exact=True).fill('phase2alice')
            page.get_by_label('密码',exact=True).fill('phase2-local-test-only')
            page.get_by_role('button',name='登录',exact=True).click()
            page.get_by_role('button',name='源分析 · succeeded',exact=False).click()
            video=page.get_by_label('生成结果',exact=True)
            video.evaluate('(v)=>{v.muted=true;return v.play()}')
            page.wait_for_timeout(300);self.assertGreater(video.evaluate('(v)=>v.currentTime'),0)
            page.locator('button[data-frame]').first.click()
            expect(video).to_have_js_property('paused',True)
            page.get_by_role('button',name='未读 · 计算完成',exact=False).click()
            expect(page.get_by_role('button',name='已读 · 计算完成',exact=False)).to_be_visible()
            page.get_by_label('Trial 2 视频',exact=True).set_input_files(str(Path(os.environ['BETA_TRANSLATOR_ROOT'])/'videos/trial2.mp4'))
            with page.expect_response(lambda r:r.url.endswith('/api/tasks/analyze') and r.request.method=='POST') as created:
                page.get_by_role('button',name='上传并分析',exact=True).click()
            self.assertEqual(created.value.status,202)
            expect(page.get_by_test_id('task-state')).to_contain_text('queued')
            page.get_by_role('button',name='退出',exact=True).click()
            expect(page.get_by_role('button',name='登录',exact=True)).to_be_visible()
            browser.close()
