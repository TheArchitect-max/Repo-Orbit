# R9 — Factorized Filtered Redraw (post-native R9 candidate)

**Source basis:** accepted native R9 commit `3a5fe9aec30e3f5e46ab51bcd8f46b6d2251e061`, immutable renderer SHA-256 `3a31ebb30438a198dd4b3e117822ed0d77a9cc3756b03977bfe094c93554f9fc`.
**Status:** NEW CANDIDATE, local Linux/Chromium validated within a narrow redraw scope; native Linux/Windows/macOS on this changed source **HOLD**. Previously accepted R9 evidence remains valid ONLY for its original SHA and cannot be reused as acceptance of this new renderer.

## Problem and algorithmic improvement

The accepted R9 renderer iterated every file for every filtered Canvas draw, lowercasing filenames repeatedly, even when the query selected a single path. This is O(N) work per redraw, where N may be 80,000. The new candidate normalizes paths once, then computes an ordered list and a typed-array membership mask whenever a search query or folder filter changes. Repaints iterate the K selected matches (O(K)), not all N tracked paths. This includes exact SVG rendering. Hit testing consults the same mask; the original coordinate index and exact Git object/mode version logic are unchanged.

The query-change event itself remains O(N). Memory increases by a lowercased string per path, an optional byte-per-path mask and a K-entry index array. We do **not** claim constant-time search construction, a smaller peak heap or an end-to-end 10x+ application speedup.

## Evidence from the local Linux/Chromium 144 synthetic fixture

Compared to the immutable native-accepted R9 renderer with the same real Git-derived browser fixture (8,000 commits / 80,000 paths / 900,000 change events), Chromium viewport and dataset bytes, **21 batches of 32 draw callbacks per case in the initial Linux measurements** produced the following representative measured factor improvements. Draw times were averaged per batch to reduce coarse timer quantization; input latency is recorded separately.

| Filter case | Constellation R9 -> new factor | Atlas R9 -> new factor |
| --- | ---: | ---: |
| Exact file | ~195x | ~244x |
| Selective 100 paths | ~103x | ~90x |
| Cluster 2,500 paths | ~9.5x | ~9.5x |

The six measured filtered states reproduced exact old/new Canvas pixel hashes and selected DOM texts. Additional clearing, zero-result, folder-only and combined-search comparisons passed in the final local report. Existing Python regressions: **122/122 PASS**, Chromium browser used only locally.

These ratios do **not** mean 195x/244x faster startup, analysis, native performance across operating systems, or 195x speedup on unfiltered/full-density rendering. Near-zero per-callback timings are resolution-sensitive and require independent native repetition; no universal guarantee is claimed.

## Gates and custody

The accepted R9 commit and its three original ZIPs remain immutable. This new candidate has a separate source SHA, so all native browser/R9 performance controls and an explicit filtered-redraw performance protocol must be rerun on the candidate's exact Git commit. Capture original PNG bytes, each host's timing arrays and source snapshots; reject any mismatch rather than trusting reported PASS. Preserve fallback for no filter and zero matches, keyboard search, folder filter, A/B snapshot comparison and SVG export. Do not change the 8k/80k/900k limits without distinct scientific evidence.

**Do not merge PR #1 or publish an active MIT license/release.** Unfinished security, accessibility, third-party licensing and owner authorization gates remain separate release HOLDs. No other repository or product is integrated.

## Native R9 filter-factorization acceptance (new hardening candidate)

The filter optimization is now a **mandatory sixth stage** for each existing opt-in CircleCI Chromium job:
\`r9_filter_factor_performance\`. It runs \`scripts/benchmark_r9_filter_candidates.py\` against the immutable native-accepted R9 baseline and the currently checked-out candidate at the exact CircleCI commit. Only one development branch is active; no automatic trigger is enabled.

On each native host, the benchmark requires **21 timed batches × 256 real Canvas redraws** in both Constellation/orbit and Atlas views for each of three filters (exact file, selective ~100-file query, ~2,500-file cluster). All six host-local median ratios must be **at least 3.0×** vs accepted R9; the original PNGs (12 per host) and selected DOM states must be identical. Separate behavior checks cover clearing the search, zero matches, folder-only filter, combined folder and search, plus keyboard Enter semantics. Input-handler latency is recorded separately but is **not** a claimed end-to-end gain.

The revised batch length is a test-only measurement hardening: the macOS ARM Chromium 159 log showed six speed ratios above 3× and exact primary Canvas parity but the filter gate still returned HOLD. The exact rejection reason was not present in the supplied step logs. At ~0.003 ms per draw, a 32-draw batch approaches one coarse browser timer tick; the new fixed 256-draw batches reduce zero-duration quantization without introducing fictitious durations. Every raw positive finite duration, 21 batches, ≥3× speedup, PNG equality, functional parity, accepted-source hash, and independent ZIP audit remain mandatory. A benchmark failure now prints explicit independent-validator and behavioral diagnostics. This mitigation is not yet a native PASS and does not prove the original failure cause.

Every R9 native ZIP must include \`R9_FILTER_PAIRED_DRAW.json\`, the 12 \`FILTER_PIXELS/\` PNGs, six-stage logs, the accepted R9 baseline source and the benchmark source snapshot. Both the on-host evidence finalizer and the three-ZIP auditor independently recompute raw timing medians, compare source identities and verify archived PNG bytes; absent/mismatched/fabricated evidence fails closed.

Local integrated candidate validation on Linux/Chromium 144: **136/136 Python regression tests PASS**, new browser benchmark exit 0 with six-case parity and 12 actual PNG files, at least 9× median redraw speedup in each measured case. This is **not native CI evidence**. A previous R9 three-host PASS on \`3a5fe9a...\` does not transfer to this changed commit or any future new head SHA.

**Acceptance state:** local PASS; **Linux/Windows/macOS native browser/performance matrix HOLD** pending three original same-SHA ZIPs and their independent audit. PR #1 remains DRAFT; release gates for security, independent accessibility, third-party licenses and owner publication decision remain HOLD. No merge or release while those required controls are incomplete.

## Immutable three-OS native acceptance and subsequent security candidate (2026-11-21)

The 21 × 256-draw R9 filter-factorization candidate was **independently accepted** on exactly `689bdc64a42678464860c65eb44682880aeaf78a` using original Linux, Windows and macOS CircleCI ZIPs and their full offline matrix audit. The 18 cross-platform filter scenarios met the ≥3× median threshold, with exact PNG and DOM parity. This historical browser acceptance cannot be relabeled or transferred to any later commit.

The subsequent Git stderr hardening changes `repoorbit/core.py` without changing either the native-accepted baseline renderer or the candidate `repoorbit/viewer.js`. Therefore **current HEAD remains HOLD** for cross-platform native CLI, browser, independent security and accessibility, third-party licensing and explicit owner release authorization. Rerun all required native gates at the new source SHA, preserve the historic ZIPs unchanged and report independent audit results rather than treating this documentation entry as a PASS.
