# Six native CircleCI jobs — root cause and repair record

- Date: 2026-11-21
- Failed Git SHA: `82ee09832c061ffbcbecf4fe8e1cc95590ba3bce`
- Failed CircleCI run: `8706ce21-80d0-4e4d-95e5-78872e2da7e5`
- Evidence: six original owner-supplied checkout-step logs `build_58` through `build_63`, all showing zero-length SSH checkout key and permission-denied publickey, before tests.
- Cause: CircleCI built-in checkout SSH key unavailable/invalid in current project integration; explicit YAML `checkout: method: full` is the failing step.
- Scope: CI infrastructure only. App source, R6 columnar viewer and acceptance thresholds are untouched.
- Repair: replace six built-in SSH checkouts with the exact public HTTPS Git clone + strict `CIRCLE_SHA1` strategy used by previously accepted native R5 runs. GitHub repository verified PUBLIC before applying this fix. Preserve six manual pipeline booleans `default: true`, API-only workflow condition and all existing evidence gates.
- Test expectations: YAML parse; six HTTPS clone commands and SHA checks; no SSH checkout; all other native and browser paths unchanged; full Python regression and preflight; new 6-job CircleCI run needed on exact repair commit.
- Explicitly not proven: CircleCI remote run after repair, independent security/privacy, AT, licensing/IP or release authorization. No merge permitted.
