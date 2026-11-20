"""v0.7 regressions for mirror repositories, bounded process output and reproducibility."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repoorbit.core import OrbitError, _git_output, analyze
from repoorbit.render import render

POPEN = subprocess.Popen


def git(root: Path, *args: str) -> None:
    subprocess.run(['git', '-C', str(root), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class V7Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='repoorbit-v7-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.repo = self.base / 'working'
        git(self.base, 'init', '-q', str(self.repo))
        git(self.repo, 'config', 'user.name', 'Mirror Tester')
        git(self.repo, 'config', 'user.email', 'mirror@example.invalid')
        (self.repo / 'tracked.txt').write_text('version1', encoding='utf-8')
        git(self.repo, 'add', 'tracked.txt')
        git(self.repo, 'commit', '-qm', 'initial')
        (self.repo / 'tracked.txt').write_text('version2', encoding='utf-8')
        git(self.repo, 'add', 'tracked.txt')
        git(self.repo, 'commit', '-qm', 'update')

    def test_bare_mirror_matches_working_repo_object_replay(self):
        bare = self.base / 'mirror.git'
        git(self.base, 'clone', '--bare', '-q', str(self.repo), str(bare))
        working = analyze(self.repo, verification='full')
        mirror = analyze(bare, verification='full')
        self.assertIsNone(mirror['dirty'])
        self.assertFalse(working['dirty'])
        for field in ('head','commits','baseline','baseline_versions','files_final',
                      'changes_total','verified_frames','top_paths'):
            self.assertEqual(working[field],mirror[field],field)
        self.assertEqual(mirror['verified_frames'],2)
        self.assertIn('data-encoding=',render(mirror))

    def test_linked_worktree_and_detached_head(self):
        worktree = self.base / 'alternate'
        git(self.repo, 'worktree', 'add', '-q', '--detach', str(worktree), 'HEAD')
        found = analyze(worktree, verification='full')
        self.assertEqual(found['commits'],analyze(self.repo,verification='full')['commits'])
        self.assertIs(found['dirty'], False)

    def test_path_control_characters_replay_as_json_without_code_execution(self):
        unusual = self.repo / 'src\x01control.txt'
        unusual.write_text('control',encoding='utf-8')
        git(self.repo,'add','-A')
        git(self.repo,'commit','-qm','control-char-test')
        data=analyze(self.repo,verification='full')
        self.assertIn('src\x01control.txt', [p for row in data['commits'] for _code,p in row['changes']])
        self.assertIn('src\\u0001control.txt', render(data,compression='plain'))

    def test_output_limit_is_enforced_during_streaming_not_after_exit(self):
        code = 'import os,sys,time\nfor _ in range(100):\n os.write(1,b"x"*65536)\n time.sleep(.01)'
        def fake_git(command, **kwargs):
            return POPEN([sys.executable,'-c',code],**kwargs)
        with patch('repoorbit.core.subprocess.Popen',side_effect=fake_git):
            with self.assertRaisesRegex(OrbitError,'Git response exceeds'):
                with _git_output(self.base,'ignored',max_bytes=1024,timeout=4):
                    pass

    def test_blocked_git_pipe_times_out(self):
        def fake_git(command, **kwargs):
            return POPEN([sys.executable,'-c','import time;time.sleep(5)'],**kwargs)
        with patch('repoorbit.core.subprocess.Popen',side_effect=fake_git):
            with self.assertRaisesRegex(OrbitError,'timed out'):
                with _git_output(self.base,'ignored',max_bytes=1024,timeout=.2):
                    pass

    def test_git_errors_remain_actionable_and_allow_failure_remains_optional(self):
        with _git_output(self.repo,'rev-parse','--verify','unknown-nonexistent-branch',allow_failure=True) as result:
            self.assertIsNone(result)
        with self.assertRaisesRegex(OrbitError,'Git command failed'):
            with _git_output(self.repo,'rev-parse','--verify','unknown-nonexistent-branch'):
                pass

    def test_gzip_and_plain_deterministic_for_mirror(self):
        d=analyze(self.repo)
        self.assertEqual(render(d,compression='gzip'),render(d,compression='gzip'))
        self.assertEqual(render(d,compression='plain'),render(d,compression='plain'))

    def test_sha256_git_repository_when_supported(self):
        sha = self.base / 'sha256'
        p = subprocess.run(['git','init','--object-format=sha256','-q',str(sha)],capture_output=True,text=True)
        if p.returncode:
            self.skipTest('Git installation lacks SHA-256 object-format support')
        git(sha,'config','user.name','Hash Tester')
        git(sha,'config','user.email','hash@example.invalid')
        (sha/'x').write_text('sha256')
        git(sha,'add','x')
        git(sha,'commit','-qm','hash-test')
        d=analyze(sha,verification='full')
        self.assertEqual(len(d['head']),64)
        self.assertEqual(d['files_final'],1)


if __name__=='__main__':
    unittest.main()
