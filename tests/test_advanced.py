"""Adversarial, privacy, independent-oracle, and deterministic-v2 regression gates."""
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
from repoorbit.__main__ import _atomic_write
from repoorbit.core import OrbitError, analyze, _redacted_paths
from repoorbit.render import render
from portable_git import commit_unsafe_paths


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args]).decode('utf-8','replace').strip()


class Repository(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name)/'top-secret-repository';self.repo.mkdir()
        git(self.repo,'init','-q');git(self.repo,'config','user.name','Secret Scientist')
        git(self.repo,'config','user.email','secret.email@example.invalid')
    def commit(self, message, changes=None, deletes=()):
        for path, content in (changes or {}).items():
            p=self.repo/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
        for path in deletes:(self.repo/path).unlink()
        git(self.repo,'add','-A');git(self.repo,'commit','-q','-m',message)
        return git(self.repo,'rev-parse','HEAD')


class V2Tests(Repository):
    def test_each_replayed_frame_against_independent_git_tree_oracle(self):
        a=self.commit('create',{'src/base.py':'one','docs/guide.md':'hello'})
        b=self.commit('modify',{'src/base.py':'two','assets/icon.png':'png'})
        c=self.commit('remove',{'src/base.py':'three'},['docs/guide.md'])
        d=self.commit('rename',{'src/new.py':'three'},['src/base.py'])
        report=analyze(self.repo,verification='full')
        self.assertEqual(report['verified_frames'],4)
        current=set(report['baseline'])
        for row, sha in zip(report['commits'],[a,b,c,d]):
            for op, path in row['changes']:
                if op=='D':current.remove(path)
                else:current.add(path)
            expected=set(git(self.repo,'ls-tree','-r','--name-only',sha).splitlines())
            self.assertEqual(current,expected)

    def test_redaction_no_sensitive_tokens_in_structured_data_or_html(self):
        sha=self.commit('secret acquisition plan',{'clients/acme/board-minutes.md':'secret',
                'src/critical-secret.py':'secret','credentials.txt':'secret'})
        self.commit('finish PRIVATE',{'src/critical-secret.py':'changed'})
        original=analyze(self.repo)
        clean=analyze(self.repo,share_safe=True)
        self.assertEqual(clean['files_final'],original['files_final'])
        self.assertEqual(clean['changes_total'],original['changes_total'])
        self.assertEqual(clean,analyze(self.repo,share_safe=True))
        for payload in (json.dumps(clean),render(clean)):
            for token in ['clients','acme','critical-secret','credentials','board-minutes',
                          'top-secret-repository','secret acquisition plan','Secret Scientist',sha,
                          'secret.email','PRIVATE']:
                self.assertNotIn(token,payload)
        self.assertEqual(clean['name'],'Private repository')
        self.assertEqual(clean['commits'][0]['date'],'')
        self.assertTrue(any('/' in path for c in clean['commits'] for _,path in c['changes']))

    def test_original_mode_does_not_relabel_source_files(self):
        self.commit('primary',{'src/main.py':'X'})
        data=analyze(self.repo)
        self.assertIn(['A','src/main.py'],data['commits'][0]['changes'])
        self.assertFalse(data['share_safe'])

    def test_render_escapes_adversarial_subject_and_path(self):
        payload='</script><script>throw new Error("INJECTED")</script>'
        commit_unsafe_paths(self.repo, payload, {'src/'+payload+'.txt':'safe'})
        html=render(analyze(self.repo))
        self.assertNotIn(payload,html)
        self.assertEqual(html.count('<script'),2)
        self.assertIn('\\u003c/script\\u003e',html)

    def test_template_placeholders_in_data_do_not_reexpand(self):
        self.commit('TOKEN __REPO_NAME__ __VIEWER_JS__ __PAYLOAD__',{'__PAYLOAD__.py':'safe'})
        html=render(analyze(self.repo))
        data=json.loads(re.search(r'<script type="application/json"[^>]*id="dataset">(.*?)</script>',html,re.S).group(1))
        self.assertEqual(data['commits'][0]['subject'],'TOKEN __REPO_NAME__ __VIEWER_JS__ __PAYLOAD__')
        self.assertIn('__PAYLOAD__.py',data['paths'][data['commits'][0]['changes'][0][1]])

    def test_redaction_aliases_unique_and_hierarchy_retained(self):
        original={'src/feature/main.py','src/feature/test.py','src/other/main.py',
                  'docs/feature/main.md','main.py'}
        mapping=_redacted_paths(original)
        self.assertEqual(len(mapping),len(set(mapping.values())))
        self.assertTrue(mapping['src/feature/main.py'].rsplit('/',1)[0] == mapping['src/feature/test.py'].rsplit('/',1)[0])
        self.assertTrue(mapping['src/feature/main.py'].rsplit('/',1)[0] != mapping['src/other/main.py'].rsplit('/',1)[0])
        self.assertTrue(mapping['main.py'].startswith('file-'))
        self.assertEqual(mapping,_redacted_paths(original))

    def test_sample_and_full_verification_parity(self):
        for n in range(10):self.commit('iteration'+str(n),{f'core/{n}.py':str(n)})
        sample=analyze(self.repo,verification='sample')
        full=analyze(self.repo,verification='full')
        self.assertEqual(sample['verified_frames'],3)
        self.assertEqual(full['verified_frames'],10)
        self.assertEqual(sample['commits'],full['commits'])
        self.assertEqual(sample['files_final'],full['files_final'])

    def test_corrupted_replay_is_detected_before_final_state(self):
        self.commit('first',{'a.py':'1'})
        self.commit('second',{'b.py':'2'})
        from repoorbit import core
        genuine=core._tree_objects
        calls={'count':0}
        def corrupt(root, rev):
            result=genuine(root,rev)
            if rev is not None and set(result)=={'a.py'}:
                calls['count']+=1
                return {'bad.py':result['a.py']}
            return result
        with patch.object(core,'_tree_objects',side_effect=corrupt):
            with self.assertRaisesRegex(OrbitError,'integrity failure'):
                analyze(self.repo,verification='full')
        self.assertGreater(calls['count'],0)

    @unittest.skipUnless(os.name=='posix','Raw-byte filenames require POSIX')
    def test_non_utf8_filename_rejected_instead_of_corrupted(self):
        raw=os.fsencode(str(self.repo))+b'/invalid-\xff.py'
        fd=os.open(raw,os.O_WRONLY|os.O_CREAT,0o644);os.write(fd,b'pass');os.close(fd)
        git(self.repo,'add','-A');git(self.repo,'commit','-q','-m','invalid path')
        with self.assertRaisesRegex(OrbitError,'Non-UTF-8'):analyze(self.repo)

    def test_cli_redact_full_verify_and_json(self):
        self.commit('secret message',{'root/alpha.py':'x'})
        html=Path(self.tmp.name)/'clean.html';data=Path(self.tmp.name)/'clean.json'
        process=subprocess.run([sys.executable,'-m','repoorbit',str(self.repo),
             '--redact','--verify','full','--json',str(data),'-o',str(html)],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertNotIn('secret message',html.read_text())
        self.assertNotIn('root/alpha.py',data.read_text())
        self.assertEqual(json.loads(data.read_text())['verified_frames'],1)

    def test_atomic_write_retains_old_file_if_replace_fails(self):
        dest=Path(self.tmp.name)/'atomic.txt';dest.write_text('original')
        with patch('repoorbit.__main__.os.replace',side_effect=OSError('injected')):
            with self.assertRaises(OSError):_atomic_write(dest,'new')
        self.assertEqual(dest.read_text(),'original')
        self.assertEqual(list(dest.parent.glob('.atomic.txt.*.tmp')),[])

    def test_deterministic_export_across_reruns(self):
        self.commit('a',{'a.py':'1'})
        self.commit('b',{'a.py':'2','b.md':'3'})
        self.assertEqual(render(analyze(self.repo)),render(analyze(self.repo)))
        self.assertEqual(render(analyze(self.repo,share_safe=True)),render(analyze(self.repo,share_safe=True)))

if __name__=='__main__':unittest.main()
