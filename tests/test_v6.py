"""v0.6 source-level gates; browser-level gates live in browser_v6.py."""
import json
import re
import unittest
from pathlib import Path

from repoorbit import __version__
from repoorbit.render import render


def fixture():
    tricky='src/odd&<tag>"quote\'file.py'
    return {
        'schema': 'repoorbit-v3', 'name': 'Synthetic <repo> & "quotes"', 'head': 'a'*40,
        'dirty':False,'history_total':1,'history_window':1,'partial_history':False,
        'baseline':[], 'baseline_versions':[],
        'commits':[{'sha':'a'*40,'date':'2026-01-01T00:00:00+00:00',
                    'author':'A & B','subject':'</script><svg onload="window.XSS=1">',
                    'changes':[['A',tricky]],'versions':[1]}],
        'paths_total':1,'files_final':1,'changes_total':1,
        'top_paths':[[tricky,1]],'excluded_paths':0,'excluded_events':0,
        'exclude_patterns':[],'share_safe':False,'verification':'sample',
        'verified_frames':1,'object_equality':'mode+git-object','notes':[]
    }


class V6Tests(unittest.TestCase):
    def test_version_and_viewer_controls(self):
        self.assertGreaterEqual(tuple(map(int,__version__.split('.'))),(0,6,0))
        html=render(fixture(),compression='plain')
        self.assertIn(f'v{__version__}',html)
        self.assertIn('id="exportsvgexact"',html)
        self.assertIn('id="exportsvg"',html)

    def test_export_is_local_and_uses_no_downloaded_javascript(self):
        html=render(fixture(),compression='plain')
        self.assertIn("connect-src 'none'",html)
        self.assertNotRegex(html,r'<script\s+[^>]*src=')
        self.assertEqual(html.count('<script'),2)

    def test_untrusted_git_metadata_cannot_terminate_payload(self):
        html=render(fixture(),compression='plain')
        self.assertNotIn('</script><svg onload=',html)
        self.assertIn('\\u003csvg',html)
        self.assertIn('&lt;repo&gt;',html)

    def test_gzip_is_still_deterministic(self):
        self.assertEqual(render(fixture(),compression='gzip'),render(fixture(),compression='gzip'))

    def test_svg_escaper_and_dual_export_are_embedded(self):
        html=render(fixture(),compression='plain')
        self.assertIn('function svgExport(exact=false)',html)
        self.assertIn('xmlText(files[id])',html)
        self.assertIn('data-count=',html)
        self.assertIn("svgExport(true)",html)


if __name__=='__main__':unittest.main()
