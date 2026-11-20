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
