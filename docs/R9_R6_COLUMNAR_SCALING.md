# R9 R6 — Compact Event Columns and On-Demand File Histories

**Repository:** `TheArchitect-max/Repo-Orbit`, standalone proprietary-first development candidate.

**Frozen accepted R5 parent:** `108eb4edc50bad5c01ccb0913ceaa275b7c0ac55`, Git tree `2f81bca71554310a0222410d56ff0726568082f9`.

**Objective.** Improve the product across independent, measurable dimensions—memory, startup, correct navigation, private offline use, accessibility, and reproducibility. “Factorial improvement” is not a defined or mathematically justifiable runtime complexity target for this Git visualization system. No `n!` throughput, arbitrary scaling, or automatic capacity increase is claimed.

## Bottleneck and design

The R5 browser eagerly unpacked up to 900,000 compressed Git change tuples into replacement JavaScript arrays, recreated each event a second time as replay triples, then allocated one `{frame,code}` object for every historical file-change record. This retained substantial data that the active UI does not need concurrently. It was a memory amplification and garbage-collection issue, not a Git repository history correctness flaw.

R6 retains the *same* `path-index-v1` HTML/JSON serialization and the unmodified external `repoorbit-v3` structured JSON schema. Inside the browser only:

1. Keep the packed path dictionary rather than eagerly expanding every event into a new `[status,stringPath]` pair. Preserve `compact=False` plain JSON compatibility.
2. Compile each commit's event IDs, object-version IDs and status categories into `Uint32Array`, `Uint32Array` and `Uint16Array` columns. Each commit retains the exact number and chronological ordering of changes; original Git object/mode equality tokens are unmodified.
3. Store per-file chronological history in a stable compressed-sparse-row (CSR) index: event counts and prefix offsets, frame numbers and status-category identifiers. Only materialize the requested file's event list when the user inspects that file.
4. Preserve snapshot checkpoints, exact A/B equality, all Canvas drawing rules, exported PNG/SVG and application accessibility behavior. The frozen HTML template remains byte-identical.
5. Fail closed on unknown change-path IDs and event-category overflow. The 64 MiB gzip expansion and strict UTF-8 guards remain in force.

## Independent exactness checks

- Full browser input: the same original 8,000 first-parent commits, 80,000 unique paths and 900,000 synthetic real-Git change events; canonical uncompressed SHA-256 `1de6f6fbe504db5bacdb1e1be1b178404b969f1cd3ef3dacf24d7f310f25bf63`.
- Paired R5/R6 Chromium replay: exact PNG SHA-256 parity at orbit frame 1, orbit frame 8,000 with object-identity comparison, atlas frame 8,000 comparison, and filtered frame 8,000. Exact SVG bytes and DOM comparison summaries also matched.
- The R6 browser now compares the selected highest-activity path's exact event count, latest eight ordered Git frame/status pairs and path identity with a **separately decompressed canonical payload**. Both platform-side validation and offline ZIP auditor recompute and require this result. Adversarial tests reject a forged event count even when the gzip/payload hash reference is constructed to match that altered fixture.
- `tests/browser_smoke.py` also checks the pre-existing unpacked, `compact=False`, plain JSON interface in real Chromium to prevent a format-only optimization from breaking compatibility.
- R9 R5's native a11y view-switch, privacy/security controls and R8/R9 accepted pixel/DOM baselines remain mandatory.

## Measured performance — single Linux x86-64 Chromium 144 environment

Source-bound paired test: `scripts/benchmark_r9_r6_columnar.py` against frozen SHA-256 `7970f1ab67c96eddc2cf44c22840b6317c085cf72f4692b465140c4a816490b4` at `baselines/r9-r5-native-accepted/repoorbit/viewer.js`. Nine measured alternating pairs after one unmeasured warm-up pair; same HTML embedded canonical dataset, viewport, reduced motion and browser executable. Each measurement starts with a new browser context. `performance.memory.usedJSHeapSize` is read after explicit exposed GC.

| Metric | R5 median | R6 median | Change |
| --- | ---: | ---: | ---: |
| Used JavaScript heap after page initialization | 165,697,595 bytes | 84,013,925 bytes | **49.30% lower / 1.972× reduction** |
| Startup-to-visible viewer from `set_content` | 0.92863 s | 0.76922 s | **1.207× faster** |
| Allocated JavaScript heap total | 259,083,471 bytes | 158,131,745 bytes | Lower allocation footprint on the measured host |

The experiment is evidence of one synthetic fixture on one host, *not* universal performance. `performance.memory` is non-standard and not total browser RSS. Startup excludes Git analysis, Python HTML rendering, client-to-browser data transfer, production browser installation and CI queue latency. Different GC timing and OS/builds may differ. The existing R9 21-pair Canvas benchmark remains separate from the startup/heap benchmark.

## Validation and release state

- Local Python regression **157/157 PASS**; four Chromium suites PASS, including nonpacked JSON, maximum Git dataset and browser gzip limits. Syntax/preflight PASS (21 regression modules).
- R8-vs-current R9 Canvas redraw benchmark: 21 pairs, pixel parity PASS; Orbit `9.89×`, Atlas `4.81×` on one Linux host. No claim about end-to-end rendering.
- The longer filtered R9 benchmark **timed out locally** and is therefore **HOLD**, not PASS. Native Linux/Windows/macOS CLI and browser evidence must rerun on the *new exact SHA*, including full 21-pair filtered redraw acceptance; earlier R5 ZIPs cannot be reused.
- PR #1 stays OPEN/DRAFT. Main stays unchanged. Separate independent security/privacy, qualified assistive-technology accessibility, third-party licensing/IP and explicit owner **proprietary** licensing/distribution decision remain HOLD. The old proposed public MIT grant has **not** been approved.
- No public or production release, hosted service, source sharing between projects or merge is authorized by this document.
