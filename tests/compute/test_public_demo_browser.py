"""Public demo acceptance: fresh browser, no API/login, all media and seek paths."""
import os
from pathlib import Path
import unittest


@unittest.skipUnless(os.getenv('BETALAB_PUBLIC_DEMO_URL'), 'Requires built or deployed public demo')
class PublicDemoTest(unittest.TestCase):
    def test_anonymous_playback_desktop_and_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        output=Path('backend/compute/runs/public-demo-check');output.mkdir(exist_ok=True)
        with sync_playwright() as p:
            browser=p.chromium.launch()
            for width,height in [(1280,1000),(390,844)]:
                context=browser.new_context(viewport={'width':width,'height':height})
                page=context.new_page();api_requests=[]
                page.on('request',lambda r: api_requests.append(r.url) if '/api/' in r.url else None)
                response=page.goto(os.environ['BETALAB_PUBLIC_DEMO_URL'])
                self.assertEqual(response.status,200)
                expect(page.get_by_text('Public demo · No sign-in')).to_be_visible()
                for case in ['trial1','trial2','trial3']:
                    page.locator(f'[data-case="{case}"]').click()
                    player=page.get_by_label('Skeleton and original video comparison')
                    player.evaluate('(v) => v.play()')
                    page.wait_for_function('document.querySelector("video").currentTime > 0')
                    player.evaluate('(v) => { v.pause(); v.currentTime = 5; }')
                    page.wait_for_function('Math.abs(document.querySelector("video").currentTime - 5) < .2 && !document.querySelector("video").seeking')
                    self.assertEqual(player.evaluate('(v) => [v.videoWidth,v.videoHeight]'),[960,1180])
                    self.assertGreater(player.evaluate('(v) => v.duration'),10)
                self.assertEqual(api_requests,[])
                self.assertEqual(context.cookies(),[])
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.reload()
                expect(page.locator('[data-case="trial3"]')).to_have_attribute('aria-pressed','true')
                page.screenshot(path=str(output/f'demo-{width}.png'),full_page=True)
                context.close()
            browser.close()
