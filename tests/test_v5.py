"""v0.5 scale engine, compact payload and offline-compression gates."""
from __future__ import annotations
import base64
import gzip
import io
import json
import random
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from repoorbit.core import OrbitError, MAX_COMMITS, MAX_GIT_FIELD_BYTES, _nul_fields, analyze
from repoorbit.render import _packed_payload, render

class SmallReads(io.BytesIO):
    def __init__(self, value: bytes, size: int):
        super().__init__(value)
        self.size=size
    def read(self, n: int = -1):
        return super().read(self.size if n<0 else min(n,self.size))


class V5Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='orbit-v5-gate-')
        self.addCleanup(tmp.cleanup)
        self.repo=Path(tmp.name)
        self.git('init','-q')
        self.git('config','user.name','Gate Tester')
        self.git('config','user.email','gate@example.invalid')
        (self.repo/'src').mkdir()
        (self.repo/'src'/'alpha.py').write_text('a')
        self.git('add','-A');self.git('commit','-qm','first')
        (self.repo/'src'/'alpha.py').write_text('b')
        (self.repo/'README.md').write_text('hello')
        self.git('add','-A');self.git('commit','-qm','second')

    def git(self,*args):
        return subprocess.run(['git','-C',str(self.repo),*args],capture_output=True,check=True)

    def test_nul_stream_parses_every_byte_boundary(self):
        original=[b'first',b'',b'COMMIT:'+b'a'*40,b'\n:100644',b'path\nname',b'last']
        value=b'\0'.join(original)+b'\0'
        for chunk in [1,2,3,5,7,29,64,65536]:
            self.assertEqual(list(_nul_fields(SmallReads(value,chunk))),original)

    def test_nul_stream_rejects_oversized_unterminated_field(self):
        with self.assertRaisesRegex(OrbitError,'field exceeds'):
            list(_nul_fields(SmallReads(b'z'*(MAX_GIT_FIELD_BYTES+1),121)))

    def test_nul_stream_accepts_maximal_field(self):
        value=b'X'*MAX_GIT_FIELD_BYTES+b'\0'
        self.assertEqual(list(_nul_fields(SmallReads(value,203)))[0],b'X'*MAX_GIT_FIELD_BYTES)

    def test_randomized_nul_boundaries(self):
        randomizer=random.Random(8021)
        for _ in range(60):
            fields=[bytes(randomizer.randint(1,255) for _ in range(randomizer.randint(1,100))) for _ in range(15)]
            raw=b'\0'.join(fields)+b'\0'
            self.assertEqual(list(_nul_fields(SmallReads(raw,randomizer.randint(1,100)))),fields)

    def test_limit_exact_upper_bound(self):
        self.assertGreaterEqual(MAX_COMMITS,8000)
        self.assertEqual(analyze(self.repo,limit=MAX_COMMITS)['history_window'],2)
        with self.assertRaises(OrbitError):analyze(self.repo,limit=MAX_COMMITS+1)

    def test_dictionary_payload_losslessly_preserves_all_changes(self):
        data=analyze(self.repo)
        packed=_packed_payload(data)
        self.assertEqual(packed['schema'],data['schema'])
        self.assertEqual(len(packed['paths']),data['paths_total'])
        decoded_baseline=[packed['paths'][i] for i in packed['baseline']]
        self.assertEqual(decoded_baseline,data['baseline'])
        decoded=[[(code,packed['paths'][i],version) for code,i,version in row['changes']] for row in packed['commits']]
        expected=[[(code,path,v) for (code,path),v in zip(row['changes'],row['versions'])] for row in data['commits']]
        self.assertEqual(decoded,expected)
        self.assertEqual([[packed['paths'][i],n] for i,n in packed['top_paths']],data['top_paths'])

    def test_forced_gzip_is_reproducible_and_lossless(self):
        data=analyze(self.repo)
        first=render(data,compression='gzip')
        self.assertEqual(first,render(data,compression='gzip'))
        self.assertIn('data-encoding="gzip-base64"',first)
        payload=re.search(r'id="dataset">(.*?)</script>',first,re.S).group(1)
        result=json.loads(gzip.decompress(base64.b64decode(payload)))
        self.assertEqual(result,_packed_payload(data))

    def test_plain_render_escapes_script_breakout(self):
        data=analyze(self.repo)
        data['commits'][0]['subject']='</script><script>alert(1)</script>'
        html=render(data,compression='plain')
        self.assertNotIn('</script><script>alert(1)',html)
        self.assertIn('\\u003c/script\\u003e',html)
        self.assertEqual(html.count('<script'),2)

    def test_compression_option_rejects_invalid_codec(self):
        with self.assertRaises(ValueError):render(analyze(self.repo),compression='brotli')

    def test_tiny_auto_export_stays_plain_for_older_browsers(self):
        html=render(analyze(self.repo))
        self.assertIn('data-encoding="plain-json"',html)
        self.assertNotIn('data-encoding="gzip-base64"',html)

    def test_redacted_compression_still_removes_original_paths(self):
        data=analyze(self.repo,share_safe=True)
        html=render(data,compression='gzip')
        payload=re.search(r'id="dataset">(.*?)</script>',html,re.S).group(1)
        unpacked=json.loads(gzip.decompress(base64.b64decode(payload)))
        serialized=json.dumps(unpacked)
        self.assertNotIn('alpha.py',serialized)
        self.assertNotIn('README.md',serialized)
        self.assertEqual(unpacked['head'],'withheld')

    def test_cli_forced_compression_and_json_separate(self):
        with tempfile.TemporaryDirectory(prefix='orbit-v5-output-') as tmp:
            html=Path(tmp)/'out.html';jsonpath=Path(tmp)/'out.json'
            result=subprocess.run(['python','-m','repoorbit',str(self.repo),'-o',str(html),
                                   '--html-format','gzip','--json',str(jsonpath)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('data-encoding="gzip-base64"',html.read_text())
            payload=json.loads(jsonpath.read_text())
            self.assertNotIn('packed',payload)
            self.assertEqual(payload['commits'][-1]['changes'][0][1],'README.md')

if __name__=='__main__':unittest.main()
