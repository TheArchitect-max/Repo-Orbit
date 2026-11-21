# Independent REPO ORBIT development roadmap

**Implemented through v0.7.0 local candidate:** exact first-parent Git object/mode replay; sampled/full independent Git-tree oracle; privacy redaction and presentation exclusions; hotspot inspection; object-correct A/B; offline PNG/SVG; portable wheel; 8,000-commit streaming reader, 80,000-file separate full-oracle stress, packed/gzipped offline exports, density overview, bounded checkpoints and pixel-aggregated timeline. Individual project, no integrations with other portfolio repos.

**R1 — Cross-platform and adversarial hardening (HOLD):** native Windows/macOS wheel+CLI tests; Python 3.10–3.13 matrix; Firefox and WebKit including `DecompressionStream` fallback; accessibility and keyboard-only end-to-end evaluation; Git temp-file disk quotas before process completion; hostile/non-UTF-8 pathname policy and extreme object-mode cases.

**R2 — Representative real-repository tasks (HOLD):** permissioned repositories across mono-repo/poly-repo sizes, independent developer task evaluations, usability and comprehension testing, comparatives with Gource/related open-source tooling. Disentangle benchmarks from usefulness.

**R3 — Differentiation after evidence (PLANNED):** optional historical start/end selection, narrative exports, GitHub README-friendly static preview, incremental accessibility work, profile-driven alternative renderer for 80k-path upper bound. Demand product justification and hard performance acceptance before expanding.

**R4 — Public release (HOLD):** explicit MIT license grant, third-party legal/security review, immutable tagged artifact, hashes, source SHA and verified docs. No SaaS runtime on GitHub Pages/Actions; no public release until controls pass.

- **v0.6.0 completed locally:** bounded density SVG export, exact per-file SVG fallback, XML-escaping gate, paired legacy performance measurement. No claims about broader speedups, market traction, or new Git architecture.
- **Future, not implemented:** independent Windows/macOS/Firefox/WebKit/browser accessibility testing, larger real-world workload evaluation, public license decision, more efficient sparse redraw on pan/zoom, independent vulnerability review.

- **v0.7.0 completed locally:** bare mirrors/linked worktree handling, early bounded Git stdout, keyboard-search results, XML 1.0-invalid filename replacement in SVG, 70/70 Python regression checks, Chromium browser acceptance, canonical JSON parity check. Does not raise established maximum Git limits.

## R9 — High-impact viewer performance optimization (native PASS on accepted commit; later changes HOLD)

R7 and R8 are interim engineering acceptance, not the product endpoint. R9 replaces repeated per-frame hover spatial indexing and density hash maps with a lazy layout-space index and typed-array viewport counters, respectively. Preserve exact Git object and A/B semantics; require pixel-identical Canvas output against immutable R8 viewer. **Predeclared native target: ≥3.0x median faster draws in BOTH constellation and atlas modes on the 8,000/80,000/900,000 synthetic fixture, 21 paired measurements per platform/mode, independently audited R9 evidence ZIPs on Linux, Windows and macOS.** No increase to logical ceilings until separate capacity research proves an actual advance. See `docs/R9_MULTIPLICATIVE_SCALING.md`.

## R9 follow-up: Git stderr exhaustion prevention (new candidate; native HOLD)

The R9 native Chromium acceptance on source `689bdc64a42678464860c65eb44682880aeaf78a` is immutable historical evidence. Following that acceptance, a separate hardening patch removes unbounded Git stderr temp-file spooling from the active replay engine. It concurrently drains stderr with stdout, retains only the first 280 error-diagnostic bytes, enforces an absolute 1 MiB stderr budget, terminates an excessive producer, and preserves existing stdout-size/time-out boundaries and `allow_failure` semantics. Its purpose is to close a documented local disk-exhaustion risk, not improve end-to-end rendering speed.

Offline adversarial subprocess tests and Python regression results are candidate evidence only. The changed core source SHA invalidates transfer of prior native acceptance; all affected preflight/native CLI and browser matrix gates must be rerun on the new same-SHA candidate, and the security, independent accessibility and third-party licensing/release gates remain HOLD. No merge or distribution is authorized.

## R9 follow-up — bounded browser data decompression (current candidate)

Following six-job exact-SHA native acceptance on `158a97cf1d6f`, address the
remaining identified compressed-payload memory-exhaustion exposure in the
standalone offline HTML and Python evidence inspection. Maintain the existing
8k/80k/900k canonical Git payload and immutable baselines. Require (1) bounded
64 MiB gzip streaming before JSON parsing, (2) strict UTF-8, (3) a real Chromium
oversize-gzip adversarial gate on every OS, (4) original PNG/DOM parity and the
existing performance protocol, and (5) independent same-SHA evidence ZIP
integrity. No incremental capacity or end-to-end speedup is claimed. Security,
accessibility, licences and owner publication are independent HOLD gates.
