"""Check cross-repository and native OS benchmark evidence without optimistic PASS.

No dependencies outside Python stdlib. Does not invent unavailable measurements.
Audit is intentionally stringent: for a broad *bounded* performance claim,
all predeclared targets, native hosts, windows and parity checks are required.
A universal all-repository speedup can never be inferred from finite sampling.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONF = ROOT / 'validation' / 'PINNED_TARGETS.json'


def system_from_platform(description: str) -> str | None:
    if description.startswith('Linux'):
        return 'Linux'
    if description.startswith('Windows'):
        return 'Windows'
    if description.startswith(('macOS', 'Darwin')):
        return 'Darwin'
    return None


def verify_one(record: dict, target: str, system: str, config: dict) -> tuple[list, list]:
    errors, regressions = [], []
    target_spec = config['repositories'][target]
    m = record.get('metadata', {})
    host = record.get('host', {})
    if record.get('status') != 'PASS':
        errors.append('benchmark_status_not_pass')
    if m.get('HEAD') != target_spec['sha']:
        errors.append('pinned_SHA_mismatch')
    if m.get('origin', '').removesuffix('.git').rstrip('/') != target_spec['url'].removesuffix('.git').rstrip('/'):
        errors.append('origin_mismatch')
    if system_from_platform(m.get('platform', '')) != system or host.get('os') != system:
        errors.append('native_platform_mismatch')
    if not host.get('cpu') or not host.get('python') or not host.get('git'):
        errors.append('incomplete_machine_profile')
    if m.get('is_shallow') and any(int(c.get('actual_commits',0)) < max(config['required_windows']) for c in record.get('cases', [])):
        errors.append('shallow_or_truncated_window')
    if record.get('source_sha256') != config['source_sha256']:
        errors.append('source_identity_mismatch')
    windows_seen = set()
    for case in record.get('cases', []):
        n = case.get('actual_commits')
        if n not in config['required_windows']:
            continue
        if n in windows_seen:
            errors.append(f'duplicate_window_{n}')
        windows_seen.add(n)
        if case.get('requested_commits') != n:
            errors.append(f'truncated_window_{n}')
        if case.get('verification') not in ('sample','full'):
            errors.append(f'unverified_tree_{n}')
        if case.get('parity') != {'canonical_json':'PASS','browser_dataset':'PASS'}:
            errors.append(f'output_mismatch_{n}')
        try:
            times = case['raw_ms']
            for version in ('v0.7.0','v0.8.0'):
                for metric in ('analyze_ms','render_ms','total_ms'):
                    seq = times[version][metric]
                    if len(seq) < config['min_runs'] or any(not isinstance(v,(float,int)) or not math.isfinite(v) or v <= 0 for v in seq):
                        raise ValueError('invalid measurements')
            med_old = statistics.median(times['v0.7.0']['total_ms'])
            med_new = statistics.median(times['v0.8.0']['total_ms'])
            if med_new > med_old * config['maximum_regression_ratio']:
                regressions.append({'target':target,'os':system,'window':n,
                                    'baseline_ms':round(med_old,4),'candidate_ms':round(med_new,4),
                                    'slowdown_ratio':round(med_new/med_old,4)})
        except (KeyError, ValueError, TypeError, ZeroDivisionError):
            errors.append(f'invalid_raw_measurements_{n}')
    for n in config['required_windows']:
        if n not in windows_seen:
            errors.append(f'missing_window_{n}')
    return errors, regressions


def audit_browser(records: list[dict], expected: dict, platforms: list[str]) -> dict:
    required_names={'tests/browser_smoke.py','tests/browser_v7.py','tests/browser_combined_limits.py','tests/browser_security_limits.py'}
    seen={}
    errors=[]
    for record in records:
        osname=record.get('os')
        if osname not in platforms:
            errors.append({'os':osname,'reason':'unrecognized_native_platform'})
            continue
        if osname in seen:
            errors.append({'os':osname,'reason':'duplicate_platform_evidence'})
            continue
        seen[osname]=record
        if record.get('status')!='PASS' or record.get('browser')!='Chromium' or not record.get('browser_version'):
            errors.append({'os':osname,'reason':'browser_not_pass_or_missing_version'})
        if record.get('expected_asset_hashes')!=expected or record.get('asset_hashes_match')!={k:True for k in expected}:
            errors.append({'os':osname,'reason':'dataset_or_viewer_hash_mismatch'})
        tests=record.get('test_results',[])
        if {x.get('name') for x in tests}!=required_names or any(x.get('status')!='PASS' or x.get('returncode')!=0 for x in tests):
            errors.append({'os':osname,'reason':'required_browser_tests_not_pass'})
    missing=sorted(set(platforms)-set(seen))
    status='FAIL' if errors else ('HOLD' if missing else 'PASS_WITHIN_PREDECLARED_SCOPE')
    return {'status':status,'measured_native_platforms':sorted(seen),
            'missing_platforms':missing,'invalid_browser_results':errors,
            'scope':'Chromium E2E only; Firefox/WebKit and universal browser performance remain unverified'}


def evaluate(records: list[dict], config: dict, browser_records: list[dict] | None = None,
             expected_browser_hashes: dict | None = None) -> dict:
    """Pure acceptance gate, suitable for unit tests with synthetic evidence."""
    required = {(r,os_) for r in config['required_repositories'] for os_ in config['required_platforms']}
    supplied = {}
    ignored = []
    for record in records:
        repo = record.get('pinned_target')
        system = record.get('host',{}).get('os')
        if (repo,system) not in required:
            ignored.append({'repo':repo,'system':system,'reason':'not a required matrix entry'})
            continue
        supplied.setdefault((repo,system),[]).append(record)
    failures = []
    regressions = []
    valid = []
    for cell, bundle in supplied.items():
        repo, system = cell
        if len(bundle) != 1:
            failures.append({'repo':repo,'os':system,'errors':['duplicate_evidence']})
            continue
        errors, slow = verify_one(bundle[0],repo,system,config)
        if errors:
            failures.append({'repo':repo,'os':system,'errors':errors})
        else:
            valid.append({'repo':repo,'os':system})
        regressions.extend(slow)
    missing = [{'repo':repo,'os':system} for repo,system in sorted(required-set(supplied))]
    # Priority: explicit regression / corrupted supplied evidence => FAIL.
    # Otherwise incomplete matrix => HOLD; complete nonregressing coverage => PASS.
    if failures or regressions:
        status = 'FAIL'
    elif missing:
        status = 'HOLD'
    else:
        status = 'PASS_WITHIN_PREDECLARED_SCOPE'
    return {
        'cli_performance_gate':status,
        'general_all_possible_repositories_claim':'NOT_PROVABLE_BY_FINITE_BENCHMARK',
        'browser_cross_platform_gate':audit_browser(browser_records or [], expected_browser_hashes or {},
                                                    config['required_platforms']),
        'required_independent_repositories': len(config['required_repositories']),
        'required_native_platforms': len(config['required_platforms']),
        'required_scenarios':len(required)*len(config['required_windows']),
        'valid_host_repo_cells':valid,
        'missing_host_repo_cells':missing,
        'invalid_evidence':failures,
        'performance_regressions_gt_5pct':regressions,
        'ignored_supplemental_evidence':ignored,
    }


def report_md(audit: dict) -> str:
    lines=['# REPO ORBIT — Native external performance acceptance', '',
           f"CLI performance gate: **{audit['cli_performance_gate']}**",
           f"Native Chromium browser gate: **{audit['browser_cross_platform_gate']['status']}**", '',
           f"Valid native repo/host cells: {len(audit['valid_host_repo_cells'])}; "
           f"missing: {len(audit['missing_host_repo_cells'])}; "
           f"invalid: {len(audit['invalid_evidence'])}; "
           f"measured >5% regressions: {len(audit['performance_regressions_gt_5pct'])}.", '',
           'The Chromium browser gate is evaluated separately; no finite evidence proves speedup on all Git repositories.', '',
           '## Valid measurements', '']
    for r in audit['valid_host_repo_cells']:
        lines.append(f"- {r['repo']} / {r['os']}")
    lines.extend(['','## Missing native measurements',''])
    for r in audit['missing_host_repo_cells']:
        lines.append(f"- {r['repo']} / {r['os']}")
    if audit['invalid_evidence']:
        lines.extend(['','## Rejected evidence','', '```json',json.dumps(audit['invalid_evidence'],indent=2),'```'])
    if audit['performance_regressions_gt_5pct']:
        lines.extend(['','## Measured regressions','', '```json',json.dumps(audit['performance_regressions_gt_5pct'],indent=2),'```'])
    lines.extend(['','Important: repeated samples from one Git repository are not independent codebases; '
                  'paired measurement intervals also do not quantify variability among unrelated machines.',''])
    return '\n'.join(lines)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,nargs='+',required=True,help='Folders containing native benchmark JSON files')
    parser.add_argument('--out',type=Path,default=ROOT/'external-results'/'matrix_audit.json')
    parser.add_argument('--browser-inputs',type=Path,nargs='*',default=[],
                        help='Folders/files of native Chromium evidence')
    args=parser.parse_args()
    config=json.loads(CONF.read_text())
    records=[]
    paths=[]
    for root in args.inputs:
        for path in sorted(root.rglob('*.json')):
            # Metadata, status and old-format legacy evidence are not native matrix records.
            try:
                val=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,json.JSONDecodeError):
                continue
            if isinstance(val,dict) and 'cases' in val and 'pinned_target' in val:
                records.append(val)
                paths.append(str(path))
    browsers=[]
    for entry in args.browser_inputs:
        files=[entry] if entry.is_file() else list(entry.rglob('*.json')) if entry.is_dir() else []
        for path in files:
            try: val=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,json.JSONDecodeError):continue
            if isinstance(val,dict) and 'test_results' in val and 'browser' in val:
                browsers.append(val)
    expected=json.loads((ROOT/'validation'/'BROWSER_EXPECTED_SHA256.json').read_text())
    result=evaluate(records,config,browsers,expected)
    result['input_evidence_files']=paths
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    args.out.with_suffix('.md').write_text(report_md(result))
    print(result['cli_performance_gate'])
    print(f"Valid cells: {len(result['valid_host_repo_cells'])}; missing: {len(result['missing_host_repo_cells'])}")
    print(args.out)

if __name__=='__main__':
    main()
