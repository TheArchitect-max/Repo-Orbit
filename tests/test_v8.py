"""v0.8 optimizations must preserve correctness and offline determinism."""
from __future__ import annotations
import base64
import gzip
import json
import re
import unittest
from pathlib import Path

from repoorbit import __version__
from repoorbit.core import analyze
from repoorbit.render import render, _packed_payload
from test_v6 import fixture


class V8Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, '0.8.0')

    def test_compressed_payload_remains_lossless(self):
        data = fixture()
        doc = render(data, compression='gzip')
        match = re.search(r'<script type="application/json" data-encoding="gzip-base64" id="dataset">(.*?)</script>', doc, re.S)
        self.assertIsNotNone(match)
        content = json.loads(gzip.decompress(base64.b64decode(match.group(1))))
        self.assertEqual(content, _packed_payload(data))

    def test_gzip_determinism_and_zero_timestamp(self):
        data = fixture()
        html_a = render(data, compression='gzip')
        html_b = render(data, compression='gzip')
        self.assertEqual(html_a, html_b)
        match = re.search(r'id="dataset">(.*?)</script>', html_a, re.S)
        header = base64.b64decode(match.group(1))[:10]
        self.assertEqual(header[4:8], b'\x00'*4)

    def test_plain_and_gzip_same_browser_dataset(self):
        data=fixture()
        plain=render(data,compression='plain')
        gz=render(data,compression='gzip')
        p=re.search(r'id="dataset">(.*?)</script>',plain,re.S).group(1)
        g=re.search(r'id="dataset">(.*?)</script>',gz,re.S).group(1)
        self.assertEqual(json.loads(p),json.loads(gzip.decompress(base64.b64decode(g))))

    def test_core_default_and_no_matching_exclusion_have_same_results(self):
        import subprocess, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)
            def git(*args):
                subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
            git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.invalid')
            (repo/'sample.py').write_text('x=1\n');git('add','.');git('commit','-qm','initial')
            regular=analyze(repo,limit=1)
            with_excludes=analyze(repo,limit=1,exclude=('non-existent-directory/**',))
            with_excludes['exclude_patterns']=[]
            self.assertEqual(regular,with_excludes)

if __name__ == '__main__': unittest.main()
