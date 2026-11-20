"""Independent REPO ORBIT R7 multi-platform CircleCI ZIP acceptance audit.

Provide exactly one ZIP each from Linux, Windows and macOS. All payloads must
match the same commit and the pinned source; verifies each ZIP SHA-256 manifest
and all 9 real native performance cells. Browser E2E remains a separate gate.
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
from scripts.audit_native_matrix import evaluate
PINS = ROOT/'validation'/'PINNED_TARGETS.json'
OS_SET = {'Linux', 'Windows', 'Darwin'}


def read_zip(path: Path) -> tuple[dict, list[dict]]:
    with zipfile.ZipFile(path) as z:
        failed = z.testzip()
        if failed is not None:
            raise ValueError(f'ZIP CRC failed on {failed}')
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP names are prohibited')
        manifest = json.loads(z.read('SHA256_MANIFEST.json'))
        listed = manifest['files']
        if set(names) != {f['path'] for f in listed} | {'SHA256_MANIFEST.json'}:
            raise ValueError('ZIP member and SHA256 manifest mismatch')
        for item in listed:
            blob = z.read(item['path'])
            if len(blob) != item['bytes'] or hashlib.sha256(blob).hexdigest() != item['sha256']:
                raise ValueError('ZIP evidence hash mismatch: '+item['path'])
        context = json.loads(z.read('CI_CONTEXT.json'))
        audit = json.loads(z.read('CI_PLATFORM_AUDIT.json'))
        status = json.loads(z.read('RUN_STAGE_STATUS.json'))
        hashes = json.loads(z.read('SOURCE_SHA256.json'))
        pins = json.loads(PINS.read_text(encoding='utf-8'))
        if z.read('PINNED_TARGETS.json') != PINS.read_bytes():
            raise ValueError('ZIP pinned target definition changed')
        system = context['system']
        if system not in OS_SET or manifest['platform'] != system or audit['system'] != system:
            raise ValueError('Conflicting native OS identity')
        if context['commit'] != manifest['commit'] or context['commit'] != context['circleci'].get('CIRCLE_SHA1'):
            raise ValueError('Conflicting commit identity')
        if audit['status'] != 'PASS_WITHIN_PREDECLARED_SCOPE' or status['status'] != 'MEASUREMENTS_COMPLETED_PENDING_AUDIT':
            raise ValueError('Platform did not pass all native gates')
        if {s['step'] for s in status['stages'] if s['status']=='PASS'} != {'source_preflight','regression_tests','native_benchmarks'}:
            raise ValueError('Missing successful native stage')
        if any(not x['match'] for x in hashes['reference_source_sha256'].values()):
            raise ValueError('Source digest mismatch')
        members = {p['path']:p for p in hashes['git_tracked_files']}
        for rel,d in members.items():
            name='SOURCE_SNAPSHOT/'+rel
            if name not in names or hashlib.sha256(z.read(name)).hexdigest()!=d['sha256']:
                raise ValueError('Incomplete exact Git source snapshot: '+rel)
        records = []
        for target in pins['required_repositories']:
            matches = [n for n in names if n.startswith('measurements/'+target+'_'+system+'_') and n.endswith('.json')]
            if len(matches)!=1:
                raise ValueError('Missing/duplicate target measurements: '+target)
            records.append(json.loads(z.read(matches[0])))
        return {'system':system,'commit':context['commit'],'tree':context['git_tree'],
                'bundle':path.name, 'files':len(listed), 'zip_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'host':{'python':context['python'],'git':context['git_version']},
                'native_platform_audit':'PASS_WITHIN_PREDECLARED_SCOPE'},records


def audit(paths: list[Path]) -> dict:
    findings, all_records, errors = [], [], []
    for path in paths:
        try:
            result, records=read_zip(path)
            findings.append(result)
            all_records.extend(records)
        except Exception as exc:
            errors.append({'bundle':path.name,'error':type(exc).__name__+': '+str(exc)})
    systems=[f['system'] for f in findings]
    if len(paths)!=3 or set(systems)!=OS_SET or len(systems)!=len(set(systems)):
        errors.append({'error':'Exactly one valid native ZIP per Linux, Windows and Darwin is required'})
    if len({r['commit'] for r in findings})!=1 or len({r['tree'] for r in findings})!=1:
        errors.append({'error':'All native ZIPs must have an identical commit SHA and Git tree'})
    pins=json.loads(PINS.read_text(encoding='utf-8'))
    matrix=evaluate(all_records,pins)
    if matrix['cli_performance_gate']!='PASS_WITHIN_PREDECLARED_SCOPE':
        errors.append({'error':'Native 9-cell matrix did not meet predeclared acceptance'})
    return {'status':'PASS_WITHIN_PREDECLARED_SCOPE' if not errors else 'HOLD_OR_FAIL',
            'errors':errors, 'platform_evidence':findings, 'native_matrix':matrix,
            'browser_e2e':'HOLD; browser acceptance is separate',
            'no_claim_of_universal_speedup':True}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('evidence_zips',type=Path,nargs=3)
    p.add_argument('--out',type=Path,default=ROOT/'external-results'/'R7_CROSS_PLATFORM_AUDIT.json')
    args=p.parse_args()
    result=audit(args.evidence_zips)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'],str(args.out))
    return 0 if result['status']=='PASS_WITHIN_PREDECLARED_SCOPE' else 2


if __name__=='__main__':
    raise SystemExit(main())
