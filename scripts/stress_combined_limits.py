"""Acceptance at ALL REPO ORBIT v0.5.0 advertised bounds, simultaneously.

Fixture consists of real Git objects and real Git commits constructed through
`git fast-import`; only synthetic metadata is used. No network required.

Test targets:
 - MAX_COMMITS = 8,000 first-parent commits
 - MAX_PATHS  = 80,000 distinct Git paths
 - MAX_EVENTS = 900,000 true path-level Git diff events
 - exact Git tree and object identity checkpoints from --verify sample
 - self-contained HTML generation and browser load (separate script)

Does not prove all possible Git filesystems, input encodings, or browsers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repoorbit.core import MAX_COMMITS, MAX_EVENTS, MAX_PATHS, analyze
from repoorbit.render import render


def git(root: Path, *args: str, timeout: int = 300) -> bytes:
    run = subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, check=True, timeout=timeout)
    return run.stdout


def build_fixture(root: Path, commits: int, paths: int, events: int) -> dict:
    if commits <= 0 or paths <= 0 or events < paths or (events-paths) < (commits-1):
        raise ValueError('invalid fixture dimensions')
    root.mkdir(parents=True, exist_ok=True)
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'config', 'user.name', 'Orbit Benchmark')
    git(root, 'config', 'user.email', 'benchmark@example.invalid')
    names = [f'src/cluster_{i//2500:02d}/file_{i:05d}.py' for i in range(paths)]
    proc = subprocess.Popen(['git', '-C', str(root), 'fast-import', '--quiet'],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, bufsize=1024*1024)
    assert proc.stdin is not None
    cursor = 0
    subsequent = events-paths
    base, extra = divmod(subsequent, commits-1) if commits>1 else (0,0)
    started = time.perf_counter()
    written = 0
    try:
        for c in range(commits):
            data=f'content for Git commit {c:05d}\n'.encode()
            proc.stdin.write(f'blob\nmark :{c+1}\ndata {len(data)}\n'.encode())
            proc.stdin.write(data+b'\n')
            epoch=1700000000+c
            message=f'combined bounds fixture {c:05d}'
            proc.stdin.write((f'commit refs/heads/main\n'
                f'author Orbit Fixture <fixture@example.invalid> {epoch} +0000\n'
                f'committer Orbit Fixture <fixture@example.invalid> {epoch} +0000\n'
                f'data {len(message)}\n{message}\n').encode())
            if c == 0:
                changed = paths
                for name in names:
                    proc.stdin.write(f'M 100644 :1 {name}\n'.encode())
            else:
                changed = base + (1 if c<=extra else 0)
                for _ in range(changed):
                    name = names[cursor%paths]
                    proc.stdin.write(f'M 100644 :{c+1} {name}\n'.encode())
                    cursor += 1
            written+=changed
            proc.stdin.write(b'\n')
        proc.stdin.close()
        try:
            code=proc.wait(timeout=900)
        except subprocess.TimeoutExpired:
            proc.kill(); raise RuntimeError('git fast-import timeout')
        if code:
            raise RuntimeError('git fast-import exit '+str(code)+': '+proc.stderr.read(3000).decode(errors='replace'))
    except BaseException:
        if proc.poll() is None: proc.kill()
        raise
    elapsed = time.perf_counter()-started
    assert written == events,(written,events)
    assert int(git(root,'rev-list','--count','--first-parent','HEAD')) == commits
    # No checkout: core.status porcelain on unborn bare worktree would interpret all
    # committed paths as deleted; materialize only index, not a huge worktree.
    git(root,'read-tree','HEAD',timeout=300)
    return {'build_seconds':round(elapsed,3),'git_head':git(root,'rev-parse','HEAD').decode().strip(),
            'git_count':commits,'paths_constructed':paths,'events_constructed':written,
            'fixture_worktree':'index-only, no checked-out source files',
            'repo_disk_bytes':sum(p.stat().st_size for p in (root/'.git').rglob('*') if p.is_file())}


def analyze_fixture(root: Path, output: Path, html_path: Path) -> dict:
    started=time.perf_counter()
    data=analyze(root,limit=MAX_COMMITS,verification='sample')
    elapsed=time.perf_counter()-started
    assert data['history_window']==MAX_COMMITS, data['history_window']
    assert data['files_final']==MAX_PATHS, data['files_final']
    assert data['paths_total']==MAX_PATHS, data['paths_total']
    assert data['changes_total']==MAX_EVENTS, data['changes_total']
    assert data['verified_frames']==3, data['verified_frames']
    assert data['partial_history'] is False
    assert data['dirty'] is True, 'index-only fixture must report missing worktree as dirty'
    assert sum(len(c['changes']) for c in data['commits'])==MAX_EVENTS
    assert len(data['baseline'])==0
    # Probe change counts and stable metadata in real Git independently.
    assert len(data['commits'][0]['changes'])==MAX_PATHS
    assert len(data['commits'][-1]['changes']) in [102,103]
    assert all(len(c['versions'])==len(c['changes']) for c in data['commits'])
    assert git(root, 'rev-parse','HEAD').decode().strip()==data['head']
    elapsed_render=time.perf_counter()
    html=render(data,compression='gzip')
    render_s=time.perf_counter()-elapsed_render
    html_path.write_text(html,encoding='utf-8')
    html_bytes=html_path.stat().st_size
    if html_bytes > 32*1024*1024:
        raise AssertionError('Default 32 MiB HTML cap exceeded')
    report={
        'status':'PYTHON_GATE_PASS',
        'fixture_type':'actual Git fast-import objects and commits, synthetic contents',
        'limits': {'MAX_COMMITS':MAX_COMMITS,'MAX_PATHS':MAX_PATHS,'MAX_EVENTS':MAX_EVENTS},
        'observed': {'commits':data['history_window'],'paths_total':data['paths_total'],
            'files_final':data['files_final'],'events':data['changes_total'],
            'checked_snapshots':data['verified_frames'], 'full_snapshots_verified':False,
            'first_commit_events':len(data['commits'][0]['changes']),
            'last_commit_events':len(data['commits'][-1]['changes']),
            'HTML_bytes':html_bytes,'HTML_SHA256':hashlib.sha256(html_path.read_bytes()).hexdigest(),
            'JSON_uncompressed_estimated_bytes':len(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode())},
        'timing_seconds':{'analysis':round(elapsed,3),'render':round(render_s,3)},
        'process_peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'environment':{'platform':platform.platform(),'python':platform.python_version(),
                       'git':git(root,'--version').decode().strip()},
        'security_notes':['Synthetic repository only; no user files or networking',
                          'sampled tree/object-oracle validation: 3 frames, NOT full 8,000-frame verification'],
        'limitations':['No guarantee for arbitrary histories or uncommon filenames',
                       'Browser acceptance performed separately',
                       'No platform-independent memory/performance guarantee']
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,sort_keys=True),flush=True)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repository',type=Path,required=True)
    p.add_argument('--html',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--reuse-fixture',action='store_true')
    args=p.parse_args()
    assert (MAX_COMMITS,MAX_PATHS,MAX_EVENTS)==(8000,80000,900000)
    if not args.reuse_fixture:
        result=build_fixture(args.repository,MAX_COMMITS,MAX_PATHS,MAX_EVENTS)
        print('Fixture construction: '+json.dumps(result),flush=True)
    analyze_fixture(args.repository,args.report,args.html)

if __name__=='__main__': main()
