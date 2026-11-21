"""R9: native Chromium E2E and paired renderer benchmark with complete fail-closed evidence ZIP per OS.

Requires Playwright only in the test environment; no application runtime dependency.
Builds two deterministic synthetic Git-backed browser fixtures from source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_ci_evidence import (build_zip, digest, now, provenance,
                                     run_logged, write_json)
from scripts.audit_native_matrix import audit_browser
from scripts.browser_payload_integrity import inspect_fixture
from scripts.benchmark_viewer_r9 import validate_performance, sha_bytes
from scripts.r9_raster_evidence import inspect_png_artifacts
from scripts.benchmark_r9_filter_candidates import validate_filter_benchmark, OLD_SHA as ACCEPTED_R9_SHA

PLATFORMS = {'Linux': 'linux', 'Windows': 'windows', 'Darwin': 'macos'}
PLAYWRIGHT_PIN = '1.65.2'
STAGES = ('preflight', 'small_demo_fixture', 'combined_maximum_fixture', 'chromium_e2e', 'r9_paired_viewer_performance', 'r9_filter_factor_performance')
EXPECTED = ROOT / 'validation' / 'BROWSER_EXPECTED_SHA256.json'


def copy_results(staging: Path) -> None:
    """Save actual generated assets/reports even when browser tests fail."""
    for relative in ('demo/RepoOrbit_Demo.html',
                     'demo/RepoOrbit_CombinedMaximum.html',
                     'demo/RepoOrbit_Preview.png',
                     'evidence/v07_browser.json',
                     'evidence/browser_combined_limits.json',
                     'evidence/browser_security_limits.json'):
        source = ROOT / relative
        if source.is_file():
            destination = staging / 'GENERATED' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)


def fixture_provenance(staging: Path) -> dict:
    spec = json.loads(EXPECTED.read_text(encoding='utf-8'))
    checked = {}
    for rel, expected_hash in spec.items():
        path = ROOT / rel
        actual = digest(path) if path.is_file() else None
        checked[rel] = {'expected': expected_hash, 'actual': actual,
                        'match': actual == expected_hash}
    root = ROOT / 'external-results' / 'browser-fixture-git'
    proc = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                          capture_output=True, text=True, encoding='utf-8')
    head = proc.stdout.strip() if proc.returncode == 0 else None
    result = {'status': 'PASS' if all(x['match'] for x in checked.values()) else 'FAIL',
              'assets': checked, 'git_fixture_head': head,
              'git_fixture_is_real_history': head is not None,
              'synthetic_data_only': True}
    try:
        result['combined_canonical_dataset'] = inspect_fixture(
            ROOT / 'demo' / 'RepoOrbit_CombinedMaximum.html')
    except (OSError, ValueError) as exc:
        result['status'] = 'FAIL'
        result['combined_canonical_dataset'] = {'status': 'FAIL', 'error': str(exc)}
    if head is None:
        result['status'] = 'FAIL'
    write_json(staging / 'FIXTURE_PROVENANCE.json', result)
    return result


def run_all(staging: Path, system: str) -> int:
    if staging.exists():
        raise RuntimeError('HOLD: stale browser evidence workspace')
    staging.mkdir(parents=True)
    state = {'schema': 1, 'system': system, 'started_utc': now(),
             'status': 'FAIL', 'stages': []}
    write_json(staging / 'BROWSER_STAGE_STATUS.json', state)
    try:
        state['provenance'] = provenance(staging, system)
        from importlib.metadata import version
        actual_playwright = version('playwright')
        if actual_playwright != PLAYWRIGHT_PIN:
            raise RuntimeError(f'HOLD: Playwright must be {PLAYWRIGHT_PIN}; got {actual_playwright}')
        context = json.loads((staging / 'CI_CONTEXT.json').read_text(encoding='utf-8'))
        context['playwright_version'] = actual_playwright
        context['browser_scope'] = 'Native Chromium only, not Firefox/WebKit or accessibility certification'
        write_json(staging / 'CI_CONTEXT.json', context)
        (ROOT / 'evidence').mkdir(exist_ok=True)
        (ROOT / 'demo').mkdir(exist_ok=True)
        commands = [
            ('preflight', [sys.executable, 'scripts/preflight_circleci.py']),
            ('small_demo_fixture', [sys.executable, 'scripts/make_demo.py']),
            ('combined_maximum_fixture', [sys.executable, 'scripts/stress_combined_limits.py',
                '--repository', 'external-results/browser-fixture-git',
                '--html', 'demo/RepoOrbit_CombinedMaximum.html',
                '--report', str(staging / 'FIXTURE_BUILD.json')]),
            ('chromium_e2e', [sys.executable, 'scripts/run_native_browser.py',
                '--out', str(staging / 'BROWSER_NATIVE.json')]),
            ('r9_paired_viewer_performance', [sys.executable, '-u', 'scripts/benchmark_viewer_r9.py',
                '--pairs', '21', '--out', str(staging / 'R9_PAIRED_VIEWER_PERFORMANCE.json')]),
            ('r9_filter_factor_performance', [sys.executable, '-u', 'scripts/benchmark_r9_filter_candidates.py',
                '--pairs', '21', '--out', str(staging / 'R9_FILTER_PAIRED_DRAW.json')]),
        ]
        for i, (name, command) in enumerate(commands, 1):
            logname = f'logs/{i:02d}_{name}.log'
            print(f'R9 BROWSER: {system}/{name}', flush=True)
            rc, elapsed = run_logged(command, ROOT, staging / logname)
            record = {'stage': name, 'status': 'PASS' if rc == 0 else 'FAIL',
                      'returncode': rc, 'elapsed_seconds': elapsed, 'log': logname}
            if not rc and name == 'combined_maximum_fixture':
                f = fixture_provenance(staging)
                if f['status'] != 'PASS':
                    record['status'] = 'FAIL'
                    record['returncode'] = rc = 2
                    record['error'] = 'Fixture integrity failed: ' + json.dumps(f, ensure_ascii=True)
                    print('R9 BROWSER HOLD: ' + record['error'], file=sys.stderr, flush=True)
            state['stages'].append(record)
            write_json(staging / 'BROWSER_STAGE_STATUS.json', state)
            if rc:
                state.update(status='FAIL', failed_stage=name, finished_utc=now())
                write_json(staging / 'BROWSER_STAGE_STATUS.json', state)
                return rc
        state.update(status='BROWSER_EXECUTED_PENDING_AUDIT', finished_utc=now())
        write_json(staging / 'BROWSER_STAGE_STATUS.json', state)
        return 0
    except Exception as exc:
        state.update(status='FAIL', error=type(exc).__name__ + ': ' + str(exc),
                     finished_utc=now())
        write_json(staging / 'BROWSER_STAGE_STATUS.json', state)
        print('R9 BROWSER HOLD: ' + str(exc), file=sys.stderr, flush=True)
        return 2
    finally:
        copy_results(staging)


def evaluate_platform(staging: Path, system: str) -> dict:
    errors = []
    status = json.loads((staging / 'BROWSER_STAGE_STATUS.json').read_text(encoding='utf-8'))
    observed = {s['stage'] for s in status.get('stages', []) if s.get('status') == 'PASS'}
    if status.get('status') != 'BROWSER_EXECUTED_PENDING_AUDIT' or observed != set(STAGES):
        errors.append({'type': 'missing_successful_stages', 'have': sorted(observed)})
    required = ('CI_CONTEXT.json', 'SOURCE_SHA256.json', 'FIXTURE_PROVENANCE.json',
                'SOURCE_SNAPSHOT/validation/BROWSER_CANONICAL_PAYLOAD.json',
                'FIXTURE_BUILD.json', 'BROWSER_NATIVE.json',
                'R9_PAIRED_VIEWER_PERFORMANCE.json',
                'R9_FILTER_PAIRED_DRAW.json',
                'SOURCE_SNAPSHOT/scripts/benchmark_r9_filter_candidates.py',
                'SOURCE_SNAPSHOT/baselines/r9-native-accepted/repoorbit/viewer.js',
                'SOURCE_SNAPSHOT/baselines/v0.8.0/repoorbit/viewer.js',
                'SOURCE_SNAPSHOT/validation/BROWSER_R8_ACCEPTED_SHA256.json',
                'GENERATED/demo/RepoOrbit_Demo.html',
                'GENERATED/demo/RepoOrbit_CombinedMaximum.html',
                'GENERATED/demo/RepoOrbit_Preview.png',
                'GENERATED/evidence/v07_browser.json',
                'GENERATED/evidence/browser_combined_limits.json',
                'GENERATED/evidence/browser_security_limits.json')
    for name in required:
        if not (staging / name).is_file():
            errors.append({'type': 'missing_browser_evidence', 'path': name})
    if not errors:
        context = json.loads((staging / 'CI_CONTEXT.json').read_text(encoding='utf-8'))
        source = json.loads((staging / 'SOURCE_SHA256.json').read_text(encoding='utf-8'))
        assets = json.loads((staging / 'FIXTURE_PROVENANCE.json').read_text(encoding='utf-8'))
        fixture = json.loads((staging / 'FIXTURE_BUILD.json').read_text(encoding='utf-8'))
        browser = json.loads((staging / 'BROWSER_NATIVE.json').read_text(encoding='utf-8'))
        v7 = json.loads((staging / 'GENERATED/evidence/v07_browser.json').read_text(encoding='utf-8'))
        maximum = json.loads((staging / 'GENERATED/evidence/browser_combined_limits.json').read_text(encoding='utf-8'))
        security = json.loads((staging / 'GENERATED/evidence/browser_security_limits.json').read_text(encoding='utf-8'))
        expected = json.loads(EXPECTED.read_text(encoding='utf-8'))
        if context.get('system') != system or context.get('playwright_version') != PLAYWRIGHT_PIN:
            errors.append({'type': 'native_host_or_playwright_mismatch'})
        if not all(v['match'] for v in source['reference_source_sha256'].values()):
            errors.append({'type': 'source_integrity_mismatch'})
        if assets.get('status') != 'PASS' or not assets.get('git_fixture_head') or assets.get('combined_canonical_dataset',{}).get('status') != 'PASS':
            errors.append({'type': 'fixture_provenance_failed'})
        try:
            canonical = inspect_fixture(staging/'GENERATED/demo/RepoOrbit_CombinedMaximum.html')
            if canonical['sha256_uncompressed_dataset'] != assets['combined_canonical_dataset']['sha256_uncompressed_dataset']:
                errors.append({'type': 'different_runtime_and_archived_browser_dataset'})
        except (OSError, ValueError, KeyError) as exc:
            errors.append({'type': 'combined_canonical_dataset_not_verified', 'error': str(exc)})
        for relative, refhash in expected.items():
            rel = 'GENERATED/' + relative if relative.startswith('demo/') else 'SOURCE_SNAPSHOT/' + relative
            if not (staging / rel).is_file() or digest(staging / rel) != refhash:
                errors.append({'type': 'browser_asset_sha_mismatch', 'asset': relative})
        observed_counts = fixture.get('observed', {})
        if fixture.get('status') != 'PYTHON_GATE_PASS' or any(
            observed_counts.get(k) != v for k,v in
            [('commits',8000), ('paths_total',80000), ('events',900000), ('checked_snapshots',3)]
        ):
            errors.append({'type': 'combined_git_fixture_not_proven'})
        if v7.get('status') != 'PASS' or v7.get('javascript_errors') or v7.get('network_requests'):
            errors.append({'type': 'v7_browser_assertions_not_pass'})
        if maximum.get('status') != 'PASS' or maximum.get('uncaught_javascript_errors') or maximum.get('console_errors') or not maximum.get('no_external_http_requests'):
            errors.append({'type': 'maximum_browser_assertions_not_pass'})
        if maximum.get('r9_r6_compact_history_exact') != canonical.get('r9_r6_compact_history_exact'):
            errors.append({'type': 'r9_r6_compact_history_not_exact'})
        if (security.get('status') != 'PASS' or security.get('cases') != {
            'normal_synthetic_demo':'PASS',
            'gzip_expansion_exceeds_64_mib':'PASS',
            'invalid_utf8_gzip_rejected':'PASS'} or
            security.get('expected_guard_bytes') != 64*1024*1024 or
            security.get('oversize_expanded_bytes') != 64*1024*1024 + 1 or
            security.get('network_requests') or
            security.get('source_sha256') != digest(staging/'GENERATED/demo/RepoOrbit_Demo.html') or
            security.get('browser_version') != browser.get('browser_version')):
            errors.append({'type': 'browser_gzip_security_limit_not_proven'})
        perf = json.loads((staging / 'R9_PAIRED_VIEWER_PERFORMANCE.json').read_text(encoding='utf-8'))
        candidate_sha = digest(staging/'SOURCE_SNAPSHOT/repoorbit/viewer.js')
        perf_errors = validate_performance(perf,candidate_sha)
        if perf_errors:
            errors.append({'type':'r9_performance_gate_failed','details':perf_errors})
        png_errors = inspect_png_artifacts(perf, lambda path:(staging/path).read_bytes())
        if png_errors:
            errors.append({'type':'r9_png_artifacts_failed','details':png_errors})
        filter_report = json.loads((staging / 'R9_FILTER_PAIRED_DRAW.json').read_text(encoding='utf-8'))
        filter_errors = validate_filter_benchmark(filter_report, candidate_sha,
            lambda path: (staging / path).read_bytes())
        if filter_report.get('acceptance') != 'PASS_WITHIN_SCOPE' or filter_errors:
            errors.append({'type':'r9_filter_factor_gate_failed','details':filter_errors,
                'reported_status':filter_report.get('acceptance')})
        if digest(staging/'SOURCE_SNAPSHOT/baselines/r9-native-accepted/repoorbit/viewer.js') != ACCEPTED_R9_SHA:
            errors.append({'type':'accepted_r9_baseline_mismatch'})
        summary = audit_browser([browser], expected, [system])
        if summary['status'] != 'PASS_WITHIN_PREDECLARED_SCOPE':
            errors.append({'type': 'native_browser_requirements_not_pass',
                           'details': summary})
    return {'schema': 1, 'system': system,
            'status': 'PASS_WITHIN_PREDECLARED_SCOPE' if not errors else 'FAIL',
            'errors': errors, 'playwright_pin': PLAYWRIGHT_PIN,
            'scope': 'Chromium E2E + R8/R9 Canvas draw + R9 filter factor six-context benchmark, 21 paired batches per context',
            'other_browser_engines': 'NOT_TESTED',
            'a11y_independent_review': 'HOLD'}


def package(staging: Path, out: Path, system: str) -> int:
    out.mkdir(parents=True, exist_ok=True)
    if not staging.is_dir():
        staging.mkdir(parents=True)
        write_json(staging / 'BROWSER_STAGE_STATUS.json',
                   {'status': 'FAIL', 'stages': [], 'error': 'No browser execution workspace'})
    installer_log = out.parent / ('browser-' + PLATFORMS[system] + '-install.log')
    if installer_log.is_file():
        install_archive = staging / 'logs' / '00_playwright_install.log'
        install_archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installer_log, install_archive)
    try:
        result = evaluate_platform(staging, system)
    except Exception as exc:
        result = {'schema': 1, 'system': system, 'status': 'FAIL',
                  'errors': [{'type': 'audit_exception', 'message': repr(exc)}]}
    write_json(staging / 'BROWSER_PLATFORM_AUDIT.json', result)
    archive, manifest = build_zip(staging, out, system)
    renamed = out / archive.name.replace('REPO_ORBIT_R7_', 'REPO_ORBIT_R9_BROWSER_')
    archive.rename(renamed)
    (out/(archive.name+'.sha256')).unlink()
    (out/(renamed.name+'.sha256')).write_text(digest(renamed)+'  '+renamed.name+'\n', encoding='utf-8')
    # Rename only the envelope; ZIP manifest still references all internal bytes.
    with zipfile.ZipFile(renamed) as z:
        if z.testzip() is not None or len(z.namelist()) != manifest['archive_entry_count']:
            raise RuntimeError('R9 browser ZIP integrity failed')
    print('R9_BROWSER_ZIP:', renamed, 'files:', len(manifest['files']), flush=True)
    print('R9_BROWSER_PLATFORM_AUDIT:', result['status'], flush=True)
    if result['status'] != 'PASS_WITHIN_PREDECLARED_SCOPE':
        print('R9_BROWSER_PLATFORM_ERRORS:', json.dumps(result.get('errors', []), sort_keys=True), flush=True)
    return 0 if result['status'] == 'PASS_WITHIN_PREDECLARED_SCOPE' else 2


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--platform', choices=PLATFORMS, required=True)
    p.add_argument('--out', type=Path, required=True)
    op = p.add_mutually_exclusive_group(required=True)
    op.add_argument('--run', action='store_true')
    op.add_argument('--package-only', action='store_true')
    args = p.parse_args()
    output = args.out.resolve()
    if output.parent != (ROOT/'external-results').resolve() or output.name != 'browser-'+PLATFORMS[args.platform]:
        p.error('Browser outputs must be external-results/browser-<platform>')
    staging = output.parent / (output.name + '-raw')
    if args.run:
        return run_all(staging, args.platform)
    return package(staging, output, args.platform)


if __name__ == '__main__':
    raise SystemExit(main())
