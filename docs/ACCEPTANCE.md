# R9 native Chromium accepted on prior source; security follow-up pending (2026-11-21)

**Immutable R9 accepted commit:** `689bdc64a42678464860c65eb44682880aeaf78a`, Git tree `4beaa27685f357155b0e54661bfcb76d056193f1`. All three Linux/Windows/macOS Chromium E2E + filter benchmarks passed the exact-SHA, original-ZIP independent matrix audit within the synthetic fixture and performance scopes declared in the PR #1 evidence comment. This is not general-browser, security, accessibility or release approval.

**Current candidate:** bounded Git stderr hardening. The core engine source changed and its SHA-256 pin was updated; native R7 CLI and R9 browser acceptance **must be rerun** at the new commit (the accepted renderer JS remains unchanged). Local Python regression and 8k/80k/900k maximum Git fixture tests do not substitute for the three operating systems. Separate security/privacy, assistive-technology accessibility, licensing/IP and explicit owner MIT authorization gates remain **HOLD**. PR #1 must remain draft and `main` unchanged.

---

# Current R7/R8 acceptance status (2026-11-20)

R7 native CLI: **PASS_WITHIN_PREDECLARED_SCOPE**, independently audited
on one CircleCI commit across Linux, Windows and macOS, with complete evidence
ZIPs. Windows: 104 PASS and 2 POSIX-specific SKIP; other OSes: 106 PASS.
25 of 27 median benchmark scenarios are faster; two Windows Requests windows
are ~0.10% and ~0.01% slower, both within the predeclared 5% threshold.
This is not a universal performance claim.

R8 native Chromium E2E: **HOLD** until independent same-SHA CircleCI evidence
from all three platforms passes `scripts/audit_browser_zips.py`. The local
Chromium smoke, V7 search/escaping and 8,000/80,000/900,000 maximum-viewer
checks are locally exercised, but Linux-only local checks cannot satisfy
the native OS matrix. Browser-specific Playwright/Chromium is test-only.

Open-source direction: MIT engineering showcase selected; active license,
release, accessibility/security and publication checks not yet accepted.
PR #1 MUST remain draft and no merge is allowed until the required gates PASS.

---

# REPO ORBIT v0.8.0 — local candidate acceptance

**Decision:** LOCAL PASS on the exact enumerated controls. PUBLIC RELEASE HOLD (MIT approval, Windows/macOS and independent security/usability reviews not performed).

| Current v0.8 control | Evidence / source | Result |
|---|---|---|
| Full Python regression suite including deterministic gzip, payload equality and no-exclusion code path | `tests/test_*.py`, `evidence/v08_unit_tests.log` | **75/75 PASS** |
| Same true Git-tree replay results compared with unmodified v0.7 across 60-, 180-, and 1,200-commit datasets | `scripts/benchmark_v8_paired.py`, `evidence/v08_paired_performance.json` | **PASS**, full canonical JSON and decompressed browser payload equal |
| Paired analyze + render timings, 7 alternating runs per fixture | `evidence/v08_paired_performance.json` | Short 1.10×; wide 1.14×; deep 1.27× faster total medians |
| HTML gzip size trade-off | Same evidence | **0.27–0.54% larger**, no identical-byte HTML expectation across versions |
| No analysis-only regression across all fixtures | Same evidence | **NOT PASS** — deep fixture analysis was ~6% slower |
| Chromium viewer behavior incl. 8,000 commits / 80,000 paths / 900,000 events | `evidence/v08_browser_regression.log` | **6/6 suites PASS** |
| JavaScript syntax | `evidence/v08_js_syntax.log` | PASS |
| Wheel build and clean installation | `evidence/v08_clean_install.json` | PASS |
| Maximum simultaneous real Git-object fixture: 8,000 commits, 80,000 paths, 900,000 events, 3 tree oracles | `evidence/v08_maximum_engine_acceptance.json` | **PASS** on one Linux run; not a paired maximum-speed claim |
| Complete artifact manifest / ZIP checksums | `evidence/acceptance_manifest.json`, ZIP sidecar | PASS after build |
| Windows, macOS, Firefox, WebKit, NVDA/VoiceOver and independent security review | Not performed | **HOLD** |
| MIT grant / GitHub publication | Owner decision required / no upload | **HOLD** |

**Scope limitation:** These are synthetic local Git histories on Linux/Python and a Chromium browser. The measured operation is `analyze()` + `render()`, and browser startup, working tree checkout, SVG export and subsequent interactive use are excluded from its timing. A faster total median on three fixtures is evidence for those fixtures, not a universal acceleration. The browser's maximum fixture was opened and operated again, but the 8,000 commits' real Git trees were not all independently verified anew in this build. The three-checkpoint `--verify sample` policy remains unchanged. No new maximum-limit Git-engine acceptance claim is made from the viewer alone.

## Historical v0.7.0 acceptance


**Decision:** Local Python/Chromium candidate PASS on enumerated controls only; public release HOLD. v0.6 evidence below is historical and does not substitute for current v0.7 gates.

| v0.7 acceptance control | Evidence | Result |
| --- | --- | --- |
| Bare mirror exact replay vs normal checkout, linked worktree and detached HEAD | `tests/test_v7.py`, `evidence/v07_unit_tests.log` | PASS |
| SHA-256 Git object format and metadata control characters | `tests/test_v7.py` | PASS |
| Early termination of oversized Git stdout and blocked child timeout | `tests/test_v7.py` | PASS; does not bound Git CPU/memory or stderr spool |
| Keyboard search: Enter, missing-path navigation, zero matches, bounded 24 results and mobile viewport | `tests/browser_v7.py`, `evidence/v07_browser.json` | PASS in Chromium 144 |
| SVG XML 1.0-invalid control characters, escaping of markup | `tests/browser_v7.py` | PASS with XML parser; replacement character used in SVG label |
| Existing playback, exact A/B, hotspots, SVG aggregation, PNG/SVG, mobile and combined maximum fixture | `evidence/v07_browser_regression.log` | PASS across legacy browser scripts |
| Current Python regression suite | `evidence/v07_unit_tests.log` | 70/70 PASS |
| Canonical JSON parity against v0.6 on same 48-commit / 4,800-file Git history | `evidence/v07_paired_engine_comparison.json` | PASS byte-identical canonical JSON |
| Paired engine speed sample | same five-run timing evidence | 1.238× in one Linux sample; not an overall guarantee |
| Repacked prior 8,000-commit / 80,000-path / 900,000-event synthetic dataset | `evidence/v07_dataset_rebuild.json` | canonical data unchanged; Git source fixture not regenerated in this release |
| Standalone wheel installation and release ZIP integrity | `evidence/v07_clean_install.json`, `evidence/acceptance_manifest.json`, ZIP SHA-256 sidecar | PASS locally after final ZIP verification |
| Windows/macOS/Firefox/WebKit, independent security audit, WCAG/assistive-tech review | Not performed | HOLD |
| MIT license and GitHub release | Owner has not granted explicit approval | HOLD |

## Historical v0.6.0 acceptance


**Scope:** Local Linux/Python and Chromium validation of the exact v0.6.0 source tree. Do not conflate historical v0.4 evidence with current candidate PASS. Owner-approved public release is separately HOLD.

## v0.6.0 additional acceptance

| Control | Evidence | Disposition |
| --- | --- | --- |
| Legacy per-file SVG elements replaced by bounded density cells at maximum fixture | `evidence/svg_comparison_v06.json`; `scripts/benchmark_svg_v6.py` | PASS in tested browser, 249 cells for 80,000 files |
| **Factorial export improvement**, fair paired five-run sample | `evidence/svg_comparison_v06.json` | PASS: 43.94× faster overview export, 377.44× smaller, without claiming per-file equivalence |
| Exact per-file SVG kept available, filenames XML-escaped | `tests/browser_v6.py`, XML parsing of 80,000 path nodes | PASS: 80,000 exact nodes, 4.46× faster than legacy export on test fixture |
| Adversarial filename and repository title; script injection | `tests/test_v6.py`, `tests/browser_v6.py` | PASS in tested fixture; not an independent audit |
| At-scale offline viewer, replay/search/A-B/zoom/fallback | `tests/browser_v6.py`, `tests/browser_combined_limits.py` | PASS in Chromium |
| Complete Python regression suite | `evidence/v06_unit_tests.log` | 62/62 PASS |
| Previous v0.5.0 combined scaling limits | `evidence/combined_limits.json`, original verifier, v0.6.0 Chromium replay | carried forward; not repeated Git object generation in this release |

The new candidate changes the **browser vector-export implementation only**; Python Git replay and JSON schemas remain unchanged. Prior maximum-limit Git evidence is version-specific historical provenance, not proof of a new v0.6 engine benchmark. The large v0.6 browser test uses the same previously verified synthetic dataset, embedded into a newly assembled v0.6 offline viewer. No network is required or used. Public release remains HOLD pending license approval and independent platform/security checks.

## Historical and unchanged controls (v0.5.0 baseline)

The following entries describe checks carried forward from earlier candidate evidence or rerun in v0.6.0. Their filenames contain historical version labels where appropriate.

| Control | Evidence | Current disposition |
| --- | --- | --- |
| Git tree replay and exact object/mode fidelity | `tests/test_core.py`, `tests/test_v3.py`, `tests/test_v4.py`, `evidence/unit_tests.log` | PASS on test fixtures |
| Streaming NUL boundaries and bounded field handling | `tests/test_v5.py` and complete regressions | PASS |
| Complete legacy v0.4 JSON equivalence | `evidence/differential_parity_v04.json` — SHA-256 match at 400 commits | PASS on that fixture |
| Script-breakout resistance and redaction | `tests/test_advanced.py`, `tests/test_v5.py` | PASS for specified adversarial inputs; **anonymity not proven** |
| Compact data dictionary and deterministic gzip/roundtrip | `tests/test_v5.py`, `evidence/unit_tests.log` | PASS |
| Native browser A/B/history, hotspots, export, mobile, timeline | `evidence/browser_current.log`, Chromium scripts | PASS in Chromium only |
| 8,000 real Git commits / 30,000 files / 69,995 changes | `evidence/scale_v5.json` | PASS (`--verify sample`, three independent real trees) |
| Independently verified 80,000-file root commit | `evidence/stress_80k.json` | PASS with full tree oracle (one commit) |
| **Combined simultaneous maximums: 8,000 commits / 80,000 unique paths / 900,000 real events** | `evidence/combined_limits.json`, `scripts/stress_combined_limits.py`, `evidence/combined_run.log` | **PASS**, 3 separate sampled real-tree/object checks; **not** 8,000/8,000 independently verified trees |
| **Chromium at all simultaneous maximums** | `evidence/browser_combined_limits.json`, `tests/browser_combined_limits.py` | **PASS**, navigate 1/4,000/8,000, inspect, search, hotspot, exact A/B (80,000 changed), no requests/uncaught exceptions |
| Browser startup, Canvas timing, 30k-file A/B & hotspot | `evidence/browser_v5_scale.json`, same data in v0.4 and v0.5 viewer | PASS in one controlled environment; no general SLA |
| Standalone HTML offline/no requests and gzip decompression | `evidence/browser_v5_scale.json`, `tests/browser_v5_scale.py` | PASS in Chromium |
| JavaScript syntax | `evidence/v06_js_syntax.log` | PASS via Node 22 |
| v0.6.0 wheel from source and isolated install | `evidence/v06_wheel_build.log`, `evidence/v06_clean_install.json` | PASS on Linux/Python 3.13 |
| ZIP content SHA-256 and immutable manifest | `evidence/v06_release_manifest.json` and ZIP sidecar checksum | PASS — verified post-package using ZIP-extracted SHA-256 hashes |
| Windows, macOS, Firefox and WebKit, accessibility | No acceptance run | HOLD |
| Independent security review / full SBOM and vulnerability scan | No independent audit | HOLD |
| External developer user-value, GitHub adoption/virality | Not conducted | HOLD |
| Public open-source MIT approval and live GitHub release | No approval or publication | HOLD |

**Measurement discipline:** HTML bytes are from exact v0.4/v0.5 renderers using identical real Git fixture data. Chromium startup and draw times are single-system controlled samples, not statistical distributions or universality claims. The full simultaneous event/commit/path limit combination **has been tested and passed** in a single synthetic real-Git fixture under Linux/Python 3.13 and Chromium. Engine time 5.614 s, rendering 4.395 s, Python maximum RSS 393,064 KiB; 2,984,317-byte standalone HTML loaded in Chromium in 1.571 s; V8 used 221,490,122 heap bytes at measurement. Only 3 of 8,000 snapshots were independently checked. No arbitrary-input proof, multi-environment performance guarantee or full-tree verification is claimed. The v0.5 data export continues as `repoorbit-v3`; only the standalone HTML uses packed/embedded encoding.

**Decision:** LOCAL CANDIDATE PASS for verified gates. PUBLIC RELEASE HOLD pending owner license grant and remaining risk-based acceptance controls. No merged PR, GitHub `main` SHA or public tag exists for this candidate.
