"""Human hold provenance and correction bounds; no source-motion solver."""
import json
import unittest
from backend.compute.hold_review import HoldReview, normalize
import test_contact_review as contacts

def payload(**changes):
    return dict(reference_frame=0, corrections=[dict(hold_id='manual-extra',cx_px=10,cy_px=20,note='Visible missed hold')],notes='Reviewed reference',**changes)

class HoldValidationTest(unittest.TestCase):
    def test_bounds_and_identity(self):
        summary=dict(reference_frame=0,width=100,height=80)
        original=[dict(hold_id='H1',cx_px=5,cy_px=5)]
        result=normalize(HoldReview(**payload()),summary,original)
        self.assertEqual(len(result),2);self.assertEqual(len(original),1)
        for change in [dict(cx_px=100),dict(cy_px=80),dict(hold_id='untracked')]:
            data=payload();data['corrections'][0].update(change)
            with self.assertRaises(ValueError):normalize(HoldReview(**data),summary,original)

class HoldApiTest(contacts.ContactReviewApiTest):
    def test_hold_contact_versions_and_old_history(self):
        from backend.compute import storage
        from backend.database import database
        from psycopg.types.json import Jsonb
        with database() as db:
            row=db.execute('SELECT payload FROM compute_results WHERE task_id=%s',(self.task_id,)).fetchone()
            result=row['payload'];a=result['artifacts']['input_summary'];p=storage.resolve(a['storage_key'])
            info=json.loads(p.read_text());info.update(width=100,height=80);p.write_text(json.dumps(info));a['sha256']=storage.digest(p)
            db.execute('UPDATE compute_results SET payload=%s WHERE task_id=%s',(Jsonb(result),self.task_id))
        hp='/api/tasks/'+self.task_id+'/hold-review'
        self.assertEqual(self.bob.get(hp).status_code,404)
        response=self.alice.post(hp,json=payload());self.assertEqual(response.status_code,200,response.text)
        version=response.json()['version']
        self.assertEqual(self.alice.get(hp).json()['version'],version)
        body=dict(intervals=[dict(limb='left_hand',state='hold',hold_id='manual-extra',start_frame=0,release_frame=3)],confirmed=True,notes='Confirmed',hold_review_version=version)
        saved=self.alice.post(self.path,json=body);self.assertEqual(saved.status_code,200,saved.text)
        cv=saved.json()['version']
        self.assertEqual(self.alice.get(self.path+'/export?version='+cv).status_code,200)
        newer=payload(base_version=version);newer['corrections'][0]['cx_px']=12
        self.assertEqual(self.alice.post(hp,json=newer).status_code,200)
        self.assertEqual(self.alice.get(self.path+'/export?version='+cv).json()['input_sha256']['hold_review_version'],version)
        self.assertEqual(self.alice.post(hp,json=payload()).status_code,409)
        bad=payload(base_version='f'*64);self.assertEqual(self.alice.post(hp,json=bad).status_code,409)
        self.assertEqual(self.alice.delete('/api/videos/'+self.video_id).status_code,204)
        self.assertEqual(self.alice.get(hp).status_code,404)
