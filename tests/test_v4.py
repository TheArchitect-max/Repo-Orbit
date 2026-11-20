"""v0.4 batch reader differential checks against v0.3 independent process oracle."""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from repoorbit.core import OrbitError, _history_batch, _commit_rows, _changes, analyze
from repoorbit.render import render
from portable_git import commit_unsafe_paths


def git(root, *args):
    r = subprocess.run(['git','-C',str(root),*args],capture_output=True,check=True)
    return r.stdout.decode('utf-8','replace').strip()

class BatchGate(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='orbit-batch-')
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/'test';self.root.mkdir()
        git(self.root,'init','-q');git(self.root,'config','user.name','Experiment')
        git(self.root,'config','user.email','exp@example.invalid')
    def commit(self, subject, files=(), allow_empty=False):
        for name,text in files:
            dest=self.root/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(text,encoding='utf-8')
        git(self.root,'add','-A')
        args=['commit','-qm',subject]
        if allow_empty:args.insert(1,'--allow-empty')
        git(self.root,*args)
        return git(self.root,'rev-parse','HEAD')
    def parity(self, limit=800):
        rows, events=_history_batch(self.root,limit)
        old=_commit_rows(self.root,limit)
        self.assertEqual(rows,old)
        for i,row in enumerate(rows):
            parent=git(self.root,'rev-parse',f'{rows[i-1]["sha"]}') if i else ''
            if i==0:
                r=subprocess.run(['git','-C',str(self.root),'rev-parse','--verify',f'{row["sha"]}^1'],capture_output=True)
                parent=r.stdout.decode().strip() if r.returncode==0 else None
            self.assertEqual(events[i],_changes(self.root,row['sha'],parent))
        self.assertEqual(analyze(self.root,limit=limit,verification='full')['verified_frames'],len(rows))
    def test_empty_commits_and_abbreviated_window(self):
        self.commit('init', [('a.py','a')]);self.commit('no-op',allow_empty=True)
        self.commit('update',[('a.py','b')]);self.commit('no-op again',allow_empty=True)
        self.parity();self.parity(limit=2)
    def test_first_parent_merge_and_branch_commit_filtering(self):
        self.commit('root',[('base.py','x')]);branch=git(self.root,'branch','--show-current')
        git(self.root,'checkout','-qb','branch')
        self.commit('branch',[('side.py','b')])
        git(self.root,'checkout','-q',branch)
        self.commit('main',[('base.py','updated')])
        git(self.root,'merge','--no-ff','-qm','merge branch','branch')
        rows,diffs=_history_batch(self.root,10)
        self.assertEqual(len(rows),3)
        self.assertEqual(diffs[-1],[('A','side.py',diffs[-1][0][2])])
        self.parity()
    def test_rename_delete_and_same_blob_revert(self):
        self.commit('start',[('old.py','1')]);
        (self.root/'old.py').rename(self.root/'new.py')
        git(self.root,'add','-A');git(self.root,'commit','-qm','rename')
        self.commit('modify',[('new.py','2')]);self.commit('revert',[('new.py','1')])
        self.parity()
        state=analyze(self.root)['commits']
        self.assertEqual({tuple(x) for x in state[1]['changes']},{('D','old.py'),('A','new.py')})
        self.assertEqual(state[1]['versions'][state[1]['changes'].index(['A','new.py'])],state[0]['versions'][0])
    def test_adversarial_marker_like_filenames_and_html_escape(self):
        name='COMMIT:'+('a'*40)
        commit_unsafe_paths(self.root, 'a commit marker', dict([(name,'x'),('line\nbreak.txt','y'),('<script>.js','z'),('café.py','q')]))
        self.parity()
        html=render(analyze(self.root,share_safe=True))
        self.assertNotIn('<script>.js',html)
        self.assertNotIn(name,html)
    @unittest.skipUnless(os.name=='posix','chmod requires POSIX')
    def test_symlink_and_executable_identity(self):
        self.commit('file',[('run.sh','echo yes\n')])
        (self.root/'link').symlink_to('run.sh')
        (self.root/'run.sh').chmod(0o755)
        git(self.root,'add','-A');git(self.root,'commit','-qm','link and mode')
        self.parity()
    def test_sha256_repository_when_git_supports_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sha256'
            p=subprocess.run(['git','init','--object-format=sha256','-q',str(path)],capture_output=True)
            if p.returncode: self.skipTest('Git SHA-256 not supported')
            git(path,'config','user.name','Test');git(path,'config','user.email','test@example.invalid')
            (path/'file').write_text('x');git(path,'add','-A');git(path,'commit','-qm','root')
            rows,diffs=_history_batch(path,10)
            self.assertEqual(len(rows[0]['sha']),64)
            self.assertEqual(len(rows),1)
            self.assertEqual(analyze(path)['files_final'],1)
    def test_batch_parser_does_not_trust_fake_commit_metadata(self):
        self.commit('regular',[('file','text')])
        from repoorbit import core
        with patch.object(core,'_nul_fields',return_value=iter([b'COMMIT:fake'])):
            with self.assertRaisesRegex(OrbitError,'Malformed streaming'):
                _history_batch(self.root,10)
    def test_matches_legacy_for_34_snapshot_frames(self):
        for i in range(34):self.commit('iteration '+str(i),[(f'docs/{i%5}.md',str(i)),(f'code/{i%7}.py',str(i))])
        self.parity()

if __name__=='__main__':unittest.main()
