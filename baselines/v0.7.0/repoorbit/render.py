"""Produce a fully standalone, escaped, offline HTML visualization."""
from __future__ import annotations

import base64
import gzip
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
TOKENS = re.compile(r"__REPO_NAME__|__PAYLOAD__|__VIEWER_JS__|__DATA_ENCODING__")


def _packed_payload(data: dict) -> dict:
    """Lossless browser-only path dictionary; structured JSON export is unchanged.

    A single sorted path table avoids repeating long file names for every
    commit. Version integers and commit metadata are preserved exactly.
    """
    paths = sorted(set(data["baseline"]) | {
        path for commit in data["commits"] for _code, path in commit["changes"]
    })
    index = {path: i for i, path in enumerate(paths)}
    payload = {k: v for k, v in data.items() if k not in {"baseline", "commits", "top_paths"}}
    payload["packed"] = "path-index-v1"
    payload["paths"] = paths
    payload["baseline"] = [index[path] for path in data["baseline"]]
    payload["top_paths"] = [[index[path], n] for path, n in data["top_paths"]]
    payload["commits"] = [
        {**{key: value for key, value in commit.items() if key not in {"changes", "versions"}},
         "changes": [[code, index[path], version] for (code, path), version in zip(commit["changes"], commit["versions"])]}
        for commit in data["commits"]
    ]
    return payload


def render(data: dict, *, compact: bool = True, compression: str = "auto") -> str:
    # HTML script data terminates at literal '<', even with application/json.
    # Decode only after DOM textContent has been retrieved by trusted viewer JS.
    if compression not in {"auto", "plain", "gzip"}:
        raise ValueError("compression must be auto, plain, or gzip")
    serialized = json.dumps(_packed_payload(data) if compact else data, ensure_ascii=False, separators=(",", ":"))
    use_gzip = compression == "gzip" or (compression == "auto" and len(serialized) > 262144)
    if use_gzip:
        # gzip's mtime=0 makes the offline HTML byte-for-byte reproducible.
        encoded = base64.b64encode(gzip.compress(serialized.encode("utf-8"), compresslevel=9, mtime=0)).decode("ascii")
    else:
        encoded = serialized
        for character, escaped in (("&", "\\u0026"), ("<", "\\u003c"),
                                   (">", "\\u003e"), ("\u2028", "\\u2028"),
                                   ("\u2029", "\\u2029")):
            encoded = encoded.replace(character, escaped)
    snippets = {
        "__REPO_NAME__": html.escape(data["name"], quote=True),
        "__PAYLOAD__": encoded,
        "__DATA_ENCODING__": "gzip-base64" if use_gzip else "plain-json",
        "__VIEWER_JS__": (HERE / "viewer.js").read_text(encoding="utf-8"),
    }
    # One-pass expansion: user-controlled values cannot themselves act as template tokens.
    return TOKENS.sub(lambda match: snippets[match.group(0)],
                      (HERE / "viewer.html").read_text(encoding="utf-8"))
