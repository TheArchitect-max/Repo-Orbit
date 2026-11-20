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

## Cost-controlled manual execution
1. Connect this GitHub repository to CircleCI via GitHub App.
2. In CircleCI Project Settings > Triggers, disable all automatic push/PR triggers.
   CircleCI creates an automatic trigger by default for new projects; setting
   YAML booleans to false does **not** disable that trigger by itself.
3. Select **Trigger Pipeline**.
4. Set both **Config Source Branch** and **Checkout Source Branch** to
   `build/circleci-native-r4`.
5. Use only one parameter at a time: `run_windows=true` or
   `run_macos=true`; other `run_*` parameters stay false.
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
