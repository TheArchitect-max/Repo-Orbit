# REPO ORBIT v0.8.0 — External benchmark addendum

This ZIP contains the **unaltered v0.8.0 software distribution** plus
additional documentation, an independently repeatable benchmark script and
real-repository measurement evidence.

New files:

- `docs/EXTERNAL_BENCHMARK_AUDIT.md` — methodology, results, interpretation,
  prospective multi-repository and cross-platform gates.
- `scripts/benchmark_real_workloads.py` — paired v0.7/v0.8 native Git benchmark.
- `scripts/summarize_real_workloads.py` — descriptive table and exploratory
  paired-trial bootstrap intervals.
- `evidence/external_novnc_linux_7runs.json` — original short pilot (7 runs).
- `evidence/external_novnc_linux_21runs.json` — extended follow-up (21 runs).
- `evidence/external_novnc_linux_summary.md` — human-readable summary.
- `evidence/external_audit_manifest.json` — checksums and source-distribution
  provenance for this addendum.

The original `README.md`, `CHANGELOG.md`, `evidence/acceptance_manifest.json`,
Python modules, browser code and wheel are preserved unmodified, including
all their original SHA-256 hashes. The original acceptance manifest continues
to refer to that exact original distribution. The new addendum manifest covers
the new files separately. **No new application version is asserted.**

**Decision:** 75/75 existing Python tests PASS on the re-extracted package;
source-file SHA parity PASS. The external performance evidence is still
insufficient to claim a universal improvement. Windows/macOS and the three
proposed additional public repositories were not tested in this environment.
GitHub is unchanged; licensing/public release remains HOLD.

## R2 continuation (2026-11-20)

Read `docs/EXTERNAL_VALIDATION_R2.md`. The R2 native benchmark matrix adds
exact commit pins for Requests, Flask and uv; prevents evidence gaps from
becoming PASS; and includes one additional noVNC Linux re-run. Original
v0.8.0 engine, renderer and viewer files remain byte-identical.
