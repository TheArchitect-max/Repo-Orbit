"""Dependency-free semantic guard; native Chromium validates actual accessible names."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class AccessibleViewToggleGuard(unittest.TestCase):
    def test_initial_view_switch_has_explicit_action_label(self):
        js=(ROOT/'repoorbit/viewer.js').read_text(encoding='utf-8')
        self.assertIn("$('viewmode').setAttribute('aria-label','Switch to atlas view');",js)

    def test_action_name_changes_with_display_mode(self):
        js=(ROOT/'repoorbit/viewer.js').read_text(encoding='utf-8')
        self.assertIn("'Switch to atlas view':'Switch to constellation view'",js)
        self.assertIn("toggle.setAttribute('aria-label'",js)
        self.assertIn('toggle.title=',js)

if __name__=='__main__':unittest.main()
