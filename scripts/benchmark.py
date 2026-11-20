"""Reproducible mid-size Git ingestion benchmark; no fixed performance claim.

Synthetic code files only; intentionally no real user data or network.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from repoorbit.core import analyze
from repoorbit.render import render


def git(repo,*args):
    subprocess.run(['git','-C',str(repo),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)


def run():
    with tempfile.TemporaryDirectory(prefix='repoorbit-scale-') as directory:
        repo=Path(directory)/'SyntheticScale';repo.mkdir()
        git(repo,'init','-q');git(repo,'config','user.name','Benchmark')
        git(repo,'config','user.email','benchmark@example.invalid')
        start=time.perf_counter()
        for i in range(48):
            for j in range(100):
                file=repo/f'src/module_{i%8:02d}'/f'file_{i*100+j:05d}.py'
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text(f'# synthetic file {i*100+j}\n',encoding='utf-8')
            git(repo,'add','-A');git(repo,'commit','-qm',f'Synthetic event {i+1}')
        fixture_ms=round((time.perf_counter()-start)*1000)
        start=time.perf_counter()
        data=analyze(repo,limit=48,verification='sample')
        analyze_ms=round((time.perf_counter()-start)*1000)
        start=time.perf_counter();html=render(data)
        render_ms=round((time.perf_counter()-start)*1000)
        if data['files_final']!=4800 or data['changes_total']!=4800:
            raise AssertionError('Scale fixture was not faithfully replayed')
        return {'fixture':'48 real Git commits x 100 unique files',
                'synthetic_paths':4800,'changes':4800,
                'git_fixture_build_ms':fixture_ms,
                'analyze_ms':analyze_ms,'render_ms':render_ms,
                'html_bytes':len(html.encode('utf-8')),
                'verification':'sample','verified_frames':data['verified_frames'],
                'environment':{'python':sys.version.split()[0],
                               'platform':sys.platform},
                'disclaimer':'Measurements are one environment-specific sample, not an SLA or throughput guarantee.'}


if __name__=='__main__':
    result=run()
    target=ROOT/'evidence'/'scale_benchmark.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
