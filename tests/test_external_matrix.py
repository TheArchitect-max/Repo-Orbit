"""Logic tests only: fixtures here are synthetic and NEVER released as benchmark evidence."""
import copy
import json
import unittest
from pathlib import Path
from scripts.audit_native_matrix import evaluate, verify_one, audit_browser
from scripts.run_native_matrix import ensure_sources, native_host

CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'validation' / 'PINNED_TARGETS.json').read_text())


def case(n, old=100.0, new=90.0, parity=True):
    return {
        'requested_commits':n,'actual_commits':n,'verification':'sample',
        'parity':{'canonical_json':'PASS','browser_dataset':'PASS'} if parity else {'canonical_json':'FAIL','browser_dataset':'PASS'},
        'raw_ms':{
            'v0.7.0':{'analyze_ms':[60.0]*21,'render_ms':[old-60.0]*21,'total_ms':[old]*21},
            'v0.8.0':{'analyze_ms':[50.0]*21,'render_ms':[new-50.0]*21,'total_ms':[new]*21}
        },
    }


def fixture(repo,system):
    target = CONFIG['repositories'][repo]
    osname = {'Linux':'Linux-6.0-x86_64','Windows':'Windows-11-10.0','Darwin':'macOS-14.7-arm64'}[system]
    return {
        'status':'PASS','pinned_target':repo,
        'host':{'os':system,'cpu':'fixture only','python':'3.13','git':'git version 2.47'},
        'metadata':{'HEAD':target['sha'],'origin':target['url'],'platform':osname,'is_shallow':False},
        'source_sha256':copy.deepcopy(CONFIG['source_sha256']),
        'cases':[case(n) for n in CONFIG['required_windows']],
    }


class AcceptanceGateTests(unittest.TestCase):
    def test_baseline_sources_match_checked_sha(self):
        ensure_sources(CONFIG)

    def test_host_reports_actual_kernel(self):
        self.assertIn(native_host()['os'], ('Linux','Windows','Darwin'))

    def test_incomplete_matrix_is_hold(self):
        result=evaluate([fixture('requests','Linux')],CONFIG)
        self.assertEqual(result['cli_performance_gate'],'HOLD')
        self.assertEqual(len(result['missing_host_repo_cells']),8)

    def test_all_required_complete_is_bounded_pass(self):
        records=[fixture(r,s) for r in CONFIG['required_repositories'] for s in CONFIG['required_platforms']]
        self.assertEqual(evaluate(records,CONFIG)['cli_performance_gate'],'PASS_WITHIN_PREDECLARED_SCOPE')

    def test_regression_gt_five_percent_is_fail(self):
        rec=fixture('flask','Linux')
        rec['cases'][0]=case(60,old=100.0,new=106.0)
        result=evaluate([rec],CONFIG)
        self.assertEqual(result['cli_performance_gate'],'FAIL')
        self.assertEqual(result['performance_regressions_gt_5pct'][0]['window'],60)

    def test_wrong_commit_is_rejected(self):
        rec=fixture('flask','Linux')
        rec['metadata']['HEAD']='0'*40
        self.assertIn('pinned_SHA_mismatch',verify_one(rec,'flask','Linux',CONFIG)[0])

    def test_wrong_origin_is_rejected(self):
        rec=fixture('flask','Linux')
        rec['metadata']['origin']='https://github.com/example/misleading.git'
        self.assertIn('origin_mismatch',verify_one(rec,'flask','Linux',CONFIG)[0])

    def test_different_source_is_rejected(self):
        rec=fixture('flask','Linux')
        rec['source_sha256']['v0.8.0']['core']='0'*64
        self.assertIn('source_identity_mismatch',verify_one(rec,'flask','Linux',CONFIG)[0])

    def test_bad_parity_is_rejected(self):
        rec=fixture('flask','Linux')
        rec['cases'][0]=case(60,parity=False)
        self.assertIn('output_mismatch_60',verify_one(rec,'flask','Linux',CONFIG)[0])

    def test_truncated_window_is_rejected(self):
        rec=fixture('flask','Linux')
        rec['cases'][2]['actual_commits']=950
        errors,_=verify_one(rec,'flask','Linux',CONFIG)
        self.assertIn('missing_window_1000',errors)

    def test_short_trials_are_rejected(self):
        rec=fixture('flask','Linux')
        rec['cases'][1]['raw_ms']['v0.8.0']['total_ms']=[1.0]*5
        self.assertIn('invalid_raw_measurements_300',verify_one(rec,'flask','Linux',CONFIG)[0])

    def test_spoofed_native_platform_is_rejected(self):
        rec=fixture('flask','Windows')
        rec['metadata']['platform']='Linux-6-x86_64'
        self.assertIn('native_platform_mismatch',verify_one(rec,'flask','Windows',CONFIG)[0])

    def test_duplicate_cell_is_rejected(self):
        rec=fixture('flask','Linux')
        result=evaluate([rec,rec],CONFIG)
        self.assertEqual(result['cli_performance_gate'],'FAIL')

    def test_browser_linux_only_is_hold(self):
        expected={'demo.html':'abc'}
        rec={'os':'Linux','status':'PASS','browser':'Chromium','browser_version':'144',
             'expected_asset_hashes':expected,'asset_hashes_match':{'demo.html':True},
             'test_results':[{'name':f,'status':'PASS','returncode':0} for f in
              ('tests/browser_smoke.py','tests/browser_v7.py','tests/browser_combined_limits.py')]}
        result=audit_browser([rec],expected,CONFIG['required_platforms'])
        self.assertEqual(result['status'],'HOLD')
        self.assertEqual(result['missing_platforms'],['Darwin','Windows'])

    def test_browser_matrix_pass_only_when_complete(self):
        expected={'demo.html':'abc'}
        def rec(system):
            return {'os':system,'status':'PASS','browser':'Chromium','browser_version':'144',
                    'expected_asset_hashes':expected,'asset_hashes_match':{'demo.html':True},
                    'test_results':[{'name':f,'status':'PASS','returncode':0} for f in
                     ('tests/browser_smoke.py','tests/browser_v7.py','tests/browser_combined_limits.py')]}
        result=audit_browser([rec(p) for p in CONFIG['required_platforms']],expected,CONFIG['required_platforms'])
        self.assertEqual(result['status'],'PASS_WITHIN_PREDECLARED_SCOPE')
        bad=rec('Linux'); bad['asset_hashes_match']={'demo.html':False}
        self.assertEqual(audit_browser([bad],expected,CONFIG['required_platforms'])['status'],'FAIL')

    def test_one_repo_not_three_independent_repos(self):
        rec=fixture('requests','Linux')
        self.assertEqual(evaluate([rec]*1,CONFIG)['cli_performance_gate'],'HOLD')


if __name__=='__main__':
    unittest.main()
