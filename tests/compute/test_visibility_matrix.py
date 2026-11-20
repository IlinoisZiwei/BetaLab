"""N3.1 (B side): every video and social read path follows one visibility rule.

Owner / another signed-in user / anonymous against Private, Public and
Public + Share as beta videos uploaded through the real API, including direct
requests (content URL, comments, danmaku, reactions, saved list, author page).
Run with BETALAB_TEST_DB=1 against a disposable database (see README, Testing).
"""
import os
import unittest

from support import database as db_support

PRIVATE, PUBLIC, BETA = 'private', 'public', 'beta'


@unittest.skipUnless(os.getenv('BETALAB_TEST_DB') == '1', 'Requires disposable PostgreSQL schema')
class VisibilityMatrixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_support.setup_database(cls)
        from starlette.testclient import TestClient
        cls.anonymous = TestClient(cls.api.app, headers={'origin': 'http://localhost:8443'})
        response = cls.alice.put('/api/profile', json={'display_name': 'Alice', 'height_cm': 165, 'arm_span_cm': 170})
        assert response.status_code == 200, response.text
        cls.ids = {}
        for name, form in ((PRIVATE, {'visibility': 'private'}), (PUBLIC, {'visibility': 'public'}),
                           (BETA, {'visibility': 'public', 'share_as_beta': 'true'})):
            with cls.video.open('rb') as stream:
                response = cls.alice.post('/api/videos', data={'route_id': 'test-route', 'title': f'Matrix {name}', **form},
                                          files={'video': ('clip.mp4', stream, 'video/mp4')})
            assert response.status_code == 201, response.text
            cls.ids[name] = response.json()['id']

    @classmethod
    def tearDownClass(cls):
        cls.anonymous.close()
        db_support.teardown_database(cls)

    def clients(self):
        return {'owner': self.alice, 'other': self.bob, 'anonymous': self.anonymous}

    def expected(self, who, kind):
        if who == 'anonymous':
            return 401
        return 200 if who == 'owner' or kind != PRIVATE else 404

    def test_direct_reads_follow_visibility(self):
        reads = ['/api/videos/{id}', '/api/videos/{id}/content', '/api/videos/{id}/comments',
                 '/api/videos/{id}/danmaku']
        for who, client in self.clients().items():
            for kind, video_id in self.ids.items():
                for path in reads:
                    url = path.format(id=video_id)
                    with self.subTest(who=who, kind=kind, path=path):
                        headers = {'range': 'bytes=0-99'} if path.endswith('/content') else {}
                        status = client.get(url, headers=headers).status_code
                        expected = self.expected(who, kind)
                        if expected == 200 and path.endswith('/content'):
                            self.assertIn(status, (200, 206))
                        else:
                            self.assertEqual(status, expected)

    def test_writes_on_private_video_are_hidden_from_others(self):
        private = self.ids[PRIVATE]
        attempts = [('post', f'/api/videos/{private}/comments', {'json': {'body': 'hi'}}),
                    ('put', f'/api/videos/{private}/like', {}), ('put', f'/api/videos/{private}/save', {}),
                    ('post', f'/api/videos/{private}/share', {})]
        for method, url, kwargs in attempts:
            with self.subTest(url=url, method=method):
                self.assertEqual(getattr(self.bob, method)(url, **kwargs).status_code, 404)
                self.assertEqual(getattr(self.anonymous, method)(url, **kwargs).status_code, 401)
        # Nothing was recorded by the refused writes.
        self.assertEqual(self.alice.get(f'/api/social/videos?ids={private}').json()['items'][private],
                         {'like_count': 0, 'comment_count': 0, 'share_count': 0, 'liked': False, 'saved': False})

    def test_lists_show_only_allowed_videos_and_body_data_only_for_beta(self):
        privacy = {'account_visibility': 'public', 'calendar_visible': False, 'library_visible': True}
        self.assertEqual(self.alice.patch('/api/profile/privacy', json=privacy).status_code, 200)
        feed = {v['id']: v for v in self.bob.get('/api/videos?owned=false&limit=100').json()['items']}
        self.assertNotIn(self.ids[PRIVATE], feed)
        self.assertIsNone(feed[self.ids[PUBLIC]]['height_cm'])
        self.assertEqual(feed[self.ids[BETA]]['height_cm'], 165)
        route_beta = self.bob.get('/api/videos?owned=false&share_as_beta=true&route_id=test-route').json()['items']
        self.assertEqual([v['id'] for v in route_beta if v['id'] in self.ids.values()], [self.ids[BETA]])
        summary = self.bob.get('/api/social/videos?ids=' + ','.join(self.ids.values())).json()['items']
        self.assertEqual(set(summary), {self.ids[PUBLIC], self.ids[BETA]})
        for viewer in (self.bob, self.alice):  # the author page is always the public view
            profile = viewer.get(f'/api/users/{self.alice_id}/profile').json()
            shown = {v['id']: v for v in profile['videos']}
            self.assertEqual(set(shown) & set(self.ids.values()), {self.ids[PUBLIC], self.ids[BETA]})
            self.assertIsNone(shown[self.ids[PUBLIC]]['height_cm'])
        self.assertEqual(self.anonymous.get('/api/videos?owned=false').status_code, 401)
        self.assertEqual(self.anonymous.get(f'/api/users/{self.alice_id}/profile').status_code, 401)

    def test_author_page_visibility_does_not_change_direct_video_visibility(self):
        url = f'/api/users/{self.alice_id}/profile'
        public_video = f'/api/videos/{self.ids[PUBLIC]}'
        visible = {'account_visibility': 'public', 'calendar_visible': False, 'library_visible': True}
        hidden_library = {**visible, 'library_visible': False}
        private_account = {**visible, 'account_visibility': 'private'}
        try:
            self.alice.patch('/api/profile/privacy', json=visible)
            shown = self.bob.get(url).json()
            self.assertIn(self.ids[PUBLIC], [video['id'] for video in shown['videos']])
            self.alice.patch('/api/profile/privacy', json=hidden_library)
            self.assertEqual(self.bob.get(url).json()['videos'], [])
            self.assertEqual(self.bob.get(public_video).status_code, 200)
            self.alice.patch('/api/profile/privacy', json=private_account)
            hidden = self.bob.get(url).json()
            self.assertEqual(hidden['account_visibility'], 'private')
            self.assertEqual(hidden['videos'], [])
            self.assertEqual(hidden['public_video_count'], 0)
            self.assertEqual(hidden['display_name'], '')
            self.assertEqual(self.bob.get(public_video).status_code, 200)
        finally:
            self.alice.patch('/api/profile/privacy', json=visible)

    def test_turning_private_revokes_everything_and_public_restores_it(self):
        video = self.ids[PUBLIC]
        self.bob.post(f'/api/videos/{video}/comments', json={'body': 'nice', 'time_s': 1})
        self.bob.put(f'/api/videos/{video}/save')
        self.bob.put(f'/api/users/{self.alice_id}/follow')  # following never unlocks private videos
        try:
            self.assertEqual(self.alice.patch(f'/api/videos/{video}', json={'visibility': 'private'}).status_code, 200)
            for path in ('', '/content', '/comments', '/danmaku'):
                self.assertEqual(self.bob.get(f'/api/videos/{video}{path}').status_code, 404, path)
            self.assertNotIn(video, [v['id'] for v in self.bob.get('/api/me/saved-videos').json()['items']])
            self.assertNotIn(video, [v['id'] for v in self.bob.get(f'/api/users/{self.alice_id}/profile').json()['videos']])
            self.assertEqual(self.alice.get(f'/api/videos/{video}/comments').json()['total'], 1)  # owner keeps them
        finally:
            self.alice.patch(f'/api/videos/{video}', json={'visibility': 'public'})
        self.assertEqual(self.bob.get(f'/api/videos/{video}/comments').json()['total'], 1)
        self.assertIn(video, [v['id'] for v in self.bob.get('/api/me/saved-videos').json()['items']])
        self.bob.delete(f'/api/users/{self.alice_id}/follow')
        self.bob.delete(f'/api/videos/{video}/save')

    def test_beta_share_requires_public(self):
        response = self.alice.patch(f'/api/videos/{self.ids[PRIVATE]}', json={'share_as_beta': True})
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()
