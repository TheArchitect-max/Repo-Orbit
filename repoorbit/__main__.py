"""CLI: python -m repoorbit [repository] [options]."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__
from .core import OrbitError, MAX_COMMITS, analyze
from .render import render


def _atomic_write(path: Path, contents: str) -> None:
    """Replace a destination only after a complete UTF-8 write succeeds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         prefix=f".{path.name}.", suffix=".tmp",
                                         dir=str(path.parent), delete=False) as handle:
            temporary = handle.name
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repoorbit", description="Transform Git history into a local-first code constellation."
    )
    parser.add_argument("repo", nargs="?", default=".", help="Local Git repository (default: current directory)")
    parser.add_argument("-o", "--output", default="repo-orbit.html", help="Standalone HTML output path")
    parser.add_argument("-n", "--commits", type=int, default=220,
                        help=f"Most recent first-parent commits (1–{MAX_COMMITS}; default 220)")
    parser.add_argument("--share-safe", "--redact", dest="redact", action="store_true",
                        help="Replace file and directory names, metadata and dates with aliases; structural patterns remain")
    parser.add_argument("--verify", choices=["sample", "full"], default="sample",
                        help="Cross-check 3 snapshots (sample) or every snapshot (full)")
    parser.add_argument("--json", dest="json_path", help="Also export uncompressed, structured v3 JSON")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                        help="Hide tracked paths matching a glob, e.g. --exclude 'vendor/**' (repeatable)")
    parser.add_argument("--html-format", choices=["auto", "plain", "gzip"], default="auto",
                        help="Auto-gzip large embedded datasets (offline browser decompression), or force plain HTML")
    parser.add_argument("--max-html-mb", type=int, default=32, metavar="MB",
                        help="Refuse HTML larger than this size (1–128 MiB, default 32)")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    try:
        target = Path(args.output).expanduser().resolve()
        json_target = Path(args.json_path).expanduser().resolve() if args.json_path else None
        if json_target == target:
            raise OrbitError("HTML and JSON output paths must be different.")
        if not 1 <= args.max_html_mb <= 128:
            raise OrbitError("--max-html-mb must be between 1 and 128.")
        data = analyze(args.repo, limit=args.commits, share_safe=args.redact,
                       verification=args.verify, exclude=tuple(args.exclude))
        document = render(data, compression=args.html_format)
        if len(document.encode("utf-8")) > args.max_html_mb * 1024 * 1024:
            raise OrbitError("HTML artifact exceeds --max-html-mb; reduce --commits or use --exclude.")
        serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n" if json_target else None
        # Produce both complete payloads before writing either file.
        _atomic_write(target, document)
        if json_target and serialized is not None:
            _atomic_write(json_target, serialized)
    except (OrbitError, OSError, ValueError) as exc:
        print(f"Repo Orbit: {exc}", file=sys.stderr)
        return 2
    print(f"Repo Orbit → {target}")
    print(f"{data['history_window']} commits · {data['changes_total']} changes · "
          f"{data['files_final']} files · {data['verified_frames']} checked snapshots")
    if data["partial_history"]:
        print(f"Recent window: {data['history_window']} of {data['history_total']} first-parent commits.")
    if args.exclude:
        print(f"Presentation excludes {data['excluded_paths']} paths / {data['excluded_events']} events; full Git trees still verified.")
    if args.redact:
        print("Metadata redacted, but structure and change patterns may remain identifiable.")
    print("Open the HTML file locally; no server or account is required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
