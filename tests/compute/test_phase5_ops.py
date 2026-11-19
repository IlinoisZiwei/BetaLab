"""Operational guardrails; these small fixtures are checksum tests, not generated media."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from backend.compute import preflight,standby

class OperationsTest(unittest.TestCase):
    def fixture(self,root):
        for name in ('index.html','README.txt','source.bin','target.bin'):(root/name).write_text('synthetic checksum fixture')
        metadata=dict(prerecorded=True,is_mock=False,examples={role:dict(video=name,artifacts={'video':name}) for role,name in [('analysis','source.bin'),('generation','target.bin')]})
        (root/'metadata.json').write_text(json.dumps(metadata))
        manifest=dict(schema_version=1,prerecorded=True,is_mock=False,sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()})
        (root/'manifest.json').write_text(json.dumps(manifest))
        return manifest

    def test_corruption_and_missing_artifact_fail_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);standby.verify(root)
            (root/'target.bin').write_text('changed')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):standby.verify(root)
            (root/'target.bin').unlink()
            with self.assertRaises(ValueError):standby.verify(root)

    def test_incomplete_manifest_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);manifest=self.fixture(root)
            manifest['sha256']={};(root/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'Incomplete'):standby.verify(root)
            with self.assertRaises(ValueError):standby.within(root,'../outside')

    def test_public_storage_is_rejected_without_creating_it(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=Path(temp);storage=repo/'public'/'private-results'
            with patch.object(preflight,'REPO',repo),patch.dict(os.environ,{'COMPUTE_STORAGE_DIR':str(storage),'BETA_TRANSLATOR_ROOT':''}):
                report=preflight.check()
            self.assertFalse(next(c for c in report['checks'] if c['name']=='storage')['ok'])
            self.assertFalse(report['environment_ready'])
            self.assertFalse(storage.exists())

    def test_existing_backup_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);destination=root/'existing';destination.mkdir();sentinel=destination/'keep';sentinel.write_text('keep')
            with self.assertRaises(FileExistsError):standby.pack(root/'absent.json',destination,root)
            self.assertEqual(sentinel.read_text(),'keep')

if __name__=='__main__':unittest.main()
