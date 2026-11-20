"""Offline, independent v0.3-versus-current performance and JSON-equivalence runner.

Use a previously extracted v0.3 source tree and a representative local Git
repository. No data are uploaded and this script does not modify the repo.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def execute(source: Path, repo: Path, commits: int) -> dict:
    program = (
        "import json,sys,time;"
        "from repoorbit.core import analyze;"
        "t=time.perf_counter();"
        "d=analyze(sys.argv[1],limit=int(sys.argv[2]),verification='sample');"
        "print(json.dumps({'elapsed_ms':round((time.perf_counter()-t)*1000,3),'payload':d},sort_keys=True,separators=(',',':'),ensure_ascii=False))"
    )
    r = subprocess.run([sys.executable, '-c', program, str(repo), str(commits)],
                       env={**os.environ,'PYTHONPATH':str(source)},cwd=str(source),
                       text=True,capture_output=True,timeout=120,check=False)
    if r.returncode:
        raise RuntimeError(f'Analysis failed in {source.name}: {r.stderr.strip()[:400]}')
    return json.loads(r.stdout)


def main():
    parser=argparse.ArgumentParser(description='Compare Git analysis times and exact JSON data offline.')
    parser.add_argument('--baseline',required=True,type=Path,help='Extracted v0.3.0 REPO_ORBIT source root')
    parser.add_argument('--repo',required=True,type=Path,help='Local Git repo used by both engines')
    parser.add_argument('--commits',type=int,default=220,help='History length for both engines (1-800)')
    parser.add_argument('--runs',type=int,default=3,help='Runs per engine (1-20)')
    args=parser.parse_args()
    baseline=args.baseline.expanduser().resolve();repo=args.repo.expanduser().resolve()
    if not (baseline/'repoorbit/core.py').is_file() or not (HERE/'repoorbit/core.py').is_file():
        parser.error('Both source trees must contain repoorbit/core.py')
    if not repo.is_dir() or not 1<=args.commits<=800 or not 1<=args.runs<=20:
        parser.error('Expected a local repository, 1-800 commits and 1-20 runs')
    times={'baseline':[],'candidate':[]}
    expected=None
    # Interleave runs to reduce systematic drift; output is never persisted to disk.
    for _ in range(args.runs):
        for name,source in [('baseline',baseline),('candidate',HERE)]:
            result=execute(source,repo,args.commits)
            payload=json.dumps(result['payload'],sort_keys=True,ensure_ascii=False,separators=(',',':'))
            digest=hashlib.sha256(payload.encode('utf-8')).hexdigest()
            if expected is None:expected=digest
            if digest!=expected:raise RuntimeError(f'FAIL: structured JSON mismatch in {name}; versions are not equivalent')
            times[name].append(result['elapsed_ms'])
    a=statistics.median(times['baseline']);b=statistics.median(times['candidate'])
    print(json.dumps({'parity':'PASS','commits':args.commits,'runs_per_engine':args.runs,
                      'baseline_median_ms':a,'candidate_median_ms':b,
                      'speedup_x':round(a/b,3) if b else None,
                      'runs_ms':times,'json_sha256':expected,
                      'note':'Synthetic or chosen local workloads only; results are environment-specific.'},indent=2))

if __name__=='__main__':main()
