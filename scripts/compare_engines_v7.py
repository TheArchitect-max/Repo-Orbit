"""Paired v0.6→v0.7 Git engine comparison on the same real synthetic repository.

Requires v0.6 core.py as --baseline; no network and no real user data.
Checks full canonical JSON equality before reporting timing differences.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def load(path: Path, module: str):
    spec=importlib.util.spec_from_file_location(module,str(path))
    candidate=importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(candidate)
    return candidate


def git(path:Path,*args:str):
    subprocess.run(['git','-C',str(path),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--baseline',type=Path,required=True,help='Unmodified repoorbit/core.py from v0.6.0')
    ap.add_argument('--runs',type=int,default=5)
    args=ap.parse_args()
    if args.runs<3 or args.runs>30:ap.error('--runs must be between 3 and 30')
    old=load(args.baseline,'reporbit_baseline_v06')
    new=load(ROOT/'repoorbit/core.py','reporbit_candidate_v07')
    with tempfile.TemporaryDirectory(prefix='repo-orbit-v7-bench-') as td:
        repo=Path(td)/'Bench';repo.mkdir()
        git(repo,'init','-q');git(repo,'config','user.name','Synthetic Benchmark')
        git(repo,'config','user.email','benchmark@example.invalid')
        for i in range(48):
            directory=repo/'src'/f'module_{i%8:02d}'
            directory.mkdir(parents=True,exist_ok=True)
            for n in range(100):
                (directory/f'file_{i*100+n:05d}.py').write_text(f'VALUE={i*100+n}\n')
            git(repo,'add','-A');git(repo,'commit','-qm',f'Synthetic commit {i+1}')
        canonical=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
        assert canonical(old.analyze(repo,48))==canonical(new.analyze(repo,48)), 'JSON replay parity failure'
        timings={'v06':[],'v07':[]}
        for i in range(args.runs):
            ordered=[('v07',new),('v06',old)] if i%2 else [('v06',old),('v07',new)]
            for label, engine in ordered:
                started=time.perf_counter();result=engine.analyze(repo,48)
                timings[label].append(round((time.perf_counter()-started)*1000,3))
                assert result['files_final']==4800 and result['verified_frames']==3
        med_old=statistics.median(timings['v06'])
        med_new=statistics.median(timings['v07'])
        report={
            'status':'PASS', 'fixture':'48 actual local Git commits / 4,800 paths / 4,800 events',
            'comparison':'same repository, same verification=sample, alternating 5-run order',
            'canonical_json_parity':'BYTE_IDENTICAL',
            'baseline_source_sha256':hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
            'candidate_source_sha256':hashlib.sha256((ROOT/'repoorbit/core.py').read_bytes()).hexdigest(),
            'runs_ms':timings,'medians_ms':{'v06':med_old,'v07':med_new},
            'speedup_x':round(med_old/med_new,3),
            'environment':{'platform':platform.platform(),'git':subprocess.check_output(['git','--version'],text=True).strip()},
            'limitations':'Synthetic data; five local samples; measures analyze only; not a universal performance guarantee.'
        }
        dest=ROOT/'evidence/v07_paired_engine_comparison.json'
        dest.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
