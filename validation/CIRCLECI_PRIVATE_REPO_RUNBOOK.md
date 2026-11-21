# REPO ORBIT — private GitHub CircleCI manual pipeline runbook (R9 R6)

## Exact scope and diagnosis

The standalone repository was switched from public to private during R9 R5. Its prior CircleCI config used six unauthenticated `git clone https://github.com/TheArchitect-max/Repo-Orbit.git` operations: these are not appropriate for private-repo checkout. The corresponding unit regression had *required* these public-clone commands and explicitly prohibited CircleCI `checkout`.

The previous private-checkout patch replaced these six steps with CircleCI's authenticated `checkout` (full repository history), after configuring `core.autocrlf=false` on the worker to preserve pinned byte hashes, and it independently verifies `git rev-parse HEAD == CIRCLE_SHA1`. The old credential-free public checkout is removed. No repository token is embedded or printed.

All six workflows are **preselected for a manually triggered pipeline** using six `default: true` parameters. Every workflow also has `when: pipeline.event.name == "api" and pipeline.parameters.<name>`, so ordinary push, PR, webhook and scheduled events select no jobs. Keep automatic VCS triggers disabled in the CircleCI project as an additional defense. Manual runs may still incur CI credits; nothing is deployed or used as SaaS runtime. The change to `.circleci/config.yml` and its tests creates a **new Git SHA**, so the previous R6 local acceptance remains local evidence only and all new native tests must be run against the new commit.

## Manual CircleCI trigger procedure

1. Confirm the CircleCI project is visible under its organization, and the GitHub App/OAuth installation still grants access to the repository after it became **private**. If the project is absent, disabled or needs authorization, reconnect the GitHub connection first. This cannot be validated from GitHub source files alone.
2. In CircleCI select **Pipelines > Trigger Pipeline** (or **Run Pipeline** depending on UI). Set **Config Source Branch** and **Checkout Source Branch** both to `build/circleci-native-r4`. Confirm checkout source is the private `TheArchitect-max/Repo-Orbit` repository.
3. CircleCI **automatically pre-populates** the six BOOLEAN parameters from the selected branch config: `run_linux=true`, `run_windows=true`, `run_macos=true`, `run_browser_linux=true`, `run_browser_windows=true`, `run_browser_macos=true`. **Do not add them manually.** If the UI does not display those values, do not trigger; the CircleCI project connection/config source may be broken. CircleCI announced UI parameter auto-population in November 2024 (https://discuss.circleci.com/t/product-update-pre-populate-pipeline-parameters-when-triggering-a-pipeline-in-the-circleci-web-app/52346).
4. Start the pipeline. In the run details, confirm `CIRCLE_SHA1` equals the newly committed CI-fix SHA and not the prior R6 candidate. The six workflows should appear. If no pipeline appears, capture the exact trigger-modal error or integration-authorization message. If a workflow appears but checkout fails, capture the full first checkout-step logs: that is a different error from a missing trigger.
5. Only the six original same-commit native CLI/browser ZIPs plus their SHA-256 digests can qualify cross-platform acceptance using `scripts/audit_ci_zips.py` and `scripts/audit_browser_zips.py`.

## Why this is safe from automatic push-triggered jobs

The `default: true` values affect a manually launched pipeline, but each workflow is gated on `pipeline.event.name == "api"` (CircleCI documents that manual UI/API launches use `api`). GitHub push/PR events do not satisfy this condition; changing the defaults without this gate would consume credits on push. This is a **config-level assertion**, not proof that CircleCI project triggers are correctly configured. Manual UI prefill depends on CircleCI loading the selected branch; it cannot work while the project page shows Page Not Found. The owner must re-authorize/connect the private repo if the CircleCI project is missing.

## Current acceptance limitations

Local YAML parsing, source regression and SHA guards can be tested offline. The actual CircleCI account's project authorization and UI trigger cannot be tested without an authenticated CircleCI connection. It must never be reported as succeeded without a genuine run. Independent security/privacy, AT accessibility, third-party licensing/IP and explicit owner proprietary/public distribution decisions remain separately HOLD. No merge or release authorized.
