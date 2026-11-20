"""Community interactions (backend/routes/social.py): access rules, threads, likes, danmaku, shares.

Video rows are inserted directly: these tests check social rules, not the upload pipeline.
Run with BETALAB_TEST_DB=1 against a disposable database (see README, Testing).
"""
import os
import unittest
from uuid import uuid4
from support import database as db_support


@unittest.skipUnless(os.getenv('BETALAB_TEST_DB') == '1', 'Requires disposable PostgreSQL schema')
class SocialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_support.setup_database(cls)
        from starlette.testclient import TestClient
        cls.carol = TestClient(cls.api.app, headers={'origin': 'http://localhost:8443'})
        response = cls.carol.post('/api/auth/register', json=dict(username='socialcarol', password='phase2-local-test-only'))
        assert response.status_code == 201, response.text
        cls.carol.headers['x-csrf-token'] = response.json()['csrf_token']
        cls.anonymous = TestClient(cls.api.app, headers={'origin': 'http://localhost:8443'})

    @classmethod
    def tearDownClass(cls):
        cls.carol.close()
        cls.anonymous.close()
        db_support.teardown_database(cls)

    def make_video(self, owner_id, visibility='public', share_as_beta=False, duration=12):
        from backend.database import database
        video_id = str(uuid4())
        with database() as db:
            db.execute('INSERT INTO user_videos(id,owner_id,route_id,visibility,share_as_beta,original_name,title,'
                       'storage_key,media_type,size_bytes,duration_seconds) '
                       "VALUES (%s,%s,'test-route',%s,%s,'clip.mp4','Clip',%s,'video/mp4',1000,%s)",
                       (video_id, owner_id, visibility, share_as_beta, f'test/{video_id}.mp4', duration))
        return video_id

    def set_visibility(self, video_id, visibility):
        response = self.alice.patch(f'/api/videos/{video_id}', json={'visibility': visibility})
        self.assertEqual(response.status_code, 200, response.text)

    def post(self, client, video_id, **body):
        return client.post(f'/api/videos/{video_id}/comments', json=body)

    # ------------------------------------------------------------- comments

    def test_comment_lifecycle_on_public_video(self):
        video = self.make_video(self.alice_id)
        created = self.post(self.bob, video, body='  Nice drop knee  ')
        self.assertEqual(created.status_code, 201, created.text)
        comment = created.json()
        self.assertEqual(comment['body'], 'Nice drop knee')
        self.assertEqual(comment['author']['id'], self.bob_id)
        self.assertTrue(comment['can_delete'])
        listed = self.alice.get(f'/api/videos/{video}/comments').json()
        self.assertEqual(listed['total'], 1)
        self.assertFalse(listed['items'][0]['can_delete'])  # the video owner is not the author
        self.assertEqual(self.alice.delete(f"/api/comments/{comment['id']}").status_code, 403)
        self.assertEqual(self.bob.delete(f"/api/comments/{comment['id']}").status_code, 204)
        self.assertEqual(self.alice.get(f'/api/videos/{video}/comments').json()['total'], 0)

    def test_private_video_comments_are_invisible_to_others(self):
        video = self.make_video(self.alice_id, 'private')
        self.assertEqual(self.post(self.alice, video, body='note to self').status_code, 201)
        self.assertEqual(self.bob.get(f'/api/videos/{video}/comments').status_code, 404)
        self.assertEqual(self.post(self.bob, video, body='hi').status_code, 404)

    def test_public_then_private_revokes_comment_access(self):
        video = self.make_video(self.alice_id)
        comment = self.post(self.bob, video, body='great send').json()
        self.set_visibility(video, 'private')
        self.assertEqual(self.bob.get(f'/api/videos/{video}/comments').status_code, 404)
        self.assertEqual(self.post(self.bob, video, body='still?').status_code, 404)
        self.assertEqual(self.bob.delete(f"/api/comments/{comment['id']}").status_code, 404)
        self.assertEqual(self.alice.get(f'/api/videos/{video}/comments').json()['total'], 1)

    def test_validation_pagination_and_bad_ids(self):
        video = self.make_video(self.alice_id)
        self.assertEqual(self.post(self.alice, video, body='   ').status_code, 422)
        self.assertEqual(self.post(self.alice, video, body='x' * 501).status_code, 422)
        self.assertEqual(self.post(self.alice, video, body='ok', author_id='x').status_code, 422)
        for i in range(3):
            self.post(self.alice, video, body=f'c{i}')
        page = self.alice.get(f'/api/videos/{video}/comments?limit=2&offset=0').json()
        self.assertEqual([c['body'] for c in page['items']], ['c0', 'c1'])
        self.assertEqual(page['total'], 3)
        page2 = self.alice.get(f'/api/videos/{video}/comments?limit=2&offset=2').json()
        self.assertEqual([c['body'] for c in page2['items']], ['c2'])
        self.assertEqual(self.alice.get(f'/api/videos/{video}/comments?limit=0').status_code, 422)
        # Bundled samples are not database videos: plain 404, never a database error.
        self.assertEqual(self.alice.get('/api/videos/sample-a1/comments').status_code, 404)
        self.assertEqual(self.alice.put('/api/videos/preset-beta-b1/like').status_code, 404)
        self.assertEqual(self.alice.delete('/api/comments/not-a-uuid').status_code, 404)

    def test_login_and_csrf_required(self):
        video = self.make_video(self.alice_id)
        self.assertEqual(self.anonymous.get(f'/api/videos/{video}/comments').status_code, 401)
        token = self.bob.headers.pop('x-csrf-token')
        try:
            self.assertEqual(self.post(self.bob, video, body='hi').status_code, 403)
        finally:
            self.bob.headers['x-csrf-token'] = token

    def test_deleting_video_removes_its_comments(self):
        video = self.make_video(self.alice_id)
        self.post(self.bob, video, body='bye')
        self.assertEqual(self.alice.delete(f'/api/videos/{video}').status_code, 204)
        self.assertEqual(self.alice.get(f'/api/videos/{video}/comments').status_code, 404)

    # ------------------------------------------------- replies and comment likes

    def test_replies_stay_one_level_and_mention_the_reply_author(self):
        video = self.make_video(self.alice_id)
        top = self.post(self.bob, video, body='How do you start?', time_s=3.5).json()
        self.assertEqual((top['time_s'], top['parent_id'], top['reply_count']), (3.5, None, 0))
        reply = self.post(self.alice, video, body='Left hand first', parent_id=top['id'], time_s=9).json()
        self.assertEqual(reply['parent_id'], top['id'])
        self.assertIsNone(reply['reply_to'])
        self.assertIsNone(reply['time_s'])  # replies never become danmaku
        nested = self.post(self.carol, video, body='Thanks!', parent_id=reply['id']).json()
        self.assertEqual(nested['parent_id'], top['id'])
        self.assertEqual(nested['reply_to']['id'], self.alice_id)
        listed = self.bob.get(f'/api/videos/{video}/comments').json()
        self.assertEqual([c['id'] for c in listed['items']], [top['id']])
        self.assertEqual((listed['total'], listed['total_with_replies']), (1, 3))
        self.assertEqual(listed['items'][0]['reply_count'], 2)
        replies = self.bob.get(f"/api/comments/{top['id']}/replies").json()
        self.assertEqual([r['body'] for r in replies['items']], ['Left hand first', 'Thanks!'])
        self.assertEqual(self.bob.get(f"/api/comments/{reply['id']}/replies").status_code, 404)
        self.assertEqual(self.bob.get(f'/api/social/videos?ids={video}').json()['items'][video]['comment_count'], 3)
        self.assertEqual(self.bob.delete(f"/api/comments/{top['id']}").status_code, 204)
        self.assertEqual(self.bob.get(f'/api/videos/{video}/comments').json()['total_with_replies'], 0)

    def test_reply_parent_must_belong_to_the_same_visible_video(self):
        v1, v2 = self.make_video(self.alice_id), self.make_video(self.alice_id)
        top = self.post(self.alice, v1, body='first').json()
        self.assertEqual(self.post(self.bob, v2, body='x', parent_id=top['id']).status_code, 404)
        self.assertEqual(self.post(self.bob, v1, body='x', parent_id='nope').status_code, 404)

    def test_comment_likes(self):
        video = self.make_video(self.alice_id)
        c = self.post(self.alice, video, body='beta here').json()
        self.assertEqual(self.bob.put(f"/api/comments/{c['id']}/like").json(), {'liked': True, 'like_count': 1})
        self.assertEqual(self.bob.put(f"/api/comments/{c['id']}/like").json(), {'liked': True, 'like_count': 1})
        self.assertEqual(self.carol.put(f"/api/comments/{c['id']}/like").json()['like_count'], 2)
        item = self.bob.get(f'/api/videos/{video}/comments').json()['items'][0]
        self.assertEqual((item['like_count'], item['liked']), (2, True))
        self.assertFalse(self.alice.get(f'/api/videos/{video}/comments').json()['items'][0]['liked'])
        self.assertEqual(self.bob.delete(f"/api/comments/{c['id']}/like").json(), {'liked': False, 'like_count': 1})
        self.set_visibility(video, 'private')
        self.assertEqual(self.carol.put(f"/api/comments/{c['id']}/like").status_code, 404)

    # ------------------------------------------------------ danmaku and shares

    def test_danmaku_lists_timed_top_level_comments_in_playback_order(self):
        video = self.make_video(self.alice_id, duration=12)
        self.post(self.bob, video, body='late', time_s=8)
        first = self.post(self.bob, video, body='early', time_s=1.25).json()
        self.post(self.bob, video, body='no time')
        self.post(self.bob, video, body='reply', parent_id=first['id'], time_s=2)
        clamped = self.post(self.bob, video, body='past end', time_s=60).json()
        self.assertEqual(clamped['time_s'], 12)  # clamped to the video length
        self.assertEqual(self.post(self.bob, video, body='bad', time_s=-1).status_code, 422)
        items = self.carol.get(f'/api/videos/{video}/danmaku').json()['items']
        self.assertEqual([d['body'] for d in items], ['early', 'late', 'past end'])
        self.assertFalse(items[0]['mine'])
        self.assertTrue(self.bob.get(f'/api/videos/{video}/danmaku').json()['items'][0]['mine'])
        self.set_visibility(video, 'private')
        self.assertEqual(self.carol.get(f'/api/videos/{video}/danmaku').status_code, 404)

    def test_share_counts_people_not_clicks(self):
        video = self.make_video(self.alice_id)
        self.assertEqual(self.bob.post(f'/api/videos/{video}/share').json(), {'share_count': 1})
        self.assertEqual(self.bob.post(f'/api/videos/{video}/share').json(), {'share_count': 1})
        self.assertEqual(self.carol.post(f'/api/videos/{video}/share').json(), {'share_count': 2})
        self.assertEqual(self.alice.get(f'/api/social/videos?ids={video}').json()['items'][video]['share_count'], 2)
        private = self.make_video(self.alice_id, 'private')
        self.assertEqual(self.bob.post(f'/api/videos/{private}/share').status_code, 404)

    # ---------------------------------------------------- likes, saves, wanted

    def test_video_like_is_idempotent_and_counted(self):
        video = self.make_video(self.alice_id)
        self.assertEqual(self.bob.put(f'/api/videos/{video}/like').json(), {'liked': True, 'like_count': 1})
        self.assertEqual(self.bob.put(f'/api/videos/{video}/like').json(), {'liked': True, 'like_count': 1})
        self.assertEqual(self.carol.put(f'/api/videos/{video}/like').json()['like_count'], 2)
        self.assertEqual(self.bob.delete(f'/api/videos/{video}/like').json(), {'liked': False, 'like_count': 1})
        summary = self.bob.get(f'/api/social/videos?ids={video}').json()['items'][video]
        self.assertEqual(summary, {'like_count': 1, 'comment_count': 0, 'share_count': 0, 'liked': False, 'saved': False})

    def test_cannot_like_or_save_someone_elses_private_video(self):
        video = self.make_video(self.alice_id, 'private')
        self.assertEqual(self.bob.put(f'/api/videos/{video}/like').status_code, 404)
        self.assertEqual(self.bob.put(f'/api/videos/{video}/save').status_code, 404)
        self.assertEqual(self.alice.put(f'/api/videos/{video}/like').status_code, 200)

    def test_saved_list_follows_visibility(self):
        beta = self.make_video(self.alice_id, share_as_beta=True)
        plain = self.make_video(self.alice_id)
        self.assertEqual(self.bob.put(f'/api/videos/{beta}/save').json(), {'saved': True})
        self.assertEqual(self.bob.put(f'/api/videos/{plain}/save').status_code, 200)
        items = {v['id']: v for v in self.bob.get('/api/me/saved-videos').json()['items']}
        self.assertEqual(set(items), {beta, plain})
        self.assertEqual(items[beta]['content_url'], f'/api/videos/{beta}/content')
        self.assertIsNone(items[plain]['height_cm'])  # body data only for Beta shares
        self.set_visibility(plain, 'private')
        self.assertEqual({v['id'] for v in self.bob.get('/api/me/saved-videos').json()['items']}, {beta})
        self.assertEqual(self.bob.delete(f'/api/videos/{plain}/save').json(), {'saved': False})
        self.set_visibility(plain, 'public')
        self.assertEqual({v['id'] for v in self.bob.get('/api/me/saved-videos').json()['items']}, {beta})

    def test_social_summary_hides_inaccessible_and_ignores_bad_ids(self):
        public, private = self.make_video(self.alice_id), self.make_video(self.alice_id, 'private')
        self.post(self.bob, public, body='hi')
        items = self.bob.get(f'/api/social/videos?ids={public},{private},sample-a1,preset-beta-b1').json()['items']
        self.assertEqual(set(items), {public})
        self.assertEqual(items[public]['comment_count'], 1)

    def test_wanted_routes_round_trip(self):
        self.assertEqual(self.bob.put('/api/routes/test-route/want').json(), {'wanted': True})
        self.assertEqual(self.bob.put('/api/routes/test-route/want').json(), {'wanted': True})
        self.assertEqual(self.bob.put('/api/routes/nope/want').status_code, 404)
        self.assertEqual([r['route_id'] for r in self.bob.get('/api/me/wanted-routes').json()['items']], ['test-route'])
        self.assertEqual(self.carol.get('/api/me/wanted-routes').json()['items'], [])
        self.assertEqual(self.bob.delete('/api/routes/test-route/want').json(), {'wanted': False})
        self.assertEqual(self.bob.get('/api/me/wanted-routes').json()['items'], [])


    # ----------------------------------------------------------- follows

    def test_follow_is_idempotent_and_never_self(self):
        self.assertEqual(self.bob.put(f'/api/users/{self.alice_id}/follow').json(), {'following': True, 'follower_count': 1})
        self.assertEqual(self.bob.put(f'/api/users/{self.alice_id}/follow').json(), {'following': True, 'follower_count': 1})
        self.assertEqual(self.carol.put(f'/api/users/{self.alice_id}/follow').json()['follower_count'], 2)
        self.assertEqual(self.alice.get(f'/api/users/{self.alice_id}/follow').json(), {'following': False, 'follower_count': 2})
        self.assertEqual(self.alice.put(f'/api/users/{self.alice_id}/follow').status_code, 422)
        self.assertEqual(self.alice.put(f'/api/users/{uuid4()}/follow').status_code, 404)
        self.assertEqual(self.alice.put('/api/users/not-a-uuid/follow').status_code, 404)
        self.assertEqual([u['id'] for u in self.bob.get('/api/me/following').json()['items']], [self.alice_id])
        self.assertEqual(self.alice.get('/api/me/following').json()['items'], [])
        self.assertEqual(self.bob.delete(f'/api/users/{self.alice_id}/follow').json(), {'following': False, 'follower_count': 1})
        self.assertEqual(self.bob.delete(f'/api/users/{self.alice_id}/follow').json(), {'following': False, 'follower_count': 1})
        self.carol.delete(f'/api/users/{self.alice_id}/follow')

    def test_following_does_not_unlock_private_videos(self):
        private = self.make_video(self.alice_id, 'private')
        self.bob.put(f'/api/users/{self.alice_id}/follow')
        try:
            self.assertEqual(self.bob.get(f'/api/videos/{private}').status_code, 404)
            self.assertEqual(self.bob.get(f'/api/videos/{private}/comments').status_code, 404)
            self.assertNotIn(private, [v['id'] for v in self.bob.get('/api/videos?owned=false').json()['items']])
        finally:
            self.bob.delete(f'/api/users/{self.alice_id}/follow')


if __name__ == '__main__':
    unittest.main()
