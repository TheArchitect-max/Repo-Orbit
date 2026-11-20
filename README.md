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

## R9 multiplicative Canvas optimization (candidate)

The first R9 renderer optimization removes repeated full-frame spatial index
construction and replaces string-key density aggregation with compact, reusable
typed-array grids. In a **local**, 21-pair Linux Chromium 144 measurement on
the fixed 8k-commit/80k-path/900k-event synthetic fixture, median `draw()`
duration improved **8.45–9.04x in constellation mode** and **4.74–5.96x in atlas
mode** across two runs, with pixel-identical canvas results. This is not a
universal throughput claim, nor a native cross-platform result. Three new
native R9 performance evidence ZIPs, independent licensing/security and
accessibility acceptance remain HOLD; `main` is unchanged.

Technical methodology and limitations: [R9 Multiplicative Scaling](docs/R9_MULTIPLICATIVE_SCALING.md).

## Validation status

| Gate | Evidence / status |
| --- | --- |
| Python regressions | **R7 native:** 106/106 Linux, 106/106 macOS, Windows 104 PASS + 2 POSIX skips; **R9 local candidate:** 120/120 tests PASS |
| Independent Git core/render hashes | **PASS** against pinned v0.7.0 and v0.8.0 hashes |
| External Linux CLI benchmarks | **PASS** on pinned Requests, Flask and uv; 9/9 scenarios |
| Native Windows CLI | **R7 native CLI accepted** within predeclared scope; R8 Chromium E2E PASS on accepted R8 SHA; R9 new renderer **HOLD** |
| Native macOS CLI | **R7 native CLI accepted** within predeclared scope; R8 Chromium E2E PASS on accepted R8 SHA; R9 new renderer **HOLD** |
| Linux/Windows/macOS browser acceptance | **R8: 3/3 platforms PASS** on accepted SHA `b9dff99e`; **R9: native HOLD**, changed renderer requires new evidence |
| MIT license and public release | **MIT direction selected**; active license/release **HOLD** pending acceptance |

The source-only repository intentionally excludes generated wheels, large demo media, older historical logs and the already collected raw evidence package. The full reproducible scripts, pinned production and reference engines, Python tests, documentation and validation configuration are included here. No pass is inferred from an unexecuted CircleCI job.

## CircleCI native validation

See [validation/CIRCLECI_NATIVE_VALIDATION.md](validation/CIRCLECI_NATIVE_VALIDATION.md) and [.circleci/config.yml](.circleci/config.yml).

All six CircleCI workflows default to **disabled**; disable automatic VCS
triggers. R7 native CLI matrix and R8 native browser matrix were independently
accepted on their respective immutable commits. For R9, manually trigger only
the three browser workflows on the **new, identical commit** with both Config
Source Branch and Checkout Source Branch set to `build/circleci-native-r4` and
`run_browser_linux=true`, `run_browser_windows=true`, `run_browser_macos=true`.
Set all three native CLI `run_*` parameters false. Each new R9 browser job now
performs the existing Chromium E2E and a **required, 21-pair R8-vs-R9 Canvas
benchmark**, produces one SHA-256-verified evidence ZIP, and fails closed when
speedup is below 3x, raster output differs or source/measurement integrity
fails. Audit the three ZIPs with `scripts/audit_browser_zips.py`.

Each native job checks source integrity, runs the regression suite, retrieves the three pinned complete Git histories, and performs 21 paired measurements for each requested commit window. Inspect CircleCI results and save the job artifacts before granting acceptance. **CircleCI is for validation only, never for SaaS runtime.**

## Scope and documentation

REPO ORBIT is a Git visualization utility, not a source-code security scanner, semantic dependency analyzer, or AI code-review service. It does not host a live application, run a database, manage user sessions or process payments.

Details: [Engineering](docs/ENGINEERING.md) · [Acceptance](docs/ACCEPTANCE.md) · [Roadmap](docs/ROADMAP.md) · [Security](SECURITY.md) · [Third-party notices](THIRD_PARTY_NOTICES.md).
## R8 native Chromium acceptance (historically completed)

Browser E2E adds **zero production dependencies**. Playwright 1.65.2 and its
Chromium browser are installed for CI only. Deterministic synthetic Git
fixtures are generated on each native host, then offline UI interactions,
search, exact A/B, export, XSS safeguards and the combined maximum dataset are
validated. The three `run_browser_*` CircleCI parameters default to `false`.
Each job publishes one independent SHA-256-audited browser evidence ZIP,
including a real screenshot and fixture provenance, even if tests fail.
The R8 three-platform evidence was accepted on commit `b9dff99e`. R9 changes
the renderer, so its updated ZIP audit must be repeated on the new commit.
Use `scripts/audit_browser_zips.py` on the new three platform ZIPs.

**Publication decision:** REPO ORBIT is to become a free, MIT-licensed,
standalone THE ARCHITECT engineering reference project after acceptance.
The source is already publicly visible, but no MIT license grant or release
has yet been published. Other repositories remain separate IP assets.
