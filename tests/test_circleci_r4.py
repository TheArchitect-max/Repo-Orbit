"""Regression checks for CircleCI R4 validation additions (offline tests)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'run_circleci_native.py'
_spec = importlib.util.spec_from_file_location('circleci_native_r4', SCRIPT)
_ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ci)


def git(*args, cwd=None, data=None):
    p = subprocess.run(['git', *args], cwd=cwd, input=data, capture_output=True, check=True)
    return p.stdout.decode().strip()


class CircleCIValidationTests(unittest.TestCase):
    def test_cli_uses_offline_benchmark_after_full_history_fetch(self):
        # Inspect Python argument values, not quote style or local variable names.
        import ast

        src = SCRIPT.read_text(encoding='utf-8')
        module = ast.parse(src)
        main = next(n for n in module.body
                    if isinstance(n, ast.FunctionDef) and n.name == 'main')
        executions = [n for n in ast.walk(main)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and isinstance(n.func.value, ast.Name)
                      and n.func.value.id == 'subprocess'
                      and n.func.attr == 'run'
                      and n.args and isinstance(n.args[0], ast.Name)]
        self.assertEqual(len(executions), 1)
        argv_name = executions[0].args[0].id
        commands = [n for n in ast.walk(main)
                    if isinstance(n, ast.Assign) and isinstance(n.value, ast.List)
                    and any(isinstance(t, ast.Name) and t.id == argv_name
                            for t in n.targets)]
        self.assertEqual(len(commands), 1)
        command = commands[0]
        args = [n.value for n in command.value.elts
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        self.assertIn('--offline', args)
        self.assertIn('--targets', args)
        self.assertEqual(args[args.index('--runs') + 1], '21')
        self.assertEqual(args[args.index('--commits') + 1:
                              args.index('--commits') + 4], ['60', '300', '1000'])
        self.assertEqual(args[args.index('--verify') + 1], 'sample')
        self.assertTrue(any(isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Name)
                            and n.func.id == 'prep_one' and n.lineno < command.lineno
                            for n in ast.walk(main)))
        self.assertLess(command.lineno, executions[0].lineno)
        self.assertIn('Git history is still shallow', src)

    def test_original_core_and_render_hashes_remain_pinned(self):
        import hashlib
        pins = json.loads((ROOT/'validation'/'PINNED_TARGETS.json').read_text())
        for version, folder in [('v0.7.0',ROOT/'baselines'/'v0.7.0'/'repoorbit'),
                                ('v0.8.0',ROOT/'repoorbit')]:
            for part in ['core','render']:
                self.assertEqual(hashlib.sha256((folder/(part+'.py')).read_bytes()).hexdigest(),
                                 pins['source_sha256'][version][part])

    def test_config_is_opt_in_and_has_three_native_platforms(self):
        data = (ROOT/'.circleci'/'config.yml').read_text()
        for field in ['run_linux:', 'run_windows:', 'run_macos:']:
            self.assertIn(field,data)
        self.assertEqual(data.count('default: false'),3)
        for s in ['cimg/python:3.13', 'executor: win/default', 'm4pro.medium',
                  'store_artifacts:', '--out external-results/circleci-']:
            self.assertIn(s,data)
        self.assertNotIn('deploy:',data)

    def test_public_https_checkout_is_pinned_and_requires_no_ssh_key(self):
        config = (ROOT / '.circleci' / 'config.yml').read_text()
        self.assertNotIn('      - checkout', config)
        url = 'https://github.com/TheArchitect-max/Repo-Orbit.git'
        self.assertEqual(config.count('git clone --quiet --no-checkout ' + url), 3)
        self.assertEqual(config.count('git -c advice.detachedHead=false checkout --quiet --detach'), 3)
        self.assertEqual(config.count('HOLD: missing CIRCLE_SHA1'), 3)
        self.assertEqual(config.count('HOLD: checkout SHA mismatch'), 3)
        self.assertNotIn('git@github.com:', config)

    def test_local_git_full_history_preparation(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            origin = d/'source'
            git('init','-q','-b','main',str(origin))
            lines = []
            for i in range(1000):
                lines.extend(['commit refs/heads/main',
                              'author Test <test@example.test> 1700000000 +0000',
                              'committer Test <test@example.test> 1700000000 +0000',
                              'data 0',
                              'M 100644 inline test.txt',
                              'data 1',
                              'a', ''])
            git('fast-import','--quiet',cwd=origin,data='\n'.join(lines).encode())
            pin=git('rev-parse','HEAD',cwd=origin)
            out = _ci.prep_one('flask', {'url':str(origin), 'default_branch':'main','sha':pin},d/'cache')
            self.assertEqual(out['status'],'PASS')
            self.assertEqual(out['pinned_sha'],pin)
            self.assertFalse(out['shallow'])
            self.assertEqual(out['first_parent_commits'],1000)

if __name__ == '__main__': unittest.main()
