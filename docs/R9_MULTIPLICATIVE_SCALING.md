# R9 — Multiplicative performance improvement (candidate)

**Project:** REPO ORBIT, standalone open-source reference project.
**State:** locally measured R9 candidate; external Linux/Windows/macOS acceptance **HOLD**.
**Baseline:** independently accepted R8 Chromium viewer, SHA-256 `8747ec9eec22b26840235eb3d4329e3e5ea02fc71cb7e6fcedb6ce119dc573ae` (frozen in `baselines/v0.8.0/repoorbit/viewer.js`).
**Candidate:** new viewer.js SHA-256 `3a31ebb30438a198dd4b3e117822ed0d77a9cc3756b03977bfe094c93554f9fc`.

## Technical bottlenecks removed

1. **Repeated hover index construction:** R8 built screen-space spatial buckets for every visible file **on every Canvas draw**, including repeated 80,000-point lists and string-key lookups. R9 constructs layout-space spatial indices only when a pointer queries a layout for the first time. Zoom/pan is inverted at lookup; indices are invalidated only after viewport resize. Exact Git file presence, filtering, A/B deletions and per-file hit testing are retained.
2. **Repeated density allocations:** R8 allocated a `Map` keyed by new `"x,y"` strings and one mutable object for each dense Canvas cell on every draw. R9 uses reusable typed arrays (`Uint32Array` count per file category and `Uint8Array` change priority) in a bounded viewport grid. Only cells touched during the previous frame are cleared. Density colors and change priority retain the same semantics.
3. **Redundant work:** when neither a search query nor a folder filter is active, skip the unconditional filename lowercasing in the per-file draw loop. Inline the simple zoom/pan transform rather than allocating a new `{x,y}` object per visible file.

These optimizations do **not** increase the maximum Git history, path or event constants. Raising 8,000 commits / 80,000 paths / 900,000 events requires separate real-Git throughput, memory and correctness evidence; changing a constant alone is not a scale improvement.

## Local performance evidence (Linux Chromium)

The direct exploratory screen-draw instrumentation on one 8k/80k/900k synthetic Git fixture recorded a baseline 25.0 ms median vs a candidate 4.8 ms median (**5.2x**) and JavaScript used heap ~284 MB vs ~171 MB. This was a single unpaired exploration and is not the formal performance acceptance measurement.

The formal paired R9 protocol (`scripts/benchmark_viewer_r9.py`) uses **21 measured redraws per renderer per mode**, reverse-order alternating pairs, JIT warmup, the same Chromium and viewport, identical compressed JSON payload, fixed 8k/80k/900k synthetic Git fixture and reduced motion. It measures **Canvas `draw()` callback duration**, not startup time or CPU throughput for Git analysis. Results on one Linux x86-64 Chromium 144 host:

| Measurement | R8 baseline | R9 candidate | Speedup |
| --- | ---: | ---: | ---: |
| Constellation (first local paired run) | 21.7 ms | 2.4 ms | **9.04x** |
| Atlas (first local paired run) | 28.6 ms | 4.8 ms | **5.96x** |
| Constellation (second local paired run) | 18.6 ms | 2.2 ms | **8.45x** |
| Atlas (second local paired run) | 23.7 ms | 5.0 ms | **4.74x** |

Two repeated local runs exceeded the **predeclared native acceptance threshold of 3.0x median improvement** in both modes. They do not establish the same improvement on Windows, macOS, different GPUs or larger arbitrary repositories. Used JS heap varies across garbage collection and is a supplementary observation, not a memory ceiling or a claimed 10x gain.

## Exactness and fail-closed gates

- In one controlled Chromium comparison at 8k/80k/900k, baseline and candidate Canvas PNG hashes were **byte-identical** at constellation frame 8,000 and 4,000, atlas frame 4,000 and 8,000, a search filtering 80,000 paths, and a comparison marking 80,000 modified files. HTML behavior and displayed counters matched, with no JavaScript exceptions.
- The candidate passed the existing Python regression suite (115 checks before dedicated R9 additions) and all three existing real Chromium scripts: smoke, V7/search and combined maximum.
- `validate_performance()` independently recalculates raw-array counts and median ratios, rejects fewer than 21 paired measurements, altered baseline/candidate identities, nonfinite or nonpositive timing values, mismatched Canvas hashes, network requests, JavaScript errors, insufficient speedup or optimistic reported PASS metadata.
- The R9 browser CI runner appends a fifth mandatory stage to each of Linux, Windows and macOS (`r9_paired_viewer_performance`), with complete per-step logs and a fail-closed evidence ZIP. The three-ZIP auditor requires the full R9 report, exact accepted baseline viewer and current candidate source, and recomputes the acceptance independently.
- R7 and R8 evidence are immutable and accepted **on their original commits**; they are not a same-SHA validation of this changed renderer. The new native R9 browsers and benchmark acceptance are **HOLD** until the new three-platform evidence is collected and independently audited.

## Next steps and constraints

Re-run the three **browser-only** CircleCI jobs manually with `run_browser_linux=true`, `run_browser_windows=true`, `run_browser_macos=true`, all CLI parameters false, both branch selector fields `build/circleci-native-r4`, and automatic triggers disabled. Verify one ZIP + `.sha256` per OS on exactly the new SHA, then execute `scripts/audit_browser_zips.py` on all three original files. Keep PR #1 Draft/HOLD; no public MIT release or merge until outstanding security, licensing and independent accessibility requirements are accepted.

## R9 follow-up: independently inspectable pixel evidence (pre-native hardening)

Before the first native R9 performance acceptance, the single-final-frame
comparison is extended to **three independent visual states per mode**:
frame 4,000, frame 8,000, and frame 8,000 with a real 80,000-path search
filter. Both the accepted R8 renderer and R9 renderer are compared with
identical input data and viewport. Each state records exact Canvas PNG bytes,
SHA-256, length and selected live DOM counters. All **12 actual PNG artifacts**
are retained in each host evidence ZIP under `R9_PIXELS/`. The acceptance
recomputes reported digests from these bytes, checks baseline/candidate
pixel identity, DOM parity and rejects missing or modified images. The
predeclared >=3x median draw speed threshold and 21 measured pairs per
mode remain **unchanged**. This strengthens correctness evidence without
claiming additional acceleration. The new source commit requires an entirely
new native R9 evidence run; old R9 local numbers remain historical.

This is **not** an external accessibility or security certification; native
CircleCI evidence remains HOLD until its three independent same-SHA ZIPs
pass the cross-platform audit. Do not merge PR #1 before that acceptance.
