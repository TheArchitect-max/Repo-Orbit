# REPO ORBIT

**Every commit. A new constellation.**

REPO ORBIT converts local Git history into a fully offline, interactive HTML atlas. Explore a repository across first-parent commits, inspect file activity, compare two historical snapshots, navigate hotspots, and export PNG or SVG.

> **Development candidate — v0.8.0.** The source is available on the active CircleCI validation branch. No public software release has been accepted. A public GitHub repository is not automatically an open-source license; the proposed MIT license remains subject to owner approval.

## Use from source

Requires **Python 3.10+** and **Git**. There are no mandatory third-party Python runtime dependencies.

```bash
python -m repoorbit /path/to/git/repository -o orbit.html
python -m repoorbit . --commits 1000 --verify sample -o orbit.html
python -m repoorbit . --redact -o orbit-redacted.html
python -m unittest discover -s tests -p 'test_*.py'
```

The generated HTML runs locally without a REPO ORBIT backend. The `--redact` option reduces identifier exposure but is **not** a guarantee of anonymity: repository structure and activity patterns can remain sensitive.

## Key capabilities

- Object-aware replay with independently checked Git trees and an exact A/B snapshot comparison.
- Animated constellation and hotspot navigation, plus keyboard-accessible file search.
- PNG, exact SVG and aggregated overview SVG exports.
- Local processing, bounded Git output, and optional compressed self-contained HTML.
- Tested combined workload of **8,000 commits**, **80,000 unique paths**, and **900,000 change events** on a synthetic Linux/Chromium fixture. This is not a universal performance guarantee.

## Validation status

| Gate | Evidence / status |
| --- | --- |
| Python regressions | **95/95 PASS**, local Linux, on the source-only GitHub import candidate |
| Independent Git core/render hashes | **PASS** against pinned v0.7.0 and v0.8.0 hashes |
| External Linux CLI benchmarks | **PASS** on pinned Requests, Flask and uv; 9/9 scenarios |
| Native Windows CLI | **HOLD** — CircleCI evidence not yet collected |
| Native macOS CLI | **HOLD** — CircleCI evidence not yet collected |
| Windows/macOS browser acceptance | **HOLD** — separate gate |
| MIT license and public release | **HOLD** — owner approval and remaining release checks |

The source-only repository intentionally excludes generated wheels, large demo media, older historical logs and the already collected raw evidence package. The full reproducible scripts, pinned production and reference engines, Python tests, documentation and validation configuration are included here. No pass is inferred from an unexecuted CircleCI job.

## CircleCI native validation

See [validation/CIRCLECI_NATIVE_VALIDATION.md](validation/CIRCLECI_NATIVE_VALIDATION.md) and [.circleci/config.yml](.circleci/config.yml).

All CircleCI workflows default to **disabled**. In CircleCI, keep automatic VCS triggers removed. Run **one manually triggered native OS job at a time** with both Config Source Branch and Checkout Source Branch set to `build/circleci-native-r4`:

- Windows: `run_windows=true`, leave the other parameters `false`.
- macOS: `run_macos=true`, leave the other parameters `false`.
- Linux: `run_linux=true` only if additional Linux evidence is required; R3 Linux evidence was already accepted.

Each native job checks source integrity, runs the regression suite, retrieves the three pinned complete Git histories, and performs 21 paired measurements for each requested commit window. Inspect CircleCI results and save the job artifacts before granting acceptance. **CircleCI is for validation only, never for SaaS runtime.**

## Scope and documentation

REPO ORBIT is a Git visualization utility, not a source-code security scanner, semantic dependency analyzer, or AI code-review service. It does not host a live application, run a database, manage user sessions or process payments.

Details: [Engineering](docs/ENGINEERING.md) · [Acceptance](docs/ACCEPTANCE.md) · [Roadmap](docs/ROADMAP.md) · [Security](SECURITY.md) · [Third-party notices](THIRD_PARTY_NOTICES.md).