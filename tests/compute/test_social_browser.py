"""N3.2 / N3.3 (B side) in a real browser: Community social features end to end.

Starts its own API (8798) and Vite (5178) on a disposable schema, uploads one
public Beta video as alice, then checks touch-phone and desktop flows:

- touch gestures: vertical swipe changes video; right swipe opens the author
  page; left swipe goes back; swipes never trigger the browser's own history
  navigation; a swipe inside the comment sheet does nothing;
- bundled samples take likes, saves and comments, and live comments are labelled in English;
- failure states: comments and the author page show Try again, a failed post
  keeps the draft, a failed like rolls back, and My Page statistics retry;
- account switching on one device never shows the previous account's state;
- desktop right/left drags open and close the author page, Calendar month drags
  stay inside the Calendar, and My Page renders persistent social statistics.

Opt in with BETALAB_TEST_DB=1 BETALAB_SOCIAL_BROWSER=1 (Playwright required;
BETALAB_CHROME may point at a Chrome binary).
"""
import os
import re
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

from support import database as db_support

API, WEB = 8798, 5178
BASE = f'http://127.0.0.1:{WEB}/'
PASSWORD = 'phase2-local-test-only'


@unittest.skipUnless(os.getenv('BETALAB_TEST_DB') == '1' and os.getenv('BETALAB_SOCIAL_BROWSER') == '1',
                     'Requires disposable PostgreSQL and social browser opt-in')
class SocialBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_env = {k: os.environ.get(k) for k in ('UPLOAD_DIR', 'APP_ORIGINS', 'BETALAB_API_TARGET')}
        # The in-process test clients use localhost:8443; the browser uses the Vite origin.
        os.environ['APP_ORIGINS'] = f"http://localhost:8443,{BASE.rstrip('/')}"
        db_support.setup_database(cls)
        os.environ.update(UPLOAD_DIR=str(cls.videos.UPLOAD_DIR), BETALAB_API_TARGET=f'http://127.0.0.1:{API}')
        from backend.database import database
        with database() as db:
            db.execute("INSERT INTO routes(id,gym_id,name,grade) VALUES ('r1','test-gym','Corner Study','V3')")
        with cls.video.open('rb') as stream:
            response = cls.alice.post('/api/videos', data={'route_id': 'r1', 'visibility': 'public',
                                                           'share_as_beta': 'true', 'title': 'Alice corner send'},
                                      files={'video': ('clip.mp4', stream, 'video/mp4')})
        assert response.status_code == 201, response.text
        cls.video_id = response.json()['id']
        cls.processes, cls.logs = [], []
        logs = Path(cls.directory.name)
        node = os.environ.get('BETALAB_NODE', 'node')
        for name, cmd in (('api', [sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', str(API)]),
                          ('vite', [node, 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(WEB), '--strictPort'])):
            log = (logs / f'{name}.log').open('w')
            cls.logs.append(log)
            cls.processes.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        for url in (f'http://127.0.0.1:{API}/api/health', BASE):
            for _ in range(150):
                try:
                    with urlopen(url) as r:
                        if r.status == 200:
                            break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Server failed: ' + url)

    @classmethod
    def tearDownClass(cls):
        for process in reversed(cls.processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        for log in cls.logs:
            log.close()
        for key, value in cls.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        db_support.teardown_database(cls)

    # ------------------------------------------------------------------ helpers

    def login(self, page, user):
        page.goto(BASE)
        page.get_by_label('Username', exact=True).fill(user)
        page.get_by_label('Password', exact=True).fill(PASSWORD)
        page.get_by_role('button', name='Sign in', exact=True).last.click()
        page.wait_for_selector('text=Go Climbing')

    def sign_out(self, page):
        page.goto(BASE)
        page.wait_for_selector('text=Go Climbing')
        page.get_by_role('button', name=re.compile('^My Page')).click()
        page.get_by_role('button', name='Edit profile').click()
        page.get_by_role('button', name='Sign out').click()
        page.get_by_label('Username', exact=True).wait_for()

    @staticmethod
    def nav(page, label):
        page.locator('nav').get_by_text(label, exact=True).click()

    def open_video(self, page, title, video_id):
        page.goto(BASE)
        page.wait_for_selector('text=Go Climbing')
        self.nav(page, 'Community')
        page.locator('.community-feed-card', has_text=title).click()
        slide = page.locator(f'#community-video-{video_id}')
        slide.wait_for()
        return slide

    @staticmethod
    def swipe(page, cdp, x0, y0, x1, y1, steps=8):
        """A real touch gesture through Chrome's input pipeline (touch events, scrolling and history swipes)."""
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
        for i in range(1, steps + 1):
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [
                {'x': x0 + (x1 - x0) * i / steps, 'y': y0 + (y1 - y0) * i / steps}]})
            page.wait_for_timeout(16)
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        page.wait_for_timeout(500)

    # -------------------------------------------------------------------- test

    def test_phone_and_desktop_gestures_failures_and_account_switch(self):
        from playwright.sync_api import expect, sync_playwright
        errors = []
        with sync_playwright() as p:
            chrome = os.environ.get('BETALAB_CHROME')
            browser = p.chromium.launch(**({'executable_path': chrome} if chrome else {}),
                                        args=['--autoplay-policy=no-user-gesture-required'])
            phone = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
            page = phone.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            cdp = phone.new_cdp_session(page)
            self.login(page, 'phase2bob')

            # The list exposes Follow beside the author and a real server-filtered Following feed.
            self.nav(page, 'Community')
            entry = page.locator('.community-feed-entry', has_text='Alice corner send')
            entry.get_by_role('button', name='Follow phase2alice').click()
            expect(entry.get_by_role('button', name='Unfollow phase2alice')).to_be_visible()
            audience = page.locator('.community-audience-tabs')
            audience.get_by_role('button', name='Following', exact=True).click()
            expect(page.locator('.community-feed-card', has_text='Alice corner send')).to_have_count(1)
            expect(page.locator('.community-feed-badge.is-preset')).to_have_count(0)
            page.locator('.community-feed-entry', has_text='Alice corner send').get_by_role(
                'button', name='Unfollow phase2alice').click()
            expect(page.get_by_text('No videos from people you follow yet')).to_be_visible()
            audience.get_by_role('button', name='All', exact=True).click()

            # Touch gestures (N3.2)
            slide = self.open_video(page, 'Alice corner send', self.video_id)
            expect(slide.get_by_role('slider', name='Video timeline')).to_be_visible()
            expect(slide.get_by_role('slider', name='Video timeline')).to_be_enabled()
            scroller = page.locator('.community-tiktok-scroll')
            before = scroller.evaluate('e => e.scrollTop')
            self.swipe(page, cdp, 200, 600, 205, 200)
            self.assertGreater(scroller.evaluate('e => e.scrollTop'), before + 200, 'vertical swipe changes video')
            expect(page.locator('.author-page')).to_have_count(0)
            self.swipe(page, cdp, 200, 200, 205, 640)
            expect(slide).to_be_in_viewport(ratio=0.6)
            self.swipe(page, cdp, 60, 420, 300, 430)
            self.assertTrue(page.url.startswith(BASE), 'a right swipe must not trigger browser history navigation')
            expect(page.locator('.author-page').get_by_role('heading', name='phase2alice')).to_be_visible()
            self.swipe(page, cdp, 320, 420, 60, 425)
            expect(page.locator(f'#community-video-{self.video_id}')).to_be_visible()
            slide.get_by_role('button', name=re.compile('^Comments')).click()
            sheet = page.get_by_role('dialog', name='Comments')
            box = sheet.bounding_box()
            self.swipe(page, cdp, box['x'] + 40, box['y'] + 40, box['x'] + 300, box['y'] + 45)
            self.assertTrue(page.url.startswith(BASE))
            expect(sheet).to_be_visible()
            expect(page.locator('.author-page')).to_have_count(0)
            sheet.get_by_role('button', name='Close comments').click()

            # Bundled samples are interactive; no Chinese in the viewer (task 17)
            sample = self.open_video(page, "Nora P.'s beta", 'preset-beta-b1')
            sample.get_by_role('button', name=re.compile(r'^Like video \(0 likes\)$')).click()
            expect(sample.get_by_role('button', name='Like video (1 likes)')).to_have_attribute('aria-pressed', 'true')
            sample.get_by_role('button', name='Save video').click()
            page.wait_for_selector('text=Saved to My Library')
            expect(sample.get_by_role('button', name='Show live comments on the video')).to_be_visible()
            self.assertIsNone(re.search(r'[㐀-鿿]', page.evaluate('document.body.innerText')))

            # Failure states (N3.3)
            page.route('**/api/videos/*/comments*', lambda route: route.abort())
            slide = self.open_video(page, 'Alice corner send', self.video_id)
            slide.get_by_role('button', name=re.compile('^Comments')).click()
            sheet = page.get_by_role('dialog', name='Comments')
            expect(sheet.get_by_role('button', name='Try again')).to_be_visible()
            page.unroute('**/api/videos/*/comments*')
            sheet.get_by_role('button', name='Try again').click()
            expect(sheet.get_by_label('Write a comment')).to_be_visible()
            page.route('**/api/videos/*/comments', lambda route: route.fulfill(status=500, json={'error': {'message': 'Server unavailable'}})
                       if route.request.method == 'POST' else route.continue_())
            sheet.get_by_label('Write a comment').fill('Draft that must survive')
            sheet.get_by_role('button', name='Post').click()
            expect(sheet.get_by_role('alert')).to_contain_text('Server unavailable')
            expect(sheet.get_by_label('Write a comment')).to_have_value('Draft that must survive')
            page.unroute('**/api/videos/*/comments')
            sheet.get_by_role('button', name='Close comments').click()
            like = slide.get_by_role('button', name=re.compile('^Like video'))
            page.route('**/api/videos/*/like', lambda route: route.fulfill(status=500, json={'error': {'message': 'Like failed'}}))
            like.click()
            page.wait_for_selector('text=Like failed')
            expect(like).to_have_attribute('aria-pressed', 'false')
            page.unroute('**/api/videos/*/like')
            page.route('**/api/users/*/profile*', lambda route: route.abort())
            slide.get_by_role('button', name="Open phase2alice's page").click()
            retry = page.locator('.author-page').get_by_role('button', name='Try again')
            expect(retry).to_be_visible()
            page.unroute('**/api/users/*/profile*')
            retry.click()
            expect(page.locator('.author-page').get_by_role('heading', name='phase2alice')).to_be_visible()

            # Account switching on one device (N3.3)
            slide = self.open_video(page, 'Alice corner send', self.video_id)
            slide.get_by_role('button', name=re.compile('^Like video')).click()
            slide.get_by_role('button', name='Save video').click()
            slide.locator('.follow-button').click()
            expect(slide.locator('.follow-button')).to_have_attribute('aria-pressed', 'true')
            self.sign_out(page)
            self.login(page, 'phase2alice')
            slide = self.open_video(page, 'Alice corner send', self.video_id)
            expect(slide.get_by_role('button', name=re.compile('^Like video'))).to_have_attribute('aria-pressed', 'false')
            expect(slide.get_by_role('button', name='Save video')).to_have_attribute('aria-pressed', 'false')
            expect(slide.locator('.follow-button')).to_have_count(0)  # your own video
            expect(slide.get_by_role('button', name=re.compile(r'^Like video \(1 likes\)$'))).to_be_visible()
            page.goto(BASE)
            page.wait_for_selector('text=Go Climbing')
            page.route('**/api/me/social-stats', lambda route: route.abort())
            page.get_by_role('button', name=re.compile('^My Page')).click()
            stats_error = page.locator('.my-page-stats-error')
            expect(stats_error).to_contain_text('Cannot connect')
            page.unroute('**/api/me/social-stats')
            stats_error.get_by_role('button', name='Try again').click()
            stats = page.get_by_label('Social statistics')
            expect(stats.locator('div', has_text='Likes received').locator('strong')).to_have_text('1')
            expect(stats.locator('div', has_text='Saves received').locator('strong')).to_have_text('1')
            expect(stats.locator('div', has_text='Followers').locator('strong')).to_have_text('1')
            expect(stats.locator('div', has_text='Following').locator('strong')).to_have_text('0')
            page.get_by_role('button', name='Saved Beta').click()
            expect(page.get_by_text("Nora P.'s beta")).to_have_count(0)
            self.sign_out(page)
            self.login(page, 'phase2bob')
            slide = self.open_video(page, 'Alice corner send', self.video_id)
            expect(slide.get_by_role('button', name=re.compile('^Like video'))).to_have_attribute('aria-pressed', 'true')
            expect(slide.locator('.follow-button')).to_have_attribute('aria-pressed', 'true')

            # Desktop pointer gestures and the Calendar's isolated month drag (N3.2).
            desktop = browser.new_context(viewport={'width': 1280, 'height': 900})
            desktop_page = desktop.new_page()
            desktop_page.on('pageerror', lambda error: errors.append(str(error)))
            self.login(desktop_page, 'phase2bob')
            desktop_slide = self.open_video(desktop_page, 'Alice corner send', self.video_id)
            box = desktop_slide.bounding_box()
            desktop_page.mouse.move(box['x'] + 70, box['y'] + box['height'] / 2)
            desktop_page.mouse.down()
            desktop_page.mouse.move(box['x'] + 270, box['y'] + box['height'] / 2, steps=8)
            desktop_page.mouse.up()
            expect(desktop_page.locator('.author-page').get_by_role('heading', name='phase2alice')).to_be_visible()
            author = desktop_page.locator('.author-page').bounding_box()
            desktop_page.mouse.move(author['x'] + author['width'] - 50, author['y'] + author['height'] / 2)
            desktop_page.mouse.down()
            desktop_page.mouse.move(author['x'] + 60, author['y'] + author['height'] / 2, steps=8)
            desktop_page.mouse.up()
            expect(desktop_page.locator(f'#community-video-{self.video_id}')).to_be_visible()

            desktop_page.goto(BASE)
            desktop_page.wait_for_selector('text=Go Climbing')
            desktop_page.get_by_role('button', name=re.compile('^My Page')).click()
            desktop_page.get_by_role('button', name='My Calendar').click()
            month_heading = desktop_page.locator('.calendar-month-navigation h3')
            before_month = month_heading.inner_text()
            calendar = desktop_page.get_by_label('Monthly activity').bounding_box()
            next_month = desktop_page.get_by_role('button', name='Next month')
            go_forward = not next_month.is_disabled()
            start_x = calendar['x'] + (calendar['width'] * (.8 if go_forward else .2))
            end_x = calendar['x'] + (calendar['width'] * (.2 if go_forward else .8))
            y = calendar['y'] + calendar['height'] / 2
            desktop_page.mouse.move(start_x, y)
            desktop_page.mouse.down()
            desktop_page.mouse.move(end_x, y, steps=8)
            desktop_page.mouse.up()
            expect(month_heading).not_to_have_text(before_month)
            desktop.close()
            browser.close()
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
