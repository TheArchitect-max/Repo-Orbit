"""CircleCI R7 native evidence: fail-closed validation and one complete ZIP per OS.

Python 3.10+ stdlib only. This runs local product tests and external Git-history
benchmarks, never runs source code from the external benchmark repositories.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / 'validation' / 'PINNED_TARGETS.json'
LABELS = {'Linux': 'linux', 'Windows': 'windows', 'Darwin': 'macos'}
PHASES = ('source_preflight', 'regression_tests', 'native_benchmarks')
CIRCLE_KEYS = ('CIRCLE_SHA1', 'CIRCLE_BRANCH', 'CIRCLE_JOB', 'CIRCLE_BUILD_NUM',
               'CIRCLE_BUILD_URL', 'CIRCLE_WORKFLOW_ID', 'CIRCLE_PIPELINE_ID',
               'CIRCLE_PIPELINE_NUM', 'CIRCLE_PROJECT_REPONAME', 'CIRCLE_PROJECT_USERNAME')


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    p = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError('git failed: ' + ' '.join(args) + ': ' + p.stderr[-300:])
    return p.stdout.strip()


def provenance(staging: Path, system: str) -> dict:
    sha = git('rev-parse', 'HEAD')
    expected = os.environ.get('CIRCLE_SHA1', '')
    if not expected or sha != expected:
        raise RuntimeError('HOLD: required CircleCI commit SHA missing or does not match HEAD')
    if platform.system() != system:
        raise RuntimeError('HOLD: executor platform mismatch, actual=' + platform.system())
    pins = json.loads(PINS.read_text(encoding='utf-8'))
    pin_results = {}
    for version, folder in (('v0.7.0', ROOT/'baselines'/'v0.7.0'/'repoorbit'),
                            ('v0.8.0', ROOT/'repoorbit')):
        for part, expected_hash in pins['source_sha256'][version].items():
            f = folder / (part + '.py')
            actual_hash = digest(f)
            pin_results[f'{version}/{part}.py'] = {'expected': expected_hash,
                                                    'actual': actual_hash,
                                                    'match': actual_hash == expected_hash}
    if not all(v['match'] for v in pin_results.values()):
        raise RuntimeError('HOLD: pinned source integrity mismatch')
    raw = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'],
                         capture_output=True, check=True).stdout
    tracked_files = []
    for entry in raw.split(b'\x00'):
        if not entry:
            continue
        name = entry.decode('utf-8', 'strict')
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or not (ROOT / rel).is_file():
            raise RuntimeError('HOLD: invalid/missing tracked path ' + repr(name))
        src = ROOT / rel
        target = staging / 'SOURCE_SNAPSHOT' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        tracked_files.append({'path': name, 'sha256': digest(src), 'bytes': src.stat().st_size})
    if not tracked_files:
        raise RuntimeError('HOLD: no source files in checkout')
    write_json(staging/'SOURCE_SHA256.json', {'reference_source_sha256': pin_results,
                                            'git_tracked_files': tracked_files})
    write_json(staging/'CI_CONTEXT.json', {
        'utc': now(), 'system': system, 'system_release': platform.release(),
        'machine': platform.machine(), 'python': platform.python_version(),
        'python_executable': sys.executable,
        'git_version': subprocess.check_output(['git', '--version'],
            text=True, encoding='utf-8', errors='replace').strip(),
        'commit': sha, 'git_tree': git('rev-parse', 'HEAD^{tree}'),
        'circleci': {key: os.environ[key] for key in CIRCLE_KEYS if key in os.environ},
        'tracks': len(tracked_files),
        'note': 'Executor-native CLI validation; browser E2E is separate',
    })
    # Record the actual installed distribution environment without running pip.
    packages = sorted(({'name': x.metadata.get('Name', ''), 'version': x.version}
                       for x in importlib.metadata.distributions()),
                      key=lambda x: (x['name'].casefold(), x['version']))
    write_json(staging/'PYTHON_DISTRIBUTIONS.json', packages)
    shutil.copyfile(PINS, staging/'PINNED_TARGETS.json')
    return {'sha': sha, 'system': system, 'pinned_source_integrity': 'PASS',
            'tracked_file_count': len(tracked_files)}


def run_logged(args: list[str], cwd: Path, logfile: Path) -> tuple[int, float]:
    logfile.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with logfile.open('wb') as sink:
        sink.write(('UTC_START: ' + now() + '\n' +
                    'ARGV: ' + json.dumps(args, ensure_ascii=True) + '\n').encode('utf-8'))
        sink.flush()
        proc = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, bufsize=0)
        assert proc.stdout is not None
        for line in proc.stdout:
            sink.write(line)
            sink.flush()
            print(line.decode('utf-8', 'backslashreplace').rstrip('\r\n'), flush=True)
        rc = proc.wait()
        elapsed = round(time.monotonic() - start, 3)
        sink.write(f'EXIT_CODE: {rc}\nELAPSED_SECONDS: {elapsed}\nUTC_END: {now()}\n'.encode('utf-8'))
    return rc, elapsed


def run_all(staging: Path, system: str) -> int:
    if staging.exists():
        raise RuntimeError('HOLD: stale evidence workspace; refusing to mix runs')
    staging.mkdir(parents=True)
    report = {'schema': 1, 'platform': system, 'started_utc': now(),
              'stages': [], 'status': 'FAIL'}
    write_json(staging/'RUN_STAGE_STATUS.json', report)
    try:
        report['provenance'] = provenance(staging, system)
        write_json(staging/'RUN_STAGE_STATUS.json', report)
        executions = [
            ('source_preflight', [sys.executable, 'scripts/preflight_circleci.py']),
            ('regression_tests', [sys.executable, '-m', 'unittest', 'discover',
                                  '-s', 'tests', '-p', 'test_*.py']),
            ('native_benchmarks', [sys.executable, '-u', 'scripts/run_circleci_native.py',
                                   '--out', str(staging/'measurements')]),
        ]
        for i, (name, cmd) in enumerate(executions, 1):
            logname = f'logs/{i:02d}_{name}.log'
            print(f'CI EVIDENCE R7: {system} {name}', flush=True)
            rc, elapsed = run_logged(cmd, ROOT, staging/logname)
            record = {'step': name, 'status': 'PASS' if rc == 0 else 'FAIL',
                      'exit_code': rc, 'elapsed_seconds': elapsed, 'log': logname}
            if name == 'regression_tests':
                log = (staging/logname).read_bytes().decode('utf-8', 'replace')
                m = re.search(r'Ran (\d+) tests? in ([\d.]+)s', log)
                record['test_count'] = int(m.group(1)) if m else None
                if rc == 0 and (not m or int(m.group(1)) < 100):
                    record.update(status='FAIL', exit_code=2,
                                  error='HOLD: incomplete regression suite')
                    rc = 2
            report['stages'].append(record)
            write_json(staging/'RUN_STAGE_STATUS.json', report)
            if rc:
                report['failed_stage'] = name
                report['finished_utc'] = now()
                write_json(staging/'RUN_STAGE_STATUS.json', report)
                return rc
        report['status'] = 'MEASUREMENTS_COMPLETED_PENDING_AUDIT'
        report['finished_utc'] = now()
        write_json(staging/'RUN_STAGE_STATUS.json', report)
        return 0
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        report['finished_utc'] = now()
        write_json(staging/'RUN_STAGE_STATUS.json', report)
        print('CI EVIDENCE R7 HOLD: ' + str(exc), file=sys.stderr, flush=True)
        return 2


def audit_platform(staging: Path, system: str) -> dict:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.audit_native_matrix import verify_one
    pins = json.loads(PINS.read_text(encoding='utf-8'))
    errors = []
    stages = json.loads((staging/'RUN_STAGE_STATUS.json').read_text(encoding='utf-8'))
    completed = {x['step'] for x in stages['stages'] if x['status'] == 'PASS'}
    if completed != set(PHASES):
        errors.append({'type': 'missing_successful_stages',
                       'missing': sorted(set(PHASES) - completed)})
    results_dir = staging/'measurements'
    expected = pins['required_repositories']
    full = results_dir/'FULL_HISTORY_STATUS.json'
    run = results_dir/'RUN_STATUS.json'
    meta = results_dir/'CIRCLECI_RUN_META.json'
    for path in (full,run,meta,results_dir/'HOST.json'):
        if not path.is_file():
            errors.append({'type': 'missing_required_file', 'file': str(path.relative_to(staging))})
    if full.is_file():
        history = json.loads(full.read_text(encoding='utf-8'))
        if len(history) != len(expected) or {x.get('target') for x in history} != set(expected):
            errors.append({'type': 'wrong_full_history_target_set'})
        for row in history:
            if row.get('status') != 'PASS' or row.get('shallow') is not False or row.get('pinned_sha') != pins['repositories'].get(row.get('target'),{}).get('sha') or int(row.get('first_parent_commits',0)) < 1000:
                errors.append({'type': 'full_history_not_proven', 'target':row.get('target')})
    if run.is_file():
        observed = json.loads(run.read_text(encoding='utf-8'))
        status = observed.get('results', [])
        if len(status) != len(expected) or {x.get('target') for x in status} != set(expected) or any(x.get('status') != 'MEASURED' for x in status):
            errors.append({'type': 'benchmarks_not_all_measured'})
    if meta.is_file() and json.loads(meta.read_text(encoding='utf-8')).get('status') != 'MEASUREMENTS_COMPLETED':
        errors.append({'type': 'benchmark_runner_incomplete'})
    per_target = []
    for target in expected:
        matches = sorted(results_dir.glob(f'{target}_{system}_*.json'))
        if len(matches) != 1:
            errors.append({'type': 'missing_or_duplicate_target_evidence', 'target':target,
                           'matches':len(matches)})
            continue
        record = json.loads(matches[0].read_text(encoding='utf-8'))
        issues, regressions = verify_one(record, target, system, pins)
        if issues:
            errors.append({'type': 'invalid_native_measurements', 'target':target,'reasons':issues})
        if regressions:
            errors.append({'type': 'performance_regressions_gt_5pct','target':target,
                           'regressions':regressions})
        per_target.append({'target':target, 'file':matches[0].name,
                           'status': 'PASS' if not issues and not regressions else 'FAIL'})
    return {'schema':1,'system':system,'scope':'3 pinned Git repositories x 3 commit windows x 21 paired repetitions',
            'status':'PASS_WITHIN_PREDECLARED_SCOPE' if not errors else 'FAIL',
            'errors':errors,'per_target':per_target,
            'cross_platform_matrix':'HOLD until all three native ZIPs independently audited',
            'browser_e2e':'NOT_EXECUTED'}


def build_zip(staging: Path, out: Path, platform_name: str) -> tuple[Path,dict]:
    out.mkdir(parents=True, exist_ok=True)
    context_file = staging/'CI_CONTEXT.json'
    if context_file.exists():
        sha = json.loads(context_file.read_text(encoding='utf-8')).get('commit','UNKNOWN')
    else:
        sha = (os.environ.get('CIRCLE_SHA1') or 'UNKNOWN')
    archive = out / f'REPO_ORBIT_R7_{LABELS[platform_name].upper()}_{sha[:12]}_EVIDENCE.zip'
    members = []
    for file in sorted(staging.rglob('*')):
        if file.is_file():
            rel = file.relative_to(staging).as_posix()
            members.append({'path':rel,'bytes':file.stat().st_size,'sha256':digest(file)})
    manifest = {'schema':1,'generated_utc':now(),'platform':platform_name,'commit':sha,
                'files':members, 'archive_entry_count':len(members)+1}
    write_json(staging/'SHA256_MANIFEST.json',manifest)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6,allowZip64=True) as z:
        for entry in members:
            z.write(staging/entry['path'], entry['path'])
        z.write(staging/'SHA256_MANIFEST.json','SHA256_MANIFEST.json')
    with zipfile.ZipFile(archive, 'r') as z:
        if z.testzip() is not None:
            raise RuntimeError('ZIP integrity failed')
        if len(z.namelist()) != manifest['archive_entry_count']:
            raise RuntimeError('ZIP manifest entry count mismatch')
        for entry in members:
            if hashlib.sha256(z.read(entry['path'])).hexdigest() != entry['sha256']:
                raise RuntimeError('ZIP entry digest mismatch: '+entry['path'])
    (out/(archive.name+'.sha256')).write_text(digest(archive)+'  '+archive.name+'\n',encoding='utf-8')
    return archive, manifest


def package(staging: Path,out: Path,system: str) -> int:
    out.mkdir(parents=True, exist_ok=True)
    if not staging.is_dir():
        staging.mkdir(parents=True)
        write_json(staging/'RUN_STAGE_STATUS.json',
                   {'status':'FAIL','error':'No native validation workspace', 'stages':[]})
    try:
        report = audit_platform(staging,system)
    except Exception as exc:
        report = {'schema':1,'system':system,'status':'FAIL',
                  'errors':[{'type':'audit_exception','details':repr(exc)}]}
    write_json(staging/'CI_PLATFORM_AUDIT.json',report)
    archive,manifest=build_zip(staging,out,system)
    print('EVIDENCE_ZIP:',archive,flush=True)
    print('EVIDENCE_SHA256:',digest(archive),flush=True)
    print('EVIDENCE_FILES:',len(manifest['files']),flush=True)
    print('NATIVE_PLATFORM_AUDIT:',report['status'],flush=True)
    return 0 if report['status']=='PASS_WITHIN_PREDECLARED_SCOPE' else 2


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--platform',required=True,choices=list(LABELS))
    p.add_argument('--out',required=True,type=Path)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--run',action='store_true')
    g.add_argument('--package-only',action='store_true')
    args=p.parse_args()
    out=args.out.resolve()
    allowed=(ROOT/'external-results').resolve()
    if out.parent != allowed:
        p.error('Evidence ZIP output must be a direct directory of external-results')
    if not out.name.startswith('circleci-'):
        p.error('Evidence output directory must start with circleci-')
    staging=out.parent/(out.name+'-raw')
    if args.run:
        return run_all(staging,args.platform)
    return package(staging,out,args.platform)


if __name__=='__main__':
    raise SystemExit(main())
