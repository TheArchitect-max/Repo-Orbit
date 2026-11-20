"""R7 host ZIP evidence integrity regression tests; no benchmark network calls."""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.run_ci_evidence import build_zip, audit_platform
from scripts.audit_ci_zips import audit as audit_matrix


class R7EvidenceTests(unittest.TestCase):
    def test_archive_contains_complete_manifest_and_verified_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, out = Path(tmp) / 'staged', Path(tmp) / 'artifact'
            (work / 'logs').mkdir(parents=True)
            (work / 'logs' / 'test.log').write_text('95 tests pass\n', encoding='utf-8')
            (work / 'data.bin').write_bytes(b'\x00\xff\x01')
            (work / 'CI_CONTEXT.json').write_text(json.dumps({'commit': 'a' * 40}), encoding='utf-8')
            archive, manifest = build_zip(work, out, 'Linux')
            self.assertTrue(archive.is_file())
            self.assertEqual(len(manifest['files']), 3)
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(z.testzip(), None)
                self.assertEqual(z.read('data.bin'), b'\x00\xff\x01')
                self.assertEqual(json.loads(z.read('SHA256_MANIFEST.json'))['files'], manifest['files'])
            self.assertTrue((out / (archive.name + '.sha256')).is_file())

    def test_missing_raw_measurements_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / 'RUN_STAGE_STATUS.json').write_text(json.dumps({
                'stages': [{'step': name, 'status': 'PASS'} for name in
                           ('source_preflight', 'regression_tests', 'native_benchmarks')]
            }), encoding='utf-8')
            audit = audit_platform(work, 'Linux')
            self.assertEqual(audit['status'], 'FAIL')
            self.assertTrue(audit['errors'])

    def test_cross_platform_empty_input_never_passes(self):
        result = audit_matrix([])
        self.assertEqual(result['status'], 'HOLD_OR_FAIL')
        self.assertTrue(result['errors'])

    def test_incomplete_test_gate_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / 'RUN_STAGE_STATUS.json').write_text(json.dumps({'stages': [
                {'step': 'source_preflight', 'status': 'PASS'},
                {'step': 'regression_tests', 'status': 'FAIL'}
            ]}), encoding='utf-8')
            audit = audit_platform(work, 'Windows')
            self.assertEqual(audit['status'], 'FAIL')
            self.assertIn('missing_successful_stages', [x['type'] for x in audit['errors']])


if __name__ == '__main__':
    unittest.main()
