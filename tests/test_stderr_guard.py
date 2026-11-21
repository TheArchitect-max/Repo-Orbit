"""Portable adversarial subprocess checks for bounded Git diagnostic output."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repoorbit.core import OrbitError, _git_output, MAX_GIT_STDERR_BYTES

POPEN = subprocess.Popen


class GitStderrGuardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="repoorbit-stderr-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def _command(self, code: str):
        def python_child(_command, **kwargs):
            return POPEN([sys.executable, "-c", code], **kwargs)
        return patch("repoorbit.core.subprocess.Popen", side_effect=python_child)

    def test_default_budget_is_one_mebibyte(self):
        self.assertEqual(MAX_GIT_STDERR_BYTES, 1024 * 1024)

    def test_unbounded_stderr_is_killed_without_writing_tempfile(self):
        code = "import os,time\nwhile True:\n os.write(2,b'e'*65536)\n time.sleep(.002)"
        with self._command(code), patch("repoorbit.core.MAX_GIT_STDERR_BYTES", 4096):
            with self.assertRaisesRegex(OrbitError, "standard error exceeds 4096 bytes"):
                with _git_output(self.root, "ignored", timeout=5) as output:
                    self.fail("excessive Git stderr must never be yielded")

    def test_stdout_and_large_but_allowed_stderr_do_not_deadlock(self):
        code = "import os\nos.write(2,b'x'*70000)\nos.write(1,b'complete')"
        with self._command(code):
            with _git_output(self.root, "ignored", timeout=4) as output:
                self.assertEqual(output.read(), b"complete")

    def test_stderr_diagnostic_is_bounded_but_actionable(self):
        code = "import os,sys\nos.write(2,b'known-failure:'+b'Z'*80000)\nsys.exit(3)"
        with self._command(code):
            with self.assertRaisesRegex(OrbitError, r"Git command failed \(3\): known-failure") as err:
                with _git_output(self.root, "ignored", timeout=5):
                    pass
        self.assertLess(len(str(err.exception)), 400)

    def test_allow_failure_preserved_but_not_for_stderr_budget(self):
        code = "import os,sys\nos.write(2,b'expected missing ref')\nsys.exit(5)"
        with self._command(code):
            with _git_output(self.root, "ignored", timeout=5, allow_failure=True) as output:
                self.assertIsNone(output)
        flood = "import os\nfor _ in range(100): os.write(2,b'X'*65536)"
        with self._command(flood), patch("repoorbit.core.MAX_GIT_STDERR_BYTES", 4096):
            with self.assertRaisesRegex(OrbitError, "standard error exceeds"):
                with _git_output(self.root, "ignored", timeout=5, allow_failure=True):
                    pass


if __name__ == "__main__":
    unittest.main()
