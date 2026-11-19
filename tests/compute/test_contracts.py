import copy
import json
import unittest
from pathlib import Path
from pydantic import ValidationError
from backend.compute.contracts import GenerationRequest, SourceRequest, Task, Artifact
from backend.compute.mock import MockExecutor
from backend.compute.policy import VideoAccess, source_access, task_access

ROOT = Path(__file__).resolve().parents[2]/'docs/compute/examples'

class ContractsTest(unittest.TestCase):
    def setUp(self):
        self.request = json.loads((ROOT/'generation-request.json').read_text())

    def test_body_and_scope_rejections(self):
        for change in ({'height_cm': float('nan')}, {'arm_span_cm': 0}, {'provenance': 'estimated'}):
            request = copy.deepcopy(self.request)
            request['target_body'].update(change)
            with self.assertRaises(ValidationError):
                GenerationRequest.model_validate(request)
        for change in ({'preserve_contact_timing': False}, {'owner_id': 'forged'}, {'technique_limit': 4}):
            with self.assertRaises(ValidationError):
                GenerationRequest.model_validate({**self.request, **change})

    def test_legacy_spacing_rejected(self):
        source = json.loads((ROOT/'analysis-request.json').read_text())
        source['calibration']['grid_spacing_cm'] = 15
        with self.assertRaises(ValidationError):
            SourceRequest.model_validate(source)

    def test_simulated_terminal_states_and_notification_idempotence(self):
        for outcome, expected in [('success', 'succeeded'), ('failure', 'failed'), ('insufficient', 'succeeded')]:
            executor = MockExecutor()
            task = executor.submit(self.request, 'alice')
            self.assertEqual(task.state, 'queued')
            self.assertEqual(executor.advance(task.id, outcome).state, 'running')
            final = executor.advance(task.id, outcome)
            self.assertEqual(final.state, expected)
            self.assertTrue(final.is_mock)
            executor.advance(task.id, outcome)
            self.assertEqual(len(executor.notifications), 1)
            if outcome == 'insufficient':
                self.assertEqual(final.result.technique_status, 'blocked')
                self.assertEqual(final.result.artifacts, {})

    def test_retry_ownership_and_new_attempt(self):
        executor = MockExecutor()
        task = executor.submit(self.request, 'alice')
        with self.assertRaises(ValueError):
            executor.submit(self.request, 'alice', task.id)
        executor.advance(task.id, 'failure')
        executor.advance(task.id, 'failure')
        with self.assertRaises(ValueError):
            executor.submit(self.request, 'bob', task.id)
        retry = executor.submit(self.request, 'alice', task.id)
        self.assertNotEqual(task.id, retry.id)
        self.assertEqual(retry.attempt, 2)

    def test_result_cannot_bypass_baseline_or_claim_real_artifacts(self):
        fixture = json.loads((ROOT/'generation-success.json').read_text())['history'][-1]
        broken = copy.deepcopy(fixture)
        broken['result']['baseline_status'] = 'failed'
        with self.assertRaises(ValidationError):
            Task.model_validate(broken)
        broken = copy.deepcopy(fixture)
        broken['result']['artifacts'] = {'video': dict(storage_key='jobs/video.mp4', media_type='video/mp4', sha256='a'*64)}
        with self.assertRaises(ValidationError):
            Task.model_validate(broken)

    def test_storage_key(self):
        for key in ('/tmp/video.mp4', 'jobs/../secret', 'https://example.com/video.mp4'):
            with self.assertRaises(ValidationError):
                Artifact(storage_key=key, media_type='video/mp4', sha256='a'*64)

    def test_all_generated_fixtures_follow_contract(self):
        for path in ROOT.glob('*.json'):
            payload = json.loads(path.read_text())
            if 'history' in payload:
                for state in payload['history']:
                    Task.model_validate(state)

    def test_permissions_rechecked_after_visibility_change_or_deletion(self):
        public = VideoAccess('uploader', 'public')
        private = VideoAccess('uploader', 'private')
        deleted = VideoAccess('uploader', 'public', True)
        self.assertTrue(source_access('alice', public))
        self.assertFalse(source_access(None, public))
        self.assertTrue(source_access('uploader', private))
        self.assertFalse(source_access('alice', private))
        self.assertTrue(task_access('alice', 'alice', public))
        self.assertFalse(task_access('bob', 'alice', public))
        self.assertFalse(task_access('alice', 'alice', private))
        self.assertFalse(task_access('alice', 'alice', deleted))
        self.assertFalse(task_access('uploader', 'uploader', deleted))

if __name__ == '__main__':
    unittest.main()
