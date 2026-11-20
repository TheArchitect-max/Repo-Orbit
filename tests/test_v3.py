"""Independent content-identity, integrity, redaction and resource-bound gates."""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from repoorbit.core import OrbitError, analyze, _git
from repoorbit.render import render


def git(repo, *args):
    return subprocess.check_output(['git','-C',str(repo),*args]).decode('utf-8','replace').strip()


class Repo(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='reporbit-v3-');self.addCleanup(tmp.cleanup)
        self.repo=Path(tmp.name)/'security-studies';self.repo.mkdir()
        git(self.repo,'init','-q');git(self.repo,'config','user.name','Private Person')
        git(self.repo,'config','user.email','private@example.invalid')
        self.tmp=Path(tmp.name)
    def commit(self, name, changes=None, deletes=()):
        for path,contents in (changes or {}).items():
            file=self.repo/path;file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text(contents,encoding='utf-8')
        for path in deletes:
            (self.repo/path).unlink()
        git(self.repo,'add','-A');git(self.repo,'commit','-q','-m',name)
        return git(self.repo,'rev-parse','HEAD')
    @staticmethod
    def state(data, target):
        state={p:v for p,v in zip(data['baseline'],data['baseline_versions'])}
        for c in data['commits'][:target+1]:
            for (op,path),version in zip(c['changes'],c['versions']):
                if op=='D': state.pop(path)
                else: state[path]=version
        return state


class V3Tests(Repo):
    def test_object_identity_detects_reverted_change_without_fake_difference(self):
        self.commit('original',{'src/alpha.py':'x'})
        self.commit('intermediate',{'src/alpha.py':'y'})
        self.commit('revert to same blob',{'src/alpha.py':'x'})
        d=analyze(self.repo,verification='full')
        self.assertEqual(d['schema'],'repoorbit-v3')
        self.assertEqual(d['object_equality'],'mode+git-object')
        self.assertNotEqual(self.state(d,0)['src/alpha.py'],self.state(d,1)['src/alpha.py'])
        self.assertEqual(self.state(d,0),self.state(d,2))
        self.assertEqual(d['verified_frames'],3)

    @unittest.skipUnless(os.name=='posix','File mode check requires POSIX')
    def test_chmod_changes_mode_identity_even_with_unchanged_blob(self):
        self.commit('base',{'run.sh':'echo hi\n'})
        (self.repo/'run.sh').chmod(0o755)
        git(self.repo,'add','-A');git(self.repo,'commit','-qm','make executable')
        d=analyze(self.repo,verification='full')
        self.assertEqual(d['commits'][1]['changes'],[['M','run.sh']])
        self.assertNotEqual(self.state(d,0)['run.sh'],self.state(d,1)['run.sh'])

    def test_same_contents_copy_has_same_opaque_identity(self):
        self.commit('two copies',{'a.txt':'one','b.txt':'one'})
        d=analyze(self.repo)
        state=self.state(d,0)
        self.assertEqual(state['a.txt'],state['b.txt'])
        self.assertEqual(len(d['commits'][0]['versions']),2)
        self.assertNotIn(git(self.repo,'rev-parse','HEAD:a.txt'),json.dumps(d))

    def test_rename_as_add_and_delete_preserves_version(self):
        self.commit('base',{'old/a.py':'same'})
        (self.repo/'new').mkdir()
        (self.repo/'old/a.py').rename(self.repo/'new/a.py')
        git(self.repo,'add','-A');git(self.repo,'commit','-qm','move')
        d=analyze(self.repo,verification='full')
        self.assertIn(['D','old/a.py'],d['commits'][1]['changes'])
        self.assertIn(['A','new/a.py'],d['commits'][1]['changes'])
        self.assertEqual(self.state(d,0)['old/a.py'],self.state(d,1)['new/a.py'])

    def test_real_tree_oracle_all_frames_and_versions(self):
        revs=[]
        revs.append(self.commit('initial',{'alpha':'a','folder/x':'x'}))
        revs.append(self.commit('change',{'alpha':'b','folder/y':'y'}))
        revs.append(self.commit('revert and delete',{'alpha':'a'},['folder/x']))
        revs.append(self.commit('new',{'new':'b'}))
        d=analyze(self.repo,verification='full')
        id_to_identity={}
        for i,sha in enumerate(revs):
            raw=subprocess.check_output(['git','-C',str(self.repo),'ls-tree','-r','-z',sha])
            expected={}
            for line in raw.split(b'\0'):
                if not line: continue
                header,name=line.split(b'\t',1)
                mode,_,oid=header.decode().split(' ')
                expected[name.decode()] = (mode,oid)
            actual=self.state(d,i)
            self.assertEqual(set(actual),set(expected))
            for path, token in actual.items():
                if token in id_to_identity:self.assertEqual(id_to_identity[token],expected[path])
                id_to_identity[token]=expected[path]

    def test_integrity_fails_on_object_substitution_even_if_paths_match(self):
        self.commit('base',{'a':'x'})
        from repoorbit import core
        original=core._history_stream
        def forged(*args,**kwargs):
            for row, events in original(*args,**kwargs):
                yield row, [(op,path,('100644:'+'e'*40) if oid else None) for op,path,oid in events]
        with patch.object(core,'_history_stream',side_effect=forged):
            with self.assertRaisesRegex(OrbitError,'objects/modes'):analyze(self.repo,verification='full')

    def test_exclude_is_presentation_only_with_full_integrity_gate(self):
        self.commit('base',{'vendor/third.js':'x','src/real.js':'a','src/temp.lock':'a'})
        self.commit('edit',{'vendor/third.js':'y','src/real.js':'b'})
        data=analyze(self.repo,verification='full',exclude=('vendor/**','*.lock'))
        self.assertEqual(data['files_final'],1)
        self.assertEqual(data['changes_total'],2)
        self.assertEqual(data['excluded_paths'],2)
        self.assertEqual(data['excluded_events'],3)
        self.assertEqual(data['verified_frames'],2)
        self.assertEqual(set(self.state(data,1)),{'src/real.js'})
        self.assertEqual(data['exclude_patterns'],['vendor/**','*.lock'])

    def test_redaction_with_exclusions_does_not_echo_filter_or_object_ids(self):
        sha=self.commit('secret',{'clients/acme-budget.py':'private','vendor/trojan.js':'secret'})
        clean=analyze(self.repo,verification='full',exclude=('vendor/**',),share_safe=True)
        raw=json.dumps(clean)
        for secret in ('clients','acme-budget','trojan','vendor','Private Person','security-studies',sha):
            self.assertNotIn(secret,raw)
        self.assertEqual(clean['exclude_patterns'],[])
        self.assertEqual(clean['files_final'],1)
        self.assertEqual(clean['baseline_versions'],[])
        self.assertEqual(clean['commits'][0]['versions'][0],1)

    def test_redaction_reorders_baseline_versions_correctly(self):
        self.commit('base',{'z-last.py':'Z','a-first.py':'A','nested/item.py':'x'})
        self.commit('next',{'new.py':'N'})
        normal=analyze(self.repo,limit=1)
        redacted=analyze(self.repo,limit=1,share_safe=True)
        originals={p:v for p,v in zip(normal['baseline'],normal['baseline_versions'])}
        self.assertEqual(sorted(redacted['baseline']),redacted['baseline'])
        self.assertEqual(set(redacted['baseline_versions']),set(originals.values()))
        self.assertEqual(len(redacted['baseline']),3)

    def test_git_output_limit_rejected_before_python_ingestion(self):
        self.commit('initial',{'x':'X'})
        with patch('repoorbit.core.MAX_GIT_OUTPUT_BYTES',8):
            with self.assertRaisesRegex(OrbitError,'response exceeds'):_git(self.repo,'rev-parse','HEAD')

    def test_invalid_exclude_patterns_and_verify_mode_rejected(self):
        self.commit('initial',{'x':'X'})
        for opts in ({'exclude':('x'*257,)},{'exclude':('',)},{'exclude':tuple('a' for _ in range(33))},
                     {'verification':'wrong'}):
            with self.assertRaises(OrbitError):analyze(self.repo,**opts)

    def test_standalone_html_has_no_real_object_hashes_or_network_dependencies(self):
        self.commit('one',{'secret.py':'print(9)'})
        html=render(analyze(self.repo,share_safe=True))
        oid=git(self.repo,'rev-parse','HEAD:secret.py')
        self.assertNotIn(oid,html)
        self.assertIn('repoorbit-v3',html)
        self.assertIn('Hotspot explorer',html)
        self.assertIn("connect-src 'none'",html)

    def test_cli_exclude_json_and_size_validation(self):
        self.commit('base',{'vendor/test.js':'x','src/main.py':'y'})
        out=self.tmp/'candidate.html'; js=self.tmp/'result.json'
        cmd=[sys.executable,'-m','repoorbit',str(self.repo),'--exclude','vendor/**','--json',str(js),'-o',str(out)]
        run=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(js.read_text())['files_final'],1)
        self.assertIn('excludes 1 paths',run.stdout)
        bad=subprocess.run(cmd+['--max-html-mb','0'],capture_output=True,text=True)
        self.assertEqual(bad.returncode,2)
        self.assertIn('max-html-mb',bad.stderr)

    def test_token_replay_over_many_frames_is_deterministic(self):
        for n in range(34):self.commit(f'update {n}',{'x.py':str(n),'a.md':'a'})
        one=analyze(self.repo,verification='sample')
        two=analyze(self.repo,verification='full')
        self.assertEqual(one['commits'],two['commits'])
        self.assertEqual(one['baseline_versions'],two['baseline_versions'])
        self.assertEqual(self.state(one,33),self.state(two,33))
        self.assertEqual(render(one),render(analyze(self.repo,verification='sample')))

if __name__=='__main__':unittest.main()
