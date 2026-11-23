"""Global alignment editor uses synthetic measured geometry, never real-video claims."""
import re
import json
import os
import unittest
from support import browser as support

@unittest.skipUnless(os.getenv('BETALAB_WORLD_BROWSER')=='1','Requires global alignment browser opt-in')
class WorldBrowserTest(unittest.TestCase):
    historical_display_only = True
    @classmethod
    def setUpClass(cls): support.setup_browser(cls)
    @classmethod
    def tearDownClass(cls): support.teardown_browser(cls)
    @classmethod
    def start(cls,name,cmd): support.start(cls,name,cmd)

    def test_missing_data_save_overlay_and_refresh(self):
        from support.world_api import prepare
        from playwright.sync_api import sync_playwright,expect
        with self.video.open('rb') as stream:
            uploaded = self.alice.post('/api/videos',data=dict(route_id='r1',visibility='private',title='SYNTHETIC global test'),
                files={'video':('test.mp4',stream,'video/mp4')}).json()
        task,review = prepare(self.alice,uploaded['id'],self.output)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width':390,'height':844})
            page.goto('http://127.0.0.1:5177')
            page.get_by_label('Username',exact=True).fill('phase2alice')
            page.get_by_label('Password',exact=True).fill('phase2-local-test-only')
            page.get_by_role('button',name='Sign in',exact=True).last.click()
            page.get_by_role('button',name=re.compile(r'^My Page(?: |$)')).click();page.get_by_role('button',name='My Skeletons',exact=True).click()
            page.get_by_role('button',name='Source analysis · Completed',exact=False).first.click()
            panel = page.get_by_label('Global wall alignment',exact=True)
            expect(panel).to_be_visible()
            expect(panel).to_contain_text('Handheld video')
            page.get_by_role('button',name='Validate and save global alignment',exact=True).click()
            expect(panel.get_by_role('alert')).to_be_visible()
            page.get_by_label('Global geometry JSON',exact=True).fill(json.dumps(review))
            page.get_by_role('button',name='Validate and save global alignment',exact=True).click()
            expect(panel).to_contain_text('Global alignment version saved')
            expect(panel).to_contain_text('4 / 4 camera-aligned frames')
            expect(page.get_by_label('Reference camera reprojection',exact=True)).to_be_visible()
            url = page.get_by_role('link',name='Export pinned world coordinates',exact=True).get_attribute('href')
            exported = page.request.get('http://127.0.0.1:5177'+url).json()
            self.assertFalse(exported['aligned']['summary']['pose_depth_reconstructed'])
            self.assertEqual(len(exported['aligned']['contacts']),16)
            page.get_by_label('Reference camera reprojection',exact=True).scroll_into_view_if_needed()
            page.screenshot(path=str(self.output/'world-review-mobile.png'),full_page=True)
            page.reload()
            page.get_by_role('button',name=re.compile(r'^My Page(?: |$)')).click();page.get_by_role('button',name='My Skeletons',exact=True).click()
            page.get_by_role('button',name='Source analysis · Completed',exact=False).first.click()
            expect(panel).to_contain_text('4 / 4 camera-aligned frames')
            page.set_viewport_size({'width':1440,'height':1000})
            page.get_by_label('Reference camera reprojection',exact=True).scroll_into_view_if_needed()
            page.screenshot(path=str(self.output/'world-review-desktop.png'),full_page=True)
            browser.close()
        print('Synthetic global alignment browser:',self.output)
