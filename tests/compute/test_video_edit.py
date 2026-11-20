"""Owner-only video edits, partial updates and Community/Beta consistency."""
import os
import unittest
from support import database as db_support

@unittest.skipUnless(os.getenv('BETALAB_TEST_DB')=='1','Requires disposable PostgreSQL schema')
class VideoEditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_support.setup_database(cls)

    @classmethod
    def tearDownClass(cls):
        db_support.teardown_database(cls)

    def setUp(self):
        db_support.upload_sample(self)
        self.url='/api/videos/'+self.video_id

    def test_edit_metadata_and_sharing_persists_across_queries(self):
        body=dict(title='  My second attempt  ',description='  Better footwork\nNext try  ',visibility='public',share_as_beta=True)
        response=self.alice.patch(self.url,json=body)
        self.assertEqual(response.status_code,200,response.text)
        saved=response.json()
        self.assertEqual(saved['title'],'My second attempt')
        self.assertEqual(saved['description'],'Better footwork\nNext try')
        self.assertEqual(saved['id'],self.video_id)
        for client,path in ((self.alice,'/api/videos?owned=true'),(self.bob,'/api/videos?owned=false'),(self.bob,'/api/videos?owned=false&route_id=test-route&share_as_beta=true')):
            item=next(v for v in client.get(path).json()['items'] if v['id']==self.video_id)
            self.assertEqual(item['title'],saved['title'])
            self.assertEqual(item['description'],saved['description'])
        self.assertEqual(self.bob.get(self.url).json()['title'],saved['title'])

    def test_partial_metadata_retains_sharing_and_private_clears_beta(self):
        self.alice.patch(self.url,json={'visibility':'public','share_as_beta':True})
        saved=self.alice.patch(self.url,json={'title':'Renamed'}).json()
        self.assertTrue(saved['share_as_beta'])
        self.assertEqual(saved['visibility'],'public')
        self.assertEqual(self.alice.patch(self.url,json={'description':''}).json()['description'],'')
        saved=self.alice.patch(self.url,json={'visibility':'private'}).json()
        self.assertFalse(saved['share_as_beta'])
        self.assertEqual(self.bob.get(self.url).status_code,404)
        items=self.bob.get('/api/videos?owned=false&share_as_beta=true').json()['items']
        self.assertNotIn(self.video_id,[v['id'] for v in items])
        self.assertEqual(self.alice.get(self.url).json()['title'],'Renamed')

    def test_rejects_invalid_or_unauthorized_edits_without_changes(self):
        original=self.alice.get(self.url).json()
        self.assertEqual(self.bob.patch(self.url,json={'title':'Not mine'}).status_code,404)
        for body in ({'title':'  '},{'title':'x'*121},{'description':'x'*501},{'title':None},{},{'visibility':'friends'},{'visibility':'private','share_as_beta':True}):
            r=self.alice.patch(self.url,json=body)
            self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(self.alice.get(self.url).json(),original)

if __name__=='__main__':
    unittest.main()
