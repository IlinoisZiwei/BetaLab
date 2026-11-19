"""Page/hook split acceptance with real HTTP video mutations; no solver execution."""
import os
import re
import unittest
from support import browser as support

@unittest.skipUnless(os.getenv('BETALAB_VIDEO_BROWSER_TEST')=='1','Requires video management browser opt-in')
class VideoManagementBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): support.setup_browser(cls)
    @classmethod
    def tearDownClass(cls): support.teardown_browser(cls)
    @classmethod
    def start(cls,name,cmd): support.start(cls,name,cmd)

    def test_navigation_sharing_delete_refresh_and_account_switch(self):
        from playwright.sync_api import sync_playwright,expect
        with sync_playwright() as p:
            browser=p.chromium.launch();page=browser.new_page(viewport={'width':390,'height':844})
            page.goto('http://127.0.0.1:5177')
            def login(name):
                page.get_by_label('Username',exact=True).fill(name)
                page.get_by_label('Password',exact=True).fill('phase2-local-test-only')
                page.get_by_role('button',name='Sign in',exact=True).last.click()
                expect(page.get_by_role('button',name='Profile and account')).to_be_visible()
            def home(): page.get_by_role('button',name='Home',exact=True).click()
            def logout():
                home();page.get_by_role('button',name='Profile and account').click()
                page.get_by_role('button',name='Sign out',exact=True).click()
                expect(page.get_by_label('Username',exact=True)).to_be_visible()
            def library(): page.get_by_role('button',name=re.compile('^My Library')).last.click()
            def open_attempt():
                page.locator('.attempt-gym-group > summary').filter(has_text='Test Gym').click()
                page.locator('.attempt-route-group > summary').filter(has_text='Trial2').click()
                page.get_by_role('button',name=re.compile(title)).click()
            login('phase2bob')
            page.get_by_role('button',name=re.compile('^Go Climbing')).last.click()
            page.locator('.gym-card').filter(has_text='Test Gym').click()
            page.locator('.route-open').filter(has_text='Trial2').click()
            page.get_by_role('button',name='Back',exact=True).first.click()
            page.locator('.route-open').filter(has_text='Trial2').click()
            page.get_by_role('button',name='Add my video',exact=True).click()
            page.locator('input[type=file]').set_input_files(str(self.video))
            title='Round two state isolation'
            page.get_by_label('Title',exact=True).fill(title)
            page.get_by_role('radio',name='Private',exact=True).check()
            with page.expect_response(lambda r:r.url.endswith('/api/videos') and r.request.method=='POST') as upload:
                page.get_by_role('button',name='Upload video',exact=True).click()
            video_id=upload.value.json()['id']
            def visibility(value):
                page.get_by_role('button',name='Manage my video',exact=True).click()
                page.get_by_role('button',name='Change visibility',exact=True).click()
                with page.expect_response(lambda r:r.url.endswith('/api/videos/'+video_id) and r.request.method=='PATCH') as update:
                    page.get_by_role('button',name=value,exact=True).click()
                self.assertEqual(update.value.status,200)
                page.get_by_role('button',name='Done',exact=True).click()
            visibility('Public')
            self.assertEqual(self.alice.get('/api/videos/'+video_id).status_code,200)
            page.get_by_role('button',name='Community',exact=True).last.click()
            expect(page.locator('.community-feed-card').filter(has_text=title)).to_have_count(1)
            library();open_attempt()
            visibility('Private')
            self.assertEqual(self.alice.get('/api/videos/'+video_id+'/content').status_code,404)
            page.get_by_role('button',name='Community',exact=True).last.click()
            expect(page.locator('.community-feed-card').filter(has_text=title)).to_have_count(0)
            page.reload();library();open_attempt()
            page.get_by_role('button',name='Manage my video',exact=True).click()
            page.get_by_role('button',name='Delete video',exact=True).click()
            page.get_by_role('button',name='Delete video',exact=True).click()
            expect(page.get_by_role('button',name='Add my video',exact=True)).to_be_visible()
            library();expect(page.get_by_role('button',name=re.compile(title))).to_have_count(0)
            page.reload();library();expect(page.get_by_role('button',name=re.compile(title))).to_have_count(0)
            logout();login('phase2alice');library()
            expect(page.get_by_role('button',name=re.compile(title))).to_have_count(0)
            self.assertEqual(page.request.get('http://127.0.0.1:5177/api/videos/'+video_id).status,404)
            browser.close()
