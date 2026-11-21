# R9 — Factorized Filtered Redraw (post-native R9 candidate)

**Source basis:** accepted native R9 commit `3a5fe9aec30e3f5e46ab51bcd8f46b6d2251e061`, immutable renderer SHA-256 `3a31ebb30438a198dd4b3e117822ed0d77a9cc3756b03977bfe094c93554f9fc`.
**Status:** NEW CANDIDATE, local Linux/Chromium validated within a narrow redraw scope; native Linux/Windows/macOS on this changed source **HOLD**. Previously accepted R9 evidence remains valid ONLY for its original SHA and cannot be reused as acceptance of this new renderer.

## Problem and algorithmic improvement

The accepted R9 renderer iterated every file for every filtered Canvas draw, lowercasing filenames repeatedly, even when the query selected a single path. This is O(N) work per redraw, where N may be 80,000. The new candidate normalizes paths once, then computes an ordered list and a typed-array membership mask whenever a search query or folder filter changes. Repaints iterate the K selected matches (O(K)), not all N tracked paths. This includes exact SVG rendering. Hit testing consults the same mask; the original coordinate index and exact Git object/mode version logic are unchanged.

The query-change event itself remains O(N). Memory increases by a lowercased string per path, an optional byte-per-path mask and a K-entry index array. We do **not** claim constant-time search construction, a smaller peak heap or an end-to-end 10x+ application speedup.

## Evidence from the local Linux/Chromium 144 synthetic fixture

Compared to the immutable native-accepted R9 renderer with the same real Git-derived browser fixture (8,000 commits / 80,000 paths / 900,000 change events), Chromium viewport and dataset bytes, **21 batches of 32 draw callbacks per case** produced the following representative measured factor improvements. Draw times were averaged per batch to reduce coarse timer quantization; input latency is recorded separately.

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
