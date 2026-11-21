# REPO ORBIT v0.8.0 — Independent native benchmark continuation (R2)

**Date:** 2026-11-20.  **Decision:** GENERAL PERFORMANCE CLAIM HOLD.

The v0.8.0 Git engine, renderer and browser assets have not changed in R2.
This is a validation and reproducibility package, **not** a new faster engine.
All evidence is scoped to the actual hardware, repositories and commit windows tested.

## New empirical evidence in R2

Existing independently developed repository: `novnc/noVNC`.
Pinned HEAD: `7fcf9dcfe0cc5b14e3841a4429dc091a6ffca861`.
Machine: native Linux / AMD EPYC 9V74 / Python 3.13.5 / Git 2.47.3.
21 paired measured runs with an alternating order; one warm-up.
Git verification: `sample`. Both engines produced identical canonical JSON
and identical decoded browser payloads in every reported commit window.

| First-parent window | v0.7.0 median total | v0.8.0 median total | Old/new |
|---:|---:|---:|---:|
| 60 | 42.3788 ms | 40.9325 ms | 1.0353x |
| 300 | 50.1865 ms | 48.0106 ms | 1.0453x |
| 1,000 | 95.8957 ms | 84.4670 ms | 1.1353x |

Evidence: `external-results/linux-novnc/novnc_Linux_7fcf9dcfe0cc.json`.
This is *one* independent real codebase, not three independent samples.
The three windows share Git objects and filesystem caches.

## Public repositories verified but still unmeasured here

On 2026-11-20, the GitHub connection confirmed these repositories and the
following exact default-branch revisions:

| Repository | Pinned commit SHA | Required native platforms |
|---|---|---|
| psf/requests | `3c7baaa05ab4aa49cc819ce3a819d260de19c157` | Linux, Windows, macOS |
| pallets/flask | `49943b5a94413a530761350f04e896f76e8d620e` | Linux, Windows, macOS |
| astral-sh/uv | `7bf2d9a3ae44f53a19eed9dcc2348492c8f9f2be` | Linux, Windows, macOS |

**No execution result exists for the three repositories in this environment.**
Git fetch was attempted for all three and failed because `github.com` could
not be resolved by the execution container. Failure evidence:
`external-results/remote_attempt/RUN_STATUS.json`. This must not be treated
as a failure of REPO ORBIT or the external repositories.

## Run natively on Linux, Windows and macOS

Requirements: Python >=3.10, Git >=2.19 with partial-clone support, network
access to github.com, disk space for Git trees, and this unpacked ZIP.
No project dependency installation is required; no third-party repo source
is checked out or executed. Network access is used only for `git fetch`.

From `REPO_ORBIT` in a terminal:

```sh
python scripts/run_native_matrix.py --targets requests flask uv \
  --runs 21 --commits 60 300 1000 --verify sample \
  --out external-results/native
```

Windows PowerShell (run **on native Windows**, not WSL):

```powershell
py -3 scripts/run_native_matrix.py --targets requests flask uv --runs 21 --commits 60 300 1000 --verify sample --out external-results/native-windows
```

macOS (run in the **native macOS kernel**, not a Linux VM):

```sh
python3 scripts/run_native_matrix.py --targets requests flask uv \
  --runs 21 --commits 60 300 1000 --verify sample \
  --out external-results/native-macos
```

Convenience launchers: `validation/run_windows.ps1`,
`validation/run_macos.sh` and `validation/run_linux.sh`.
The notebook `validation/REPO_ORBIT_COLAB_CPU.ipynb` is a Linux-only fallback;
**Google Colab never counts as native Windows/macOS**.

The runner uses pinned commit SHAs, 1,500-deep blobless Git fetch,
no source checkout, identical `verification=sample` in both engines,
21 alternating-order trials, one unmeasured warm-up and a source integrity
check before execution. The HTTP remote and commit SHA are verified again
before accepting evidence. A short/shallow history with fewer than 1,000
first-parent commits is refused rather than being silently truncated.

If GitHub is unreachable, the runner writes **BLOCKED**, not PASS. A complete
set of JSON evidence is written only for actually completed runs.

## Combine evidence and enforce the predeclared thresholds

Once the individual hosts have produced their JSON result folders, combine:

```sh
python scripts/audit_native_matrix.py \
  --inputs external-results/linux external-results/windows external-results/macos \
  --out external-results/native_matrix_audit.json
```

A **bounded CLI performance PASS** requires all nine repo/platform cells
(3 repositories times 3 actual native operating systems), 3 windows per
cell, 21 measured paired runs per window, byte-equivalent canonical Git
results and decoded browser payloads, the exact pinned Git SHAs, a matching
baseline/candidate source manifest, native host metadata, and no scenario
where the candidate median total time is more than 5% slower.

Any invalid provenance/parity or measured regression >5% is a **FAIL**.
Missing evidence is **HOLD**, never imputed. Existing noVNC evidence is
supplemental and does not replace the three predeclared repositories.
The Chromium browser cross-platform gate is independent. Execute the
bundled E2E scripts through `python scripts/run_native_browser.py --out
external-results/browser_<OS>.json` with the optional Playwright test
framework (`python -m pip install playwright` and `python -m playwright
install chromium`). This creates a native browser result with the actual
browser version, logs and required HTML/viewer SHA-256 values.

The R2 Linux runner completed all three browser E2E scripts successfully
using Chromium 144.0.7559.96, including seek, replay, filtering, A/B,
keyboard search, SVG/PNG and the 8,000-commit/80,000-file maximum viewer.
Windows and macOS remain untested, so the cross-platform Chromium gate
is **HOLD**. Firefox/WebKit are distinct additional platform gates.

To audit both kinds of evidence in one report, supply
`--browser-inputs external-results/browser_Linux.json
external-results/browser_Windows.json external-results/browser_Darwin.json`
together with the native benchmark folders. Missing browser results are
HOLD; a failed check or mismatching dataset hash is FAIL.

## Limitations

- The measured total comprises `core.analyze` and `render(...gzip)` only,
  not browser initialization, Canvas frame time, SVG export or perceived UX.
- Warm-cache timings are not cold-start or disk-I/O benchmarks.
- Alternating order reduces but cannot eliminate load, thermal, or cache
  effects; single-machine bootstrap intervals are not population intervals.
- A 5% tolerance is an *engineering acceptance threshold*, not a confidence
  interval or assurance of performance on every workload.
- Even 27 complete native measurements cannot prove the tool is faster on
  **all possible Git repositories**. The strongest legitimate claim would
  be improvement/no material regression within the predeclared sample.
- No change to publishing or license status is authorized here.
