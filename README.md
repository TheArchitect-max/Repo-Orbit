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
| Python regressions | **R7 native:** 106/106 Linux, 106/106 macOS, Windows 104 PASS + 2 POSIX skips; **R8 local candidate:** 112/112 tests PASS |
| Independent Git core/render hashes | **PASS** against pinned v0.7.0 and v0.8.0 hashes |
| External Linux CLI benchmarks | **PASS** on pinned Requests, Flask and uv; 9/9 scenarios |
| Native Windows CLI | **R7 native CLI accepted** within predeclared scope; R8 browser E2E **HOLD** |
| Native macOS CLI | **R7 native CLI accepted** within predeclared scope; R8 browser E2E **HOLD** |
| Windows/macOS browser acceptance | **HOLD** — separate gate |
| MIT license and public release | **MIT direction selected**; active license/release **HOLD** pending acceptance |

The source-only repository intentionally excludes generated wheels, large demo media, older historical logs and the already collected raw evidence package. The full reproducible scripts, pinned production and reference engines, Python tests, documentation and validation configuration are included here. No pass is inferred from an unexecuted CircleCI job.

## CircleCI native validation

See [validation/CIRCLECI_NATIVE_VALIDATION.md](validation/CIRCLECI_NATIVE_VALIDATION.md) and [.circleci/config.yml](.circleci/config.yml).

All CircleCI workflows default to **disabled**. Keep automatic VCS triggers
removed. For the final R7 evidence run, manually trigger **all three** native
platform jobs from the same commit. Set both Config Source Branch and Checkout
Source Branch to `build/circleci-native-r4`, with `run_linux=true`,
`run_windows=true` and `run_macos=true`. The three OS-specific jobs
publish one complete downloadable evidence ZIP plus SHA-256 per platform.
Use `scripts/audit_ci_zips.py` to verify all three ZIPs against the
predeclared nine-cell CLI performance matrix. The R7 same-commit matrix has
been independently accepted. The separate R8 native Chromium E2E gate,
accessibility/security reviews and release/merge acceptance remain on HOLD.

Each native job checks source integrity, runs the regression suite, retrieves the three pinned complete Git histories, and performs 21 paired measurements for each requested commit window. Inspect CircleCI results and save the job artifacts before granting acceptance. **CircleCI is for validation only, never for SaaS runtime.**

## Scope and documentation

REPO ORBIT is a Git visualization utility, not a source-code security scanner, semantic dependency analyzer, or AI code-review service. It does not host a live application, run a database, manage user sessions or process payments.

Details: [Engineering](docs/ENGINEERING.md) · [Acceptance](docs/ACCEPTANCE.md) · [Roadmap](docs/ROADMAP.md) · [Security](SECURITY.md) · [Third-party notices](THIRD_PARTY_NOTICES.md).
## R8 native Chromium acceptance (in development)

Browser E2E adds **zero production dependencies**. Playwright 1.65.2 and its
Chromium browser are installed for CI only. Deterministic synthetic Git
fixtures are generated on each native host, then offline UI interactions,
search, exact A/B, export, XSS safeguards and the combined maximum dataset are
validated. The three `run_browser_*` CircleCI parameters default to `false`.
Each job publishes one independent SHA-256-audited browser evidence ZIP,
including a real screenshot and fixture provenance, even if tests fail.
Use `scripts/audit_browser_zips.py` on the three downloaded ZIPs.

**Publication decision:** REPO ORBIT is to become a free, MIT-licensed,
standalone THE ARCHITECT engineering reference project after acceptance.
The source is already publicly visible, but no MIT license grant or release
has yet been published. Other repositories remain separate IP assets.
