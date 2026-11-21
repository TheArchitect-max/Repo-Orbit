"""Independent demo fixture must ignore injected Git identity/config values."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.make_demo import build
from repoorbit.core import analyze as real_analyze

ROOT = Path(__file__).resolve().parents[1]


class DemoIdentityIsolationTests(unittest.TestCase):
    def test_fixed_html_sha_survives_adversarial_git_environment(self):
        expected = json.loads((ROOT / 'validation/BROWSER_EXPECTED_SHA256.json')
                              .read_text(encoding='utf-8'))['demo/RepoOrbit_Demo.html']
        hostile = {
            'GIT_AUTHOR_NAME': 'Demo ContributorABCDE',
            'GIT_COMMITTER_NAME': 'Demo ContributorABCDE',
            'GIT_AUTHOR_EMAIL': 'outsider@example.invalid',
            'GIT_COMMITTER_EMAIL': 'outsider@example.invalid',
            'GIT_AUTHOR_DATE': '2020-02-02T10:00:00 +0400',
            'GIT_COMMITTER_DATE': '2020-02-02T10:00:00 +0400',
            'GIT_DEFAULT_HASH': 'sha256',
            'GIT_CONFIG_COUNT': '1',
            'GIT_CONFIG_KEY_0': 'user.name',
            'GIT_CONFIG_VALUE_0': 'Untrusted Config User',
        }
        with tempfile.TemporaryDirectory(prefix='orbit-isolated-demo-') as d:
            fixture = Path(d) / 'RepoOrbit_Demo.html'
            with patch.dict(os.environ, hostile):
                build(fixture)
                output = fixture.read_bytes()
                self.assertEqual(hashlib.sha256(output).hexdigest(), expected)
                self.assertIn(b'"author":"Demo Contributor"', output)
                self.assertNotIn(b'Demo ContributorABCDE', output)
                self.assertNotIn(b'outsider@example.invalid', output)
            # Changing the environment back must not change the fixture.
            build(fixture)
            self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), expected)


    def test_git_243_utc_plus_zero_offset_keeps_exact_golden_html(self):
        # Git 2.43 on Colab produced 32 "+00:00" timestamps instead of "Z".
        # Substitute that precise date representation on a genuine Git fixture,
        # then require the original pinned byte-for-byte HTML hash.
        def colab_utc_offset(repository, *args, **kwargs):
            data = real_analyze(repository, *args, **kwargs)
            self.assertEqual(len(data['commits']), 32)
            for commit in data['commits']:
                if commit['date'].endswith('Z'):
                    commit['date'] = commit['date'][:-1] + '+00:00'
            self.assertTrue(all(c['date'].endswith('+00:00') for c in data['commits']))
            return data

        expected = json.loads((ROOT / 'validation/BROWSER_EXPECTED_SHA256.json')
                              .read_text(encoding='utf-8'))['demo/RepoOrbit_Demo.html']
        with tempfile.TemporaryDirectory(prefix='orbit-git243-demo-') as d:
            target = Path(d) / 'RepoOrbit_Demo.html'
            with patch('scripts.make_demo.analyze', side_effect=colab_utc_offset):
                build(target)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), expected)



if __name__ == '__main__':
    unittest.main()
