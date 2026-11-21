"""Create adversarial Git trees without Windows-incompatible working tree paths.

Git for Windows validates names even when fast-import creates tree objects,
so a fast-import fixture is not portable. This test-only helper writes Git blobs
and raw tree objects, then commits the resulting root tree. No unsafe path is
materialized in the host filesystem, and no source Git repository is modified.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    proc = subprocess.run(
        ['git', '-C', str(repo), *args], input=input_bytes,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if proc.returncode:
        raise AssertionError(
            f'Git fixture failed ({args}): {proc.stderr.decode("utf-8", "replace")}')
    return proc.stdout


def _tree_from_paths(repo: Path, paths: dict[bytes, tuple[bytes, bytes]]) -> str:
    """Write native Git tree objects from raw entries, sorted as Git requires.

    The tree binary format is mode + SP + filename + NUL + raw object id.
    This bypasses Git for Windows' fast-import checkout-path validation while
    preserving the real bytes that production Git-history readers must parse.
    """
    root: dict[bytes, object] = {}
    for path, (mode, oid) in paths.items():
        parts = path.split(b'/')
        if not path or b'\0' in path or any(p in (b'', b'.', b'..') for p in parts):
            raise ValueError('Git fixture path must be non-empty and NUL-free with safe components')
        node = root
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise ValueError('Conflicting Git fixture file/directory path')
            node = child
        if isinstance(node.get(parts[-1]), dict):
            raise ValueError('Conflicting Git fixture directory/file path')
        node[parts[-1]] = (mode, oid)

    def write_tree(entries: dict[bytes, object]) -> str:
        ordered = []
        for name, value in entries.items():
            if isinstance(value, dict):
                object_id = write_tree(value)
                ordered.append((name, b'40000', object_id))
            else:
                mode, object_id = value
                ordered.append((name, mode, object_id.decode('ascii')))
        ordered.sort(key=lambda entry: entry[0] + (b'/' if entry[1] == b'40000' else b''))
        raw = b''.join(mode + b' ' + name + b'\0' + bytes.fromhex(sha)
                       for name, mode, sha in ordered)
        return _git(repo, 'hash-object', '-w', '-t', 'tree', '--stdin', input_bytes=raw).strip().decode('ascii')

    return write_tree(root)


def commit_unsafe_paths(repo: Path, subject: str, additions: dict[str | bytes, str]) -> str:
    """Commit test-only unsafe filename objects without checking them out.

    Preserve the existing parent tree and history. Keys may be raw Git path
    bytes (including invalid UTF-8), which must never touch the host filesystem.
    Valid and unsafe names appear together in the exact Git tree under test.
    """
    branch = _git(repo, 'symbolic-ref', 'HEAD').strip().decode('ascii')
    parent = subprocess.run(
        ['git', '-C', str(repo), 'rev-parse', '--verify', 'HEAD'],
        capture_output=True, check=False,
    )
    if parent.returncode not in (0, 128):
        raise AssertionError('Unexpected Git rev-parse error')
    previous = parent.stdout.strip().decode('ascii') if parent.returncode == 0 else None

    files: dict[bytes, tuple[bytes, bytes]] = {}
    if previous:
        listing = _git(repo, 'ls-tree', '--full-tree', '-r', '-z', previous)
        for record in listing.split(b'\0'):
            if not record:
                continue
            metadata, filename = record.split(b'\t', 1)
            mode, kind, oid = metadata.split(b' ', 2)
            if kind not in (b'blob', b'commit'):
                raise AssertionError(f'Unexpected tree entry type: {kind!r}')
            files[filename] = (mode, oid)

    for name, contents in additions.items():
        raw_name = name if isinstance(name, bytes) else name.encode('utf-8')
        if not raw_name or b'\0' in raw_name:
            raise ValueError('Git fixture path must be non-empty and NUL-free')
        if any(part in (b'', b'.', b'..') for part in raw_name.split(b'/')):
            raise ValueError('Git fixture path components must be nonempty and not dot segments')
        sha = _git(repo, 'hash-object', '-w', '--stdin',
                   input_bytes=contents.encode('utf-8')).strip()
        files[raw_name] = (b'100644', sha)

    root_tree = _tree_from_paths(repo, files)
    options = ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
               'commit-tree', root_tree, '-m', subject]
    if previous:
        options.extend(['-p', previous])
    commit = _git(repo, *options).strip().decode('ascii')
    _git(repo, 'update-ref', branch, commit, previous or '')
    if _git(repo, 'rev-parse', 'HEAD').strip().decode('ascii') != commit:
        raise AssertionError('Fixture commit ref did not move to the created commit')

    result = _git(repo, 'ls-tree', '-r', '-z', '--name-only', 'HEAD').split(b'\0')
    for name in additions:
        if (name if isinstance(name, bytes) else name.encode('utf-8')) not in result:
            raise AssertionError(f'Injected Git fixture path not present: {name!r}')
    return commit
