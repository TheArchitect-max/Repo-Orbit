# REPO ORBIT — CircleCI manual CI and verified public HTTPS checkout

## Incident: six jobs failed at checkout before executing tests (2026-11-21)

The owner provided six *native CircleCI checkout-step logs* from Linux, Windows and macOS, CLI and Chromium jobs, on source SHA `82ee09832c061ffbcbecf4fe8e1cc95590ba3bce` (CircleCI run `8706ce21-80d0-4e4d-95e5-78872e2da7e5`). All six show the same failure:

```text
Warning: checkout key has zero length
Cloning git repository - git@github.com:TheArchitect-max/Repo-Orbit.git
Load key ... : invalid format
Permission denied (publickey)
fatal: Could not read from remote repository.
```

Root cause: the previous version used CircleCI's built-in `checkout: method: full`, which in the owner's current integration attempted an SSH checkout using an empty/invalid key. No source regression, benchmark or browser acceptance test executed in that run. This is an **infrastructure checkout failure**, not evidence that the REPO ORBIT engine failed.

## Minimal remediation for CURRENT PUBLIC repository

As confirmed via GitHub metadata, `TheArchitect-max/Repo-Orbit` was switched back to PUBLIC. Replace the six SSH-based CircleCI checkout steps with the **exact public HTTPS clone strategy already accepted on prior R5 native runs**. All six jobs execute `git clone --quiet --no-checkout https://github.com/TheArchitect-max/Repo-Orbit.git .` and check out the exact `CIRCLE_SHA1` with `core.autocrlf=false` (LF source integrity). Missing/mismatching SHAs fail closed.

No credentials, SSH keys or GitHub PATs are stored in the repository. **This mechanism is inappropriate after changing the repository back to PRIVATE**. If privacy is required, switch to an independently tested authenticated GitHub App token/HTTPS clone or repair the project's checkout SSH key; fail closed if it is not possible. Do not silently fall back to unauthenticated access for a private repo. A GitHub public repository is visible to the public, which matters for owner IP strategy.

The automatic parameter requirement remains: all six booleans (`run_linux`, `run_windows`, `run_macos`, `run_browser_linux`, `run_browser_windows`, `run_browser_macos`) are declared as `default: true`. The CircleCI UI should prepopulate them from the selected branch. Every workflow also requires `when: pipeline.event.name == "api" and pipeline.parameters.<name>`, so ordinary push/PR events do not select workflows, and project automatic VCS triggers should stay disabled. Manual runs still use CI credits.

## Launch and validation

1. CircleCI: `Projects > Repo-Orbit > Pipelines > Trigger Pipeline`.
2. Config Source Branch = `build/circleci-native-r4`; Checkout Source Branch = `build/circleci-native-r4`.
3. Confirm all six booleans show true automatically; do not re-enter them manually. If the UI does not prefill, investigate the CircleCI project/config branch connection before running.
4. Confirm `CIRCLE_SHA1` equals the new exact-SHA repair commit; use the same SHA for all six native jobs.
5. Check **Fetch exact CircleCI commit via public HTTPS (no SSH key)**; it must clone, check out and verify the exact commit before any tests.
6. Inspect the six original evidence ZIPs and SHA-256 sidecars with the independent R7/R9 auditors. Older R5 PASS does not qualify a changed SHA.

## Acceptance boundary

The fix is only locally verifiable until a real CircleCI run executes successfully. The six-job 2026-11-21 failure is recorded as CHECKOUT FAIL and not attributed to the engine. PR #1 remains DRAFT; no merge, tag or release until required source-bound validation plus independent security/privacy, accessibility/AT, licensing/IP and explicit owner approval gates PASS. Do not represent an operational HTTPS checkout as proof of commercial/production readiness.
