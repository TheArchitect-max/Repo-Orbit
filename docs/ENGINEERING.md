# Engineering specification — REPO ORBIT v0.7.0

## Pipeline and invariants

1. Collect selected first-parent Git commit metadata and raw file deltas via a single `git log --raw -z --diff-merges=first-parent` command. The executable's stdout/stderr are written to temporary disk files. The history stream is parsed in 64 KiB pieces and NUL-delimited fields; individual fields are capped at 64 KiB and history raw stdout at 256 MiB. Git output size is checked *after* subprocess completion, so the disk usage of a malicious Git command is not strictly bounded.
2. Get the parent of the oldest selected commit as the exact baseline, preserving partial-window semantics. Replay each commit once, storing only visible structured events and object-version integer aliases. The object token corresponds to `(mode, Git OID)`. A deletion is token zero. A rename is represented as deletion plus addition; no source blobs are read.
3. Use native `git ls-tree -r -z` as an independent exact object+path oracle at sample frames (first, middle, last) or **every frame** under `--verify full`. These checks include paths excluded from presentation. Any mutation of HEAD during analysis causes a failure, not a silent report.
4. Serialize the unchanged external `repoorbit-v3` JSON on request. For standalone HTML, encode path strings once in a stable sorted table, then encode commit file events as `[status, path_index, object_token]`. The viewer reconstructs the same logical JSON shape. The HTML exporter gzip-compresses large embedded data with `mtime=0`, and embeds it as Base64 without network calls. Small payloads remain plain JSON; `--html-format plain` explicitly bypasses gzip.
5. The browser uses typed state arrays, exact object/mode endpoint comparisons and checkpoints of at most approximately 64 full arrays on long histories. The animation for high-density maps uses pixel-grid summaries and keeps exact file IDs available for search/inspection. Activity and growth curves are downsampled to screen-width resolution. Density dots are an overview approximation, not a substitute for exact per-file topology.

## Security and limitations

Python sends Git arguments directly without shell interpolation, prohibits Git textconv and external diff tools, and does not check out or run source code. This is not a security boundary against a hostile installed Git binary or a malicious repository on a shared server. Raw processing is bounded by 8,000 selected commits, 80,000 distinct paths, 900,000 raw events and the file-output limits. The application may still consume substantial CPU, RAM and temporary disk space before reporting `OrbitError`.

HTML script-breakout forms (`<`, `>`, `&`, U+2028/U+2029) are escaped for plain JSON data. gzip mode uses a Base64-safe alphabet. Dynamic strings become text nodes; CSP blocks external resources. Browser-native `DecompressionStream` is required for gzip-based exports and must be evaluated independently on Firefox/WebKit. `--html-format plain` is the compatibility fallback. Compressing an unredacted report does **not** constitute privacy protection. `--redact` reduces direct identifiers, but structural side channels remain. The binary/text-source metadata never becomes a source blob in this application.

## Measurements (one Linux/Chromium environment, synthetic fixtures)

- **8,000 Git commits / 30,000 tracked paths / 69,995 real change events:** 3.344 s Python analysis with three independently verified Git trees. 162,688 KiB Python peak RSS on this single process. Both old and new viewer HTML were generated using the same canonical data; HTML bytes: 4,071,741 (v0.4) vs 894,241 (v0.5), ~4.55× less.
- **Chromium 8k / 30k:** initial viewer completion 0.973 s (v0.4) vs 0.296 s (v0.5), ~3.29× faster. Median measured per-Canvas-draw callback duration 16.2 ms vs 10.2 ms, ~1.59× faster; mixed actual values are included in `evidence/browser_v5_scale.json`. Single-run browser, no confidence intervals.
- **Exact parity on smaller shared fixture:** 400 commits, 3 interleaved runs; full serialized external data digest matches v0.4. Engine analysis medians 262.532 ms (v0.4) and 281.741 ms (v0.5), ~0.93×; this particular smaller workload was about 7% slower for v0.5. No analysis-speed breakthrough is claimed.

## Combined-limit acceptance supplement (2026-11-20)

- **8,000 first-parent commits; 80,000 distinct tracked paths; 900,000 actual diff events, all together:** `scripts/stress_combined_limits.py` generated a single real Git fixture via `git fast-import`. Engine `analyze()` PASS: 5.614 s; render gzip standalone HTML: 4.395 s, 2,984,317 bytes (within default 32 MiB). Python peak RSS: 393,064 KiB on Linux 6.18 / Python 3.13.5 / Git 2.47.3. Exact mode+object+path validation checked the first, midpoint and last tree; `--verify full` was **not** performed. The fixture uses an index-only checkout and the dirty-worktree flag reflects that.
- **Chromium 144 browser:** loaded the exact 2.98 MB HTML in 1.571 s; displayed 8,000 commits / 900,000 events / 80,000 final files. Navigation 1 → 4,000 → 8,000, search, hotspot, A/B all PASS; A/B reported 80,000 exact modified endpoints. No external HTTP requests, JS exceptions or console errors. V8 heap used at the end of the run: 221,490,122 bytes (not total browser RSS).
- **Scope:** a synthetic real-Git case at the three configured logical ceilings, NOT a mathematical coverage proof or a performance/functional guarantee on arbitrary repositories and browsers. Filesystem and Git objects were generated locally and the fixture is reproducible using the included script. See `evidence/combined_limits.json` and `evidence/browser_combined_limits.json`.

## Governance and pending evidence

A01 capability→gate mapping: `docs/ACCEPTANCE.md`; A02 independent Git-tree oracle; A03 metadata/security/parser adversarial tests plus boundary/property cases; A04 no Python runtime deps other than standard library; external Git and optional dev tooling notices in `THIRD_PARTY_NOTICES.md`; A05/A15 SHA-256 manifest/ZIP identity and wheel hash; A06 isolated clean-install smoke; A07 bounded size limits and measured costs; A08 compatibility of `repoorbit-v3` exported JSON and distinct HTML data encoding; A10 privacy local-first, with redaction side channels recorded; A11 escaped untrusted input and CSP, no model/LLM; A13 real-browser interaction checks without qualified external users; A14 no public release before owner approval and required validations.

**Unresolved:** Windows/macOS/Python matrix, Firefox/WebKit, qualified accessibility tests, independent threat assessment/SBOM, live customer usability, broad real-project benchmark distribution, actual virality evidence, verified GitHub repository source SHA. No false production-ready status is assigned.

## Vector export architecture (v0.6)

The SVG overview is intentionally a **lossy presentation**: cells aggregate colocalized nodes; each `data-count` is a checkable positive count and summed counts must equal the visible node count for the selected view. Export mode chooses density only when all folders are included, query is empty, zoom ≤1.8 and total file cardinality >12,000. Under zoom or filters, it falls back to exact point output. The separate SVG exact action always emits per-file XML elements with safely encoded filenames. The SVG serializer uses controlled fixed markup and an XML-text-escape function for untrusted metadata; it does not fetch resources or parse source code. DOM population is O(number of density cells) for the overview, rather than O(number of tracked paths). The aggregation pass remains O(number of files), so this is **not O(1) total export time**. No generated export implies complete Git correctness beyond the existing Git-tree replay gates.


## v0.7.0 implementation notes

- Bare repositories are detected with `git rev-parse --is-bare-repository`; the Git directory is used in place of a missing worktree root. `dirty=null` correctly describes the unavailability of working-tree status.
- `_git_output` consumes stdout through a bounded pipe into a temporary spool, checking each chunk before writing. A timer terminates a blocked child. This does not impose an OS-level RAM or CPU limit and stderr remains spooled without a strict cap.
- Keyboard search uses existing in-memory file and history indices; it renders at most 24 buttons, reports the match count, and assigns untrusted filenames via `textContent`, not `innerHTML`.
- XML 1.0-invalid control characters are substituted with the replacement character solely in SVG labels. The original Git paths are not silently changed in structured JSON or analysis results.
- `repoorbit-v3` schema unchanged. Evidence: `tests/test_v7.py`, `tests/browser_v7.py`, `evidence/v07_paired_engine_comparison.json`, `evidence/v07_dataset_rebuild.json`.
