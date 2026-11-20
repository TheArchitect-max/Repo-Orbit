"""R8 native Chromium evidence controls; offline tests, no browser installation."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.audit_browser_zips import audit as audit_bundle
from scripts.run_browser_evidence import evaluate_platform, fixture_provenance

ROOT = Path(__file__).resolve().parents[1]


class R8BrowserGateTests(unittest.TestCase):
    def test_combined_fixture_exact_uncompressed_hash_allows_gzip_variation(self):
        import base64
        import gzip
        import re
        from scripts.browser_payload_integrity import inspect_combined_export, expected_reference
        source = (ROOT/'demo/RepoOrbit_CombinedMaximum.html').read_bytes()
        reference = expected_reference()
        original = inspect_combined_export(source, reference)
        match = re.search(rb'<script[^>]*id="dataset"[^>]*>([^<]*)</script>', source, re.S)
        self.assertIsNotNone(match)
        raw = gzip.decompress(base64.b64decode(match.group(1)))
        alternate = base64.b64encode(gzip.compress(raw, compresslevel=1, mtime=0))
        different_html = source[:match.start(1)] + alternate + source[match.end(1):]
        self.assertNotEqual(hashlib.sha256(source).hexdigest(), hashlib.sha256(different_html).hexdigest())
        normalized = inspect_combined_export(different_html, reference)
        self.assertEqual(original['sha256_uncompressed_dataset'], normalized['sha256_uncompressed_dataset'])
        self.assertEqual(normalized['git_head'], reference['required_dataset_fields']['head'])

    def test_combined_fixture_changed_dataset_rejected_even_with_valid_gzip(self):
        import base64
        import gzip
        import re
        from scripts.browser_payload_integrity import inspect_combined_export, expected_reference
        original = (ROOT/'demo/RepoOrbit_CombinedMaximum.html').read_bytes()
        match = re.search(rb'<script[^>]*id="dataset"[^>]*>([^<]*)</script>', original, re.S)
        self.assertIsNotNone(match)
        raw = gzip.decompress(base64.b64decode(match.group(1)))
        tampered = raw.replace(b'"head":"0bcade52', b'"head":"9bcade52', 1)
        self.assertNotEqual(raw, tampered)
        packed = base64.b64encode(gzip.compress(tampered, compresslevel=5, mtime=0))
        html = original[:match.start(1)] + packed + original[match.end(1):]
        with self.assertRaisesRegex(ValueError, 'Canonical browser dataset SHA-256 mismatch'):
            inspect_combined_export(html, expected_reference())

    def test_browser_matrix_requires_all_three_native_platforms(self):
        self.assertEqual(audit_bundle([])['status'], 'HOLD_OR_FAIL')

    def test_browser_audit_fails_closed_on_missing_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'BROWSER_STAGE_STATUS.json').write_text(json.dumps({
                'status':'BROWSER_EXECUTED_PENDING_AUDIT',
                'stages':[{'stage':stage,'status':'PASS'} for stage in (
                    'preflight','small_demo_fixture','combined_maximum_fixture','chromium_e2e')]}),
                encoding='utf-8')
            result = evaluate_platform(root,'Linux')
            self.assertEqual(result['status'],'FAIL')
            self.assertTrue(any(x['type']=='missing_browser_evidence' for x in result['errors']))

    def test_actual_small_fixture_is_deterministic(self):
        from scripts.make_demo import build
        spec=json.loads((ROOT/'validation/BROWSER_EXPECTED_SHA256.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'RepoOrbit_Demo.html'
            build(target)
            one=hashlib.sha256(target.read_bytes()).hexdigest()
            build(target)
            two=hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(one,two)
            self.assertEqual(one,spec['demo/RepoOrbit_Demo.html'])

    def test_circleci_browser_jobs_are_opt_in_and_always_zip(self):
        config=(ROOT/'.circleci/config.yml').read_text(encoding='utf-8')
        for platform,label in [('linux','Linux'),('windows','Windows'),('macos','Darwin')]:
            self.assertIn('run_browser_'+platform+':',config)
            self.assertIn('browser-'+platform+':',config)
            self.assertIn('scripts/run_browser_evidence.py --platform '+label+' --out external-results/browser-'+platform+' --run', config)
            self.assertIn('scripts/run_browser_evidence.py --platform '+label+' --out external-results/browser-'+platform+' --package-only',config)
        self.assertEqual(config.count('when: always'),6)
        self.assertEqual(config.count('default: false'),6)
        self.assertEqual(config.count('      - store_artifacts:'),6)

    def test_windows_browser_installer_keeps_stderr_separate_and_fails_on_real_exit_code(self):
        config = (ROOT/'.circleci/config.yml').read_text(encoding='utf-8')
        windows = config.split('  browser-windows:', 1)[1].split('  browser-macos:', 1)[0]
        install = windows.split('name: Install pinned test-only Playwright and Chromium', 1)[1].split('      - run:', 1)[0]
        self.assertIn('Start-Process -FilePath $browserPython', install)
        self.assertIn('-RedirectStandardOutput $stdoutPath', install)
        self.assertIn('-RedirectStandardError $stderrPath', install)
        self.assertIn('-Wait -PassThru', install)
        self.assertNotIn('2>&1 | Tee-Object', install)
        self.assertIn('if ($process.ExitCode -ne 0)', install)
        self.assertIn('browser-windows-install.log', install)
        self.assertIn("Invoke-BrowserInstall -Stage 'pip'", install)
        self.assertIn("Invoke-BrowserInstall -Stage 'chromium'", install)
        self.assertIn("@('-m','pip','install','-r','requirements-browser-ci.txt')", install)
        self.assertIn("@('-m','playwright','install','chromium')", install)
        self.assertIn('when: always', windows)
        self.assertIn('scripts/run_browser_evidence.py --platform Windows --out external-results/browser-windows --package-only', windows)

    def test_playwright_dependency_is_test_only_and_pinned(self):
        expected='playwright==1.65.2'
        req=(ROOT/'requirements-browser-ci.txt').read_text(encoding='utf-8')
        self.assertIn(expected,req)
        self.assertNotIn('playwright', (ROOT/'pyproject.toml').read_text(encoding='utf-8'))

    def test_raw_browser_fixture_is_pinned_to_unchanged_product_sources(self):
        pin=json.loads((ROOT/'validation/PINNED_TARGETS.json').read_text(encoding='utf-8'))
        for version,location in [('v0.7.0',ROOT/'baselines/v0.7.0/repoorbit'),
                                 ('v0.8.0',ROOT/'repoorbit')]:
            for part,digest in pin['source_sha256'][version].items():
                self.assertEqual(hashlib.sha256((location/(part+'.py')).read_bytes()).hexdigest(),digest)


if __name__=='__main__':
    unittest.main()
