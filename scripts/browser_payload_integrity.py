"""Audit the byte-exact *uncompressed* dataset in a standalone browser export.

The same JSON bytes can be encoded as different gzip streams by different
zlib/Python builds. Raw HTML SHA-256 is therefore not a portable acceptance
oracle for the 8k/80k/900k compressed fixture. This is test-only validation.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'validation' / 'BROWSER_CANONICAL_PAYLOAD.json'
SCRIPT = re.compile(
    rb'<script\b(?=[^>]*\bid="dataset")(?=[^>]*\bdata-encoding="gzip-base64")[^>]*>([^<]*)</script>',
    re.DOTALL,
)


def inspect_combined_export(html: bytes, reference: dict) -> dict:
    """Fail closed on changed dataset bytes, source Git HEAD or fixture bounds."""
    if len(html) > reference['maximum_html_bytes']:
        raise ValueError('Standalone HTML exceeds the predeclared size cap')
    matched = list(SCRIPT.finditer(html))
    if len(matched) != 1:
        raise ValueError('Expected exactly one gzip-base64 dataset script')
    try:
        zipped = base64.b64decode(matched[0].group(1).strip(), validate=True)
        raw = gzip.decompress(zipped)
        payload = json.loads(raw.decode('utf-8', 'strict'))
    except (ValueError, UnicodeError, OSError) as exc:
        raise ValueError('Invalid compressed browser dataset: '+str(exc)) from exc
    digest = hashlib.sha256(raw).hexdigest()
    if digest != reference['uncompressed_dataset_sha256']:
        raise ValueError('Canonical browser dataset SHA-256 mismatch: ' + digest)
    for key, expected in reference['required_dataset_fields'].items():
        if payload.get(key) != expected:
            raise ValueError('Browser dataset field mismatch: ' + key)
    if len(payload.get('commits', [])) != reference['required_dataset_fields']['history_window']:
        raise ValueError('Browser commit array length mismatch')
    if len(payload.get('paths', [])) != reference['required_dataset_fields']['paths_total']:
        raise ValueError('Browser path dictionary length mismatch')
    return {
        'status': 'PASS', 'sha256_uncompressed_dataset': digest,
        'sha256_html': hashlib.sha256(html).hexdigest(),
        'bytes_html': len(html), 'bytes_compressed_payload': len(zipped),
        'bytes_uncompressed_payload': len(raw),
        'git_head': payload['head'],
        'method': 'exact SHA-256 of decompressed UTF-8 JSON, not gzip container bytes',
    }


def expected_reference() -> dict:
    return json.loads(REFERENCE.read_text(encoding='utf-8'))


def inspect_fixture(path: Path) -> dict:
    return inspect_combined_export(path.read_bytes(), expected_reference())
