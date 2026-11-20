"""Reproducible multi-workload v0.7 -> v0.8 end-to-end benchmark.

On the same real, synthetic, local Git fixtures, alternating engine order, report
analyze, render and analyze+render independently. Verifies complete JSON parity
and decoded offline data parity before making any performance claim.

Examples:
 python scripts/benchmark_v8_paired.py --baseline /path/to/v0.7.0/REPO_ORBIT --fixture-root /path/to/fixtures --runs 7
"""
from __future__ import annotations
import argparse
import base64
import gzip
import hashlib
import importlib.util
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CASES = [('short',60,3200,6400),('wide',180,16000,85000),('deep',1200,20000,140000)]


def load(file: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,str(file))
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decoded_payload(document: str) -> dict:
    import re
    match=re.search(r'<script type="application/json" data-encoding="([^"]+)" id="dataset">(.*?)</script>',document,re.S)
    if not match:raise AssertionError('missing embedded dataset')
    coding, encoded=match.groups()
    if coding=='gzip-base64': raw=gzip.decompress(base64.b64decode(encoded)).decode('utf8')
    elif coding=='plain-json': raw=encoded
    else: raise AssertionError('unknown encoding')
    return json.loads(raw)


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--baseline',type=Path,required=True)
    a.add_argument('--fixture-root',type=Path,required=True)
    a.add_argument('--runs',type=int,default=7)
    a.add_argument('--build-fixtures', action='store_true', help='Build missing synthetic Git fixtures locally')
    a.add_argument('--output',type=Path,default=HERE/'evidence/v08_paired_performance.json')
    args=a.parse_args()
    if not 5<=args.runs<=21:a.error('--runs must be 5..21')
    baseline=args.baseline.resolve()
    if args.build_fixtures:
        sys.path.insert(0,str(HERE))
        from scripts.stress_combined_limits import build_fixture
        for label,commits,paths,events in CASES:
            fixture=args.fixture_root/('fixture_'+label)
            if not (fixture/'.git').exists():
                build_fixture(fixture,commits,paths,events)
    v07core=load(baseline/'repoorbit/core.py','v07_core_benchmark')
    v07render=load(baseline/'repoorbit/render.py','v07_render_benchmark')
    v08core=load(HERE/'repoorbit/core.py','v08_core_benchmark')
    v08render=load(HERE/'repoorbit/render.py','v08_render_benchmark')
    reports=[]
    for label, commits,paths,events in CASES:
        fixture=args.fixture_root/('fixture_'+label)
        if not fixture.is_dir():raise RuntimeError(f'Fixture missing: {fixture}')
        times={name:{'analyze_ms':[],'render_ms':[],'total_ms':[]} for name in ('v07','v08')}
        artifacts={}
        for trial in range(args.runs):
            order=[('v08',v08core,v08render),('v07',v07core,v07render)] if trial%2 else [('v07',v07core,v07render),('v08',v08core,v08render)]
            for name,core,renderer in order:
                start=time.perf_counter(); data=core.analyze(fixture,limit=commits,verification='sample'); middle=time.perf_counter()
                html=renderer.render(data,compression='gzip'); end=time.perf_counter()
                assert data['history_window']==commits and data['paths_total']==paths and data['changes_total']==events
                times[name]['analyze_ms'].append(round((middle-start)*1000,3))
                times[name]['render_ms'].append(round((end-middle)*1000,3))
                times[name]['total_ms'].append(round((end-start)*1000,3))
                if trial==0:
                    artifacts[name]={'canonical_json':json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')),
                                     'payload':decoded_payload(html),'html_bytes':len(html.encode('utf8'))}
        assert artifacts['v07']['canonical_json']==artifacts['v08']['canonical_json'],f'full Git JSON parity failed: {label}'
        assert artifacts['v07']['payload']==artifacts['v08']['payload'],f'packed HTML payload parity failed: {label}'
        med={name:{k:round(statistics.median(vals),3) for k,vals in metric.items()} for name,metric in times.items()}
        report={'case':label,'commits':commits,'paths':paths,'events':events,'verification':'sample (3 real Git-tree checkpoints)',
                'canonical_json_parity':'PASS','embedded_payload_parity':'PASS',
                'raw_ms':times,'median_ms':med,
                'speedup_x':{k:round(med['v07'][k]/med['v08'][k],3) for k in ('analyze_ms','render_ms','total_ms')},
                'html_bytes':{name:artifacts[name]['html_bytes'] for name in ('v07','v08')},
                'html_size_ratio_v08_to_v07':round(artifacts['v08']['html_bytes']/artifacts['v07']['html_bytes'],4)}
        reports.append(report)
        print(label,report['speedup_x'],report['html_bytes'],flush=True)
    response={'status':'PASS','baseline_version':'0.7.0','candidate_version':'0.8.0',
        'protocol':'alternating paired order; seven sequential trials; median; same Git fixtures and verification; no network',
        'git':subprocess.check_output(['git','--version'],text=True).strip(),
        'python':platform.python_version(),'platform':platform.platform(),
        'baseline_sha256':{f:hashlib.sha256((baseline/'repoorbit'/f).read_bytes()).hexdigest() for f in ('core.py','render.py')},
        'candidate_sha256':{f:hashlib.sha256((HERE/'repoorbit'/f).read_bytes()).hexdigest() for f in ('core.py','render.py')},
        'cases':reports,
        'limitations':['Synthetic Git histories; cache and process scheduling influence results.',
                       'Only the tested workloads and selected first-parent sample verification are measured.',
                       'Browser interactivity, SVG exports and production hardware are not included in end-to-end timings.',
                       'Performance is not guaranteed for all possible Git repositories or operating systems.']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(response,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':response['status'],'cases':[
        {'case':x['case'],'speedup':x['speedup_x'],'size_ratio':x['html_size_ratio_v08_to_v07']} for x in reports]},indent=2))

if __name__=='__main__':main()
