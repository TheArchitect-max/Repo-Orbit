"""Verify R9 pixel and UI parity against authentic archived PNG bytes."""
from __future__ import annotations
import hashlib

from scripts.benchmark_viewer_r9 import PARITY_CASES

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def inspect_png_artifacts(report: dict, load) -> list[str]:
    """load(path)->bytes; may read a directory or exact ZIP member."""
    errors = []
    for mode in ('orbit', 'atlas'):
        cases = report.get('modes', {}).get(mode, {}).get('visual_parity', {})
        for case in PARITY_CASES:
            for label in ('r8', 'r9'):
                item = cases.get(case, {}).get(label, {})
                path = f'R9_PIXELS/{mode}_{case}_{label}.png'
                if item.get('path') != path:
                    errors.append(path+':wrong_path')
                    continue
                try:
                    content = load(path)
                except (KeyError, OSError) as exc:
                    errors.append(path+':missing:'+str(exc))
                    continue
                if not content.startswith(PNG_SIGNATURE) or len(content) < 1000:
                    errors.append(path+':invalid_png')
                if len(content) != item.get('bytes'):
                    errors.append(path+':wrong_size')
                if hashlib.sha256(content).hexdigest() != item.get('sha256'):
                    errors.append(path+':wrong_sha256')
    return errors
