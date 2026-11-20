"""Execute the shipped Chromium E2E checks on the current native host.

Playwright and the Playwright Chromium browser must be installed separately as
*test-only* dependencies. This tool does not install or download anything.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TESTS=['tests/browser_smoke.py','tests/browser_v7.py','tests/browser_combined_limits.py']


def run(out: Path) -> dict:
    checks=json.loads((ROOT/'validation'/'BROWSER_EXPECTED_SHA256.json').read_text())
    hash_status={k:hashlib.sha256((ROOT/k).read_bytes()).hexdigest()==v for k,v in checks.items()}
    evidence={'os':platform.system(),'platform':platform.platform(),
              'python':platform.python_version(),'status':'HOLD',
              'expected_asset_hashes':checks,'asset_hashes_match':hash_status,
              'test_results':[],'browser':'Chromium','browser_version':None,
              'note':'Playwright is a test-only dependency; no browser claim for untested platforms.'}
    try:
        from playwright.sync_api import sync_playwright
        evidence['playwright_version']=importlib.metadata.version('playwright')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'] if sys.platform.startswith('linux') else [])
            evidence['browser_version']=browser.version
            browser.close()
        for filename in TESTS:
            result=subprocess.run([sys.executable,str(ROOT/filename)],cwd=ROOT,
                                  capture_output=True,text=True,timeout=240)
            log=out.parent/(Path(filename).stem+'_'+evidence['os']+'.log')
            log.write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
            evidence['test_results'].append({'name':filename, 'status':'PASS' if result.returncode==0 else 'FAIL',
                                             'returncode':result.returncode,'log':log.name})
        evidence['status']='PASS' if all(hash_status.values()) and all(c['status']=='PASS' for c in evidence['test_results']) else 'FAIL'
    except (ImportError,subprocess.TimeoutExpired,OSError,Exception) as exc:
        evidence['status']='BLOCKED'
        evidence['error']=str(exc)[-2000:]
    return evidence


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=ROOT/'external-results'/'browser_native.json')
    args=p.parse_args()
    out=args.out.resolve()
    out.parent.mkdir(parents=True,exist_ok=True)
    report=run(out)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(report['os'],report['browser_version'],report['status'],out)
    if report['status']!='PASS':sys.exit(2)

if __name__=='__main__':main()
