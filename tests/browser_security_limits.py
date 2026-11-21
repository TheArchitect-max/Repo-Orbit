"""Native Chromium adversarial check for bounded standalone gzip expansion.

The fixture contains no user repository data. A real >64 MiB gzip expansion is
intentionally tested, without changing the release build's safety constant.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'demo' / 'RepoOrbit_Demo.html'
TARGET = ROOT / 'evidence' / 'browser_security_limits.json'
DATASET = re.compile(rb'(<script\s+type="application/json"\s+data-encoding="gzip-base64"\s+id="dataset">)([^<]*)(</script>)')


def substitute(html: bytes, uncompressed: bytes) -> bytes:
    match = DATASET.search(html)
    if match is None:
        raise AssertionError('Pinned demo must contain one gzip-base64 dataset')
    packed = base64.b64encode(gzip.compress(uncompressed, compresslevel=1, mtime=0))
    return html[:match.start(2)] + packed + html[match.end(2):]


def compressed_demo() -> bytes:
    # The 32-commit demo defaults to uncompressed JSON because it is small.
    # Convert only that synthetic dataset to gzip before adversarial tests.
    source = SOURCE.read_bytes()
    plain = re.search(rb'(<script\s+type="application/json"\s+data-encoding="plain-json"\s+id="dataset">)([^<]*)(</script>)', source)
    if plain is None:
        raise AssertionError('Synthetic demo must contain one plain JSON dataset')
    encoded = base64.b64encode(gzip.compress(plain.group(2), compresslevel=1, mtime=0))
    return (source[:plain.start(2)] + encoded + source[plain.end(2):]).replace(
        b'data-encoding="plain-json"', b'data-encoding="gzip-base64"', 1)


def test() -> dict:
    source = compressed_demo()
    if b'Compressed dataset exceeds 64 MiB uncompressed safety limit.' not in source:
        raise AssertionError('Rendered product is missing fixed dataset guard')
    result = {'scope': 'local/native Chromium gzip expansion guard',
              'cases': {}, 'network_requests': [], 'expected_guard_bytes': 64 * 1024 * 1024,
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'status': 'FAIL'}
    with sync_playwright() as pw:
        executable = '/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None
        browser = pw.chromium.launch(headless=True, executable_path=executable,
                                     args=['--no-sandbox'] if sys.platform.startswith('linux') else [])
        result['browser_version'] = browser.version
        ctx = browser.new_context(viewport={'width':1280,'height':900})
        page = ctx.new_page()
        page.on('request',lambda request: result['network_requests'].append(request.url)
                if request.url.startswith(('http://','https://')) else None)
        page.set_content(source.decode('utf-8'), wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#statcommits')?.textContent==='32'",timeout=60000)
        result['cases']['normal_synthetic_demo'] = 'PASS'
        page.close()

        # This 64 MiB+1 byte expansion is highly compressible but a hostile
        # downloaded HTML file must not exhaust the JS heap while parsing it.
        over_limit = b'Z' * (64 * 1024 * 1024 + 1)
        malicious = substitute(source, over_limit)
        page = ctx.new_page()
        page.on('request',lambda request: result['network_requests'].append(request.url)
                if request.url.startswith(('http://','https://')) else None)
        page.set_content(malicious.decode('utf-8'), wait_until='domcontentloaded', timeout=120000)
        page.wait_for_function("document.querySelector('#datawarning')?.textContent.includes('64 MiB uncompressed safety limit')", timeout=120000)
        warning = page.locator('#datawarning').inner_text()
        if 'DATA ERROR' not in warning:
            raise AssertionError('Oversize gzip was not rejected by the real browser')
        result['cases']['gzip_expansion_exceeds_64_mib'] = 'PASS'
        result['oversize_expanded_bytes'] = len(over_limit)
        result['oversize_html_delta_bytes'] = len(malicious) - len(source)
        page.close()

        invalid = substitute(source, b'\xff\xfe\xfd')
        page = ctx.new_page()
        page.on('request',lambda request: result['network_requests'].append(request.url)
                if request.url.startswith(('http://','https://')) else None)
        page.set_content(invalid.decode('utf-8'), wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#datawarning')?.textContent.startsWith('DATA ERROR')", timeout=60000)
        result['cases']['invalid_utf8_gzip_rejected'] = 'PASS'
        page.close()
        ctx.close()
        browser.close()
    if result['network_requests']:
        raise AssertionError('Offline Chromium test attempted network traffic')
    if set(result['cases']) != {'normal_synthetic_demo', 'gzip_expansion_exceeds_64_mib', 'invalid_utf8_gzip_rejected'}:
        raise AssertionError('Incomplete adversarial cases')
    result['status'] = 'PASS'
    return result


if __name__ == '__main__':
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = test()
    except Exception as exc:
        result = {'status':'FAIL','error':type(exc).__name__+': '+str(exc)}
    TARGET.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    raise SystemExit(0 if result['status']=='PASS' else 2)
