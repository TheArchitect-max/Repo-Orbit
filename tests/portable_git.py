"""Create Git history fixtures without materializing forbidden host filenames.

The Git tree supports arbitrary NUL-free path bytes, whereas Windows cannot
create names containing '<', newlines or control characters. This helper
builds objects only, through Git fast-import; it does not write these paths
into the host filesystem. It is test infrastructure, not benchmark evidence.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    process = subprocess.run(
        ['git', '-C', str(repo), *args], input=input_bytes,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if process.returncode:
        raise AssertionError(
            f'Git fixture failed ({args}): {process.stderr.decode("utf-8", "replace")}')
    return process.stdout.strip()


def _quote_git_path(name: str) -> bytes:
    """C-quote UTF-8 bytes as documented by git-fast-import's M command."""
    raw = name.encode('utf-8')
    if not raw or b'\x00' in raw:
        raise ValueError('Git fixture path must be non-empty and NUL-free')
    out = bytearray(b'"')
    for char in raw:
        if char == 34:
            out.extend(b'\\"')
        elif char == 92:
            out.extend(b'\\\\')
        elif char < 32 or char >= 127:
            out.extend(f'\\{char:03o}'.encode('ascii'))
        else:
            out.append(char)
    return bytes(out) + b'"'


def commit_unsafe_paths(repo: Path, subject: str, additions: dict[str, str]) -> str:
    """Commit Git objects containing paths unsupported by Windows filesystems.

    An isolated temporary Git repository must be passed. Existing contents of
    the working tree are deliberately not touched; no checkout is attempted.
    """
    branch = _git(repo, 'symbolic-ref', 'HEAD')
    previous = subprocess.run(
        ['git', '-C', str(repo), 'rev-parse', '--verify', 'HEAD'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if previous.returncode not in (0, 128):
        raise AssertionError('Unexpected Git rev-parse error')
    message = subject.encode('utf-8')
    lines = [b'commit ' + branch, b'author Fixture <fixture@example.invalid> 1700000000 +0000',
             b'committer Fixture <fixture@example.invalid> 1700000000 +0000',
             b'data ' + str(len(message)).encode('ascii'), message]
    if previous.returncode == 0:
        lines.append(b'from ' + previous.stdout.strip())
    for name, value in additions.items():
        blob = value.encode('utf-8')
        lines.extend([b'M 100644 inline ' + _quote_git_path(name),
                      b'data ' + str(len(blob)).encode('ascii'), blob])
    payload = b'\n'.join(lines) + b'\n'
    _git(repo, 'fast-import', '--quiet', input_bytes=payload)
    actual = _git(repo, 'rev-parse', 'HEAD').decode('ascii')
    names = _git(repo, 'ls-tree', '-r', '-z', '--name-only', 'HEAD').split(b'\x00')
    for name in additions:
        if name.encode('utf-8') not in names:
            raise AssertionError(f'Injected Git fixture path not present: {name!r}')
    return actual

