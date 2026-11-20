# CircleCI native validation — REPO ORBIT R4

Scope: CI/build/test/evidence only. No GitHub Pages, GitHub Actions application server, hosted SaaS, accounts or payments.

## Current state
- `main`: repository bootstrap; no accepted software release.
- Active development branch: `build/circleci-native-r4`.
- Linux (Colab R3): Requests/Flask/uv, nine benchmark windows accepted.
- Windows and macOS: HOLD pending native CircleCI evidence.
- Browser E2E on Windows/macOS: separate gate, HOLD.
- MIT licensing: proposed, not approved.

## Preconditions
CircleCI runs must check out the full R4 codebase, including `repoorbit/`,
`baselines/v0.7.0/repoorbit/`, `scripts/`, `tests/`, and
`validation/PINNED_TARGETS.json`. Do not trigger benchmark jobs on an incomplete
checkout. The pipeline's ability to start does **not** establish test PASS.

Confirm organization integration, credits, native executor availability, and
runner architecture in the CircleCI user interface before running.

## CircleCI R4 SSH checkout failure — repair

On 2026-11-20 the first manually launched Linux, Windows and macOS jobs were
reported FAILED. The Linux step log identified a zero-length SSH checkout key,
an OpenSSL/libcrypto key-load error and GitHub public-key rejection. The runner
did not reach the test suite or benchmarks.

For this **public** repository all three jobs now fetch the source using
unauthenticated HTTPS and then check out the exact `CIRCLE_SHA1`, verified
against `git rev-parse HEAD`. This does not require a GitHub token or deploy
key. It would not be suitable for a private repository without authentication.
The old CircleCI failure statuses remain valid historical failures.

The amended YAML passes local YAML parsing. A local Git clone fixture verifies
the pinned-SHA checkout logic and 96/96 Python regression tests pass on Linux.
**No CircleCI job with this fix has yet been accepted.**

To limit further credit consumption, first run only `run_linux=true`, with
`run_windows=false` and `run_macos=false`. Verify the HTTPS checkout and
preflight are PASS before the more expensive native Windows/macOS jobs.

## R4 regression failure after HTTPS checkout — 2026-11-20

The next Linux CircleCI run **passed SSH-free checkout and pinned source integrity**
(`PASS: pinned source integrity; 10 regression test modules`) but stopped at
the unittest gate: **96 tests run; 1 FAIL**. The failing test
`test_cli_uses_offline_benchmark_after_full_history_fetch` searched for the
source string `'--offline'`, whereas the committed benchmark runner uses
the equivalent Python literal `"--offline"`. The same test also depended on
the quote style of `--runs` and `--commits`. No benchmarks executed in
that failed run.

**Correction:** inspect the Python abstract syntax tree of the actual
`subprocess.run` command argument list. Assert the semantically significant
values `--offline`, `--targets`, `--runs 21`,
`--commits 60 300 1000` and `--verify sample`, and confirm
the pinned-history preparation call precedes benchmark invocation.
This avoids assuming one specific formatting style or variable name.

**Offline verification:** complete Linux Python regression suite **96/96 PASS**.
Adversarial check accepts equivalent double-quoted arguments but rejects
removal of the required `--offline` flag. These checks do not replace a native
CircleCI PASS; that job remains **HOLD pending rerun** on the new branch HEAD.
No change to the pinned product engine or benchmark implementation.

## Native Windows CircleCI failure — R5 remedial controls (2026-11-20)

The first native Windows run on `972837345f388bb87ab7c65920cb56fe84c61697`
reached Python 3.14.9 / Git 2.56.0.windows.3 but **FAILED** its source
integrity check and 11 of 96 tests (5 FAIL, 6 ERROR, 3 SKIP).
**All Windows performance measurements remain HOLD.**

Three independent causes were identified from `build_8_step_102_container_0.txt`:
1. Git Windows CRLF checkout changed the bytes of pinned v0.7.0 core.
   A repository-wide `.gitattributes` now requires LF for Python, YAML, JSON
   and Markdown; the three CI checkouts explicitly disable `core.autocrlf`
   for the source checkout. Pinned source hashes were **not** changed.
2. Five adversarial Git-filename tests tried to create Unix-only characters
   as Windows filenames. They now use in-memory Git fast-import objects,
   retaining actual Git-tree replay, security and escaping assertions on
   every host; nothing is skipped to produce artificial green.
3. The CLI printed Unicode arrows and middle dots to cp1252 stdout, raising
   `UnicodeEncodeError` on Windows. Its CLI status text now uses plain ASCII.

Offline Linux validation of the repaired source: **99/99 tests PASS**;
retested with `PYTHONIOENCODING=cp1252`, also **99/99 PASS**; all four
pinned v0.7.0/v0.8.0 source SHA-256 digests remain unchanged and match.
Native Windows **has not yet rerun** on this correction. Do not claim Windows
PASS, performance parity, browser E2E PASS, or merge readiness until the
corresponding external CircleCI evidence is inspected and accepted.

**PowerShell fail-closed safeguard:** the previous Windows step continued to
run unit tests even when `scripts/preflight_circleci.py` returned nonzero.
Windows now explicitly checks `$LASTEXITCODE` immediately after the source
preflight, before launching the unit suite. This is required to prevent
benchmark work on any integrity-failed checkout. A dedicated regression test
checks this sequencing. Local Linux suite on the full patch: **100/100 PASS**.

## Cost-controlled manual execution
1. Connect this GitHub repository to CircleCI via GitHub App.
2. In CircleCI Project Settings > Triggers, disable all automatic push/PR triggers.
   CircleCI creates an automatic trigger by default for new projects; setting
   YAML booleans to false does **not** disable that trigger by itself.
3. Select **Trigger Pipeline**.
4. Set both **Config Source Branch** and **Checkout Source Branch** to
   `build/circleci-native-r4`.
5. First use `run_linux=true`, with the other `run_*` parameters false. After
   the repaired checkout is verified on CircleCI, run Windows and macOS
   separately and capture each job's native evidence.
6. Collect `FULL_HISTORY_STATUS.json`, `RUN_STATUS.json`, `HOST.json`,
   per-repository JSON and stdout logs in each job's Artifacts.
7. Run the repository's `scripts/audit_native_matrix.py` only after all
   required native artifacts are available.

## Acceptance
All benchmarks use pinned Requests, Flask and uv history at 60, 300 and 1000
first-parent commits. Each requires 21 measurements per version, parity,
source-hash integrity, full Git history, and no regressions over 5%.
Never present a universal speedup claim from a finite benchmark matrix.
Do not merge until required checks PASS and main can be verified.

CircleCI native macOS is an Apple Silicon VM; native Windows uses the Windows orb.
Links:
- https://circleci.com/docs/guides/execute/using-windows/
- https://circleci.com/docs/guides/execute/using-macos/
- https://circleci.com/docs/guides/orchestrate/triggers-overview/
