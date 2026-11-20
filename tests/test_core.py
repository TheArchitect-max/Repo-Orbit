from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from repoorbit.core import OrbitError, analyze
from repoorbit.render import render
from portable_git import commit_unsafe_paths


def git(repo, *args):
    r=subprocess.run(["git","-C",str(repo),*args],capture_output=True,check=True)
    return r.stdout.decode('utf-8','replace').strip()


class RepoFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.repo=Path(self.temp.name)/'my-repo';self.repo.mkdir()
        git(self.repo,'init','-q');git(self.repo,'config','user.email','developer@example.invalid')
        git(self.repo,'config','user.name','Developer')

    def tearDown(self):
        self.temp.cleanup()

    def commit(self, title, additions=None, removals=()):
        for name, content in (additions or {}).items():
            p=self.repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
        for name in removals:(self.repo/name).unlink()
        git(self.repo,'add','-A');git(self.repo,'commit','-q','-m',title)
        return git(self.repo,'rev-parse','HEAD')


class CoreTests(RepoFixture):
    def test_empty_repository_rejected(self):
        with self.assertRaisesRegex(OrbitError,'no commits'):analyze(self.repo)

    def test_full_history_exact_replay(self):
        a=self.commit('first',{'README.md':'Hello','src/index.py':'pass'})
        self.commit('edit and delete',{'src/index.py':'print(1)','new.css':'body{}'},['README.md'])
        result=analyze(self.repo,limit=10)
        self.assertEqual(result['files_final'],2)
        self.assertEqual(result['history_window'],2)
        self.assertEqual(result['changes_total'],5)
        self.assertEqual(result['baseline'],[])
        self.assertEqual(result['commits'][0]['sha'],a)
        self.assertIn(['D','README.md'],result['commits'][1]['changes'])
        self.assertFalse(result['partial_history'])

    def test_limited_history_preserves_real_baseline(self):
        self.commit('first',{'old.py':'pass'})
        self.commit('second',{'another.py':'pass'})
        self.commit('third',{'third.py':'pass'})
        result=analyze(self.repo,limit=1)
        self.assertEqual(result['baseline'],['another.py','old.py'])
        self.assertEqual(result['files_final'],3)
        self.assertEqual(result['history_total'],3)
        self.assertTrue(result['partial_history'])

    def test_redaction_masks_metadata_and_paths(self):
        self.commit('Private organization plan',{'private-structure.md':'Data'})
        result=analyze(self.repo,share_safe=True)
        blob=json.dumps(result)
        self.assertNotIn('Developer',blob)
        self.assertNotIn('Private organization plan',blob)
        self.assertNotIn('private-structure.md',blob)
        self.assertIn('file-00001.docs',blob)
        self.assertNotIn('my-repo',blob)
        self.assertNotIn('2026-',blob)
        self.assertEqual(result['head'],'withheld')
        self.assertEqual(result['commits'][0]['sha'],'event-0001')

    def test_html_protects_against_script_breakout(self):
        commit_unsafe_paths(self.repo, '</script><script>alert(42)</script>', {'bad</script>.py':'ok'})
        document=render(analyze(self.repo))
        self.assertNotIn('</script><script>alert(42)</script>',document)
        self.assertIn('\\u003c/script\\u003e',document)
        self.assertIn('Content-Security-Policy',document)
        self.assertEqual(document.count('<script'),2)

    def test_git_filenames_with_spaces_and_newlines(self):
        commit_unsafe_paths(self.repo, 'strange paths', {'path with spaces.txt':'a','line\nbreak.txt':'b'})
        result=analyze(self.repo)
        paths=[p for _,p in result['commits'][0]['changes']]
        self.assertIn('path with spaces.txt',paths)
        self.assertIn('line\nbreak.txt',paths)

    def test_limit_rejects_invalid_values(self):
        self.commit('first',{'main.py':'pass'})
        for n in (-1,0,8001):
            with self.assertRaises(OrbitError):analyze(self.repo,limit=n)

    def test_tracks_only_commits_not_uncommitted_changes(self):
        self.commit('base',{'main.py':'v1'})
        (self.repo/'main.py').write_text('v2')
        (self.repo/'untracked.md').write_text('new')
        result=analyze(self.repo)
        self.assertTrue(result['dirty'])
        self.assertEqual(result['files_final'],1)
        self.assertNotIn('untracked.md',json.dumps(result))

    def test_first_parent_merge_is_replayed_as_delta(self):
        self.commit('base',{'a.py':'a'})
        default=git(self.repo,'branch','--show-current')
        git(self.repo,'checkout','-q','-b','feature')
        self.commit('feature adds new file',{'feature.py':'f'})
        git(self.repo,'checkout','-q',default)
        self.commit('main addition',{'main.py':'m'})
        git(self.repo,'merge','-q','--no-ff','feature','-m','Merge feature')
        result=analyze(self.repo)
        self.assertEqual(result['history_window'],3)
        self.assertEqual(result['files_final'],3)
        self.assertIn(['A','feature.py'],result['commits'][-1]['changes'])

    def test_cli_rejects_html_json_output_collision(self):
        self.commit('initial',{'hello.py':'print("Hello")'})
        same=Path(self.temp.name)/'overlap.html'
        run=subprocess.run([sys.executable,'-m','repoorbit',str(self.repo),
                            '-o',str(same),'--json',str(same)],capture_output=True,text=True)
        self.assertEqual(run.returncode,2)
        self.assertFalse(same.exists())

    def test_cli_creates_browsable_document(self):
        self.commit('initial',{'hello.py':'print("Hello")'})
        output=Path(self.temp.name)/'out.html'
        run=subprocess.run([sys.executable,'-m','repoorbit',str(self.repo),'-o',str(output)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('Repo Orbit',run.stdout)
        self.assertTrue(output.is_file())
        self.assertIn('repoorbit-v3',output.read_text())


if __name__=='__main__':unittest.main()
