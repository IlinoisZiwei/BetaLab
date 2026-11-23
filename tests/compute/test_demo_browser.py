"""Opt-in local showcase smoke test; credentials remain in ignored demo config.
Only saves an already-prepared demo, idempotently; never submits computation.
"""
import json
import os
from pathlib import Path
import re
import unittest


@unittest.skipUnless(os.getenv('BETALAB_DEMO_BROWSER') == '1', 'Requires seeded local showcase/API/Vite')
class DemoBrowserTest(unittest.TestCase):
    def test_community_save_reopen_and_wall_images(self):
        from playwright.sync_api import sync_playwright, expect
        config=json.loads(Path('demo/showcase.local.json').read_text())
        receipt=json.loads(Path('demo/showcase-receipt.local.json').read_text())
        account=config['accounts'][0]
        output=Path('backend/compute/runs/showcase-check');output.mkdir(exist_ok=True)
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page(viewport={'width':390,'height':844})
            page.goto('http://127.0.0.1:5173')
            page.get_by_label('Username',exact=True).fill(account['username'])
            page.get_by_label('Password',exact=True).fill(account['password'])
            page.get_by_role('button',name='Sign in',exact=True).last.click()
            page.get_by_role('button',name=re.compile(r'^Community(?: |$)')).click()
            case=receipt[0]
            page.locator('.community-feed-card').filter(has_text=case['title']).click()
            page.locator('#community-video-'+case['video_id']).get_by_role('button',name='Generate beta',exact=True).click()
            dialog=page.get_by_role('dialog',name='Generate personal skeleton')
            expect(dialog).to_contain_text('Pre-generated demonstration')
            expect(dialog.get_by_role('button',name='Generate my skeleton')).to_have_count(0)
            player=dialog.get_by_label('Prepared skeleton video')
            player.evaluate('(video) => video.play()')
            page.wait_for_function("() => [...document.querySelectorAll('video')].some(v => v.getAttribute('aria-label') === 'Prepared skeleton video' && v.currentTime > 0)")
            player.evaluate('(video) => video.pause()')
            page.screenshot(path=str(output/'community-demo.png'))
            dialog.get_by_role('button',name='Save demo to My Skeletons').click()
            page.reload()
            page.get_by_role('button',name=re.compile(r'^My Page(?: |$)')).click()
            page.get_by_role('button',name='My Skeletons',exact=True).click()
            saved=page.get_by_label('Saved demonstrations',exact=True)
            for case in receipt:
                saved.get_by_role('button',name=case['title']+' · Pre-generated',exact=True).click()
                expect(saved.get_by_label('Prepared skeleton demonstration')).to_contain_text(case['title'])
                player=saved.get_by_label('Prepared skeleton video')
                player.evaluate('(video) => video.load()')
                page.wait_for_function("() => [...document.querySelectorAll('video')].some(v => v.getAttribute('aria-label') === 'Prepared skeleton video' && v.readyState >= 2)")
                size=player.evaluate('(v) => [v.videoWidth,v.videoHeight,v.duration]')
                self.assertEqual(size[:2],[960,1180]);self.assertGreater(size[2],10)
            for route in ('demo-trial1','demo-trial3'):
                response=page.request.get('http://127.0.0.1:5173/api/demo-previews/route/'+route+'/wall')
                self.assertEqual(response.status,200)
                self.assertEqual(response.headers['content-type'],'image/jpeg')
            page.screenshot(path=str(output/'saved-demos.png'))
            page.get_by_role('button',name='Go Climbing',exact=True).click()
            page.get_by_role('button',name=re.compile('Movement Fishtown')).click()
            for title in ('Trial 1 · Demo Study','Trial 3 · Demo Study'):
                card=page.locator('.route-card').filter(has_text=title)
                expect(card).to_be_visible()
                image=card.locator('img')
                expect(image).to_be_visible()
                image.scroll_into_view_if_needed()
                image.evaluate('(img) => img.decode()')
                self.assertTrue(image.evaluate('(img) => img.complete && img.naturalWidth > 0'))
            page.screenshot(path=str(output/'demo-routes.png'))
            browser.close()
