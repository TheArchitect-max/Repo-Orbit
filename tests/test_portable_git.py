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

    def test_existing_history_and_nested_files_survive_without_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def call(*args):
                return subprocess.run(['git', '-C', str(root), *args],
                                      check=True, capture_output=True).stdout.strip()
            call('init', '-q')
            call('config', 'user.name', 'Fixture Tester')
            call('config', 'user.email', 'tester@example.invalid')
            (root / 'preserved.txt').write_text('original', encoding='utf-8')
            call('add', '--', 'preserved.txt')
            call('commit', '-qm', 'baseline')
            parent = call('rev-parse', 'HEAD')
            names = {'src/<script>.py': 'safe', 'line\nbreak.txt': 'special'}
            new_sha = commit_unsafe_paths(root, 'inject unsafe paths', names)
            self.assertEqual(call('rev-parse', 'HEAD^'), parent)
            self.assertEqual(call('rev-parse', 'HEAD').decode('ascii'), new_sha)
            self.assertEqual((root / 'preserved.txt').read_text(encoding='utf-8'),
                             'original')
            self.assertFalse((root / 'src').exists())
            file_names = set(call('ls-tree', '-r', '-z', '--name-only', 'HEAD').split(b'\0'))
            self.assertIn(b'preserved.txt', file_names)
            for name in names:
                self.assertIn(name.encode('utf-8'), file_names)
            data = analyze(root, verification='full')
            self.assertEqual(data['files_final'], 3)
            self.assertEqual(data['verified_frames'], 2)

    def test_nul_name_is_rejected_before_git_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', '-C', str(root), 'init', '-q'], check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, 'NUL-free'):
                commit_unsafe_paths(root, 'invalid', {'a\x00b.txt': 'x'})

if __name__ == '__main__':
    unittest.main()

