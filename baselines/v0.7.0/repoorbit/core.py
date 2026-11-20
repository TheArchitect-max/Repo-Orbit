"""Bounded, first-parent Git tree replay with exact object+mode identity.

Read metadata only: never checkout or read source blob bytes.  Git itself is a
required external executable, not a network service.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
import tempfile
from threading import Event, Timer
from collections import Counter
from contextlib import contextmanager
from typing import Iterator
from pathlib import Path

MAX_COMMITS = 8000
MAX_PATHS = 80000
MAX_EVENTS = 900000
MAX_GIT_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_HISTORY_OUTPUT_BYTES = 256 * 1024 * 1024
MAX_GIT_FIELD_BYTES = 65536
OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class OrbitError(Exception):
    """Expected, user-actionable analysis failure."""


@contextmanager
def _git_output(root: Path, *args: str, timeout: int = 45,
                allow_failure: bool = False, max_bytes: int | None = None):
    """Read a Git command into a bounded spool, enforcing the bound *as it runs*.

    A pipe is drained incrementally. If Git exceeds the output budget, its
    process is terminated instead of first writing arbitrary data to disk.
    The wall-clock timeout also covers blocked/slow pipe reads.
    """
    if max_bytes is None:
        max_bytes = MAX_GIT_OUTPUT_BYTES
    if max_bytes < 0:
        raise ValueError("max_bytes must be nonnegative")
    command = ["git", "--no-optional-locks", "-C", str(root),
               "-c", "core.fsmonitor=false", *args]
    try:
        with tempfile.TemporaryFile(mode="w+b") as output, tempfile.TemporaryFile(mode="w+b") as errors:
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors) as process:
                expired = Event()
                def terminate_on_timeout() -> None:
                    if process.poll() is None:
                        expired.set()
                        process.kill()
                timer = Timer(timeout, terminate_on_timeout)
                timer.daemon = True
                timer.start()
                try:
                    size = 0
                    assert process.stdout is not None
                    while True:
                        chunk = process.stdout.read(65536)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > max_bytes:
                            process.kill()
                            process.wait()
                            raise OrbitError(
                                f"Git response exceeds {max_bytes // (1024 * 1024)} MiB "
                                "limit; reduce --commits or use --exclude."
                            )
                        output.write(chunk)
                    process.wait()
                    if expired.is_set():
                        raise OrbitError(f"Git operation timed out: {' '.join(args[:2])}")
                    if process.returncode:
                        if allow_failure:
                            yield None
                            return
                        errors.seek(0)
                        detail = errors.read(280).decode("utf-8", "replace").strip()
                        raise OrbitError(f"Git command failed ({process.returncode}): {detail}")
                    output.seek(0)
                    yield output
                finally:
                    timer.cancel()
                    if process.poll() is None:
                        process.kill()
                        process.wait()
    except FileNotFoundError as error:
        raise OrbitError("Git is not installed or is not on PATH.") from error


def _git(root: Path, *args: str, timeout: int = 45, allow_failure: bool = False) -> bytes:
    with _git_output(root, *args, timeout=timeout, allow_failure=allow_failure) as output:
        return output.read() if output is not None else b""


def _nul_fields(handle) -> Iterator[bytes]:
    """Parse NUL-delimited records across arbitrary chunk boundaries.

    A single token is bounded, including adversarially large commit metadata.
    Long histories are never materialized as one Python byte string or list.
    """
    pending = b""
    while True:
        chunk = handle.read(64 * 1024)
        if not chunk:
            break
        pieces = (pending + chunk).split(b"\0")
        for field in pieces[:-1]:
            if len(field) > MAX_GIT_FIELD_BYTES:
                raise OrbitError("Git metadata field exceeds 64 KiB; refusing oversized record.")
            yield field
        pending = pieces[-1]
        if len(pending) > MAX_GIT_FIELD_BYTES:
            raise OrbitError("Git metadata field exceeds 64 KiB; refusing oversized record.")
    if pending:
        yield pending


def _path(value: bytes) -> str:
    try:
        return value.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise OrbitError("Non-UTF-8 Git filename found; lossless replay is unavailable.") from error


def _text(value: bytes) -> str:
    return value.decode("utf-8", "replace")


def _tree_objects(root: Path, rev: str | None) -> dict[str, str]:
    """Independent Git tree oracle; keys include file mode and object identity."""
    if not rev:
        return {}
    raw = _git(root, "ls-tree", "-r", "-z", rev, timeout=60)
    objects: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            header, raw_path = record.split(b"\t", 1)
            mode, _kind, oid = header.decode("ascii").split(" ")
        except (ValueError, UnicodeDecodeError) as error:
            raise OrbitError("Unexpected Git tree record.") from error
        if not mode.isdigit() or not OID.fullmatch(oid):
            raise OrbitError("Unexpected Git object identity in tree.")
        path = _path(raw_path)
        if path in objects:
            raise OrbitError("Duplicate path in Git tree.")
        objects[path] = f"{mode}:{oid}"
        if len(objects) > MAX_PATHS:
            raise OrbitError(f"Tree exceeds the {MAX_PATHS:,}-path viewer limit.")
    return objects


def _tree_paths(root: Path, rev: str | None) -> list[str]:
    """Path-level independent oracle, retained as a separately testable gate."""
    if not rev:
        return []
    raw = _git(root, "ls-tree", "-r", "-z", "--name-only", rev, timeout=60)
    return sorted(_path(p) for p in raw.split(b"\0") if p)


def _commit_rows(root: Path, limit: int) -> list[dict]:
    raw = _git(root, "-c", "log.showSignature=false", "log", "--first-parent", "--reverse",
               f"--max-count={limit}", "-z", "--format=%H%x00%aI%x00%an%x00%s%x00", "HEAD", timeout=60)
    rows = []
    for record in (r for r in raw.split(b"\0\0") if r):
        fields = record.split(b"\0")
        if len(fields) != 4:
            raise OrbitError("Unexpected Git log format (metadata boundary).")
        sha = _text(fields[0])
        if not OID.fullmatch(sha):
            raise OrbitError("Unexpected Git log SHA.")
        rows.append({"sha": sha, "date": _text(fields[1]), "author": _text(fields[2]), "subject": _text(fields[3])})
    return rows


def _changes(root: Path, sha: str, parent: str | None) -> list[tuple[str, str, str | None]]:
    """Read raw tree-to-tree diff; never infer equal contents from an event."""
    if parent:
        raw = _git(root, "diff", "--raw", "--no-abbrev", "--no-ext-diff", "--no-textconv",
                   "--no-renames", "-z", parent, sha, timeout=60)
    else:
        raw = _git(root, "diff-tree", "--root", "--raw", "--no-abbrev", "--no-commit-id",
                   "-r", "--no-renames", "-z", sha, timeout=60)
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 2:
        raise OrbitError(f"Unexpected raw diff format for {sha[:12]}.")
    parsed = []
    for i in range(0, len(fields), 2):
        try:
            tokens = fields[i].decode("ascii").split(" ")
        except UnicodeDecodeError as error:
            raise OrbitError("Unexpected raw Git diff header.") from error
        if len(tokens) != 5 or not tokens[0].startswith(":"):
            raise OrbitError(f"Unexpected raw diff record for {sha[:12]}.")
        old_mode, new_mode, old_oid, new_oid, status = tokens
        code = status[0]
        if code not in {"A", "D", "M", "T", "U"} or status != code:
            raise OrbitError(f"Unexpected raw Git diff status {status}.")
        if not OID.fullmatch(old_oid) or not OID.fullmatch(new_oid):
            raise OrbitError("Unexpected Git object identity in diff.")
        if not new_mode.isdigit():
            raise OrbitError("Unexpected Git object mode in diff.")
        path = _path(fields[i+1])
        if not path:
            raise OrbitError("Empty path in Git diff.")
        new_identity = None if code == "D" else f"{new_mode}:{new_oid}"
        parsed.append((code, path, new_identity))
    return parsed


def _history_stream(root: Path, limit: int) -> Iterator[tuple[dict, list[tuple[str, str, str | None]]]]:
    """Stream first-parent commit/delta records without holding all raw Git bytes.

    Boundaries are NUL-delimited. The parser consumes each diff path immediately
    after its validated raw diff header, so marker-like filenames are safe.
    """
    args = (
        "-c", "log.showSignature=false", "log", "--first-parent", "--reverse",
        f"--max-count={limit}", "-z", "--raw", "--root",
        "--diff-merges=first-parent", "--no-renames", "--no-ext-diff",
        "--no-textconv", "--no-abbrev",
        "--format=COMMIT:%H%x00%aI%x00%an%x00%s%x00", "HEAD",
    )
    with _git_output(root, *args, timeout=180, max_bytes=MAX_HISTORY_OUTPUT_BYTES) as stream:
        fields = iter(_nul_fields(stream))
        row: dict | None = None
        delta: list[tuple[str, str, str | None]] = []
        for token in fields:
            if not token or token == b"\n":
                continue
            if token.startswith(b"COMMIT:"):
                sha = token[7:]
                if not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", sha):
                    raise OrbitError("Malformed streaming Git commit record.")
                if row is not None:
                    yield row, delta
                try:
                    date, author, subject = next(fields), next(fields), next(fields)
                except StopIteration as error:
                    raise OrbitError("Truncated streaming Git commit metadata.") from error
                row = {"sha": sha.decode("ascii"), "date": _text(date),
                       "author": _text(author), "subject": _text(subject)}
                delta = []
                continue
            if row is None:
                raise OrbitError("Streaming Git diff appeared before a commit.")
            header = token.lstrip(b"\n")
            if not header.startswith(b":"):
                raise OrbitError("Unexpected streaming Git diff boundary.")
            try:
                tokens = header.decode("ascii").split(" ")
            except UnicodeDecodeError as error:
                raise OrbitError("Invalid streaming raw diff header.") from error
            if len(tokens) != 5 or not tokens[0].startswith(":"):
                raise OrbitError("Malformed streaming raw diff header.")
            old_mode, new_mode, old_oid, new_oid, status = tokens
            if status not in {"A", "D", "M", "T", "U"}:
                raise OrbitError("Unexpected streaming Git diff status.")
            if not old_mode[1:].isdigit() or not new_mode.isdigit():
                raise OrbitError("Malformed streaming Git file mode.")
            if not OID.fullmatch(old_oid) or not OID.fullmatch(new_oid):
                raise OrbitError("Malformed streaming Git object ID.")
            try:
                path = _path(next(fields))
            except StopIteration as error:
                raise OrbitError("Missing path in streaming Git diff.") from error
            if not path:
                raise OrbitError("Empty path in streaming Git diff.")
            delta.append((status, path, None if status == "D" else f"{new_mode}:{new_oid}"))
            if len(delta) > MAX_EVENTS:
                raise OrbitError("Single commit exceeds event capacity.")
        if row is None:
            raise OrbitError("Git history stream returned no valid commit rows.")
        yield row, delta


def _history_batch(root: Path, limit: int) -> tuple[list[dict], list[list[tuple[str, str, str | None]]]]:
    """Materialized legacy diagnostic interface; production replay is streamed."""
    rows, deltas = [], []
    for row, delta in _history_stream(root, limit):
        rows.append(row)
        deltas.append(delta)
    return rows, deltas


def _category(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in {".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".c", ".cpp", ".h", ".hpp", ".java", ".kt", ".rb", ".php", ".cs", ".swift", ".sh", ".sql", ".css", ".html", ".vue", ".svelte", ".dart", ".scala", ".lua", ".zig"}:
        return "code"
    if ext in {".md", ".mdx", ".rst", ".txt", ".adoc", ".pdf", ".tex"}:
        return "docs"
    return "asset"


def _redacted_paths(paths: set[str]) -> dict[str, str]:
    directories: set[str] = set()
    for path in paths:
        parts = path.split("/")
        for i in range(1, len(parts)):
            directories.add("/".join(parts[:i]))
    directory_alias: dict[str, str] = {}
    sibling_counts: Counter[str] = Counter()
    for directory in sorted(directories, key=lambda p: (p.count("/"), p)):
        parent = directory.rpartition("/")[0]
        sibling_counts[parent] += 1
        prefix = directory_alias[parent] + "/" if parent else ""
        directory_alias[directory] = f"{prefix}folder-{sibling_counts[parent]:03d}"
    aliases: dict[str, str] = {}
    for index, path in enumerate(sorted(paths), 1):
        folder = path.rpartition("/")[0]
        prefix = directory_alias[folder] + "/" if folder else ""
        aliases[path] = f"{prefix}file-{index:05d}.{_category(path)}"
    return aliases


def _redact(result: dict, all_paths: set[str]) -> None:
    aliases = _redacted_paths(all_paths)
    author_aliases: dict[str, str] = {}
    for i, row in enumerate(result["commits"], 1):
        author = row["author"]
        if author not in author_aliases:
            author_aliases[author] = f"Contributor {len(author_aliases) + 1}"
        row.update({"sha": f"event-{i:04d}", "date": "", "author": author_aliases[author],
                    "subject": f"Commit {i:04d}",
                    "changes": [[code, aliases[path]] for code, path in row["changes"]]})
    result["baseline"] = sorted((aliases[p], result["baseline_versions"][i]) for i,p in enumerate(result["baseline"]))
    result["baseline_versions"] = [version for _, version in result["baseline"]]
    result["baseline"] = [alias for alias, _ in result["baseline"]]
    result["top_paths"] = [[aliases[p], count] for p, count in result["top_paths"]]
    result["name"] = "Private repository"
    result["head"] = "withheld"
    result["dirty"] = None
    result["exclude_patterns"] = []


def _excluded(path: str, patterns: tuple[str, ...]) -> bool:
    # Globs match the complete Git-relative slash path. A pattern such as
    # 'vendor/**' excludes a subtree, while '*.lock' also matches nested paths.
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def analyze(repository: str | Path, limit: int = 220, share_safe: bool = False,
            verification: str = "sample", exclude: tuple[str, ...] = ()) -> dict:
    """First-parent replay, checked against real Git paths and mode/OIDs.

    JSON contains opaque integer IDs for Git object+mode equality, not hashes or
    source bytes. Redaction does not prevent structural fingerprinting.
    """
    if not isinstance(limit, int) or not 1 <= limit <= MAX_COMMITS:
        raise OrbitError(f"--commits must be between 1 and {MAX_COMMITS}.")
    if verification not in {"sample", "full"}:
        raise OrbitError("--verify must be sample or full.")
    if isinstance(exclude, str) or len(exclude) > 32 or any(not x or len(x)>256 for x in exclude):
        raise OrbitError("Specify at most 32 non-empty exclusion globs, each at most 256 characters.")
    patterns = tuple(exclude)
    requested = Path(repository).expanduser().resolve()
    if not requested.is_dir():
        raise OrbitError(f"Not a directory: {requested}")
    is_bare = _text(_git(requested, "rev-parse", "--is-bare-repository")).strip() == "true"
    # Bare mirrors have no working tree; Git's --show-toplevel fails for them.
    # For a linked worktree, --show-toplevel resolves its actual checkout.
    top_option = "--absolute-git-dir" if is_bare else "--show-toplevel"
    top = Path(_text(_git(requested, "rev-parse", top_option)).strip()).resolve()
    head_before = _text(_git(top, "rev-parse", "--verify", "HEAD", allow_failure=True)).strip()
    if not head_before:
        raise OrbitError("Repository has no commits on HEAD.")
    history_total = int(_text(_git(top, "rev-list", "--count", "--first-parent", "HEAD")).strip())
    history_window = min(history_total, limit)
    if not history_window:
        raise OrbitError("Repository has no commits on HEAD.")
    history = iter(_history_stream(top, limit))
    # The selected first row's parent supplies an exact historical baseline,
    # even when the requested window is smaller than the entire history.
    try:
        first = next(history)
    except StopIteration as error:
        raise OrbitError("Git history stream has no commits.") from error
    baseline_rev = _text(_git(top, "rev-parse", "--verify", first[0]["sha"] + "^1", allow_failure=True)).strip() or None
    base_objects = _tree_objects(top, baseline_rev)
    baseline_paths = sorted(base_objects)
    current = dict(base_objects)
    all_paths = set(base_objects)
    raw_events = 0
    commits: list[dict] = []
    # Opaque IDs preserve exact equality of file mode and Git object ID.
    identities: dict[str, int] = {}
    def token(identity: str) -> int:
        if identity not in identities:
            identities[identity] = len(identities) + 1
        return identities[identity]
    baseline_tokens = [token(base_objects[p]) for p in baseline_paths]
    checkpoints = set(range(history_window)) if verification == "full" else {0, history_window//2, history_window-1}
    from itertools import chain
    for index, (row, delta) in enumerate(chain([first], history)):
        if index >= history_window:
            raise OrbitError("Git history exceeded selected frame count; repository changed during analysis.")
        changes = []
        versions = []
        for status, path, object_key in delta:
            if status == "D":
                if path not in current:
                    raise OrbitError(f"Invalid removal in Git replay at {index+1}: {path!r}.")
                del current[path]
                version = 0
            else:
                if object_key is None:
                    raise OrbitError("Missing object identity in Git diff.")
                if status == "A" and path in current:
                    raise OrbitError(f"Invalid addition in Git replay at {index+1}: {path!r}.")
                current[path] = object_key
                version = token(object_key)
            all_paths.add(path)
            raw_events += 1
            if len(all_paths) > MAX_PATHS or raw_events > MAX_EVENTS:
                raise OrbitError("History exceeds bounded viewer size; reduce --commits or --exclude patterns.")
            if not _excluded(path, patterns):
                changes.append([status, path])
                versions.append(version)
        if index in checkpoints:
            truth = _tree_objects(top, row["sha"])
            if current != truth:
                if set(current) != set(truth):
                    raise OrbitError(f"Replay integrity failure at commit {index+1} (paths).")
                raise OrbitError(f"Replay integrity failure at commit {index+1} (objects/modes).")
        commits.append({**row, "changes": changes, "versions": versions})
    if len(commits) != history_window:
        raise OrbitError("Git history length changed during analysis; retry on a stable repository.")
    if head_before != commits[-1]["sha"] or head_before != _text(_git(top, "rev-parse", "HEAD")).strip():
        raise OrbitError("HEAD changed during analysis. Retry on a stable repository.")
    # No git-hooks, checkout or code blob reads are invoked by our operations.
    dirty = None if is_bare else bool(_git(top, "status", "--porcelain", "--untracked-files=normal", timeout=60))
    baseline = [p for p in baseline_paths if not _excluded(p, patterns)]
    baseline_versions = [v for p,v in zip(baseline_paths,baseline_tokens) if not _excluded(p, patterns)]
    frequencies = Counter(p for c in commits for _status,p in c["changes"])
    visible_paths = {p for p in all_paths if not _excluded(p, patterns)}
    result = {
        "schema": "repoorbit-v3", "name": top.name, "head": commits[-1]["sha"],
        "dirty": dirty, "history_total": history_total,
        "history_window": len(commits), "partial_history": baseline_rev is not None,
        "baseline": baseline, "baseline_versions": baseline_versions,
        "commits": commits, "paths_total": len(visible_paths),
        "files_final": sum(not _excluded(p, patterns) for p in current),
        "changes_total": sum(len(c["changes"]) for c in commits),
        "top_paths": [[p, count] for p,count in sorted(frequencies.items(), key=lambda it:(-it[1],it[0]))[:8]],
        "excluded_paths": len(all_paths)-len(visible_paths),
        "excluded_events": raw_events - sum(len(c["changes"]) for c in commits),
        "exclude_patterns": list(patterns),
        "share_safe": share_safe, "verification": verification,
        "verified_frames": len(checkpoints),
        "object_equality": "mode+git-object",
        "notes": [
            "First-parent history; other branch chains are not replayed independently.",
            "A/B compares exact Git object identity and file modes, not merely touch events.",
            "Objects are opaque integer aliases; original Git OIDs and source bytes are absent.",
            "Selected exclusion patterns filter presentation only; integrity gates check full trees.",
            "Redaction does not erase structural and activity-pattern side channels.",
            "Animation time represents commit order rather than actual elapsed time.",
        ],
    }
    if share_safe:
        _redact(result, visible_paths)
    return result
