"""Paired offline R9 R5 vs R9 R6 cold-viewer loading/GC heap, with fixed payload.

This measures one Chromium headless host and is NOT evidence of every browser,
processor, or Git repository. External Playwright/Chromium are test dependencies.
A source change requires new same-SHA native validation; no implied release.
"""
from __future__ import annotations
import argparse
import gzip
import base64
import hashlib
import json
import math
import platform
import re
import statistics
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
BASELINE=ROOT/'baselines/r9-r5-native-accepted/repoorbit/viewer.js'
CANDIDATE=ROOT/'repoorbit/viewer.js'
FIXTURE=ROOT/'demo/RepoOrbit_CombinedMaximum.html'
BASELINE_SHA256='7970f1ab67c96eddc2cf44c22840b6317c085cf72f4692b465140c4a816490b4'


def benchmark(pairs=7):
    if pairs<3:raise ValueError('At least 3 pairs required')
    old=BASELINE.read_text(encoding='utf-8')
    new=CANDIDATE.read_text(encoding='utf-8')
    if hashlib.sha256(old.encode()).hexdigest()!=BASELINE_SHA256:
        raise AssertionError('R9 R5 accepted source hash changed')
    current=FIXTURE.read_text(encoding='utf-8')
    if current.count(new)!=1:raise AssertionError('Candidate JS source not pinned into HTML')
    baseline=current.replace(new,old,1)
    match=re.search(r'<script type="application/json" data-encoding="gzip-base64" id="dataset">(.*?)</script>',current,re.S)
    if not match:raise AssertionError('Expected exact maximum payload')
    raw=gzip.decompress(base64.b64decode(match.group(1)))
    if len(raw)>64*1024*1024:raise AssertionError('Oversized fixture')
    checksum=hashlib.sha256(raw).hexdigest()
    expected='1de6f6fbe504db5bacdb1e1be1b178404b969f1cd3ef3dacf24d7f310f25bf63'
    if checksum!=expected:raise AssertionError('Dataset identity changed')
    variants={'r5':baseline,'r6':current}
    samples={'r5':[],'r6':[]}
    with sync_playwright() as playwright:
        args=['--no-sandbox','--disable-gpu','--js-flags=--expose-gc','--enable-precise-memory-info']
        chromium='/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None
        browser=playwright.chromium.launch(headless=True,executable_path=chromium,args=args)
        for pair in range(pairs+1):  # first pair is unmeasured warmup
            order=['r5','r6'] if pair%2==0 else ['r6','r5']
            for name in order:
                context=browser.new_context(viewport={'width':1380,'height':920},reduced_motion='reduce')
                page=context.new_page()
                errors=[];network=[]
                page.on('pageerror',lambda err:errors.append(str(err)))
                page.on('request',lambda request:network.append(request.url) if request.url.startswith(('http://','https://')) else None)
                t0=time.perf_counter()
                page.set_content(variants[name],wait_until='domcontentloaded',timeout=180000)
                page.wait_for_function("document.querySelector('#statcommits')?.textContent === '8,000'",timeout=180000)
                elapsed=time.perf_counter()-t0
                heap=page.evaluate('''() => {
                    if(typeof window.gc !== 'function')throw new Error('No explicit heap collection');
                    window.gc();
                    return {used:performance.memory?.usedJSHeapSize,total:performance.memory?.totalJSHeapSize};
                }''')
                if not isinstance(heap['used'],int) or heap['used']<=0 or errors or network:
                    raise AssertionError(f'Invalid heap/browser network evidence: {name}, {heap}, {errors}, {network}')
                if page.locator('#statchanges').inner_text()!='900,000':raise AssertionError('Commit events missing')
                if pair:samples[name].append({'startup_s':round(elapsed,5),'heap_used_bytes':heap['used'],'heap_allocated_bytes':heap['total']})
                print(f'paired startup {pair}/{pairs} {name}: {elapsed:.4f}s, used heap {heap["used"]:,} bytes',flush=True)
                context.close()
        version=browser.version
        browser.close()
    def med(name,key):return statistics.median(x[key] for x in samples[name])
    ratios={
        'startup_speedup_x':med('r5','startup_s')/med('r6','startup_s'),
        'heap_usage_reduction_x':med('r5','heap_used_bytes')/med('r6','heap_used_bytes'),
        'heap_usage_reduction_percent':100*(1-med('r6','heap_used_bytes')/med('r5','heap_used_bytes')),
    }
    if any(not math.isfinite(value) for value in ratios.values()):raise AssertionError('Nonfinite performance metric')
    return {'status':'PASS_WITHIN_MEASURED_SCOPE','protocol':'R9_R6_V1_ALTERNATING_WARMUP_PLUS_PAIRED_CHROMIUM',
        'platform':platform.platform(),'python':platform.python_version(),'browser_version':version,
        'fixture_canonical_sha256':checksum,'baseline_sha256':BASELINE_SHA256,
        'candidate_sha256':hashlib.sha256(new.encode()).hexdigest(),
        'pairs':pairs,'samples':samples,'median':{name:{k:med(name,k) for k in ('startup_s','heap_used_bytes','heap_allocated_bytes')} for name in samples},
        'ratios':{k:round(v,4) for k,v in ratios.items()},
        'limitations':['Chromium-only synthetic fixture','performance.memory is non-standard and not total process RSS',
        'Controlled warm browser and filesystem cache','single machine without statistical external validity',
        'Startup includes Playwright set_content and web viewer initialization, excludes Git analysis/HTML construction'],
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pairs',type=int,default=7)
    parser.add_argument('--out',type=Path,default=ROOT/'evidence/r9_r6_columnar_paired.json')
    args=parser.parse_args()
    result=benchmark(args.pairs)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ('status','median','ratios','pairs','candidate_sha256','fixture_canonical_sha256')},indent=2))
if __name__=='__main__':main()
