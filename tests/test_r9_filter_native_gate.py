"""Native R9 filtered-redraw acceptance must be fail-closed and source-bound."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import unittest
from pathlib import Path

from scripts import audit_browser_zips, run_browser_evidence
from scripts.benchmark_r9_filter_candidates import DRAW_BATCH, FILTERS, OLD_SHA, validate_filter_benchmark

ROOT = Path(__file__).resolve().parents[1]


def sample():
    image=b'\x89PNG\r\n\x1a\n'+b'Z'*1400
    digest=hashlib.sha256(image).hexdigest()
    cases={}
    for view in ('orbit','atlas'):
        for key in FILTERS:
            png={label:{'path':f'FILTER_PIXELS/{view}_{key}_{label}.png',
                        'sha256':digest,'bytes':len(image)} for label in ('r9_native','candidate')}
            cases[view+'/'+key]={
                'raw_ms':{'r9_native':[16.0]*21,'candidate':[2.0]*21},
                'median_ms':{'r9_native':16.0,'candidate':2.0},'speedup_x':8.0,
                'png_sha256':{'r9_native':digest,'candidate':digest},'png':png,
                'ui':{'r9_native':{'matches':'100'},'candidate':{'matches':'100'}},
                'parity':True,
            }
    states=[{'state':name,'status':'PASS',
             'png':{'r9_native':digest,'candidate':digest},
             'dom':{'r9_native':{'matches':'100'},'candidate':{'matches':'100'}}}
            for name in ('clear','zero_results','map_only','combined_filter')]
    r={'protocol':'R9_FILTER_V1_PAIRED_DRAW','pairs':21,'baseline_sha256':OLD_SHA,
       'candidate_sha256':'c'*64,'batch_draws':DRAW_BATCH,'filter_set':FILTERS,
       'page_errors':[],'network_requests':[],'behavioral_parity':states,
       'keyboard_inspection':{'r9_native':'file_01234.py','candidate':'file_01234.py'},
       'cases':cases,'acceptance':'PASS_WITHIN_SCOPE'}
    return r,image

class R9NativeFilterGateTests(unittest.TestCase):
    def test_runner_and_offline_matrix_auditor_require_new_gate(self):
        self.assertIn('r9_filter_factor_performance',run_browser_evidence.STAGES)
        self.assertIn('R9_FILTER_PAIRED_DRAW.json', audit_browser_zips.REQUIRED)
        self.assertIn('SOURCE_SNAPSHOT/scripts/benchmark_r9_filter_candidates.py',audit_browser_zips.REQUIRED)
        self.assertIn('SOURCE_SNAPSHOT/baselines/r9-native-accepted/repoorbit/viewer.js',audit_browser_zips.REQUIRED)
        self.assertIs(run_browser_evidence.validate_filter_benchmark,validate_filter_benchmark)
        self.assertIs(audit_browser_zips.validate_filter_benchmark,validate_filter_benchmark)
    def test_synthetic_complete_report_validates(self):
        r,png=sample()
        self.assertEqual(validate_filter_benchmark(r,'c'*64,lambda _:png),[])
    def test_missing_original_png_rejected(self):
        r,_=sample()
        self.assertTrue(any('missing_png' in e for e in validate_filter_benchmark(r,'c'*64,lambda _: (_ for _ in ()).throw(KeyError('missing')))))
    def test_worse_speed_rejected(self):
        r,png=sample(); c=r['cases']['atlas/cluster'];c['raw_ms']['candidate']=[8.0]*21;c['median_ms']['candidate']=8.0;c['speedup_x']=2.0
        self.assertIn('atlas/cluster:insufficient_speedup',validate_filter_benchmark(r,'c'*64,lambda _:png))
    def test_fabricated_median_rejected(self):
        r,png=sample();r['cases']['orbit/exact']['median_ms']['candidate']=0.1
        self.assertIn('orbit/exact:median_mismatch_candidate',validate_filter_benchmark(r,'c'*64,lambda _:png))
    def test_wrong_source_rejected(self):
        r,png=sample();self.assertIn('source_sha_mismatch',validate_filter_benchmark(r,'x'*64,lambda _:png))
    def test_corrupt_png_rejected(self):
        r,png=sample();self.assertTrue(any('png_integrity' in e for e in validate_filter_benchmark(r,'c'*64,lambda _:png+b'Z')))
    def test_missing_filter_state_rejected(self):
        r,png=sample();r['behavioral_parity'].pop()
        self.assertIn('missing_behavioral_states',validate_filter_benchmark(r,'c'*64,lambda _:png))
    def test_changed_measurement_batch_rejected(self):
        r,png=sample();r['batch_draws']=32
        self.assertIn('benchmark_parameters_modified',validate_filter_benchmark(r,'c'*64,lambda _:png))
    def test_high_resolution_batches_are_real_and_strictly_enforced(self):
        self.assertEqual(DRAW_BATCH,256)
        r,png=sample()
        rec=r['cases']['atlas/exact']
        rec['raw_ms']['candidate']=[0.0]*21
        self.assertIn('atlas/exact:invalid_raw_candidate',validate_filter_benchmark(r,'c'*64,lambda _:png))
    def test_browser_configuration_remains_opt_in(self):
        text=(ROOT/'.circleci/config.yml').read_text()
        self.assertEqual(text.count('default: false'),6)
        self.assertEqual(text.count('when: always'),6)

if __name__=='__main__':unittest.main()
