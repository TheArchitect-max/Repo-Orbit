# Changelog

## v0.8.0 — benchmarked HTML export optimization

- Faster deterministic offline gzip HTML packaging, balancing compression CPU and small size trade-off.
- No-exclusion fast path reduces repeated file/glob handling, without changing JSON or object/mode replay.
- Paired 7-run benchmark on three independent, real synthetic Git-history shapes with full structured JSON and embedded viewer-payload parity.
- Full regression and maximum-limit Chromium acceptance rerun. Zero GitHub, SaaS or license changes.
- No universal performance guarantee. See docs/ACCEPTANCE.md.


## v0.7.0 — 2026-11-20 — LOCAL DEVELOPMENT CANDIDATE

- Added support for bare Git mirrors, preserving exact object/mode replay and comparing its output against a working checkout; linked worktrees and detached HEAD covered.
- Reworked Git stdout acquisition to enforce byte limits while reading: oversized stdout kills the child early; wall-clock timers stop blocked commands. Existing memory/file-size controls remain, and this does not sandbox Git itself or globally bound stderr.
- Implemented keyboard-selectable, capped (24 result) filename-search results with assistive-technology-readable counts and navigation to a missing file's last historical change.
- Hardened SVG export to sanitize XML 1.0-invalid Git filename characters while keeping accurate Git replay data.
- 70/70 Python regressions PASS and six Chromium acceptance suites PASS including prior combined maximum viewer; no external browser requests or uncaught JavaScript errors in tested cases.
- Paired v0.6/v0.7 engine benchmark preserved canonical JSON identity; 48 commits / 4,800 files measured 78.783 vs 63.619 ms median (1.24×) in one Linux environment, not a general guarantee.
- Cross-platform/assistive-technology/security review and owner-approved open-source release remain on HOLD. No GitHub modifications.


## v0.6.0 — 2026-11-20 — LOCAL DEVELOPMENT CANDIDATE

- Redesigned vector exporting: density-aggregated small SVG overviews, plus an explicitly separate exact per-file SVG export with XML-escaped titles. No data loss in the interactive HTML or the exact export.
- Replaced expensive per-file live SVG DOM creation and XMLSerializer traversal with streaming string parts in a Blob.
- Five-run paired Chromium benchmark on unchanged 8,000-commit/80,000-file/900,000-event fixture: 43.94× faster overview export and 377.44× smaller SVG; exact export 4.46× faster, at similar byte size. Overview != exact output; not an overall engine speed claim.
- 62/62 Python tests and additional Chromium export/replay/security gates; old browser regression scripts adapted where file naming intentionally changed.
- Wheel and local candidate prepared; no GitHub publication and no final MIT license grant.

## v0.5.0 — acceptance evidence revision, 2026-11-20 (no engine version change)

- Proven simultaneous processing of 8,000 real Git commits, 80,000 paths and 900,000 raw change events; three exact independent Git-tree/object checkpoints, 57/57 regression tests.
- Added reproducible synthetic fixture generator, Chromium end-to-end acceptance and measurement files. Verified timeline, A/B, search and hotspots at these limits.
- This revision changes tests/docs/evidence only, not runtime source code or wheel. Linux/Chromium acceptance remains distinct from public open-source license approval and cross-platform readiness.


## 0.5.0 — 2026-11-19 — LOCAL DEVELOPMENT CANDIDATE

- Increased configurable commit capacity 800→8,000; unique paths 12,000→80,000; raw events 90,000→900,000. These are limits, not claims that every maximum combination has been tested.
- Refactored full-history Git stdout into a bounded disk-spooled NUL-field stream; process commits incrementally instead of materializing all raw bytes and all delta lists simultaneously.
- Added an exact path dictionary for browser HTML output; kept external `repoorbit-v3` JSON stable.
- Embedded reproducible gzip+Base64 data for large offline HTML reports with browser-native `DecompressionStream`, with `--html-format plain` as a compatibility fallback.
- Added adaptive density overview, display-pixel timeline aggregation, capped checkpoint snapshots and up to 256× replay speed for large timelines.
- Exercised a real 8,000-commit / 30,000-file / 69,995-event synthetic Git repository: 3.344 s analysis (3 sampled tree oracles), 4.55× smaller HTML than v0.4, 3.29× faster local Chromium startup, 1.59× faster median Canvas draw for the measured viewport.
- Added streaming parser boundary/property tests, compression roundtrip and script safety tests, large real-browser A/B/hotspot checks and v0.4 identical-JSON parity.
- No network runtime, no third-party Python runtime dependencies, no GitHub publication. Release remains HOLD pending license approval and additional platform evidence.

## 0.4.0 — 2026-11-19 — LOCAL DEVELOPMENT CANDIDATE

- Replaced N `git diff`/`diff-tree` processes with one bounded raw `git log` batch; preserves first-parent and root/merge semantics, object IDs, file modes and UTF-8 filename boundaries.
- Retained independent `git ls-tree` object/path integrity gates, removing only redundant duplicate name-only subprocesses.
- Added differential tests against the previous parser for merges, renames, empty commits, partial windows, SHA-256 Git and adversarial file paths.
- Improved browser playback with constant-time tracked-file counts and an optional growth-trend overlay above the commit activity histogram.
- Measured median analysis speedups of 5.8× (160 commits), 9.5× (400 commits) and 13.2× (800 commits) on controlled Linux synthetic fixtures; no universal speed guarantee.
- All 45 Python regressions and three Chromium acceptance scenarios passed; rebuilt screenshot, animated preview and clean-install wheel.
- Compatible `repoorbit-v3` JSON data format; no public-license grant or GitHub publication.

## 0.3.0 — 2026-11-19 — LOCAL DEVELOPMENT CANDIDATE

- Introduced exact Git tree object identity and file-mode replay with opaque, deterministic integer identity tokens; zero is absent.
- A/B now compares exact endpoint Git object identities; transient edits that are later exactly reverted are no longer misrepresented as net modifications.
- Added independent per-commit `git ls-tree` object/mode oracle in addition to path checks; guarded against forged identities.
- Added `--exclude GLOB` presentation filtering while retaining checks on complete unfiltered Git trees.
- Added `--max-html-mb` output size guard; spool Git stdout/stderr instead of capturing unbounded output directly to Python RAM.
- Added ranked interactive hotspot explorer and fixed event-ring highlighting keyed to file ID.
- Migrated structured schema from `repoorbit-v2` to `repoorbit-v3` (breaking for JSON consumers); HTML exports remain fully standalone.
- Expanded tests from 23 to 37, added real Chromium A/B reversion/inspector/hotspot acceptance and explicit resource-bound regression gates.
- Rebuilt browser screenshot/GIF, wheel, evidence logs, scale benchmark, package manifest and reproducible ZIP.

## 0.2.0 — prior local candidate

- Added privacy redaction, sampled/full path tree replay validation, A/B touch-based comparison, file inspection, PNG/SVG exports, browser acceptance and wheel packaging.

## 0.1.0 — initial local candidate

- First-parent Git commit visualization, deterministic standalone browser HTML and sample demo.
