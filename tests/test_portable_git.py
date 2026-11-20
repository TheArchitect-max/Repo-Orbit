"""Checks that adversarial Git names remain tested without OS-specific files."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from portable_git import commit_unsafe_paths
from repoorbit.core import analyze
from repoorbit.render import render

class PortableGitFixtureTests(unittest.TestCase):
    def test_windows_forbidden_git_names_are_real_tree_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', '-C', str(root), 'init', '-q'], check=True, capture_output=True)
            names = {'line\nbreak.txt': 'one', 'x<y>.py': 'two',
                     'control\x01char.txt': 'three', 'caf\u00e9.py': 'four'}
            commit_unsafe_paths(root, 'adversarial names', names)
            actual = {p for commit in analyze(root)['commits']
                      for _code, p in commit['changes']}
            self.assertEqual(actual, set(names))
            output = render(analyze(root))
            self.assertNotIn('x<y>.py', output)
            self.assertIn('\\u003c', output)

    def test_nul_name_is_rejected_before_git_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', '-C', str(root), 'init', '-q'], check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, 'NUL-free'):
                commit_unsafe_paths(root, 'invalid', {'a\x00b.txt': 'x'})

if __name__ == '__main__':
    unittest.main()

