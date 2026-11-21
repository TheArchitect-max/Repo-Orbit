# REPO ORBIT — private GitHub CircleCI manual pipeline runbook (R9 R6)

## Exact scope and diagnosis

The standalone repository was switched from public to private during R9 R5. Its prior CircleCI config used six unauthenticated `git clone https://github.com/TheArchitect-max/Repo-Orbit.git` operations: these are not appropriate for private-repo checkout. The corresponding unit regression had *required* these public-clone commands and explicitly prohibited CircleCI `checkout`.

This candidate replaces these six steps with CircleCI's authenticated `checkout` (full repository history), after configuring `core.autocrlf=false` on the worker to preserve pinned byte hashes, and it independently verifies `git rev-parse HEAD == CIRCLE_SHA1`. The old credential-free public checkout is removed. No repository token is embedded or printed.

All six workflows remain **explicitly opt-in** with six `default: false` parameters. There is no scheduled/automatic build or SaaS deployment. This protects CI credits. The change to `.circleci/config.yml` and its tests creates a **new Git SHA**, so the previous R6 local acceptance remains local evidence only and all new native tests must be run against the new commit.

## Manual CircleCI trigger procedure

1. Confirm the CircleCI project is visible under its organization, and the GitHub App/OAuth installation still grants access to the repository after it became **private**. If the project is absent, disabled or needs authorization, reconnect the GitHub connection first. This cannot be validated from GitHub source files alone.
2. In CircleCI select **Pipelines > Trigger Pipeline** (or **Run Pipeline** depending on UI). Set **Config Source Branch** and **Checkout Source Branch** both to `build/circleci-native-r4`. Confirm checkout source is the private `TheArchitect-max/Repo-Orbit` repository.
3. In **Pipeline Parameters**, explicitly add these six BOOLEAN parameters as **true**: `run_linux`, `run_windows`, `run_macos`, `run_browser_linux`, `run_browser_windows`, `run_browser_macos`. They default to false, so merely selecting the branch will not run any workflow.
4. Start the pipeline. In the run details, confirm `CIRCLE_SHA1` equals the newly committed CI-fix SHA and not the prior R6 candidate. The six workflows should appear. If no pipeline appears, capture the exact trigger-modal error or integration-authorization message. If a workflow appears but checkout fails, capture the full first checkout-step logs: that is a different error from a missing trigger.
5. Only the six original same-commit native CLI/browser ZIPs plus their SHA-256 digests can qualify cross-platform acceptance using `scripts/audit_ci_zips.py` and `scripts/audit_browser_zips.py`.

## Current acceptance limitations

Local YAML parsing, source regression and SHA guards can be tested offline. The actual CircleCI account's project authorization and UI trigger cannot be tested without an authenticated CircleCI connection. It must never be reported as succeeded without a genuine run. Independent security/privacy, AT accessibility, third-party licensing/IP and explicit owner proprietary/public distribution decisions remain separately HOLD. No merge or release authorized.
