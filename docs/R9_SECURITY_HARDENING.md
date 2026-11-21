# R9 post-native acceptance — compressed dataset resource hardening

## Scope and why it matters

The normal offline HTML viewer embeds a compressed JSON dataset. The browser
previously called `Response(stream).text()` on a `DecompressionStream` result,
materializing an unbounded gzip expansion before JSON parsing. Independently,
`scripts/browser_payload_integrity.py` used `gzip.decompress()` to materialize
an unbounded expansion. The compressed HTML input-size cap alone does not bound
uncompressed memory consumption. This is a resource-exhaustion risk when
processing untrusted or altered HTML evidence.

## Concrete implementation

1. `repoorbit/viewer.js`: count genuine decompressed bytes as the gzip stream
   is read, reject after 64 MiB, use streaming strict UTF-8 decoding and show
   an actionable `DATA ERROR`. The check does not silently trim dataset bytes.
2. `scripts/browser_payload_integrity.py`: use bounded `gzip.GzipFile.read()`
   with a 64 MiB+1 byte detection read rather than unbounded `gzip.decompress()`;
   reject oversized payloads, invalid JSON root types and invalid array types.
3. `tests/test_browser_payload_budget.py`: reject small high-ratio compression
   bombs, concatenated gzip streams, truncated gzip, invalid JSON types and
   preserve the exact canonical dataset/hash validation.
4. `tests/browser_security_limits.py`: run a real Chromium browser against a
   normal synthetic gzip dataset, a malicious >64 MiB expansion and malformed
   UTF-8; require zero external network requests.
5. Browser native runner, host audit and independent 3-ZIP auditor require
   this new test and archived `browser_security_limits.json` report. Missing or
   fabricated PASS reports fail closed; HTML and candidate viewer source hashes
   remain pinned to the candidate Git commit. Historical ZIPs cannot qualify.

## Provenance and limitations

The previous accepted R9 six-job CLI + Chromium matrix is immutable at
`158a97cf1d6fdba3d24f2e25d113f4e66261e8bd` (tree
`990522ebd6f420676fee60fd887f338d9b793e9a`). The locally inspected
full-size synthetic browser payload on that historical build expands to
18,574,020 bytes with canonical uncompressed SHA-256
`1de6f6fbe504db5bacdb1e1be1b178404b969f1cd3ef3dacf24d7f310f25bf63`.
The new 64 MiB ceiling accommodates that declared fixture; it is not a new
maximal data-capacity claim. Gzip encoding may differ across host zlib versions,
so the canonical uncompressed hash rather than encoded HTML hash is the cross-
platform fixture identity oracle.

The 64 MiB bound limits decompressed JSON input bytes, **not** peak browser
heap, application state, Git subprocess RSS or total HTML size. A maliciously
edited HTML file remains untrusted executable content. This is internal
engineering validation, not an independent penetration test or a certification.
An independent security/privacy assessment, a11y/AT evaluation, third-party
licence/IP clearance and owner MIT/release approval are **not completed**.

## Evidence and release decision

Local tests must PASS, then **all three native CLI and three native Chromium
CircleCI jobs** must be rerun on the exact new HEAD. The browser matrix must
retain the immutable R8 and R9 visual baselines, the original 8k/80k/900k
Git fixture, 21 paired measurement samples and >=3× filtered redraw threshold,
with exact pixel/DOM parity. The six original same-SHA ZIPs and sidecars must
pass independent matrix audits. PR #1 remains DRAFT; `main` and any release tag
remain unchanged until *all required* controls are independently demonstrated.

## Colab R2 failure reconciliation: deterministic Git demo fixture

The Colab Python 3.13.18 diagnostic for the unmerged gzip-hardening candidate
reported one failure in `test_actual_small_fixture_is_deterministic`: the
32-commit sample HTML was internally repeatable, but the exact SHA-256 differed
from `validation/BROWSER_EXPECTED_SHA256.json`. This **small demo is plain JSON**,
not a gzip serialization. Its HTML was 160 bytes longer than the canonical
fixture, consistent with 32 Git author names extended by five bytes each.
The original diagnostic did not capture the effective Git identity, so the
precise Colab environment variable is not independently established.

`make_demo.py` now constructs its own restricted Git fixture environment,
removing inherited `GIT_*` variables (including Git identity, config injection
and dates) and using fixed SHA-1 commits and fixed demo author/committer
identity. A dedicated regression injects conflicting identity, dates,
`GIT_DEFAULT_HASH` and config and requires **the original exact HTML SHA-256**
both before and after removing those injections. No existing reference hash is
changed and no comparison is skipped or downgraded. The full native Chromium
8k/80k/900k synthetic Git and renderer acceptance gates are unchanged.

This follow-up changes test/demo source, so it is a **new unaccepted commit**
until its own six-job native Linux/Windows/macOS CLI + browser evidence and
independent matrix audit pass. Release gates remain HOLD.

## Colab R3: root cause proven — Git strict UTC spelling

The owner-supplied `REPO_ORBIT_R9_COLAB_R3_DIAGNOSTICS.zip` recorded **152 tests,
149 PASS, 1 SKIP, 2 FAIL** (both exact small demo HTML hash checks). The demo
was 67,157 bytes in Colab, while the canonical Git snapshot produced 66,997
bytes. The 32 synthetic Git commits each contain an ISO-8601 author date. In
the reference rendering each timestamp has the UTC suffix `Z`. Substituting
`+00:00`, an equivalent UTC timezone representation, increases the rendered
HTML by exactly 5 bytes per commit (160 bytes). **This substitution alone
reproduces the complete Colab SHA-256**
`6213853e792a9a7eb9b263f28327bc2a3fc1ac23684d33595672ae05f0d3b498`.
This proves the serialized bytes causing the difference; it supersedes the
previous Git-identity hypothesis. The identities had already been pinned in R3.

The R4 candidate canonicalizes `+00:00` to `Z` **only inside the generated,
synthetic 32-commit demo fixture** immediately after authentic Git replay. Real
history timestamps are not modified, the exact original HTML golden SHA-256
`e9e43207e18cccbf663f2e18d272a6c7b9d866a35d896d3a74e4942f87eeca87`
remains unchanged, and no gzip/payload, rendering, security or native acceptance
gate is relaxed. A new adversarial test forces the Git 2.43 date spelling into
the fixture, then requires the exact same golden SHA. Existing Git-author
isolation and full independent R9 browser evidence remain mandatory.

**Status:** R4 local candidate; GitHub source unchanged until the corrected
notebook completes with PASS. After push, run 3 native CLI + 3 browser jobs on
one new SHA and audit original ZIPs. No automatic merge/release.
