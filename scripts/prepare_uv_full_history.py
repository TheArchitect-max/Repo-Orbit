"""Prepare a complete pinned uv Git history for REPO ORBIT validation R3.

Uses standard Git commands and does not execute repository source files.
This helper does not change v0.7.0/v0.8.0 benchmark engines or acceptance gates.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run(cmd: list[str], *, timeout: int = 900, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"git command failed ({result.returncode}): {result.stderr[-2000:]}")
    return result


def prepare(project: Path, cache: Path) -> dict:
    project = project.resolve(strict=True)
    config = json.loads((project / 'validation' / 'PINNED_TARGETS.json').read_text())
    target = config['repositories']['uv']
    cache = cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    if not (cache / '.git').exists():
        if any(cache.iterdir()):
            raise RuntimeError(f'Unsafe non-empty uninitialized cache: {cache}')
        run(['git', 'init', '-q', str(cache)])
        run(['git', '-C', str(cache), 'remote', 'add', 'origin', target['url']])
    origin = run(['git', '-C', str(cache), 'remote', 'get-url', 'origin']).stdout.strip()
    if origin.removesuffix('.git').rstrip('/') != target['url'].removesuffix('.git').rstrip('/'):
        raise RuntimeError(f'Wrong Git origin for uv: {origin}')
    is_shallow = run(['git', '-C', str(cache), 'rev-parse', '--is-shallow-repository']).stdout.strip() == 'true'
    # Never use --depth. A new full fetch or --unshallow proves complete history.
    fetch_cmd = ['git', '-C', str(cache), 'fetch', '--no-tags', '--filter=blob:none']
    if is_shallow:
        fetch_cmd.append('--unshallow')
    fetch_cmd += ['origin', 'refs/heads/' + target['default_branch']]
    run(fetch_cmd)
    has_sha = run(['git', '-C', str(cache), 'cat-file', '-e', target['sha'] + '^{commit}'], check=False)
    if has_sha.returncode:
        run(['git', '-C', str(cache), 'fetch', '--no-tags', '--filter=blob:none', 'origin', target['sha']])
    run(['git', '-C', str(cache), 'cat-file', '-e', target['sha'] + '^{commit}'])
    run(['git', '-C', str(cache), 'update-ref', 'refs/heads/repoorbit-benchmark', target['sha']])
    run(['git', '-C', str(cache), 'symbolic-ref', 'HEAD', 'refs/heads/repoorbit-benchmark'])
    sha = run(['git', '-C', str(cache), 'rev-parse', 'HEAD']).stdout.strip()
    shallow = run(['git', '-C', str(cache), 'rev-parse', '--is-shallow-repository']).stdout.strip()
    count = int(run(['git', '-C', str(cache), 'rev-list', '--first-parent', '--count', 'HEAD']).stdout.strip())
    if sha != target['sha']:
        raise RuntimeError(f'Pinned uv HEAD mismatch: {sha} != {target["sha"]}')
    if shallow != 'false':
        raise RuntimeError('Full-history requirement FAIL: uv repository is still shallow')
    if count < max(config['required_windows']):
        raise RuntimeError('Full-history requirement FAIL: fewer than 1000 first-parent commits')
    return {
        'status': 'PASS', 'repository': 'uv', 'origin': origin,
        'pinned_sha': sha, 'git_shallow': False, 'first_parent_history_available': count,
        'cache': str(cache), 'git_version': run(['git', '--version']).stdout.strip()
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = prepare(a.project, a.cache)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
