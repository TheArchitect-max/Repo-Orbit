"""Adversarial gzip acceptance checks: evidence inspection must be bounded."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import unittest
from unittest.mock import patch

from scripts import browser_payload_integrity as payload


def synthetic(raw: bytes, *, compression_level=9):
    compressed = gzip.compress(raw, compresslevel=compression_level, mtime=0)
    html = (b'<script id="dataset" data-encoding="gzip-base64">'
            + base64.b64encode(compressed) + b'</script>')
    return html, compressed


def reference(raw, commits=0, paths=0):
    return {
        'maximum_html_bytes': 1024 * 1024,
        'uncompressed_dataset_sha256': hashlib.sha256(raw).hexdigest(),
        'required_dataset_fields': {
            'head': 'a' * 40, 'history_window': commits, 'paths_total': paths,
        },
    }


class BoundedBrowserPayloadTests(unittest.TestCase):
    def test_bounded_gzip_accepts_valid_canonical_json(self):
        raw = json.dumps({'head': 'a'*40, 'history_window': 0,
                          'paths_total': 0, 'commits': [], 'paths': []},
                         separators=(',', ':')).encode()
        html, _ = synthetic(raw)
        r = payload.inspect_combined_export(html, reference(raw))
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(r['sha256_uncompressed_dataset'], hashlib.sha256(raw).hexdigest())

    def test_real_reference_has_headroom_below_decompression_ceiling(self):
        from scripts.browser_payload_integrity import expected_reference
        r = expected_reference()
        self.assertEqual(payload.MAX_UNCOMPRESSED_DATASET_BYTES, 64 * 1024 * 1024)
        self.assertEqual(r['required_dataset_fields']['history_window'], 8000)

    def test_small_compressed_expansion_bomb_is_rejected_before_json_parse(self):
        raw = b'Z' * 16000
        html, compressed = synthetic(raw, compression_level=9)
        self.assertLess(len(compressed), 256)
        with patch.object(payload, 'MAX_UNCOMPRESSED_DATASET_BYTES', 1024):
            with self.assertRaisesRegex(ValueError, 'Decompressed browser dataset exceeds'):
                payload.inspect_combined_export(html, reference(raw))

    def test_concatenated_gzip_members_are_still_bounded(self):
        first = gzip.compress(b'A' * 800, mtime=0)
        second = gzip.compress(b'B' * 800, mtime=0)
        html = (b'<script id="dataset" data-encoding="gzip-base64">'
                + base64.b64encode(first + second) + b'</script>')
        with patch.object(payload, 'MAX_UNCOMPRESSED_DATASET_BYTES', 1024):
            with self.assertRaisesRegex(ValueError, 'Decompressed browser dataset exceeds'):
                payload.inspect_combined_export(html, reference(b'A'*800+b'B'*800))

    def test_native_browser_security_gate_is_required(self):
        from scripts.run_native_browser import TESTS
        from scripts.audit_native_matrix import audit_browser
        from scripts.audit_browser_zips import REQUIRED
        self.assertIn('tests/browser_security_limits.py', TESTS)
        self.assertIn('GENERATED/evidence/browser_security_limits.json', REQUIRED)
        expected={'demo.html':'x'}
        report={'os':'Linux','browser':'Chromium','browser_version':'144',
                'status':'PASS','expected_asset_hashes':expected,
                'asset_hashes_match':{'demo.html':True},
                'test_results':[{'name':x,'status':'PASS','returncode':0}
                                for x in TESTS if x!='tests/browser_security_limits.py']}
        result=audit_browser([report],expected,['Linux'])
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['invalid_browser_results'][0]['reason'],
                         'required_browser_tests_not_pass')

    def test_truncated_gzip_is_rejected(self):
        raw = b'{"head":"' + b'a'*40 + b'"}'
        html, compressed = synthetic(raw)
        truncated = html.replace(base64.b64encode(compressed),
                                 base64.b64encode(compressed[:-3]))
        with self.assertRaisesRegex(ValueError, 'Invalid compressed browser dataset'):
            payload.inspect_combined_export(truncated, reference(raw))

    def test_malformed_json_object_type_is_rejected(self):
        raw = b'[]'
        html, _ = synthetic(raw)
        with self.assertRaisesRegex(ValueError, 'Browser dataset must be a JSON object'):
            payload.inspect_combined_export(html, reference(raw))

    def test_wrong_array_types_are_rejected(self):
        raw = json.dumps({'head':'a'*40,'history_window':0,'paths_total':0,
                          'commits': None, 'paths': []}).encode()
        html, _ = synthetic(raw)
        with self.assertRaisesRegex(ValueError, 'Browser commit array length mismatch'):
            payload.inspect_combined_export(html, reference(raw))


if __name__ == '__main__':
    unittest.main()
