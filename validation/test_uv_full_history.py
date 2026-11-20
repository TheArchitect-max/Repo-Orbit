"""Offline isolated tests of the R3 Git-history preflight helper."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

HELPER = Path(__file__).with_name('prepare_uv_full_history.py')
if not HELPER.is_file():
    HELPER = Path(__file__).resolve().parents[1] / 'scripts' / 'prepare_uv_full_history.py'
spec = importlib.util.spec_from_file_location('uvprep', HELPER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def git(*a, cwd=None):
    return subprocess.run(['git', *map(str,a)], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

class TestUvPreflight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.remote = self.d/'remote'
        git('init','-q','--initial-branch=main',self.remote)
        git('config','user.email','test@example.com', cwd=self.remote)
        git('config','user.name','Test', cwd=self.remote)
        for i in range(11):
            (self.remote/'f.txt').write_text(str(i))
            git('add','f.txt',cwd=self.remote)
            git('commit','-qm','c'+str(i),cwd=self.remote)
        self.sha = git('rev-parse','HEAD',cwd=self.remote)
        self.project = self.d/'project'
        (self.project/'validation').mkdir(parents=True)
        (self.project/'validation'/'PINNED_TARGETS.json').write_text(json.dumps({'repositories':{'uv':{'url':self.remote.as_uri(), 'sha':self.sha,'default_branch':'main'}},'required_windows':[1,2,5]}))

    def test_fresh_full_clone(self):
        result = mod.prepare(self.project, self.d/'fresh')
        self.assertEqual(result['status'],'PASS')
        self.assertFalse(result['git_shallow'])
        self.assertEqual(result['first_parent_history_available'],11)

    def test_shallow_clone_is_unshallowed(self):
        shallow = self.d/'shallow'
        git('clone','-q','--depth=5',self.remote.as_uri(),shallow)
        self.assertEqual(git('rev-parse','--is-shallow-repository',cwd=shallow),'true')
        result = mod.prepare(self.project, shallow)
        self.assertFalse(result['git_shallow'])
        self.assertEqual(result['first_parent_history_available'],11)

    def test_wrong_origin_is_rejected(self):
        other = self.d/'other'
        git('init','-q',other)
        git('remote','add','origin','file:///nonmatching/repo',cwd=other)
        with self.assertRaisesRegex(RuntimeError, 'Wrong Git origin'):
            mod.prepare(self.project, other)

    def test_does_not_overwrite_unrelated_non_git_directory(self):
        other = self.d/'unrelated'
        other.mkdir()
        (other/'important.txt').write_text('keep')
        with self.assertRaisesRegex(RuntimeError, 'Unsafe non-empty'):
            mod.prepare(self.project, other)
        self.assertEqual((other/'important.txt').read_text(),'keep')

if __name__ == '__main__': unittest.main()
