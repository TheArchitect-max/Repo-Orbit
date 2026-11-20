"""Summarize genuine-repository paired benchmark evidence (stdlib only).

The bootstrap intervals resample paired trial indices. They are exploratory;
filesystem cache, ordering and machine load can violate independence.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path


def summarize(evidence: dict, *, resamples: int = 10000, seed: int = 2080) -> str:
    if evidence.get('status') != 'PASS':
        raise ValueError('Benchmark must pass output parity before summarization')
    rng = random.Random(seed)
    out = [
        '# Real Git repository benchmark', '',
        f"Repository: `{evidence['metadata']['origin']}`",
        f"Git HEAD: `{evidence['metadata']['HEAD']}`",
        f"Platform: `{evidence['metadata']['platform']}`",
        f"Python: `{evidence['metadata']['python']}`; {evidence['metadata']['git_version']}",
        '',
        '| Commits | v0.7 total (ms) | v0.8 total (ms) | Speedup | Approx. 95% paired bootstrap interval | v0.8 pair wins |',
        '|---:|---:|---:|---:|---:|---:|',
    ]
    for case in evidence['cases']:
        old = case['raw_ms']['v0.7.0']['total_ms']
        new = case['raw_ms']['v0.8.0']['total_ms']
        assert len(old) == len(new) and len(old) >= 5
        n = len(old)
        ratios = []
        for _ in range(resamples):
            picks = [rng.randrange(n) for _ in range(n)]
            ratios.append(statistics.median(old[i] for i in picks) /
                          statistics.median(new[i] for i in picks))
        ratios.sort()
        low = ratios[int(.025 * resamples)]
        high = ratios[int(.975 * resamples)-1]
        med = case['median_ms']
        wins = sum(a > b for a, b in zip(old, new))
        out.append(f"| {case['actual_commits']} | {med['v0.7.0']['total_ms']:.2f} | "
                   f"{med['v0.8.0']['total_ms']:.2f} | "
                   f"{case['speedup_v07_div_v08']['total_ms']:.3f}× | "
                   f"{low:.3f}–{high:.3f}× | {wins}/{n} |")
    out += ['', 'Benchmark coverage: one independent external codebase; multiple first-parent windows ',
            'from the **same repository**, not multiple independent repository samples.',
            '', 'Caution: paired bootstrap intervals characterize repeated timings in this run, '
            'not variability across machines or repositories. A span containing 1.0 is '
            'inconclusive about performance direction. No cross-platform generalization is justified.', '']
    return '\n'.join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    summary = summarize(json.loads(args.evidence.read_text(encoding='utf-8')))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(summary, encoding='utf-8')
        print(f'Summary written: {args.output}')
    else:
        print(summary)


if __name__ == '__main__':
    main()
