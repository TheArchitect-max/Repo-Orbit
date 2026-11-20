"""Fail closed before spending credits on incomplete CircleCI benchmark jobs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pins_file = ROOT / "validation" / "PINNED_TARGETS.json"
if not pins_file.is_file():
    raise SystemExit("HOLD: missing pinned validation targets")
pins = json.loads(pins_file.read_text(encoding="utf-8"))

required = [
    ROOT / "scripts" / "run_native_matrix.py",
    ROOT / "scripts" / "benchmark_real_workloads.py",
    ROOT / "scripts" / "audit_native_matrix.py",
    ROOT / "tests" / "test_core.py",
    ROOT / "tests" / "test_circleci_r4.py",
    ROOT / "repoorbit" / "__init__.py",
    ROOT / "repoorbit" / "__main__.py",
    ROOT / "repoorbit" / "viewer.html",
    ROOT / "repoorbit" / "viewer.js",
    ROOT / "baselines" / "v0.7.0" / "repoorbit" / "viewer.html",
]
for file in required:
    if not file.is_file():
        raise SystemExit(f"HOLD: incomplete source checkout; missing {file.relative_to(ROOT)}")

for name, directory in [
    ("v0.7.0", ROOT / "baselines" / "v0.7.0" / "repoorbit"),
    ("v0.8.0", ROOT / "repoorbit"),
]:
    for component, digest in pins["source_sha256"][name].items():
        file = directory / (component + ".py")
        if not file.is_file():
            raise SystemExit(f"HOLD: missing {file.relative_to(ROOT)}")
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if actual != digest:
            raise SystemExit(f"HOLD: source hash mismatch for {file.relative_to(ROOT)}")

test_files = list((ROOT / "tests").glob("test_*.py"))
if len(test_files) < 9:
    raise SystemExit(f"HOLD: incomplete regression suite ({len(test_files)} test modules)")
print(f"PASS: pinned source integrity; {len(test_files)} regression test modules")
