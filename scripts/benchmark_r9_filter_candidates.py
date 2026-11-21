"""R9 candidate: paired filtered redraw benchmark vs immutable native-accepted R9.

Requires Playwright only for validation. 21 paired redraw timings for each filter
and mode, with exact PNG and DOM parity at representative states.
No performance conclusions beyond this browser/fixture are warranted.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.benchmark_viewer_r9 import INSTRUMENT, VIEWER_MARKER

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'demo/RepoOrbit_CombinedMaximum.html'
OLD = ROOT/'baselines/r9-native-accepted/repoorbit/viewer.js'
NEW = ROOT/'repoorbit/viewer.js'
OLD_SHA = '3a31ebb30438a198dd4b3e117822ed0d77a9cc3756b03977bfe094c93554f9fc'
PAIRS = 21
# 32 Canvas callbacks can finish within one coarse performance.now() clock tick
# on macOS. Use 256 real callbacks per batch, never substitute synthetic time.
DRAW_BATCH = 256
FILTERS = {'exact': 'file_01234.py', 'selective': 'file_012', 'cluster': 'src/cluster_00'}


def variants():
    html = SOURCE.read_text(encoding='utf-8')
    old, new = OLD.read_text(encoding='utf-8'), NEW.read_text(encoding='utf-8')
    if hashlib.sha256(old.encode()).hexdigest() != OLD_SHA:
        raise ValueError('Accepted R9 baseline SHA-256 mismatch')
    if html.count(new) != 1 or html.count(VIEWER_MARKER) != 1:
        raise ValueError('Candidate HTML must include exactly one candidate renderer')
    def wrap(s): return s.replace(VIEWER_MARKER, '</script>\n'+INSTRUMENT+'<script>(async () => {')
    return {'r9_native': wrap(html.replace(new, old)), 'candidate': wrap(html)}


def bench(out: Path, pairs: int=PAIRS):
    if pairs < 21: raise ValueError('At least 21 paired draws required')
    from playwright.sync_api import sync_playwright
    v=variants()
    result={'protocol':'R9_FILTER_V1_PAIRED_DRAW','pairs':pairs,'baseline_sha256':OLD_SHA,
            'candidate_sha256':hashlib.sha256(NEW.read_bytes()).hexdigest(),
            'browser':'Chromium','cases':{},'page_errors':[],'network_requests':[],
            'scope':'Synthetic 8k commits, 80k files, 900k events; Canvas draw only',
            'batch_draws':DRAW_BATCH,'filter_set':FILTERS, 'behavioral_parity':[],
            'acceptance':'HOLD'}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
                                   args=['--no-sandbox'])
        result['chromium_version']=browser.version
        ctx=browser.new_context(viewport={'width':1380,'height':920},device_scale_factor=1,reduced_motion='reduce')
        pages={}
        for label,s in v.items():
            p=ctx.new_page()
            p.on('pageerror',lambda e:result['page_errors'].append(str(e)))
            p.on('request',lambda r:result['network_requests'].append(r.url) if r.url.startswith(('http://','https://')) else None)
            p.set_content(s,wait_until='domcontentloaded',timeout=180000)
            p.wait_for_function("document.querySelector('#statcommits')?.textContent==='8,000'",timeout=180000)
            p.locator('#scrub').fill('8000')
            pages[label]=p
        for mode in ('orbit','atlas'):
            if mode=='atlas':
                for p in pages.values():p.locator('#viewmode').click()
            for filter_key, query in FILTERS.items():
                rec={'median_ms':{},'raw_ms':{},'query_change_ms':{},'png_sha256':{},'png':{},'ui':{},'speedup_x':None}
                for label,p in pages.items():
                    p.locator('#search').fill('')
                    # Record end-to-end input handler cost separately from Canvas drawing.
                    rec['query_change_ms'][label] = p.evaluate('''(q)=>{
                        const e=document.querySelector('#search');e.value=q;
                        const t=performance.now();e.dispatchEvent(new Event('input',{bubbles:true}));
                        return performance.now()-t; }''',query)
                    p.wait_for_timeout(40)
                    for target in ('7999','8000','7999','8000'):
                        p.locator('#scrub').fill(target)
                        p.wait_for_timeout(20)
                    p.evaluate('window.__r9draw=[];window.__r9on=true')
                # Measure the redraw callback in a single browser-side invocation
                # per renderer to avoid Playwright RPC latency dominating fast draws.
                # Alternate exact adjacent Git frames in each sample, excluding
                # DOM/event-handler costs from this Canvas-only performance metric.
                samples={}
                labels=('r9_native','candidate') if filter_key!='selective' else ('candidate','r9_native')
                for label in labels:
                    p=pages[label]
                    raw=p.evaluate("(config)=>{\n                      const {pairs,batch}=config;\n                      const input=document.querySelector('#scrub'), draw=window.__r9drawFn;\n                      if(typeof draw!=='function')throw new Error('instrumented draw not captured');\n                      const records=[];\n                      for(let i=0;i<pairs;i++){\n                        input.value=(i%2===0?'7999':'8000');\n                        input.dispatchEvent(new Event('input',{bubbles:true}));\n                        const t=performance.now(); for(let repeat=0;repeat<batch;repeat++)draw(0);\n                        records.push((performance.now()-t)/batch);\n                      }\n                      return records;\n                    }",{"pairs":pairs,"batch":DRAW_BATCH})
                    samples[label]=raw
                for label,p in pages.items():
                    p.evaluate('window.__r9on=false')
                    p.locator('#scrub').fill('8000')
                    p.evaluate('window.__r9drawFn(0)')
                    raw=p.locator('#orbit').evaluate('(c)=>c.toDataURL("image/png")')
                    image=base64.b64decode(raw.split(',',1)[1],validate=True)
                    if not image.startswith(b'\x89PNG\r\n\x1a\n') or len(image)<1000:
                        raise ValueError('Missing real PNG evidence')
                    digest=hashlib.sha256(image).hexdigest()
                    relative=f'FILTER_PIXELS/{mode}_{filter_key}_{label}.png'
                    target=out.parent/relative
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(image)
                    rec['png_sha256'][label]=digest
                    rec['png'][label]={'path':relative,'bytes':len(image),'sha256':digest}
                    rec['ui'][label]={k:p.locator('#'+k).inner_text() for k in ('statfiles','timeposition','frameinfo','matchcount')}
                    rec['median_ms'][label]=statistics.median(samples[label])
                    rec['raw_ms'][label]=samples[label]
                rec['speedup_x']=rec['median_ms']['r9_native']/rec['median_ms']['candidate']
                rec['parity']=(rec['png_sha256']['r9_native']==rec['png_sha256']['candidate'] and
                               rec['ui']['r9_native']==rec['ui']['candidate'])
                result['cases'][mode+'/'+filter_key]=rec
        # Functional parity is checked independently of the six timing cases.
        # Include filter clearing, zero matches, map-only filter, comparison
        # overlays and keyboard-based selection to catch stale memberships.
        states=(('clear', '', '', '8000', False),
                ('zero_results','not_a_path_in_this_fixture','', '8000',False),
                ('map_only','', 'src','4000',False),
                ('combined_filter','file_012','src','4000',False))
        for state, q, group, target, do_compare in states:
            record={'state':state,'png':{},'dom':{},'status':'HOLD'}
            for label,p in pages.items():
                p.locator('#search').fill('')
                p.locator('#groupfilter').select_option('')
                p.locator('#scrub').fill('4000')
                if do_compare:
                    p.locator('#pinA').click()
                p.locator('#groupfilter').select_option(group)
                p.locator('#search').fill(q)
                p.locator('#scrub').fill(target)
                if do_compare:
                    p.locator('#compare').click()
                p.wait_for_timeout(160)
                p.evaluate('window.__r9drawFn(0);window.__r9drawFn(0)')
                png=p.locator('#orbit').evaluate('(c)=>c.toDataURL("image/png")')
                record['png'][label]=hashlib.sha256(base64.b64decode(png.split(',',1)[1])).hexdigest()
                record['dom'][label]={key:p.locator('#'+key).inner_text()
                                      for key in ('statfiles','timeposition','frameinfo','matchcount','diffsummary')}
            record['status']='PASS' if (record['png']['r9_native']==record['png']['candidate'] and
                                       record['dom']['r9_native']==record['dom']['candidate']) else 'FAIL'
            result['behavioral_parity'].append(record)
        # Ensure the search-result Enter key retains exact semantic identity.
        for label,p in pages.items():
            p.locator('#search').fill('file_01234.py')
            p.locator('.match-button').first.focus()
            p.keyboard.press('Enter')
            result.setdefault('keyboard_inspection',{})[label]=p.locator('#inspectpath').inner_text()
        ctx.close();browser.close()
    result['acceptance']='PASS_WITHIN_SCOPE' if (not result['page_errors'] and not result['network_requests'] and
        all(c['parity'] and c['speedup_x']>=3 for c in result['cases'].values()) and
        len(result['behavioral_parity'])==4 and all(x['status']=='PASS' for x in result['behavioral_parity']) and
        len(set(result.get('keyboard_inspection',{}).values()))==1) else 'HOLD_OR_FAIL'
    out.parent.mkdir(parents=True,exist_ok=True)
    problems=validate_filter_benchmark(result, result['candidate_sha256'],
        lambda name:(out.parent/name).read_bytes())
    result['independent_validation_errors']=problems
    if problems: result['acceptance']='HOLD_OR_FAIL'
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result


def validate_filter_benchmark(report: dict, candidate_sha: str, read_png) -> list[str]:
    """Fail-closed verification of 6 measured contexts and original PNG bytes."""
    problems=[]
    if report.get('protocol')!='R9_FILTER_V1_PAIRED_DRAW' or report.get('pairs',0)<21:
        problems.append('invalid_protocol_or_pairs')
    if report.get('baseline_sha256')!=OLD_SHA or report.get('candidate_sha256')!=candidate_sha:
        problems.append('source_sha_mismatch')
    if report.get('page_errors') or report.get('network_requests'):
        problems.append('browser_error_or_external_network')
    if report.get('batch_draws') != DRAW_BATCH or report.get('filter_set')!=FILTERS:
        problems.append('benchmark_parameters_modified')
    behavior=report.get('behavioral_parity',[])
    if [x.get('state') for x in behavior]!=['clear','zero_results','map_only','combined_filter']:
        problems.append('missing_behavioral_states')
    for case in behavior:
        if (case.get('status')!='PASS' or case.get('png',{}).get('r9_native')!=case.get('png',{}).get('candidate') or
            case.get('dom',{}).get('r9_native')!=case.get('dom',{}).get('candidate')):
            problems.append('behavioral_parity_failed:'+str(case.get('state')))
    keyboard=report.get('keyboard_inspection',{})
    if set(keyboard)!={'r9_native','candidate'} or keyboard.get('candidate')!=keyboard.get('r9_native'):
        problems.append('keyboard_inspection_drift')
    cases=report.get('cases',{})
    if set(cases)!={mode+'/'+key for mode in ('orbit','atlas') for key in FILTERS}:
        problems.append('incomplete_scenarios')
    for key in (mode+'/'+f for mode in ('orbit','atlas') for f in FILTERS):
        rec=cases.get(key,{})
        for label in ('r9_native','candidate'):
            raw=rec.get('raw_ms',{}).get(label)
            if not isinstance(raw,list) or len(raw)!=report.get('pairs',0) or any(
                not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<=0
                for v in raw):
                problems.append(key+':invalid_raw_'+label)
                continue
            median=statistics.median(raw)
            reported=rec.get('median_ms',{}).get(label)
            if not isinstance(reported,(int,float)) or abs(reported-median)>max(1e-6,median*1e-8):
                problems.append(key+':median_mismatch_'+label)
            metadata=rec.get('png',{}).get(label,{})
            expected=f'FILTER_PIXELS/{key.replace("/","_")}_{label}.png'
            if metadata.get('path')!=expected:
                problems.append(key+':png_path_'+label)
                continue
            try:
                raw_png=read_png(expected)
            except Exception:
                problems.append(key+':missing_png_'+label)
                continue
            digest=hashlib.sha256(raw_png).hexdigest()
            if (len(raw_png)!=metadata.get('bytes') or digest!=metadata.get('sha256') or
                digest!=rec.get('png_sha256',{}).get(label) or
                not raw_png.startswith(b'\x89PNG\r\n\x1a\n') or len(raw_png)<1000):
                problems.append(key+':png_integrity_'+label)
        old=rec.get('median_ms',{}).get('r9_native',0)
        new=rec.get('median_ms',{}).get('candidate',0)
        if not isinstance(old,(int,float)) or not isinstance(new,(int,float)) or new<=0:
            problems.append(key+':missing_medians')
        else:
            ratio=old/new
            reported=rec.get('speedup_x')
            if not isinstance(reported,(int,float)) or abs(ratio-reported)>max(1e-6,ratio*1e-8):
                problems.append(key+':ratio_mismatch')
            if ratio<3.0: problems.append(key+':insufficient_speedup')
        if (rec.get('png_sha256',{}).get('r9_native')!=rec.get('png_sha256',{}).get('candidate') or
            rec.get('ui',{}).get('r9_native')!=rec.get('ui',{}).get('candidate') or
            not rec.get('parity')):
            problems.append(key+':visual_or_ui_parity')
    return problems

if __name__=='__main__':
    args=argparse.ArgumentParser()
    args.add_argument('--out',type=Path,default=ROOT/'external-results/R9_FILTER_BENCHMARK.json')
    args.add_argument('--pairs',type=int,default=PAIRS)
    ns=args.parse_args()
    res=bench(ns.out,ns.pairs)
    print('Browser:',res['chromium_version'],'acceptance:',res['acceptance'],'errors:',res['page_errors'])
    for name,c in res['cases'].items():
        print(name,round(c['speedup_x'],2),'x; baseline/candidate:',round(c['median_ms']['r9_native'],3),round(c['median_ms']['candidate'],3),'ms; parity',c['parity'], 'query event ms',round(c['query_change_ms']['r9_native'],2),round(c['query_change_ms']['candidate'],2))
    print('Behavioral parity:', [(s['state'],s['status']) for s in res['behavioral_parity']])
    print('Keyboard inspection:',json.dumps(res.get('keyboard_inspection',{}),sort_keys=True))
    print('Independent validation errors:',json.dumps(res.get('independent_validation_errors',[]),sort_keys=True))
    raise SystemExit(0 if res['acceptance']=='PASS_WITHIN_SCOPE' else 2)
