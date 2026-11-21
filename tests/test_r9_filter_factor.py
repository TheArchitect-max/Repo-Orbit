"""Factorized search-filter regression (test-only, no new runtime deps)."""
from __future__ import annotations
import hashlib
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ACCEPTED_R9='3a31ebb30438a198dd4b3e117822ed0d77a9cc3756b03977bfe094c93554f9fc'

class FactorizedFilterTests(unittest.TestCase):
    def test_accepted_native_r9_reference_is_immutable(self):
        old=ROOT/'baselines/r9-native-accepted/repoorbit/viewer.js'
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(),ACCEPTED_R9)
        self.assertNotEqual(old.read_bytes(),(ROOT/'repoorbit/viewer.js').read_bytes())

    def test_candidate_matches_browser_fixture_source_pin(self):
        pin=json.loads((ROOT/'validation/BROWSER_EXPECTED_SHA256.json').read_text())
        current=hashlib.sha256((ROOT/'repoorbit/viewer.js').read_bytes()).hexdigest()
        self.assertEqual(pin['repoorbit/viewer.js'],current)

    def test_filter_rebuilds_on_both_inputs_and_preserves_pointer_mask(self):
        js=(ROOT/'repoorbit/viewer.js').read_text()
        self.assertIn('const fileNamesLower = files.map(path => path.toLowerCase());',js)
        self.assertIn('const ids=[], mask=new Uint8Array(files.length);',js)
        self.assertIn('let visibleIDs = null, visibleMask = null;',js)
        self.assertIn('const visible = id => !visibleMask || visibleMask[id]===1;',js)
        for control in ('groupfilter','search'):
            self.assertIn("rebuildVisible();hovered=null;",js)
        self.assertIn('const drawable=visibleIDs, drawableLength=drawable?drawable.length:files.length;',js)
        self.assertIn('const candidates=visibleIDs, count=candidates?candidates.length:files.length;',js)

    def test_zero_filter_falls_back_to_all_file_semantics(self):
        js=(ROOT/'repoorbit/viewer.js').read_text()
        self.assertIn('if (!query && !filterGroup) {visibleIDs=null;visibleMask=null;return;}',js)
        self.assertIn('if(query && !fileNamesLower[id].includes(query))continue;',js)
        self.assertIn('if(filterGroup && nodeGroups[id]!==filterGroup)continue;',js)
        self.assertIn('const i=drawable?drawable[row]:row;',js)

if __name__=='__main__':unittest.main()
