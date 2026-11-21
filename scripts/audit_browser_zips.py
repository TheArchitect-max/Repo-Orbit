"""Independently audit three R9 native Chromium and performance ZIPs from one Git commit.

No browser or external dependencies are needed to audit. Refuses incomplete,
corrupt, inconsistent, or fabricated PASS claims and preserves HOLD status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_native_matrix import audit_browser
from scripts.browser_payload_integrity import inspect_combined_export, expected_reference
from scripts.benchmark_viewer_r9 import validate_performance
from scripts.r9_raster_evidence import inspect_png_artifacts
from scripts.benchmark_r9_filter_candidates import validate_filter_benchmark, OLD_SHA as ACCEPTED_R9_SHA

OS_SET = {'Linux', 'Windows', 'Darwin'}
BROWSER_HASHES = ROOT/'validation'/'BROWSER_EXPECTED_SHA256.json'
PINS = ROOT/'validation'/'PINNED_TARGETS.json'
REQUIRED = {
    'BROWSER_STAGE_STATUS.json', 'BROWSER_PLATFORM_AUDIT.json',
    'R9_PAIRED_VIEWER_PERFORMANCE.json',
    'R9_FILTER_PAIRED_DRAW.json',
    'SOURCE_SNAPSHOT/scripts/benchmark_r9_filter_candidates.py',
    'SOURCE_SNAPSHOT/baselines/r9-native-accepted/repoorbit/viewer.js',
    'CI_CONTEXT.json', 'SHA256_MANIFEST.json', 'SOURCE_SHA256.json',
    'FIXTURE_PROVENANCE.json', 'FIXTURE_BUILD.json', 'BROWSER_NATIVE.json',
    'GENERATED/demo/RepoOrbit_Demo.html',
    'GENERATED/demo/RepoOrbit_CombinedMaximum.html',
    'GENERATED/demo/RepoOrbit_Preview.png',
    'GENERATED/evidence/v07_browser.json',
    'GENERATED/evidence/browser_combined_limits.json',
    'GENERATED/evidence/browser_security_limits.json',
    'SOURCE_SNAPSHOT/scripts/run_browser_evidence.py',
    'SOURCE_SNAPSHOT/requirements-browser-ci.txt',
    'SOURCE_SNAPSHOT/validation/BROWSER_CANONICAL_PAYLOAD.json',
    'SOURCE_SNAPSHOT/scripts/browser_payload_integrity.py',
    'SOURCE_SNAPSHOT/baselines/v0.8.0/repoorbit/viewer.js',
    'SOURCE_SNAPSHOT/validation/BROWSER_R8_ACCEPTED_SHA256.json',
}


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def inspect_zip(path: Path) -> tuple[dict,dict]:
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC corruption')
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP entries')
        if not REQUIRED.issubset(set(names)):
            raise ValueError('Incomplete ZIP evidence: '+str(sorted(REQUIRED-set(names))))
        manifest = json.loads(z.read('SHA256_MANIFEST.json'))
        listed = manifest['files']
        if set(names) != {x['path'] for x in listed} | {'SHA256_MANIFEST.json'}:
            raise ValueError('Manifest/ZIP membership mismatch')
        for item in listed:
            raw = z.read(item['path'])
            if len(raw) != item['bytes'] or sha_bytes(raw) != item['sha256']:
                raise ValueError('ZIP SHA-256 mismatch: '+item['path'])
        def obj(name: str) -> dict:
            return json.loads(z.read(name))
        context = obj('CI_CONTEXT.json')
        audit = obj('BROWSER_PLATFORM_AUDIT.json')
        stage = obj('BROWSER_STAGE_STATUS.json')
        sources = obj('SOURCE_SHA256.json')
        fixtures = obj('FIXTURE_PROVENANCE.json')
        fixture_build = obj('FIXTURE_BUILD.json')
        browser = obj('BROWSER_NATIVE.json')
        v7 = obj('GENERATED/evidence/v07_browser.json')
        combined = obj('GENERATED/evidence/browser_combined_limits.json')
        security = obj('GENERATED/evidence/browser_security_limits.json')
        system = context['system']
        commit = context['commit']
        if system not in OS_SET or audit.get('system') != system or manifest.get('platform') != system:
            raise ValueError('Native platform identity mismatch')
        if commit != manifest.get('commit') or commit != context.get('circleci',{}).get('CIRCLE_SHA1'):
            raise ValueError('CircleCI commit identity mismatch')
        if context.get('playwright_version') != '1.65.2':
            raise ValueError('Playwright was not pinned')
        if stage.get('status') != 'BROWSER_EXECUTED_PENDING_AUDIT' or {s['stage'] for s in stage.get('stages',[]) if s['status']=='PASS'} != {'preflight','small_demo_fixture','combined_maximum_fixture','chromium_e2e','r9_paired_viewer_performance','r9_filter_factor_performance'}:
            raise ValueError('Missing successful E2E stages')
        if audit.get('status') != 'PASS_WITHIN_PREDECLARED_SCOPE':
            raise ValueError('Native browser host audit not accepted')
        expected = json.loads(BROWSER_HASHES.read_text(encoding='utf-8'))
        original = json.loads(PINS.read_text(encoding='utf-8'))
        for version,parts in original['source_sha256'].items():
            for component,digest in parts.items():
                if sources['reference_source_sha256'][version+'/'+component+'.py']['actual'] != digest:
                    raise ValueError('Pinned code SHA-256 mismatch')
        perf = obj('R9_PAIRED_VIEWER_PERFORMANCE.json')
        candidate_sha = sha_bytes(z.read('SOURCE_SNAPSHOT/repoorbit/viewer.js'))
        problems=validate_performance(perf,candidate_sha)
        if problems:
            raise ValueError('Independent R9 paired rendering gate failed: '+repr(problems))
        pixel_problems = inspect_png_artifacts(perf, z.read)
        if pixel_problems:
            raise ValueError('Independent R9 archived pixel evidence failed: '+repr(pixel_problems))
        filter_report = obj('R9_FILTER_PAIRED_DRAW.json')
        filter_problems = validate_filter_benchmark(filter_report, candidate_sha, z.read)
        if filter_report.get('acceptance') != 'PASS_WITHIN_SCOPE' or filter_problems:
            raise ValueError('Independent R9 factorized-filter gate failed: '+repr(filter_problems))
        if sha_bytes(z.read('SOURCE_SNAPSHOT/baselines/r9-native-accepted/repoorbit/viewer.js')) != ACCEPTED_R9_SHA:
            raise ValueError('Accepted R9 filter reference source mismatch')
        if sha_bytes(z.read('SOURCE_SNAPSHOT/baselines/v0.8.0/repoorbit/viewer.js')) != perf['baseline_viewer_sha256']:
            raise ValueError('R8 immutable viewer source snapshot mismatch')
        if fixtures.get('status') != 'PASS' or not fixtures.get('git_fixture_head'):
            raise ValueError('Missing real Git fixture proof')
        for rel, digest in expected.items():
            name = ('GENERATED/' if rel.startswith('demo/') else 'SOURCE_SNAPSHOT/') + rel
            if name not in names or sha_bytes(z.read(name)) != digest:
                raise ValueError('Browser asset mismatch: '+rel)
        canonical_pin = expected_reference()
        if json.loads(z.read('SOURCE_SNAPSHOT/validation/BROWSER_CANONICAL_PAYLOAD.json')) != canonical_pin:
            raise ValueError('Canonical payload reference changed in source snapshot')
        canonical = inspect_combined_export(z.read('GENERATED/demo/RepoOrbit_CombinedMaximum.html'), canonical_pin)
        if fixtures.get('combined_canonical_dataset',{}).get('sha256_uncompressed_dataset') != canonical['sha256_uncompressed_dataset']:
            raise ValueError('Host fixture canonical dataset evidence mismatch')
        if browser.get('combined_canonical_dataset',{}).get('sha256_uncompressed_dataset') != canonical['sha256_uncompressed_dataset']:
            raise ValueError('Chromium test canonical dataset evidence mismatch')
        if fixture_build.get('observed',{}).get('HTML_SHA256') != canonical['sha256_html']:
            raise ValueError('Combined fixture HTML provenance mismatch')
        for item in sources['git_tracked_files']:
            name = 'SOURCE_SNAPSHOT/' + item['path']
            if name not in names or sha_bytes(z.read(name)) != item['sha256']:
                raise ValueError('Source snapshot not exact: '+item['path'])
        obs = fixture_build.get('observed',{})
        if fixture_build.get('status') != 'PYTHON_GATE_PASS' or any(obs.get(k) != val for k,val in [('commits',8000),('paths_total',80000),('events',900000),('checked_snapshots',3)]):
            raise ValueError('Combined-limit Git fixture not verified')
        if v7.get('status') != 'PASS' or v7.get('javascript_errors') or v7.get('network_requests'):
            raise ValueError('v7 browser assertions did not pass')
        if combined.get('status') != 'PASS' or combined.get('uncaught_javascript_errors') or combined.get('console_errors') or not combined.get('no_external_http_requests'):
            raise ValueError('Combined-limit browser assertions did not pass')
        if (security.get('status') != 'PASS' or
            security.get('expected_guard_bytes') != 64*1024*1024 or
            security.get('oversize_expanded_bytes') != 64*1024*1024 + 1 or
            security.get('network_requests') or
            security.get('source_sha256') != sha_bytes(z.read('GENERATED/demo/RepoOrbit_Demo.html')) or
            security.get('browser_version') != browser.get('browser_version') or
            security.get('cases') != {
                'normal_synthetic_demo':'PASS',
                'gzip_expansion_exceeds_64_mib':'PASS',
                'invalid_utf8_gzip_rejected':'PASS'}):
            raise ValueError('Independent browser gzip safety evidence not accepted')
        if audit_browser([browser],expected,[system])['status'] != 'PASS_WITHIN_PREDECLARED_SCOPE':
            raise ValueError('Required Chromium E2E cases not proven')
        if len(z.read('GENERATED/demo/RepoOrbit_Preview.png')) < 1000:
            raise ValueError('Browser screenshot is missing or empty')
        return ({'system':system,'commit':commit,'git_tree':context['git_tree'],
                 'playwright':context['playwright_version'], 'chromium':browser['browser_version'],
                 'files':len(listed),'zip_sha256':sha_bytes(path.read_bytes()),
                 'status':'PASS_WITHIN_PREDECLARED_SCOPE'},browser)


def audit(paths: list[Path]) -> dict:
    examined, browsers, errors = [], [], []
    for path in paths:
        try:
            item, browser = inspect_zip(path)
            examined.append(item)
            browsers.append(browser)
        except Exception as exc:
            errors.append({'zip':path.name,'error':type(exc).__name__+': '+str(exc)})
    present = [item['system'] for item in examined]
    if len(paths) != 3 or len(present) != 3 or len(set(present)) != 3 or set(present) != OS_SET:
        errors.append({'error':'One complete ZIP from each of Linux, Windows and Darwin is required'})
    if len({item['commit'] for item in examined}) != 1 or len({item['git_tree'] for item in examined}) != 1:
        errors.append({'error':'All native browser E2E artifacts must share exact commit and Git tree'})
    cross = audit_browser(browsers,json.loads(BROWSER_HASHES.read_text(encoding='utf-8')),sorted(OS_SET))
    if cross['status'] != 'PASS_WITHIN_PREDECLARED_SCOPE':
        errors.append({'error':'Cross-platform Chromium E2E not accepted','details':cross})
    return {'status':'PASS_WITHIN_PREDECLARED_SCOPE' if not errors else 'HOLD_OR_FAIL',
            'errors':errors,'native_evidence':examined,'browser_cross_platform_gate':cross,
            'scope':'Chromium on Linux, native Windows and macOS; not Firefox/WebKit',
            'independent_accessibility_review':'HOLD',
            'source_release_gate':'HOLD until all product release requirements accepted'}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('zips',type=Path,nargs=3)
    p.add_argument('--out',type=Path,default=ROOT/'external-results'/'R9_BROWSER_MATRIX_AUDIT.json')
    args=p.parse_args()
    result=audit(args.zips)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'],args.out)
    return 0 if result['status']=='PASS_WITHIN_PREDECLARED_SCOPE' else 2


if __name__=='__main__':
    raise SystemExit(main())
