"""Paired benchmark on real, already-cloned Git histories (v0.7 vs v0.8).

No network access or checkout is required. Repository source content is not
read/executed. Only Git metadata/tree identities are analyzed. Real repos may
contain identifying metadata: the evidence reports only repository identity,
SHA, counts, hashes and timings, not commit messages or filenames.

Example:
  python scripts/benchmark_real_workloads.py \
    --baseline /path/to/repoorbit-0.7/REPO_ORBIT \
    --repo /path/to/a/local/git/checkout \
    --commits 60 300 1000 --runs 7 --output evidence/real.json
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import importlib.util
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def _load(filename: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, filename)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(path: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ['git', '-C', str(path), *arguments], text=True, stderr=subprocess.PIPE,
        timeout=40, encoding='utf-8', errors='replace').strip()


def _payload_hash(document: str) -> str:
    match = re.search(
        r'<script type="application/json" data-encoding="([^"]+)" id="dataset">(.*?)</script>',
        document, flags=re.DOTALL)
    if not match:
        raise AssertionError('Embedded browser dataset missing')
    encoding, text = match.groups()
    if encoding == 'gzip-base64':
        contents = gzip.decompress(base64.b64decode(text))
    elif encoding == 'plain-json':
        contents = text.encode('utf-8')
    else:
        raise AssertionError('Unknown browser data encoding')
    # compare canonical JSON content rather than gzip bytes / compression levels
    parsed = json.loads(contents)
    return hashlib.sha256(json.dumps(parsed, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def _median(values: list[float]) -> float:
    return round(statistics.median(values), 4)


def run_benchmark(repo: Path, baseline: Path, windows: list[int], runs: int, verification: str):
    old = {'core': _load(baseline/'repoorbit'/'core.py', 'v07_external_core'),
           'render': _load(baseline/'repoorbit'/'render.py', 'v07_external_render')}
    new = {'core': _load(HERE/'repoorbit'/'core.py', 'v08_external_core'),
           'render': _load(HERE/'repoorbit'/'render.py', 'v08_external_render')}
    engines = {'v0.7.0': old, 'v0.8.0': new}
    repo = repo.resolve(strict=True)
    max_history = int(_git(repo, 'rev-list', '--first-parent', '--count', 'HEAD'))
    if max_history < 1:
        raise RuntimeError('No Git commits available')
    is_shallow = _git(repo, 'rev-parse', '--is-shallow-repository') == 'true'
    try:
        origin = _git(repo, 'remote', 'get-url', 'origin')
    except subprocess.CalledProcessError:
        origin = None
    metadata = {
        'repository': repo.name,
        'origin': origin,
        'HEAD': _git(repo, 'rev-parse', 'HEAD'),
        'is_shallow': is_shallow,
        'first_parent_history_available': max_history,
        'git_version': subprocess.check_output(['git', '--version'], text=True).strip(),
        'python': platform.python_version(),
        'platform': platform.platform(),
        'cpu_count': os.cpu_count(),
    }
    outcomes = []
    for requested in windows:
        commits = min(requested, max_history)
        if commits < 1:
            raise ValueError('Commit windows must be positive')
        timings = {label: {'analyze_ms': [], 'render_ms': [], 'total_ms': []}
                   for label in engines}
        parity = {}
        for trial in range(runs + 1):  # first run is unmeasured warm-up
            order = ['v0.7.0', 'v0.8.0'] if trial % 2 == 0 else ['v0.8.0', 'v0.7.0']
            for label in order:
                eng = engines[label]
                t0 = time.perf_counter_ns()
                data = eng['core'].analyze(repo, limit=commits, verification=verification)
                t1 = time.perf_counter_ns()
                html = eng['render'].render(data, compression='gzip')
                t2 = time.perf_counter_ns()
                if trial == 0:
                    packed = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
                    parity[label] = {
                        'data_sha256': hashlib.sha256(packed.encode('utf-8')).hexdigest(),
                        'payload_sha256': _payload_hash(html),
                        'events': data.get('changes_total'),
                        'paths': data.get('paths_total'),
                        'commits': data.get('history_window'),
                        'html_bytes': len(html.encode('utf-8')),
                    }
                else:
                    timings[label]['analyze_ms'].append(round((t1-t0)/1_000_000, 4))
                    timings[label]['render_ms'].append(round((t2-t1)/1_000_000, 4))
                    timings[label]['total_ms'].append(round((t2-t0)/1_000_000, 4))
        equal_data = parity['v0.7.0']['data_sha256'] == parity['v0.8.0']['data_sha256']
        equal_payload = parity['v0.7.0']['payload_sha256'] == parity['v0.8.0']['payload_sha256']
        if not equal_data or not equal_payload:
            raise AssertionError(f'Output parity FAILURE: window={commits}')
        medians = {label: {metric: _median(samples) for metric, samples in metrics.items()}
                   for label, metrics in timings.items()}
        ratios = {metric: round(medians['v0.7.0'][metric] / medians['v0.8.0'][metric], 4)
                  for metric in ('analyze_ms', 'render_ms', 'total_ms')}
        result = {
            'requested_commits': requested,
            'actual_commits': commits,
            'first_parent_derived': True,
            'verification': verification,
            'parity': {'canonical_json': 'PASS', 'browser_dataset': 'PASS'},
            'shape': {k: parity['v0.8.0'][k] for k in ('events', 'paths', 'commits')},
            'html_bytes': {label: parity[label]['html_bytes'] for label in engines},
            'raw_ms': timings,
            'median_ms': medians,
            'speedup_v07_div_v08': ratios,
        }
        outcomes.append(result)
        print(f"commits={commits} total-speedup={ratios['total_ms']:.3f}x "
              f"analysis={ratios['analyze_ms']:.3f}x render={ratios['render_ms']:.3f}x",
              flush=True)
    return {
        'status': 'PASS' if all(case['parity']['canonical_json'] == 'PASS' and
                                case['parity']['browser_dataset'] == 'PASS' for case in outcomes) else 'FAIL',
        'scope': 'Real local Git checkout; analysis plus offline HTML rendering; no browser or network timing',
        'protocol': f'{runs} measured trials per version/window; one unmeasured warmup; alternating execution order; median',
        'metadata': metadata,
        'source_sha256': {
            label: {part: hashlib.sha256((root/'repoorbit'/f'{part}.py').read_bytes()).hexdigest()
                    for part in ('core', 'render')}
            for label, root in (('v0.7.0', baseline), ('v0.8.0', HERE))
        },
        'cases': outcomes,
        'limitations': [
            'Results apply only to the checked-out commit and selected first-parent windows.',
            'Running the same repository at multiple depths is NOT multiple independent external repositories.',
            'Uses warm filesystem/process caches; cold-start analysis not measured.',
            'No browser interactive measurements, SVG export, or simultaneous workload measurements.',
            'Windows and macOS remain untested until measurements are returned from those systems.',
            'A universal performance advantage across all possible repositories is logically unprovable by finite benchmarks.',
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path, help='Unmodified v0.7.0 REPO_ORBIT root')
    parser.add_argument('--repo', required=True, type=Path, help='Pre-cloned local repository')
    parser.add_argument('--commits', type=int, nargs='+', default=[60, 300, 1000])
    parser.add_argument('--runs', type=int, default=7)
    parser.add_argument('--verify', choices=['sample','full'], default='sample')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not 5 <= args.runs <= 21:
        parser.error('--runs must be 5..21')
    if any(c < 1 or c > 8000 for c in args.commits):
        parser.error('All requested commit windows must be 1..8000')
    baseline = args.baseline.resolve(strict=True)
    report = run_benchmark(args.repo, baseline, list(dict.fromkeys(args.commits)), args.runs, args.verify)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(f"Completed: {args.output}")

if __name__ == '__main__':
    main()
