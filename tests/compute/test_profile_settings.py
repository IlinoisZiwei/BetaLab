"""Profile editing, privacy precedence and password/session regressions."""
import os
import unittest
from uuid import uuid4
from support import database as db_support

@unittest.skipUnless(os.getenv('BETALAB_TEST_DB') == '1', 'Requires disposable PostgreSQL schema')
class ProfileSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_support.setup_database(cls)

    @classmethod
    def tearDownClass(cls):
        db_support.teardown_database(cls)

    def setUp(self):
        from backend.database import database
        with database() as db:
            db.execute("DELETE FROM user_videos")
            db.execute("UPDATE users SET account_visibility='public',measurements_visible=false,library_visible=false,likes_visible=false,saves_visible=false,skeletons_visible=false,calendar_visible=false")

    def test_username_bio_validation_and_existing_session(self):
        body=dict(username='RenamedAlice', display_name='Alice', bio='Climber', height_cm=165, arm_span_cm=170)
        r=self.alice.put('/api/profile',json=body)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['user']['username'],'renamedalice')
        self.assertEqual(self.alice.get('/api/auth/me').json()['user']['bio'],'Climber')
        self.assertEqual(self.alice.put('/api/profile',json={**body,'username':'phase2bob'}).status_code,409)
        self.assertEqual(self.alice.put('/api/profile',json={**body,'username':'bad name'}).status_code,422)
        self.assertEqual(self.alice.put('/api/profile',json={**body,'bio':'x'*501}).status_code,422)

    def test_public_sections_and_private_account_precedence(self):
        db_support.upload_sample(self)
        url=f'/api/users/{self.alice_id}/page'
        hidden=self.bob.get(url).json()
        self.assertEqual(hidden['videos'],[])
        self.assertIsNone(hidden['calendar'])
        self.assertNotIn('height_cm',hidden['user'])
        flags=dict(account_visibility='public',calendar_visible=True,measurements_visible=True,library_visible=True,likes_visible=True,saves_visible=True,skeletons_visible=True)
        self.assertEqual(self.alice.patch('/api/profile/privacy',json=flags).status_code,200)
        visible=self.bob.get(url).json()
        self.assertIn(self.video_id,[v['id'] for v in visible['videos']])
        self.assertTrue(visible['calendar'])
        self.assertIn('height_cm',visible['user'])
        self.assertEqual(visible['likes'],[])
        self.alice.patch('/api/videos/'+self.video_id,json={'visibility':'private'})
        revoked=self.bob.get(url).json()
        self.assertEqual(revoked['videos'],[])
        self.assertEqual(revoked['calendar'],[])
        self.alice.patch('/api/profile/privacy',json={**flags,'account_visibility':'private'})
        private=self.bob.get(url).json()
        self.assertNotIn('display_name',private['user'])
        for key in ('calendar','likes','saves','skeletons'):
            self.assertIsNone(private[key])
        own=self.alice.get(url).json()
        self.assertIn(self.video_id,[v['id'] for v in own['videos']])

    def test_merged_author_endpoint_honors_profile_and_library_privacy(self):
        db_support.upload_sample(self)
        url=f'/api/users/{self.alice_id}/profile'
        self.assertEqual(self.bob.get(url).json()['videos'], [])
        flags=dict(account_visibility='public',calendar_visible=False,library_visible=True)
        self.alice.patch('/api/profile/privacy',json=flags)
        self.assertIn(self.video_id,[v['id'] for v in self.bob.get(url).json()['videos']])
        self.alice.patch('/api/profile/privacy',json={**flags,'account_visibility':'private'})
        hidden=self.bob.get(url).json()
        self.assertEqual(hidden['account_visibility'],'private')
        self.assertEqual(hidden['videos'],[])
        self.assertEqual(hidden['public_video_count'],0)
        self.assertEqual(hidden['display_name'],'')
        self.assertEqual(self.bob.get('/api/videos/'+self.video_id).status_code,200)

    def test_skeleton_sharing_revokes_with_source_or_profile(self):
        from backend.database import database
        from psycopg.types.json import Jsonb
        from unittest.mock import patch
        from starlette.responses import Response
        db_support.upload_sample(self)
        task=uuid4()
        with database() as db:
            db.execute("INSERT INTO compute_tasks(id,owner_id,source_video_id,kind,request,request_hash,idempotency_key,state) VALUES (%s,%s,%s,'generate','{}','test',%s,'succeeded')",(task,self.alice_id,self.video_id,str(task)))
            db.execute('INSERT INTO compute_results(task_id,payload) VALUES (%s,%s)',(task,Jsonb({'artifacts':{}})))
        flags=dict(account_visibility='public',calendar_visible=False,library_visible=True,skeletons_visible=True)
        self.alice.patch('/api/profile/privacy',json=flags)
        url=f'/api/users/{self.alice_id}/skeletons/{task}/video'
        with patch('backend.compute.media.stream_artifact', return_value=Response(content=b'preview')):
            self.assertEqual(self.bob.get(url).status_code,200)
            self.assertEqual(self.bob.get('/api/tasks/'+str(task)).status_code,404)
            self.alice.patch('/api/profile/privacy',json={**flags,'skeletons_visible':False})
            self.assertEqual(self.bob.get(url).status_code,404)
            self.alice.patch('/api/profile/privacy',json=flags)
            self.alice.patch('/api/videos/'+self.video_id,json={'visibility':'private'})
            self.assertEqual(self.bob.get(url).status_code,404)
            self.assertEqual(self.alice.get(url).status_code,200)

    def test_password_change_verifies_current_and_revokes_other_sessions(self):
        from starlette.testclient import TestClient
        name='password_'+uuid4().hex[:10]
        with TestClient(self.api.app,headers={'origin':'http://localhost:8443'}) as first, TestClient(self.api.app,headers={'origin':'http://localhost:8443'}) as other:
            r=first.post('/api/auth/register',json={'username':name,'password':'Original-password-123'})
            first.headers['x-csrf-token']=r.json()['csrf_token']
            self.assertEqual(other.post('/api/auth/login',json={'username':name,'password':'Original-password-123'}).status_code,200)
            body={'current_password':'wrong-password','new_password':'Updated-password-123'}
            self.assertEqual(first.post('/api/profile/password',json=body).status_code,400)
            self.assertEqual(other.get('/api/auth/me').status_code,200)
            body['current_password']='Original-password-123'
            self.assertEqual(first.post('/api/profile/password',json=body).status_code,204)
            self.assertEqual(first.get('/api/auth/me').status_code,200)
            self.assertEqual(other.get('/api/auth/me').status_code,401)
            self.assertEqual(other.post('/api/auth/login',json={'username':name,'password':'Original-password-123'}).status_code,401)
            self.assertEqual(other.post('/api/auth/login',json={'username':name,'password':'Updated-password-123'}).status_code,200)

if __name__=='__main__':
    unittest.main()
