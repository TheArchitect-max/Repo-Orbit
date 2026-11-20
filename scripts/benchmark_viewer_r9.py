"""R9: browser-only, paired R8-vs-R9 drawing benchmark (test dependency only).

21 paired Canvas draw calls per mode on exactly the same Git-derived 8k/80k/
900k browser data. No benchmark code is placed in production viewer.js.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import platform
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BASELINE = ROOT / 'baselines' / 'v0.8.0' / 'repoorbit' / 'viewer.js'
CANDIDATE = ROOT / 'repoorbit' / 'viewer.js'
BASE_SHA = '8747ec9eec22b26840235eb3d4329e3e5ea02fc71cb7e6fcedb6ce119dc573ae'
EXPECTED_DATASET = '1de6f6fbe504db5bacdb1e1be1b178404b969f1cd3ef3dacf24d7f310f25bf63'
INSTRUMENT = r'''<script>
window.__r9draw=[]; window.__r9on=false;
const originalRAF=window.requestAnimationFrame.bind(window);
window.requestAnimationFrame=function(callback){
 if(callback.name!=='draw')return originalRAF(callback);
 return originalRAF(function(ts){
   if(!window.__r9on)return callback(ts);
   const start=performance.now();
   try{return callback(ts)}
   finally{window.__r9draw.push(performance.now()-start)}
 });
};
</script>
'''
VIEWER_MARKER = '</script>\n<script>(async () => {'


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def html_variants(source: Path) -> dict[str,str]:
    from scripts.browser_payload_integrity import inspect_fixture
    result=inspect_fixture(source)
    if result['sha256_uncompressed_dataset'] != EXPECTED_DATASET:
        raise ValueError('R9 benchmark does not use the pinned 8k/80k/900k browser data')
    old=BASELINE.read_text(encoding='utf-8')
    new=CANDIDATE.read_text(encoding='utf-8')
    if sha_bytes(old.encode())!=BASE_SHA:
        raise ValueError('R8 reference viewer.js has changed')
    html=source.read_text(encoding='utf-8')
    if html.count(new)!=1 or html.count(VIEWER_MARKER)!=1:
        raise ValueError('R9 HTML does not contain exactly one candidate renderer')
    old_html=html.replace(new,old)
    def add_instrumentation(data: str) -> str:
        return data.replace(VIEWER_MARKER,'</script>\n'+INSTRUMENT+'<script>(async () => {')
    return {'r8':add_instrumentation(old_html),'r9':add_instrumentation(html)}


def benchmark(html: Path, pairs: int = 21) -> dict:
    if pairs < 21:
        raise ValueError('Predeclared R9 acceptance requires at least 21 paired draws')
    from playwright.sync_api import sync_playwright
    variants=html_variants(html)
    result={'protocol':'R9_V1_PAIRED_CANVAS_DRAW','scope':'Chromium 8k/80k/900k synthetic Git fixture',
            'platform':platform.platform(),'python':platform.python_version(),
            'baseline_viewer_sha256':BASE_SHA,
            'candidate_viewer_sha256':sha_bytes(CANDIDATE.read_bytes()),
            'dataset_sha256':EXPECTED_DATASET,'pairs':pairs,'modes':{},
            'acceptance':'HOLD', 'browser':'Chromium'}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
                                   args=['--no-sandbox'] if sys.platform.startswith('linux') else [])
        context=browser.new_context(viewport={'width':1380,'height':920},device_scale_factor=1,reduced_motion='reduce')
        result['chromium_version']=browser.version
        pages={}
        errors=[]
        network=[]
        for label in ('r8','r9'):
            page=context.new_page()
            page.on('pageerror',lambda exc:errors.append(str(exc)))
            page.on('request',lambda req:network.append(req.url) if req.url.startswith(('https://','http://')) else None)
            page.set_content(variants[label],wait_until='domcontentloaded',timeout=180000)
            page.wait_for_function("document.querySelector('#statcommits')?.textContent === '8,000'",timeout=180000)
            pages[label]=page
        for view in ('orbit','atlas'):
            if view=='atlas':
                for page in pages.values():
                    page.locator('#viewmode').click()
                    page.wait_for_timeout(100)
            # Warm up both engines without recording the JIT and first-touch costs.
            for page in pages.values():
                for target in ('8000','7999','8000'):
                    page.locator('#scrub').fill(target)
                    page.wait_for_timeout(65)
                page.evaluate('window.__r9draw=[];window.__r9on=true')
            raw={'r8':[],'r9':[]}
            for i in range(pairs):
                target='7999' if i%2==0 else '8000'
                # Reverse measured order on alternate pairs to reduce thermal bias.
                order=('r8','r9') if i%2==0 else ('r9','r8')
                for label in order:
                    page=pages[label]
                    before=page.evaluate('window.__r9draw.length')
                    page.locator('#scrub').fill(target)
                    page.wait_for_function('(n)=>window.__r9draw.length>n',arg=before,timeout=30000)
                    raw[label].append(page.evaluate('window.__r9draw[window.__r9draw.length-1]'))
            # Compare exact raster output on the same final Git frame.
            for page in pages.values():
                page.evaluate('window.__r9on=false')
                page.locator('#scrub').fill('8000')
                page.wait_for_timeout(100)
            pixels={name:sha_bytes(pages[name].locator('#orbit').evaluate('(c)=>c.toDataURL("image/png")').encode())
                    for name in ('r8','r9')}
            med={name:statistics.median(raw[name]) for name in ('r8','r9')}
            ratio=med['r8']/med['r9'] if med['r9'] else 0
            result['modes'][view]={'baseline_draw_ms':raw['r8'],'candidate_draw_ms':raw['r9'],
                                   'baseline_median_ms':med['r8'],'candidate_median_ms':med['r9'],
                                   'speedup_x':ratio,'pixel_sha256':pixels,
                                   'pixel_exact':pixels['r8']==pixels['r9'],
                                   'gate':'PASS' if ratio>=3.0 and pixels['r8']==pixels['r9'] else 'FAIL'}
        result['javascript_errors']=errors
        result['external_network_requests']=network
        result['heap_bytes']={name:pages[name].evaluate('performance.memory.usedJSHeapSize') for name in pages}
        context.close()
        browser.close()
    if not errors and not network and all(x['gate']=='PASS' for x in result['modes'].values()):
        result['acceptance']='PASS_WITHIN_PREDECLARED_SCOPE'
    else:
        result['acceptance']='FAIL'
    return result


def validate_performance(report: dict, candidate_sha: str | None = None) -> list[str]:
    """Independently recompute the predeclared 21-pair/3x/equal-pixel gates."""
    errors=[]
    if report.get('protocol') != 'R9_V1_PAIRED_CANVAS_DRAW':
        errors.append('wrong_protocol')
    if report.get('baseline_viewer_sha256') != BASE_SHA:
        errors.append('baseline_source_mismatch')
    if candidate_sha and report.get('candidate_viewer_sha256') != candidate_sha:
        errors.append('candidate_source_mismatch')
    if report.get('dataset_sha256') != EXPECTED_DATASET:
        errors.append('dataset_mismatch')
    if report.get('javascript_errors') or report.get('external_network_requests'):
        errors.append('unexpected_js_or_network_errors')
    if not report.get('chromium_version') or report.get('browser') != 'Chromium':
        errors.append('browser_identity_missing')
    if report.get('acceptance') != 'PASS_WITHIN_PREDECLARED_SCOPE':
        errors.append('reported_gate_not_pass')
    if set(report.get('modes',{})) != {'orbit','atlas'}:
        errors.append('incorrect_view_modes')
    pairs=report.get('pairs')
    if not isinstance(pairs,int) or pairs<21:
        errors.append('too_few_paired_draws')
        pairs=21
    for mode in ('orbit','atlas'):
        obj=report.get('modes',{}).get(mode,{})
        old=obj.get('baseline_draw_ms',[])
        new=obj.get('candidate_draw_ms',[])
        if any(not isinstance(x,list) or len(x)!=pairs or
               any(not isinstance(v,(float,int)) or isinstance(v,bool) or not math.isfinite(v) or v<=0 for v in x)
               for x in (old,new)):
            errors.append(mode+':invalid_measurement_samples')
            continue
        original=statistics.median(old)
        current=statistics.median(new)
        ratio=original/current
        for name,actual in (('baseline_median_ms',original),('candidate_median_ms',current),('speedup_x',ratio)):
            value=obj.get(name)
            if not isinstance(value,(float,int)) or abs(value-actual)>max(1e-6,actual*1e-8):
                errors.append(mode+':'+name+':mismatch')
        hashes=obj.get('pixel_sha256',{})
        if not obj.get('pixel_exact') or not isinstance(hashes,dict) or not hashes.get('r8') or hashes.get('r8')!=hashes.get('r9'):
            errors.append(mode+':nonidentical_raster')
        if ratio<3.0 or obj.get('gate')!='PASS':
            errors.append(mode+':performance_gate_not_pass')
    return errors


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html',type=Path,default=ROOT/'demo/RepoOrbit_CombinedMaximum.html')
    parser.add_argument('--out',type=Path,default=ROOT/'external-results/R9_PAIRED_VIEWER_PERFORMANCE.json')
    parser.add_argument('--pairs',type=int,default=21)
    args=parser.parse_args()
    try:
        report=benchmark(args.html,args.pairs)
    except Exception as exc:
        report={'acceptance':'FAIL','error':type(exc).__name__+': '+str(exc)}
    if report.get('acceptance') == 'PASS_WITHIN_PREDECLARED_SCOPE':
        violations=validate_performance(report,sha_bytes(CANDIDATE.read_bytes()))
        if violations:
            report['acceptance']='FAIL'
            report['validation_errors']=violations
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({key:value for key,value in report.items() if key!='modes'},indent=2))
    for view,data in report.get('modes',{}).items():
        print(f"{view}: {data['baseline_median_ms']:.3f}ms -> {data['candidate_median_ms']:.3f}ms "
              f"({data['speedup_x']:.2f}x), raster parity={data['pixel_exact']}, {data['gate']}")
    return 0 if report['acceptance']=='PASS_WITHIN_PREDECLARED_SCOPE' else 2

if __name__=='__main__':
    raise SystemExit(main())
