"""Reproducible 8,000-commit, 30,000-file Git scalability experiment.

Use git fast-import (genuine Git commits/objects/trees, no mock events).
No network activity and no personal or public repositories.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repoorbit.core import analyze
from repoorbit.render import render

COMMITS = 8000
FILES = 30000
CHANGES_PER_COMMIT = 5


def git(root: Path, *args: str, timeout: int = 180) -> bytes:
    return subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=timeout).stdout


def create_fixture(root: Path, commits: int = COMMITS, paths: int = FILES, changes: int = CHANGES_PER_COMMIT) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git(root, 'init', '-q')
    git(root, 'config', 'user.name', 'Orbit Scale Fixture')
    git(root, 'config', 'user.email', 'fixture@example.invalid')
    proc = subprocess.Popen(['git', '-C', str(root), 'fast-import', '--quiet'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    def send(value: str) -> None:
        proc.stdin.write(value.encode('utf-8'))
    try:
        send('blob\nmark :1\ndata 2\nx\n')
        for c in range(commits):
            when = 1700000000+c
            send('commit refs/heads/main\n')
            send(f'author Orbit Fixture <fixture@example.invalid> {when} +0000\n')
            send(f'committer Orbit Fixture <fixture@example.invalid> {when} +0000\n')
            message = f'fixture event {c}'
            send(f'data {len(message)}\n{message}\n')
            if c == 0:
                for j in range(paths):
                    send(f'M 100644 :1 src/group_{j%24:02d}/file_{j:05d}.py\n')
            else:
                for j in range(changes):
                    which = (c*101+j*997) % paths
                    body = f'synthetic c={c} j={j}\n'
                    send(f'M 100644 inline src/group_{which%24:02d}/file_{which:05d}.py\n')
                    send(f'data {len(body)}\n{body}')
            send('\n')
    except Exception:
        proc.kill()
        raise
    finally:
        proc.stdin.close()
    try:
        proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        proc.kill(); raise
    if proc.returncode:
        raise RuntimeError('git fast-import failed: '+proc.stderr.read().decode('utf-8','replace')[:1000])
    # A normal populated checkout so --dirty and all browser data match real repos.
    git(root, 'checkout', '-q', '-f', 'main', timeout=180)


def measure(root: Path, limit: int = COMMITS, baseline: Path | None = None) -> dict:
    started = time.perf_counter()
    data = analyze(root, limit=limit)
    analysis_seconds = time.perf_counter()-started
    expected = paths_expected = FILES
    if data['history_window'] != limit or data['files_final'] != expected:
        raise AssertionError(f'Unexpected analyzed fixture: {data["history_window"]} / {data["files_final"]}')
    if data['changes_total'] != FILES + (limit-1)*CHANGES_PER_COMMIT:
        raise AssertionError('Raw changed file events do not match fixture')
    started = time.perf_counter()
    compact = render(data)
    compact_seconds = time.perf_counter()-started
    packed_uncompressed = render(data, compression='plain')
    legacy = render(data, compact=False, compression='plain')
    (ROOT/'demo'/'RepoOrbit_ScaleDemo.html').write_text(compact,encoding='utf-8')
    import importlib.util
    original = baseline/'repoorbit'/'render.py' if baseline is not None else Path('/nonexistent/v04-render.py')
    if baseline is not None and not original.is_file():
        raise RuntimeError(f'v0.4 renderer not found under {baseline}')
    if original.is_file():
        spec = importlib.util.spec_from_file_location('orbit_v04_renderer',original)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        old_html = module.render(data)
        (ROOT.parent/'v04_scale_browser_reference.html').write_text(old_html,encoding='utf-8')
    else:
        old_html = None
    out = {
        'fixture': {'genuine_git_commits':limit,'tracked_files':FILES,
                    'changes_per_later_commit':CHANGES_PER_COMMIT,'change_events':data['changes_total']},
        'verification':{'sampled_frames':data['verified_frames'], 'final_paths':data['files_final'],
                        'head':data['head'],'dirty':data['dirty']},
        'analysis_elapsed_seconds':round(analysis_seconds,3),
        'compact_html_bytes':len(compact.encode('utf-8')),
        'legacy_html_bytes':len(legacy.encode('utf-8')),
        'packed_plain_html_bytes':len(packed_uncompressed.encode('utf-8')),
        'v04_html_bytes':len(old_html.encode('utf-8')) if old_html else None,
        'html_size_reduction_x':round(len(legacy.encode())/len(compact.encode()),3),
        'v04_to_v05_html_reduction_x':round(len(old_html.encode())/len(compact.encode()),3) if old_html else None,
        'compact_render_seconds':round(compact_seconds,3),
        'python_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'disclaimer':'Environment-specific measurements on a synthetically generated real Git repository; not proof of universal performance.',
    }
    return out


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,default=None,help='Optional extracted v0.4.0 REPO_ORBIT source root for an exact old-viewer HTML comparison')
    args=parser.parse_args()
    destination = ROOT/'evidence'/'scale_v5.json'
    with tempfile.TemporaryDirectory(prefix='orbit-v5-8000-') as directory:
        repo=Path(directory)/'Synthetic8000'
        t=time.perf_counter();create_fixture(repo)
        build_seconds=time.perf_counter()-t
        result=measure(repo,baseline=args.baseline.resolve() if args.baseline else None)
        result['fixture_build_seconds']=round(build_seconds,3)
        destination.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__':main()
