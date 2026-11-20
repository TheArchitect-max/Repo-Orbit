"""Prepare complete pinned Git histories and run native REPO ORBIT benchmarks.

Reads Git metadata and trees only; never executes target repository code.
Python 3.10+ and native Git required on Linux, Windows and macOS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "validation" / "PINNED_TARGETS.json"


def command(args: list[str], *, timeout: int = 1200) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"command {args[:4]} exited {result.returncode}: {result.stderr[-2000:]}"
        )
    return result.stdout.strip()


def prep_one(name: str, target: dict, cache: Path) -> dict:
    cache = cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    if not (cache / ".git").is_dir():
        if any(cache.iterdir()):
            raise RuntimeError(f"Cannot initialize non-empty cache: {cache}")
        command(["git", "init", "-q", str(cache)])
        command(["git", "-C", str(cache), "remote", "add", "origin", target["url"]])
    prefix = ["git", "-C", str(cache)]
    url = command(prefix + ["remote", "get-url", "origin"])
    if url.removesuffix(".git").rstrip("/") != target["url"].removesuffix(".git").rstrip("/"):
        raise RuntimeError(f"Unexpected origin for {name}: {url}")

    shallow = command(prefix + ["rev-parse", "--is-shallow-repository"]) == "true"
    fetch = prefix + (["-c", "fetch.fsck.badTimezone=ignore"] if name == "requests" else [])
    fetch += ["fetch", "--no-tags", "--filter=blob:none"]
    if shallow:
        fetch.append("--unshallow")
    fetch += ["origin", "refs/heads/" + target["default_branch"]]
    command(fetch)

    pinned = target["sha"]
    exists = subprocess.run(prefix + ["cat-file", "-e", pinned + "^{commit}"],
                            capture_output=True, timeout=120).returncode == 0
    if not exists:
        command(prefix + ["fetch", "--no-tags", "--filter=blob:none", "origin", pinned])
    if command(prefix + ["rev-parse", "--is-shallow-repository"]) != "false":
        raise RuntimeError(f"{name}: Git history is still shallow")
    command(prefix + ["cat-file", "-e", pinned + "^{commit}"])
    command(prefix + ["update-ref", "refs/heads/repoorbit-benchmark", pinned])
    command(prefix + ["symbolic-ref", "HEAD", "refs/heads/repoorbit-benchmark"])
    actual = command(prefix + ["rev-parse", "HEAD"])
    if actual != pinned:
        raise RuntimeError(f"{name}: pinned HEAD mismatch {actual} != {pinned}")
    count = int(command(prefix + ["rev-list", "--first-parent", "--count", "HEAD"], timeout=240))
    if count < 1000:
        raise RuntimeError(f"{name}: only {count} first-parent commits; expected at least 1000")
    return dict(target=name, origin=url, pinned_sha=actual, shallow=False,
                first_parent_commits=count, cache=str(cache), status="PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", nargs="+", default=["requests", "flask", "uv"])
    parser.add_argument("--cache", type=Path, default=ROOT / "external-git-cache")
    parser.add_argument("--out", type=Path, default=ROOT / "external-results" / "circleci")
    args = parser.parse_args()
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    if not args.targets or any(name not in pins["required_repositories"] for name in args.targets):
        parser.error("Specify required repository names only: requests flask uv")

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    statuses = []
    for name in args.targets:
        print(f"Fetching complete pinned Git history: {name}", flush=True)
        try:
            record = prep_one(name, pins["repositories"][name], args.cache / name)
        except Exception as exc:
            record = {"target": name, "status": "FAIL", "error": str(exc)}
        statuses.append(record)
        (output / "FULL_HISTORY_STATUS.json").write_text(
            json.dumps(statuses, indent=2) + "\n", encoding="utf-8"
        )
        if record["status"] != "PASS":
            print(record, file=sys.stderr, flush=True)
            raise SystemExit(2)
        print(name, "full-history PASS", record["first_parent_commits"], flush=True)

    cmd = [
        sys.executable, str(ROOT / "scripts" / "run_native_matrix.py"),
        "--offline", "--cache", str(args.cache.resolve()), "--out", str(output),
        "--targets", *args.targets, "--runs", "21",
        "--commits", "60", "300", "1000", "--verify", "sample",
    ]
    result = subprocess.run(cmd, timeout=10800)
    if result.returncode:
        raise SystemExit(result.returncode)
    summary = {
        "status": "MEASUREMENTS_COMPLETED",
        "time_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "targets": args.targets,
        "note": "Native CLI evidence; browser performance is a separate gate.",
    }
    (output / "CIRCLECI_RUN_META.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
