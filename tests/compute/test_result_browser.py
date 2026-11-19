"""Classification and native-time playback on verified existing v5 output.
No scientific analysis or technique comparison is run by this test.
"""
import json
import os
import re
import unittest
from support import browser as community

@unittest.skipUnless(os.getenv('BETALAB_RESULT_BROWSER_TEST')=='1','Requires result browser opt-in')
class ResultBrowserTest(unittest.TestCase):
    @classmethod
    def start(cls,name,cmd): community.start(cls,name,cmd)
    @classmethod
    def setUpClass(cls):community.setup_browser(cls)
    @classmethod
    def tearDownClass(cls):community.teardown_browser(cls)

    def test_real_diagnostics_examples_and_no_comparison(self):
        from playwright.sync_api import sync_playwright,expect
        with sync_playwright() as p:
            browser=p.chromium.launch();context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page()
            page.goto('http://127.0.0.1:5177')
            page.get_by_label('Username',exact=True).fill('phase2alice');page.get_by_label('Password',exact=True).fill('phase2-local-test-only')
            page.get_by_role('button',name='Sign in',exact=True).last.click()
            page.get_by_role('button',name=re.compile(r'^My Library(?: |$)')).click();page.get_by_role('button',name='My skeletons',exact=True).click()
            page.get_by_role('button',name=re.compile('Source analysis · Completed')).click()
            categories=page.get_by_label('Result categories',exact=True)
            expect(categories.get_by_role('heading',name='Diagnostic issues',exact=True)).to_be_visible()
            expect(categories.get_by_label('Technique results',exact=True)).to_contain_text('No real technique comparison results')
            self.assertEqual(categories.get_by_label('Technique results',exact=True).locator('article').count(),0)
            task=page.request.get('http://127.0.0.1:5177/api/tasks').json()['items'][0]
            moment=next(m for m in task['result']['moments'] if m['kind']=='contact_gap' and m['at_seconds']>1)
            player=page.get_by_label('Source analysis video',exact=True)
            button=categories.locator('[data-moment="'+moment['id']+'"]')
            # First click must work with unloaded metadata; repeat must seek again.
            player.evaluate('(v)=>{let src=v.src;v.pause();v.removeAttribute("src");v.load();v.preload="none";v.src=src}')
            button.click()
            page.wait_for_function("seconds => Math.abs(document.querySelector('video[aria-label=\"Source analysis video\"]').currentTime-seconds)<.001",arg=moment['at_seconds'],timeout=15000)
            player.evaluate('(v)=>{v.currentTime=0}')
            button.click();page.wait_for_function("seconds => Math.abs(document.querySelector('video[aria-label=\"Source analysis video\"]').currentTime-seconds)<.001",arg=moment['at_seconds'])
            expect(player).to_have_js_property('paused',True)
            categories.get_by_text('Example suggestions · illustration only',exact=True).click()
            examples=categories.locator('.result-examples')
            expect(examples).to_contain_text('not observations or advice for your uploaded video')
            self.assertEqual(examples.locator('button,a').count(),0)
            page.screenshot(path=str(self.output/'result-categories-mobile.png'),full_page=True)
            # Reopen the actual owned upload in Workspace: it uses the same result panel.
            page.locator('.attempt-gym-group > summary').filter(has_text='Test Gym').click()
            page.locator('.attempt-route-group > summary').filter(has_text='Trial2').click()
            page.locator('.history-row').filter(has_text='Verified Trial2 source').click()
            expect(page.get_by_role('tab',name='Results & diagnostics')).to_be_visible()
            page.get_by_role('tab',name='Results & diagnostics').click()
            expect(page.get_by_label('Diagnostic issues',exact=True)).to_contain_text(moment['title'])
            expect(page.get_by_label('Source analysis video',exact=True)).to_be_visible()
            page.screenshot(path=str(self.output/'workspace-diagnostics-mobile.png'),full_page=True)
            # Another owned upload with no analysis must not inherit the previous result.
            page.get_by_role('button',name=re.compile(r'^My Library(?: |$)')).click();page.get_by_role('button',name='My skeletons',exact=True).click()
            page.locator('.attempt-gym-group > summary').filter(has_text='Test Gym').click()
            page.locator('.attempt-route-group > summary').filter(has_text='Trial2').click()
            page.locator('.history-row').filter(has_text='No analysis video').click()
            page.get_by_role('tab',name='Results & diagnostics').click()
            expect(page.get_by_label('Diagnostic issues',exact=True)).to_contain_text('No completed analysis')
            expect(page.get_by_label('Source analysis video',exact=True)).to_have_count(0)
            (self.output/'result-validation.json').write_text(json.dumps(dict(
                source='verified precomputed v5',scientific_analysis_run=False,technique_comparison_run=False,
                checks=['separate result categories','real native-time diagnostic','unloaded metadata seek','repeated seek','examples cannot seek uploaded media','no invented techniques','workspace integration','source-switch clears results']),indent=2))
            browser.close()
        print('Result classification validation:',self.output)
