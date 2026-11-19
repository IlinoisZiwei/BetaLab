"""Business router extraction retains sessions, CSRF, catalog and owner access."""
import os
import unittest
from starlette.testclient import TestClient
from support import database as support

@unittest.skipUnless(os.getenv('BETALAB_TEST_DB')=='1','Requires disposable PostgreSQL schema')
class BusinessRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): support.setup_database(cls)
    @classmethod
    def tearDownClass(cls): support.teardown_database(cls)
    def setUp(self): support.upload_sample(self)

    def test_profile_catalog_and_mutation_guards(self):
        self.assertEqual(self.alice.get('/api/health').json(),{'ready':True})
        self.assertEqual(self.alice.get('/api/routes/test-route').json()['gym_id'],'test-gym')
        self.assertEqual(next(gym for gym in self.alice.get('/api/gyms').json()['items'] if gym['id']=='test-gym')['active_route_count'],1)
        body=dict(display_name='Updated',height_cm=173,arm_span_cm=176)
        url='/api/profile'
        self.assertEqual(self.alice.put(url,json=body,headers={'x-csrf-token':'wrong'}).status_code,403)
        self.assertEqual(self.alice.put(url,json=body,headers={'origin':'https://untrusted.invalid'}).status_code,403)
        self.assertEqual(self.alice.put(url,json=body).status_code,200)
        self.assertEqual(self.alice.get('/api/auth/me').json()['user']['display_name'],'Updated')
        self.assertEqual(self.alice.get('/api/routes?limit=101').status_code,422)
        with TestClient(self.api.app) as guest:
            self.assertEqual(guest.get('/api/videos/'+self.video_id).status_code,401)

    def test_video_visibility_owner_delete_and_logout(self):
        url='/api/videos/'+self.video_id
        self.assertEqual(self.bob.patch(url,json={'visibility':'private'}).status_code,404)
        self.assertEqual(self.alice.patch(url,json={'visibility':'private'}).status_code,200)
        self.assertEqual(self.bob.get(url+'/content').status_code,404)
        self.assertEqual(self.alice.patch(url,json={'visibility':'public','share_as_beta':True}).status_code,200)
        self.assertEqual(self.bob.get(url+'/content').status_code,200)
        self.assertEqual(self.bob.delete(url).status_code,404)
        self.assertEqual(self.alice.delete(url).status_code,204)
        self.assertEqual(self.alice.get(url).status_code,404)
        self.assertEqual(self.bob.post('/api/auth/logout').status_code,204)
        self.assertEqual(self.bob.get('/api/auth/me').status_code,401)
        response=self.bob.post('/api/auth/login',json={'username':'phase2bob','password':'phase2-local-test-only'})
        self.assertEqual(response.status_code,200)
        self.bob.headers['x-csrf-token']=response.json()['csrf_token']
