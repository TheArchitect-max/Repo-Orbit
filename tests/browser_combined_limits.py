"""Headless Chromium smoke at all REPO ORBIT v0.6.0 caps simultaneously."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'demo'/'RepoOrbit_CombinedMaximum.html'
REPORT=ROOT/'evidence'/'browser_combined_limits.json'


def main() -> None:
    assert HTML.is_file(), 'Run scripts/stress_combined_limits.py first'
    requests=[];errors=[];warnings=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
                                  args=['--no-sandbox','--disable-gpu','--enable-precise-memory-info',
                                        '--js-flags=--max-old-space-size=3072'])
        page=browser.new_page(viewport={'width':1380,'height':920},reduced_motion='reduce')
        page.on('request',lambda req: requests.append(req.url) if req.url.startswith(('https://','http://')) else None)
        page.on('pageerror',lambda err: errors.append(str(err)))
        page.on('console',lambda msg: warnings.append(msg.text) if msg.type=='error' else None)
        start=time.perf_counter()
        content=HTML.read_text(encoding='utf-8')
        page.set_content(content,wait_until='domcontentloaded',timeout=180000)
        page.wait_for_function("document.querySelector('#statcommits')?.textContent === '8,000'",timeout=180000)
        startup=time.perf_counter()-start
        def get(id):return page.locator('#'+id).inner_text().strip()
        assert get('statchanges')=='900,000',get('statchanges')
        assert get('statfiles')=='0',get('statfiles')
        assert page.locator('#scrub').get_attribute('max')=='8000'
        page.locator('#scrub').fill('1')
        page.wait_for_function("document.querySelector('#statfiles')?.textContent === '80,000'",timeout=120000)
        page.locator('#pinA').click()
        assert get('statfiles')=='80,000'
        page.locator('#scrub').fill('8000')
        page.wait_for_function("document.querySelector('#timeposition')?.textContent?.includes('8000 / 8000')",timeout=120000)
        page.locator('#compare').click()
        compare=get('diffsummary')
        assert 'changed between frames' in compare,compare
        page.locator('#hotspots .hotspot-button').first.click(timeout=120000)
        assert get('inspectpath').startswith('src/')
        page.locator('#search').fill('file_00001.py')
        page.wait_for_timeout(500)
        page.locator('#search').fill('')
        page.locator('#scrub').fill('4000')
        page.wait_for_function("document.querySelector('#timeposition')?.textContent?.includes('4000 / 8000')",timeout=120000)
        page.locator('#scrub').fill('8000')
        page.wait_for_function("document.querySelector('#timeposition')?.textContent?.includes('8000 / 8000')",timeout=120000)
        page.wait_for_timeout(1000)
        heap=page.evaluate('''() => ({heapUsed:performance.memory?.usedJSHeapSize||null,
                                    heapTotal:performance.memory?.totalJSHeapSize||null,
                                    heapLimit:performance.memory?.jsHeapSizeLimit||null})''')
        assert not errors,errors
        assert not requests,requests
        assert not warnings,warnings
        result={
          'status':'PASS','fixture':'8,000 real Git commits / 80,000 tracked paths / 900,000 actual diff events',
          'html_bytes':HTML.stat().st_size,
          'html_sha256':hashlib.sha256(HTML.read_bytes()).hexdigest(),
          'startup_to_ready_seconds':round(startup,3),
          'final_files_shown':get('statfiles'),
          'commit_count_shown':get('statcommits'),
          'event_count_shown':get('statchanges'),
          'compare_summary':compare,
          'hotspot_and_search':'PASS',
          'timeline_jump_1_4000_8000':'PASS',
          'no_external_http_requests':not requests,
          'uncaught_javascript_errors':errors,
          'console_errors':warnings,
          'js_heap_bytes_at_end':heap,
          'browser':browser.version,
          'environment':platform.platform(),
          'limitations':['Chromium only','single test environment','sampled Git snapshot verification']
        }
        browser.close()
    REPORT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,sort_keys=True),flush=True)
if __name__=='__main__':main()
