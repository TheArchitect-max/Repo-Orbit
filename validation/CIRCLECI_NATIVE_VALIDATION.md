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

## Native Windows R5 second attempt — raw-object fixture correction (2026-11-20)

On the second native Windows attempt at HEAD `9e6b47f335c27cdaa34b18e051275f2858bf7b34`,
Python 3.14.9 and Git 2.56.0.windows.3 were confirmed. The pinned source
integrity preflight **PASSED** (11 regression modules). The unittest gate
ended with **100 tests, 6 FAIL, 3 ERROR, 3 SKIP**. No Windows benchmark ran.
Primary evidence: `build_9_step_102_container_0.txt`.

Two independent defects were identified:
1. Git for Windows checks filenames even in fast-import and rejects
   newline/control characters, `<` and `:`. The test-only
   `tests/portable_git.py` now writes real Git blob and recursive raw tree
   objects without materializing invalid host filenames or bypassing
   the production analyzer. A new test verifies that the parent commit,
   valid tracked file and nested adversarial paths remain intact.
2. Some unit tests read UTF-8 HTML/JSON using the platform-default
   cp1252 on Windows. All affected test readers now explicitly decode
   using UTF-8, as required by the artifact format.

Verification on Linux: **101/101 tests PASS**. With
`PYTHONUTF8=0 LC_ALL=C LANG=C`: **101/101 PASS**.
The four original v0.7/v0.8 core/render source SHA-256 values are unchanged.
These are local checks, **not** a native Windows PASS. Keep Windows
benchmarking and PR merge on HOLD until CircleCI supplies fresh evidence.

## Native macOS R6 — invalid UTF-8 test fixture repair (2026-11-20)

The native macOS CircleCI job on commit `cb48e709e602ee09dfeef2c698d0f52291d43236`
reported Python 3.13.3, Git 2.49.0, and a successful pinned source
preflight (11 regression modules). Its unittest stage ran 101 tests and
ended with **1 ERROR**, no benchmark execution. The only failure was
`test_non_utf8_filename_rejected_instead_of_corrupted`: APFS refused
`os.open()` for a filename containing raw `0xff` (`Errno 92: Illegal byte sequence`).

**Remedy:** retain the semantic check for invalid UTF-8 in real Git trees,
but construct the underlying Git blob/tree objects in the existing test-only
`tests/portable_git.py` fixture, using a raw `bytes` path key. This fixture
never materializes an invalid name on APFS, NTFS or another host filesystem.
The portable regression also verifies the exact byte path exists in
`git ls-tree -z` and that the production analyzer rejects it as `Non-UTF-8`.
The former POSIX-only skip is removed; the adversarial check runs on all OSes.

Locally verified on Linux: **102/102 Python tests PASS**, including a
restricted locale and `PYTHONIOENCODING=cp1252`; pinned v0.7/v0.8
core/render SHA-256 checks remain 4/4 PASS. These results are **not**
macOS CircleCI PASS. Re-run only macOS on the repaired branch HEAD and
inspect the job logs before concluding platform acceptance.
PR #1 remains DRAFT/HOLD; no merge.

## R7 — complete host ZIP artifact protocol (2026-11-20)

All three native CircleCI executors have now reported SUCCESS individually:
- Linux: CircleCI native job on `972837345f388bb87ab7c65920cb56fe84c61697`.
- Windows: CircleCI native job on `cb48e709e602ee09dfeef2c698d0f52291d43236`.
- macOS: CircleCI native job on `bcf6eefcd425d396117a093a67e25fee33710def`.

These are three independent CI successes on **different commits**. They do not
yet constitute a validated same-commit native benchmark matrix.

R7 changes only CircleCI evidence infrastructure and documentation, not the
pinned v0.7/v0.8 engines or predeclared benchmark sample. Each platform now:

1. Checks out the exact CircleCI commit via public HTTPS, rejects mismatches.
2. Captures the tracked source snapshot, SHA-256 of every source file, pinned
   benchmark targets, CircleCI commit/tree context and Python environment.
3. Runs the source-integrity preflight, full Python regression suite and pinned
   21-run benchmark matrix, preserving complete per-step stdout/stderr and exit
   codes. A failed gate prevents later benchmark execution.
4. Independently validates the three host/repository evidence cells against
   the original 5% regression, parity, SHA, history and 60/300/1000 commit
   requirements; missing or invalid evidence remains FAIL/HOLD.
5. In a CircleCI `when: always` step, publishes **one** platform-specific
   `REPO_ORBIT_R7_<OS>_<SHA>_EVIDENCE.zip` and its `.sha256` file in the
   job's Artifacts, **including when an earlier step failed**.
   The ZIP includes `CI_PLATFORM_AUDIT.json`, `CI_CONTEXT.json`,
   `RUN_STAGE_STATUS.json`, `SOURCE_SHA256.json`,
   `SOURCE_SNAPSHOT/`, `PYTHON_DISTRIBUTIONS.json`,
   `PINNED_TARGETS.json`, full `logs/`, `measurements/` and
   `SHA256_MANIFEST.json`. ZIP CRC and member hashes are verified.

**Final CI execution:** manually select `build/circleci-native-r4` as both
Config Source Branch and Checkout Source Branch; select
`run_linux=true`, `run_windows=true` and `run_macos=true` together.
Automatic GitHub triggers must remain disabled. Download all three ZIPs
and their SHA-256 companions before any merge.

**Independent cross-host audit:** after downloading all three ZIPs, run:

```sh
python scripts/audit_ci_zips.py LINUX_EVIDENCE.zip WINDOWS_EVIDENCE.zip MACOS_EVIDENCE.zip --out R7_CROSS_PLATFORM_AUDIT.json
```

This rejects mismatched commit/tree identities, missing ZIP members, corrupt
hashes, incomplete test evidence, nonnative results, wrong pinned targets,
parity failures and >5% regressions. Full native 9-cell success proves only
the **predeclared CLI benchmark scope**. Cross-platform browser E2E remains
a separate HOLD gate. PR #1 remains DRAFT until all mandatory gates PASS.

## Cost-controlled manual execution
1. Connect this GitHub repository to CircleCI via GitHub App.
2. In CircleCI Project Settings > Triggers, disable all automatic push/PR triggers.
   CircleCI creates an automatic trigger by default for new projects; setting
   YAML booleans to false does **not** disable that trigger by itself.
3. Select **Trigger Pipeline**.
4. Set both **Config Source Branch** and **Checkout Source Branch** to
   `build/circleci-native-r4`.
5. R7 final replay: set **all three** `run_linux=true`, `run_windows=true`
   and `run_macos=true` on the same updated branch commit.
6. Download each host's `REPO_ORBIT_R7_<OS>_<SHA>_EVIDENCE.zip` and
   its `.sha256` companion from the corresponding CircleCI job's Artifacts.
7. Run `scripts/audit_ci_zips.py` against the three downloaded ZIPs, inspect
   its nine-cell native benchmark audit, and keep the separate browser gate HOLD.

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
