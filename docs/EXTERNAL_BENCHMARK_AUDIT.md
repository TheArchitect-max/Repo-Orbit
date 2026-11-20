# External Git benchmark audit — v0.8.0 (2026-11-20)

## Decision: PARTIAL EVIDENCE / GENERALIZATION HOLD

The original v0.8.0's synthetic speedups do not establish faster operation
across arbitrary real repositories. This audit adds a **genuine external Git
history** and a **cross-platform portable benchmark harness** without changing
or quietly reversioning the distributed v0.8.0 analysis or rendering engine.

## What was actually measured

- Tested an existing **full (not shallow) checkout** of `novnc/noVNC`, a real,
  independent open-source GitHub repository (no project source files copied
  into this evidence ZIP).
- Exact Git HEAD: `7fcf9dcfe0cc5b14e3841a4429dc091a6ffca861`.
- Environment: Linux `6.18.57`, Python `3.13.5`, Git `2.47.3`.
- Source compared: unmodified v0.7.0 `repoorbit/core.py` and
  `repoorbit/render.py` versus unmodified v0.8.0 equivalents.
- Windows: 60, 300, 1,000, and 1,400 first-parent commits of this *one*
  external codebase. Sample Git-tree verification in both engines.
- One warm-up, then seven (initial) and 21 (follow-up) trial pairs per window.
  Execution order alternated; median timings recorded separately for
  `analyze()`, `render(compression='gzip')`, and their sequential combination.
- Checked canonical structured JSON **and** decoded browser payload hash
  equality before reporting a comparison. Both parity gates passed in all
  tested windows.
- No browsing in this benchmark. No source code was executed.

### Median end-to-end results (21 measured pairs)

| First-parent commits | v0.7.0 | v0.8.0 | v0.7/v0.8 |
|---:|---:|---:|---:|
| 60 | 40.87 ms | 39.89 ms | 1.025x |
| 300 | 57.49 ms | 55.72 ms | 1.032x |
| 1,000 | 91.85 ms | 82.70 ms | 1.111x |
| 1,400 | 121.24 ms | 108.18 ms | 1.121x |

The original seven-run 300-commit sample favored v0.7 by ~9%; the 21-run
sample favored v0.8 by ~3%. In the 21-run exploratory paired bootstrap, the
60- and 300-commit intervals include 1.0 (no demonstrable direction).
For 1,000 and 1,400 commits the intervals are above 1.0 **within this test**.
These are not population-wide confidence claims.

### Sources of evidence

- `evidence/external_novnc_linux_7runs.json` — complete raw initial samples.
- `evidence/external_novnc_linux_21runs.json` — complete raw extended samples.
- `evidence/external_novnc_linux_summary.md` — repeatable summary including
  exploratory bootstrap interval and paired-trial wins.
- `scripts/benchmark_real_workloads.py` — executable cross-platform comparator.
- `scripts/summarize_real_workloads.py` — summary generator (stdlib only).

## How to test more public Git repositories

Select at least **three unrelated public Git histories** with distinct change
patterns. Proposed candidates (selection only; **not yet tested here**):

- `psf/requests` — established, relatively small Python library.
- `pallets/flask` — Python framework with multi-year change history.
- `astral-sh/uv` — larger Rust-based developer tooling repository.

Additionally retest `novnc/noVNC` on other operating systems.
Record each fetched Git HEAD and Git version; do not call different moving
HEAD revisions identical workloads. For requests, GitHub warns about an old
bad timezone record: use `git -c fetch.fsck.badTimezone=ignore clone ...` if
required, while recording that exception explicitly.

### Clone without executing source code

Linux/macOS bash example:

```sh
git clone --filter=blob:none --no-checkout --depth=1500 https://github.com/pallets/flask.git flask
# Choose and record the SHA; do not check out/run the project code:
git -C flask rev-parse HEAD
python scripts/benchmark_real_workloads.py \
  --baseline /path/to/extracted/v0.7.0/REPO_ORBIT \
  --repo flask --commits 60 300 1000 --runs 21 \
  --output evidence/flask_Linux.json
```

Windows PowerShell example:

```powershell
git clone --filter=blob:none --no-checkout --depth=1500 https://github.com/pallets/flask.git flask
git -C flask rev-parse HEAD
py scripts/benchmark_real_workloads.py --baseline C:\baseline\REPO_ORBIT --repo .\flask --commits 60 300 1000 --runs 21 --output evidence\flask_Windows.json
```

Other example repositories:

```sh
git -c fetch.fsck.badTimezone=ignore clone --filter=blob:none --no-checkout --depth=1500 https://github.com/psf/requests.git requests
git clone --filter=blob:none --no-checkout --depth=1500 https://github.com/astral-sh/uv.git uv
```

Note: blobless fetch requires Git support on the remote, but REPO ORBIT
reads commit/tree metadata, not file contents. If the remote denies partial
clone, use ordinary `git clone --no-checkout`. Requesting a 1,000-commit
window from a shallower checkout uses only available history, and the report
explicitly records the actual commit count and `is_shallow` flag.

On Windows/macOS, use native Python and Git, not a Linux container pretending
to test the host OS. On Linux, a `file://` Chromium or browser-content test
remains distinct from this CLI benchmark. For browser evaluation, also test
startup/seek/filter/export with an identical generated dataset and browser
versions, and explicitly record browser flags and machine specifications.

## Prospective decision gate for a *broadly supported speedup*

Before describing performance improvements as broadly supported, require:

1. At least three *independent* real repositories (not merely three windows
   from one repository), and a recorded pinned HEAD for each.
2. Measured runs on Linux, Windows and macOS with native Git/Python, at least
   21 sequential paired timings per scenario, plus an explicit machine profile.
3. Identical complete structured JSON and decoded browser datasets between
   versions for every evaluated scenario.
4. The median end-to-end v0.8 time no more than 105% of baseline in each
   preselected test scenario, with any regression investigated rather than
   omitted. This 5% tolerance is a *prospective engineering gate*, not a
   mathematical confidence guarantee.
5. Browser startup and interaction separately tested on a controlled subset.
6. Publish **all**, including slow and inconclusive, workloads in the report.

**Current gate:** incomplete. One external codebase on Linux only. Clone
attempts for the three other repositories failed in this execution environment
because GitHub DNS resolution was unavailable. Their results must not be
inferred from web descriptions or synthetic repositories.

## Limits that remain

- This audit compares Git analysis + offline HTML string generation; it does
  not measure opening the file in a browser, SVG export, memory high-water
  marks, or user-perceived latency.
- The different windows on noVNC are correlated; counting them as four
  independent real codebases would be scientifically invalid.
- Page-cache warmth and run order influence results; bootstrap assumptions
  are approximations, not evidence of cross-machine reliability.
- No finite experiment can prove that any program is faster on *all possible*
  valid Git repositories. The appropriate standard is broad, bounded,
  reproducible evidence plus explicit exceptions, not an absolute guarantee.
- This is an evidence-only addendum to the v0.8.0 distribution. Licensing,
  GitHub publication and untested platform gate statuses are unchanged.
