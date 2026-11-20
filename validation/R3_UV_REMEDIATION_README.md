# REPO ORBIT v0.8.0 — External Validation R3 / uv history remediation

This is a **validation-only addendum** to R2. v0.7.0 and v0.8.0 runtime engines, the browser viewer, pin targets, and the R2 acceptance audit are untouched. The R3 ZIP preserves all R2 files byte-for-byte.

## Source evidence from Colab R2 (2026-11-20)
- Requests/Linux: 3 windows (60/300/1000), 21 trial pairs each, matching canonical JSON and browser dataset: accepted.
- Flask/Linux: same scope: accepted.
- uv/Linux: 3 windows measured but rejected for shallow Git history; its record is archived under `evidence/r2_submitted/` and excluded from new native matrix input.
- Windows and macOS CLI evidence: not measured. Cross-platform browser evidence: not measured. Native Linux Chromium results originally supplied by R2 are included under `external-results/browser_Linux.json`; they came from a different Linux host.

## How to fix only the missing uv/Linux cell
1. Open `REPO_ORBIT_COLAB_CPU_R3_UV_FIX.ipynb` in Google Colab.
2. Upload the **single** file `REPO_ORBIT_v0.8.0_EXTERNAL_VALIDATION_R3_UV_RETRY.zip` when prompted.
3. The notebook checks engine hashes, fetches the **complete** uv Git history at the exact pinned commit, runs the original 21-trial uv benchmark, independently validates shallow=false, and runs the unchanged matrix auditor.
4. Download the generated `REPO_ORBIT_COLAB_LINUX_RESULTS_R3.zip` and upload it to ChatGPT.

If GitHub download fails or the history remains shallow, the notebook reports HOLD/FAIL; it does not rewrite invalid evidence or make a fabricated PASS. A successful three-repository Linux run still leaves the full Linux/Windows/macOS matrix at HOLD. These benchmarks do not prove a universal speedup.

## Validation record identity
Use the SHA-256 file `validation/R3_ADDITIONS_SHA256.json` for the addendum files. `validation/R2_FILES_SHA256.json` remains the original unchanged R2 baseline manifest. Verified source identities are in `validation/PINNED_TARGETS.json`.
