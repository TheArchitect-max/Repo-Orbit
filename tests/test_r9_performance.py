"""R9 acceptance: immutable R8 baseline, bounded measured improvements, fail closed."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from scripts.benchmark_viewer_r9 import (BASE_SHA, EXPECTED_DATASET, PARITY_CASES,
                                         validate_performance, html_variants)
from scripts.r9_raster_evidence import inspect_png_artifacts

ROOT=Path(__file__).resolve().parents[1]


def sample_report() -> dict:
    return {'protocol':'R9_V1_PAIRED_CANVAS_DRAW','browser':'Chromium',
            'chromium_version':'159.0', 'pairs':21,
            'baseline_viewer_sha256':BASE_SHA,
            'candidate_viewer_sha256':hashlib.sha256((ROOT/'repoorbit/viewer.js').read_bytes()).hexdigest(),
            'dataset_sha256':EXPECTED_DATASET,'acceptance':'PASS_WITHIN_PREDECLARED_SCOPE',
            'javascript_errors':[],'external_network_requests':[],
            'modes':{view:{'baseline_draw_ms':[24.0]*21,'candidate_draw_ms':[3.0]*21,
                           'baseline_median_ms':24.0,'candidate_median_ms':3.0,
                           'speedup_x':8.0,'gate':'PASS','pixel_exact':True,
                           'pixel_sha256':{'r8':'a'*64,'r9':'a'*64},
                           'visual_parity':{case:{label:{'path':f'R9_PIXELS/{view}_{case}_{label}.png',
                                              'bytes':1200,'sha256':'a'*64,
                                              'dom':{'statfiles':'80000','timeposition':'FRAME 8000 / 8000',
                                                     'frameinfo':'80000 TRACKED FILES','matchcount':''}}
                                                   for label in ('r8','r9')}
                                            for case in PARITY_CASES}}
                     for view in ('orbit','atlas')}}


class R9PerformanceGates(unittest.TestCase):
    def test_accepted_baseline_viewer_is_frozen_and_active_pin_is_exact(self):
        original=hashlib.sha256((ROOT/'baselines/v0.8.0/repoorbit/viewer.js').read_bytes()).hexdigest()
        self.assertEqual(original,BASE_SHA)
        old=json.loads((ROOT/'validation/BROWSER_R8_ACCEPTED_SHA256.json').read_text())
        new=json.loads((ROOT/'validation/BROWSER_EXPECTED_SHA256.json').read_text())
        self.assertEqual(old['repoorbit/viewer.js'],original)
        self.assertEqual(new['repoorbit/viewer.js'],hashlib.sha256((ROOT/'repoorbit/viewer.js').read_bytes()).hexdigest())
        self.assertEqual(new['repoorbit/viewer.html'],old['repoorbit/viewer.html'])

    def test_valid_21_paired_draws_pass_bounded_gate(self):
        candidate=hashlib.sha256((ROOT/'repoorbit/viewer.js').read_bytes()).hexdigest()
        self.assertEqual(validate_performance(sample_report(),candidate),[])

    def test_invalid_metrics_and_raster_drift_rejected(self):
        candidate=hashlib.sha256((ROOT/'repoorbit/viewer.js').read_bytes()).hexdigest()
        for flaw in ('too_few','tampered_median','slower','different_canvas','wrong_source','network'):
            report=copy.deepcopy(sample_report())
            if flaw=='too_few':report['modes']['orbit']['candidate_draw_ms'].pop()
            elif flaw=='tampered_median':report['modes']['orbit']['baseline_median_ms']=999.0
            elif flaw=='slower':
                report['modes']['atlas']['candidate_draw_ms']=[12.0]*21
                report['modes']['atlas']['candidate_median_ms']=12.0
                report['modes']['atlas']['speedup_x']=2.0
            elif flaw=='different_canvas':report['modes']['orbit']['pixel_sha256']['r9']='b'*64
            elif flaw=='wrong_source':report['candidate_viewer_sha256']='0'*64
            elif flaw=='network':report['external_network_requests']=['https://not-permitted.example']
            with self.subTest(flaw=flaw):
                self.assertTrue(validate_performance(report,candidate))

    def test_runner_and_archive_auditor_import_native_png_integrity_gate(self):
        from scripts import run_browser_evidence, audit_browser_zips
        self.assertIs(run_browser_evidence.inspect_png_artifacts, inspect_png_artifacts)
        self.assertIs(audit_browser_zips.inspect_png_artifacts, inspect_png_artifacts)

    def test_missing_or_tampered_real_png_evidence_rejected(self):
        report = sample_report()
        self.assertEqual(validate_performance(report, report['candidate_viewer_sha256']), [])
        missing = inspect_png_artifacts(report, lambda path: (_ for _ in ()).throw(KeyError(path)))
        self.assertEqual(len(missing), 12)
        def wrong_png(_):
            return b"\x89PNG\r\n\x1a\n" + b"fake" * 400
        tampered = inspect_png_artifacts(report, wrong_png)
        self.assertTrue(any(':wrong_sha256' in value for value in tampered))
        altered = copy.deepcopy(report)
        altered['modes']['atlas']['visual_parity']['frame_4000']['r9']['sha256'] = 'b'*64
        self.assertIn('atlas:frame_4000:visual_or_dom_mismatch',
                      validate_performance(altered, altered['candidate_viewer_sha256']))

    def test_browser_pipeline_fails_closed_on_missing_r9_evidence(self):
        from scripts.run_browser_evidence import STAGES
        from scripts.audit_browser_zips import REQUIRED
        config=(ROOT/'.circleci/config.yml').read_text(encoding='utf-8')
        self.assertIn('r9_paired_viewer_performance',STAGES)
        self.assertIn('R9_PAIRED_VIEWER_PERFORMANCE.json',REQUIRED)
        self.assertIn('when: always',config)

    def test_r9_html_contains_identical_pinned_browser_dataset(self):
        source=ROOT/'demo/RepoOrbit_CombinedMaximum.html'
        if not source.is_file():self.skipTest('Generated Git fixture required for full local browser test')
        variants=html_variants(source)
        self.assertEqual(set(variants),{'r8','r9'})
        self.assertNotEqual(variants['r8'],variants['r9'])
        self.assertEqual(variants['r8'].split('id="dataset">',1)[1].split('</script>',1)[0],
                         variants['r9'].split('id="dataset">',1)[1].split('</script>',1)[0])


if __name__=='__main__':unittest.main()
