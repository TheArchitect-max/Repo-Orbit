"""Prove the R9 R6 independent compact-history oracle fails closed."""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import unittest
from scripts.browser_payload_integrity import inspect_combined_export


def fixture(n: int = 3) -> tuple[bytes, dict]:
    payload = {
        'head': 'a'*40, 'history_window': 2, 'paths_total': 2,
        'changes_total': 4, 'packed':'path-index-v1',
        'paths':['src/a.py','src/b.py'],
        'top_paths':[[0,n]],
        'commits':[
            {'changes':[['A',0,1],['M',1,2]]},
            {'changes':[['M',0,3],['D',0,0]]},
        ],
    }
    raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode('utf-8')
    document=(b'<script id="dataset" data-encoding="gzip-base64">'
        +base64.b64encode(gzip.compress(raw,mtime=0))+b'</script>')
    reference={
        'maximum_html_bytes':len(document)+100,
        'uncompressed_dataset_sha256':hashlib.sha256(raw).hexdigest(),
        'required_dataset_fields':{'head':'a'*40,'history_window':2,'paths_total':2},
    }
    return document,reference


class CompactHistoryOracleTests(unittest.TestCase):
    def test_exact_history_status_order_and_one_based_frames(self):
        html, reference=fixture()
        result=inspect_combined_export(html,reference)
        self.assertEqual(result['r9_r6_compact_history_exact'],{
            'status':'PASS',
            'source':'independently decompressed canonical packed Git dataset',
            'path':'src/a.py', 'event_count':3, 'last_events_verified':3,
            'original_events':4,
            'last_eight':[
                {'frame':1,'status':'A'},
                {'frame':2,'status':'M'},
                {'frame':2,'status':'D'},
            ],
        })

    def test_forged_count_rejected_even_with_matching_payload_sha(self):
        html,reference=fixture(n=4)
        with self.assertRaisesRegex(ValueError,'Canonical hotspot count'):
            inspect_combined_export(html,reference)

if __name__=='__main__':unittest.main()
