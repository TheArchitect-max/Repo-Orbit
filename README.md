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

## R9 — native acceptance and current safety candidate

R9 factorized Canvas rendering was **independently accepted** on commit
`158a97cf1d6fdba3d24f2e25d113f4e66261e8bd`, across six same-commit native
CircleCI jobs (three CLI, three Chromium). The independent R7/R9 matrix auditors
reported `PASS_WITHIN_PREDECLARED_SCOPE`. This is not universal performance,
security, accessibility, licence or publication acceptance.

**Current unmerged follow-up:** the browser now bounds decompressed gzip datasets
at **64 MiB**, with strict UTF-8 decoding and an explicit failure message.
The Python offline evidence auditor enforces the same expansion budget before
JSON parsing; a tiny compressed expansion bomb cannot force unbounded decoding.
The browser gate now requires an adversarial Chromium test for a real >64 MiB
expansion and malformed UTF-8, in addition to the previous R9 Canvas and
filter checks. The 8k-commit/80k-path/900k-event canonical Git fixture and
accepted baseline remain unchanged. See
[Security hardening](docs/R9_SECURITY_HARDENING.md).

**Acceptance rule:** changing the viewer and validation source creates a new
SHA-bound candidate. The six previously accepted ZIPs prove only their former
commit. Full new native CLI and Chromium evidence must PASS before merge;
independent security/privacy, WCAG/assistive-technology, third-party licensing,
and explicit owner MIT/publication authorization remain HOLD. No active MIT
licence, tagged release or hosted application is claimed.

## Validation status

| Area | Status |
| --- | --- |
| R9 six-job native matrix on `158a97cf1d6f` | **PASS within the predeclared scope**, historical evidence |
| New gzip memory-protection candidate | Local Python and Chromium proof; **native HOLD on new source SHA** |
| Independent security and privacy audit | HOLD |
| Independent accessibility and assistive-technology review | HOLD |
| Third-party licensing/IP and MIT owner release authorization | HOLD |

## CircleCI validation

[CircleCI configuration](.circleci/config.yml) is strictly opt-in, with no
application or SaaS runtime. Set both Config Source Branch and Checkout Source
Branch to `build/circleci-native-r4` and manually enable all six native
`run_*` workflows for this new candidate. Collect the three R7 native CLI ZIPs
and three R9 browser ZIPs, with SHA-256 sidecars. The independent
`scripts/audit_ci_zips.py` and `scripts/audit_browser_zips.py` must both
accept the same source SHA and tree. No ZIP from the historical accepted commit
may substitute for new-commit evidence.

## Scope and documentation

REPO ORBIT is a Git visualization utility, not a source-code security scanner, semantic dependency analyzer, or AI code-review service. It does not host a live application, run a database, manage user sessions or process payments.

Details: [Engineering](docs/ENGINEERING.md) · [Acceptance](docs/ACCEPTANCE.md) · [Roadmap](docs/ROADMAP.md) · [Security](SECURITY.md) · [Third-party notices](THIRD_PARTY_NOTICES.md).
## Historical R8 browser acceptance

R8's three-platform Chromium acceptance was previously completed on commit
`b9dff99e`. The current R9 development candidate has separate exact-SHA
gates and no release authorization. See [Acceptance](docs/ACCEPTANCE.md).
