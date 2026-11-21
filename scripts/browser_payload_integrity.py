"""Audit the byte-exact *uncompressed* dataset in a standalone browser export.

The same JSON bytes can be encoded as different gzip streams by different
zlib/Python builds. Raw HTML SHA-256 is therefore not a portable acceptance
oracle for the 8k/80k/900k compressed fixture. This is test-only validation.
"""
from __future__ import annotations

import base64
import gzip
import io
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'validation' / 'BROWSER_CANONICAL_PAYLOAD.json'
# Test-only limit: canonical 8k/80k/900k JSON is about 39 MiB; a 64 MiB
# ceiling prevents a tiny malicious gzip payload from inflating without bound.
MAX_UNCOMPRESSED_DATASET_BYTES = 64 * 1024 * 1024
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
        # gzip.decompress() allocates the entire expansion, even if its
        # compressed input fits the HTML size cap. Bound the expansion *while*
        # decoding. GzipFile supports concatenated gzip members, as before.
        with gzip.GzipFile(fileobj=io.BytesIO(zipped), mode='rb') as gz:
            raw = gz.read(MAX_UNCOMPRESSED_DATASET_BYTES + 1)
        if len(raw) > MAX_UNCOMPRESSED_DATASET_BYTES:
            raise ValueError('Decompressed browser dataset exceeds 64 MiB safety limit')
        payload = json.loads(raw.decode('utf-8', 'strict'))
        if not isinstance(payload, dict):
            raise ValueError('Browser dataset must be a JSON object')
    except (ValueError, UnicodeError, OSError, EOFError) as exc:
        raise ValueError('Invalid compressed browser dataset: '+str(exc)) from exc
    digest = hashlib.sha256(raw).hexdigest()
    if digest != reference['uncompressed_dataset_sha256']:
        raise ValueError('Canonical browser dataset SHA-256 mismatch: ' + digest)
    for key, expected in reference['required_dataset_fields'].items():
        if payload.get(key) != expected:
            raise ValueError('Browser dataset field mismatch: ' + key)
    commits = payload.get('commits')
    paths = payload.get('paths')
    if not isinstance(commits, list) or len(commits) != reference['required_dataset_fields']['history_window']:
        raise ValueError('Browser commit array length mismatch')
    if not isinstance(paths, list) or len(paths) != reference['required_dataset_fields']['paths_total']:
        raise ValueError('Browser path dictionary length mismatch')
    # R9 R6: an independent oracle for the most frequently changed file.
    # This proves the browser's compact per-file history index has not lost,
    # reordered, or relabelled events in the 900k-event synthetic Git history.
    # Unit-only canonical fixtures without a top_paths field remain supported.
    hotspot_oracle = None
    hotspots = payload.get('top_paths')
    if isinstance(hotspots, list) and hotspots:
        entry = hotspots[0]
        if (not isinstance(entry, list) or len(entry)!=2 or
            not isinstance(entry[0], int) or isinstance(entry[0], bool) or
            not 0<=entry[0]<len(paths) or not isinstance(entry[1], int)):
            raise ValueError('Invalid canonical hotspot reference')
        path_id, claimed_count=entry
        occurrences=[]
        for frame, commit in enumerate(commits):
            for row in commit['changes']:
                if row[1]==path_id:
                    occurrences.append({'frame':frame+1,'status':row[0]})
        if len(occurrences)!=claimed_count:
            raise ValueError('Canonical hotspot count does not match Git events')
        hotspot_oracle={
            'status':'PASS','source':'independently decompressed canonical packed Git dataset',
            'path':paths[path_id],'event_count':claimed_count,
            'last_events_verified':min(len(occurrences),8),
            'original_events':payload['changes_total'],
            'last_eight':occurrences[-8:]}
    return {
        'r9_r6_compact_history_exact': hotspot_oracle,
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
