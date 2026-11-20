"""Native benchmark orchestrator for pinned public Git histories.

Python 3.10+ and Git required. Runs Git log/tree processing, not repository code.
The connector verified the pins; git objects must be obtained at execution time.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "validation" / "PINNED_TARGETS.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(path: Path, *args: str, timeout: int = 90) -> str:
    command = ['git', '-C', str(path), *args]
    cp = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if cp.returncode:
        raise RuntimeError(f"Git failed ({cp.returncode}): {cp.stderr[-1500:]}")
    return cp.stdout.strip()


def ensure_sources(config: dict) -> None:
    sources = {
        'v0.7.0': ROOT / 'baselines' / 'v0.7.0' / 'repoorbit',
        'v0.8.0': ROOT / 'repoorbit',
    }
    for version, directory in sources.items():
        for part, expected in config['source_sha256'][version].items():
            location = directory / (part + '.py')
            if not location.is_file() or sha256(location) != expected:
                raise RuntimeError(f'SOURCE INTEGRITY FAIL: {version} {location}')


def native_host() -> dict:
    system = platform.system()
    processor = platform.processor()
    memory_bytes = None
    if system == 'Linux':
        info = Path('/proc/cpuinfo')
        if info.is_file():
            for line in info.read_text(errors='replace').splitlines():
                if line.startswith('model name'):
                    processor = line.partition(':')[2].strip()
                    break
        info = Path('/proc/meminfo')
        if info.is_file():
            for line in info.read_text().splitlines():
                if line.startswith('MemTotal:'):
                    memory_bytes = int(line.split()[1]) * 1024
                    break
    elif system == 'Darwin':
        try:
            processor = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True, timeout=4).strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        try:
            memory_bytes = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True, timeout=4).strip())
        except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
    return {
        'os': system, 'platform': platform.platform(), 'machine': platform.machine(),
        'cpu': processor or 'unknown', 'logical_processors': os.cpu_count(),
        'memory_bytes': memory_bytes, 'python': platform.python_version(),
        'git': subprocess.check_output(['git', '--version'], text=True).strip(),
        'time_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'environment': 'native kernel reported by Python; WSL reports Linux',
    }


def acquire(target: dict, path: Path, offline: bool) -> Path:
    path = path.resolve()
    if not (path / '.git').exists() and not (path / 'HEAD').exists():
        if offline:
            raise RuntimeError(f'Offline: missing Git repository at {path}')
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'init', '-q', str(path)], check=True)
        git(path, 'remote', 'add', 'origin', target['url'])
    # Explicit origin check prevents benchmarking an unrelated local repository.
    origin = git(path, 'remote', 'get-url', 'origin')
    if origin.removesuffix('.git').rstrip('/') != target['url'].removesuffix('.git').rstrip('/'):
        raise RuntimeError(f'Unexpected origin for {target["slug"]}: {origin}')
    sha = target['sha']
    if not offline:
        # Fetch metadata/trees without checking out or executing repository source.
        branch_ref = 'refs/heads/' + target['default_branch']
        cmd = ['git', '-C', str(path)]
        if target['slug'] == 'psf/requests':
            cmd += ['-c', 'fetch.fsck.badTimezone=ignore']
        cmd += ['fetch', '--no-tags', '--filter=blob:none', '--depth=1500', 'origin', branch_ref]
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=480)
        if cp.returncode:
            raise RuntimeError('Fetch failed: ' + cp.stderr[-1500:])
        try:
            git(path, 'cat-file', '-e', sha+'^{commit}')
        except RuntimeError:
            cp = subprocess.run(['git', '-C', str(path), 'fetch', '--no-tags', '--filter=blob:none',
                                 '--depth=1500', 'origin', sha], capture_output=True, text=True, timeout=480)
            if cp.returncode:
                raise RuntimeError('Pinned commit not fetched: ' + cp.stderr[-1500:])
    git(path, 'cat-file', '-e', sha+'^{commit}')
    git(path, 'update-ref', 'refs/heads/repoorbit-benchmark', sha)
    git(path, 'symbolic-ref', 'HEAD', 'refs/heads/repoorbit-benchmark')
    actual = git(path, 'rev-parse', 'HEAD')
    if actual != sha:
        raise RuntimeError(f'Pinned SHA mismatch: {actual} != {sha}')
    return path


def main() -> None:
    config = json.loads(CONFIG.read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--targets', nargs='+', choices=sorted(config['repositories']), default=config['required_repositories'])
    parser.add_argument('--cache', type=Path, default=ROOT / 'external-git-cache')
    parser.add_argument('--out', type=Path, default=ROOT / 'external-results')
    parser.add_argument('--runs', type=int, default=21)
    parser.add_argument('--commits', nargs='+', type=int, default=config['required_windows'])
    parser.add_argument('--verify', choices=['sample','full'], default='sample')
    parser.add_argument('--offline', action='store_true', help='Use previously fetched Git history only; never access network')
    parser.add_argument('--existing', action='append', default=[], metavar='TARGET=PATH',
                        help='Use an existing checkout without modifying its refs or HEAD; exact pinned HEAD required')
    parser.add_argument('--dry-run', action='store_true', help='Print target pins; do not clone or run')
    args = parser.parse_args()
    if not 5 <= args.runs <= 21:
        parser.error('--runs must be 5..21; 21 runs required for acceptance')
    if not args.commits or any(not 1 <= x <= 8000 for x in args.commits):
        parser.error('Commit windows must be in 1..8000')
    existing = {}
    for item in args.existing:
        if '=' not in item:
            parser.error('--existing requires TARGET=PATH')
        key, path = item.split('=', 1)
        if key not in config['repositories'] or not path:
            parser.error('--existing has invalid target or path')
        existing[key] = Path(path).resolve(strict=True)
    ensure_sources(config)
    if args.dry_run:
        for name in args.targets:
            t = config['repositories'][name]
            print(name, t['url'], t['sha'], 'windows', args.commits, 'runs', args.runs)
        return
    args.out.mkdir(parents=True, exist_ok=True)
    host = native_host()
    (args.out/'HOST.json').write_text(json.dumps(host, indent=2)+'\n')
    outcomes = []
    for name in args.targets:
        target = config['repositories'][name]
        entry = {'target': name, 'repository': target['slug'], 'sha': target['sha'],
                 'host': host['os'], 'status':'HOLD'}
        try:
            if name in existing:
                path = existing[name]
                origin = git(path, 'remote', 'get-url', 'origin')
                if origin.removesuffix('.git').rstrip('/') != target['url'].removesuffix('.git').rstrip('/'):
                    raise RuntimeError(f'Wrong origin: {origin}')
                if git(path, 'rev-parse', 'HEAD') != target['sha']:
                    raise RuntimeError('Existing checkout does not have the pinned HEAD')
            else:
                path = acquire(target, args.cache/name, args.offline)
            count = int(git(path, 'rev-list', '--first-parent', '--count', 'HEAD', timeout=120))
            if count < max(args.commits):
                raise RuntimeError(f'Insufficient first-parent history: {count}; need {max(args.commits)}. '
                                   'No silently truncated benchmark windows accepted.')
            dest = args.out / f'{name}_{host["os"]}_{target["sha"][:12]}.json'
            cmd = [sys.executable, str(ROOT/'scripts'/'benchmark_real_workloads.py'),
                   '--baseline', str(ROOT/'baselines'/'v0.7.0'), '--repo', str(path),
                   '--commits', *map(str,args.commits), '--runs', str(args.runs),
                   '--verify', args.verify, '--output', str(dest)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            (args.out/f'{name}_{host["os"]}_stdout.log').write_text(result.stdout + '\n'+result.stderr)
            if result.returncode:
                raise RuntimeError('Benchmark failed: ' + (result.stderr or result.stdout)[-1200:])
            raw = json.loads(dest.read_text())
            if raw['status'] != 'PASS' or raw['metadata']['HEAD'] != target['sha']:
                raise RuntimeError('Evidence parity or SHA verification failed')
            raw['host'] = host
            raw['pinned_target'] = name
            dest.write_text(json.dumps(raw, indent=2, ensure_ascii=False)+'\n')
            entry.update(status='MEASURED', evidence=str(dest.name), cases=len(raw['cases']))
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            entry.update(status='BLOCKED', reason=str(exc)[-2000:])
        print(f"{name}: {entry['status']}", flush=True)
        outcomes.append(entry)
    (args.out/'RUN_STATUS.json').write_text(json.dumps({'host':host,'results':outcomes}, indent=2)+'\n')
    print('Saved results under', args.out)
    if any(x['status'] != 'MEASURED' for x in outcomes):
        sys.exit(2)

if __name__ == '__main__':
    main()
