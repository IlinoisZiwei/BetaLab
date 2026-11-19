"""Contact edits and pinned downstream inputs; synthetic fixtures, no solver."""
import json
import os
from pathlib import Path
import unittest
from pydantic import ValidationError
from backend.compute.contact_schema import ContactReview
from backend.compute.contact_review import normalize
from support import database as support

def interval(**changes):
    return {**dict(limb='left_hand', state='hold', hold_id='H1', start_frame=1, release_frame=3), **changes}

def review(**changes):
    return {**dict(intervals=[interval()], confirmed=True, notes='Synthetic test observation'), **changes}

class ContactValidationTest(unittest.TestCase):
    def test_bounds_overlap_and_unknown_holds(self):
        for intervals in [[interval(release_frame=11)], [interval(hold_id='missing')],
                          [interval(), interval(start_frame=2, release_frame=4)]]:
            with self.assertRaises(ValueError):
                normalize(ContactReview(**review(intervals=intervals)), dict(frame_count=10, fps=5), [dict(hold_id='H1')])
        for item in [interval(release_frame=1), interval(start_frame=1.5), interval(state='free'),
                     interval(hold_id=None), interval(limb='head')]:
            with self.assertRaises(ValidationError): ContactReview(**review(intervals=[item]))

    def test_adjacent_contacts_release_and_unknown_coverage(self):
        data = normalize(ContactReview(**review(intervals=[interval(),
            interval(state='free', hold_id=None, start_frame=3, release_frame=5)])),
            dict(frame_count=10, fps=5), [dict(hold_id='H1')])
        self.assertEqual(data['unknown_limb_frames'], 36)
        self.assertEqual(data['intervals'][0]['release_sec'], .6)
        self.assertFalse(data['generation_ready'])

@unittest.skipUnless(os.getenv('BETALAB_TEST_DB') == '1', 'Requires disposable PostgreSQL')
class ContactReviewApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.setup_database(cls)
        cls.old_storage = os.environ.get('COMPUTE_STORAGE_DIR')
        os.environ['COMPUTE_STORAGE_DIR'] = str(Path(cls.directory.name)/'compute')
    @classmethod
    def tearDownClass(cls):
        if cls.old_storage is None: os.environ.pop('COMPUTE_STORAGE_DIR', None)
        else: os.environ['COMPUTE_STORAGE_DIR'] = cls.old_storage
        support.teardown_database(cls)
    def setUp(self):
        support.upload_sample(self)
        from backend.compute import storage, service
        from backend.database import database
        task = self.alice.post('/api/tasks/analyze', json=self.request, headers={'Idempotency-Key':'contact-fixture'}).json()
        self.task_id = task['id']
        self.path = '/api/tasks/'+self.task_id+'/contact-review'
        root = storage.root()/'published'/self.task_id
        root.mkdir(parents=True)
        content = {
            'input_summary': json.dumps(dict(frame_count=10, fps=5, reference_frame=0)),
            'holds': json.dumps([dict(hold_id='H1')]),
            'contacts': 'frame,time_sec,limb,hold_id\n0,0,left_hand,unknown\n',
            'contact_events': 'limb,hold_id,start_frame,end_frame\nleft_hand,H1,1,2\n',
            'frame_map': 'frame,source_frame,source_time_sec\n'+''.join(f'{i},{i*2},{i/5}\n' for i in range(10)),
        }
        artifacts = {}
        for name, text in content.items():
            p = root/name; p.write_text(text)
            artifacts[name] = dict(storage_key=str(p.relative_to(storage.root())), sha256=storage.digest(p), media_type='application/json')
        result = dict(kind='analyze', is_mock=False, algorithm_version=storage.INPUT_ENGINE,
            source_analysis_version='synthetic', calibration_version='synthetic', source_video_id=self.video_id,
            frame_count=10, fps=5, quality=dict(evidence='insufficient', geometry_status='assumed', warnings=['TEST ONLY']),
            artifacts=artifacts, baseline_status='insufficient_evidence', technique_status='not_requested')
        with database() as db:
            row = db.execute("UPDATE compute_tasks SET state='running', is_mock=false WHERE id=%s RETURNING *", (self.task_id,)).fetchone()
            service.finish(db, row, result=result)

    def test_versions_export_and_access(self):
        initial = self.alice.get(self.path).json()
        self.assertIsNone(initial['version'])
        self.assertEqual(initial['candidates'][0]['release_frame'], 3)
        self.assertEqual(self.bob.get(self.path).status_code, 404)
        self.assertEqual(self.bob.post(self.path, json=review()).status_code, 404)
        self.assertEqual(self.alice.post(self.path, json=review(), headers={'x-csrf-token':'wrong'}).status_code, 403)
        saved = self.alice.post(self.path, json=review())
        self.assertEqual(saved.status_code, 200, saved.text)
        v1 = saved.json()['version']
        self.assertEqual(self.alice.post(self.path, json=review()).json()['version'], v1)
        changed = review(intervals=[interval(limb='right_foot', start_frame=2, release_frame=5)])
        self.assertEqual(self.alice.post(self.path, json=changed).status_code, 409)
        changed['base_version'] = v1
        v2 = self.alice.post(self.path, json=changed).json()['version']
        self.assertNotEqual(v1, v2)
        old = self.alice.get(self.path, params={'version':v1}).json()
        self.assertEqual(old['saved']['review']['intervals'][0]['limb'], 'left_hand')
        exported = self.alice.get(self.path+'/export', params={'version':v1})
        self.assertEqual(exported.status_code, 200, exported.text)
        rows = exported.json()['frames']
        self.assertEqual(len(rows), 40)
        self.assertEqual([r['frame'] for r in rows if r['state']=='hold'], [1, 2])
        self.assertEqual(rows[1]['source_frame'], 2)
        self.assertEqual(rows[3]['state'], 'unknown')
        self.assertFalse(exported.json()['generation_ready'])
        self.assertEqual(self.bob.get(self.path+'/export', params={'version':v1}).status_code, 404)
        self.assertEqual(self.alice.get(self.path+'/export').status_code, 422)
        self.assertEqual(self.alice.get(self.path, params={'version':'../latest'}).status_code, 422)
        self.alice.delete('/api/videos/'+self.video_id)
        self.assertEqual(self.alice.get(self.path, params={'version':v1}).status_code, 404)

    def test_invalid_edits_draft_and_integrity(self):
        from backend.compute import storage
        for payload in [review(intervals=[interval(hold_id='H404')]),
                        review(intervals=[interval(release_frame=99)]),
                        review(intervals=[interval(), interval()])]:
            self.assertEqual(self.alice.post(self.path, json=payload).status_code, 422)
        draft = self.alice.post(self.path, json=review(confirmed=False)).json()
        self.assertEqual(self.alice.get(self.path+'/export', params={'version':draft['version']}).status_code, 409)
        p = storage.root()/'contact-reviews'/self.task_id/(draft['version']+'.json')
        doc = json.loads(p.read_text()); doc['review']['confirmed'] = True; p.write_text(json.dumps(doc))
        self.assertEqual(self.alice.get(self.path).status_code, 409)

    def test_concurrent_edit_conflict(self):
        from concurrent.futures import ThreadPoolExecutor
        from fastapi import HTTPException
        from backend.compute import contact_review
        initial = self.alice.post(self.path, json=review()).json()['version']
        def update(note):
            try:
                return contact_review.save(self.task_id, self.alice_id,
                    ContactReview(**review(base_version=initial, notes=note)))['version']
            except HTTPException as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(update, ['First observation', 'Second observation']))
        self.assertEqual(outcomes.count(409), 1)
        self.assertEqual(sum(isinstance(value, str) for value in outcomes), 1)

    def test_source_tamper_and_incomplete_task(self):
        from backend.compute import storage
        p = storage.root()/'published'/self.task_id/'frame_map'
        p.write_text(p.read_text()+'tampered')
        self.assertEqual(self.alice.get(self.path).status_code, 409)
        task = self.alice.post('/api/tasks/analyze', json=self.request, headers={'Idempotency-Key':'pending'}).json()
        self.assertEqual(self.alice.get('/api/tasks/'+task['id']+'/contact-review').status_code, 409)
