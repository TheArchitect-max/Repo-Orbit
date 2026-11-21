"""Real Chromium comparison against v0.4 on identical 8k/30k Git data."""
from __future__ import annotations
import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
LARGE=ROOT/'demo/RepoOrbit_ScaleDemo.html'
OLD=ROOT.parent/'v04_scale_browser_reference.html'
LOG=ROOT/'evidence/browser_v5_scale.json'


def run(browser, source: Path, label: str) -> dict:
    page=browser.new_page(viewport={'width':1380,'height':900},reduced_motion='reduce',accept_downloads=True)
    errors=[];network=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:network.append(r.url) if r.url.startswith(('http://','https://')) else None)
    before=time.perf_counter()
    page.set_content(source.read_text(encoding='utf-8'),wait_until='domcontentloaded',timeout=90000)
    page.wait_for_function("document.querySelector('#statcommits').textContent === '8,000'",timeout=90000)
    init_seconds=round(time.perf_counter()-before,3)
    assert page.locator('#statchanges').inner_text()=='69,995'
    assert page.locator('#statfiles').inner_text()=='0'
    page.evaluate('''() => {
      window.__measureDraw=[];
      const raf=window.requestAnimationFrame.bind(window);
      window.requestAnimationFrame=cb=>raf(ts=>{
        const started=performance.now();cb(ts);
        if(cb.name==='draw')window.__measureDraw.push(performance.now()-started);
      });
    }''')
    for target in [8000,4000,2000,6000,1,8000]:
        page.locator('#scrub').fill(str(target))
        page.wait_for_timeout(110)
    assert page.locator('#statfiles').inner_text()=='30,000'
    assert page.locator('#timeposition').inner_text()=='FRAME 8000 / 8000'
    durations=page.evaluate('window.__measureDraw')
    if len(durations)<5:raise AssertionError(f'Missing timed draw callbacks in {label}: {durations}')
    median_ms=round(statistics.median(durations[-6:]),3)
    if label=='v0.5':
        assert page.locator('#frameinfo').inner_text()=='30,000 TRACKED FILES'
        # A/B comparison remains exact and independent of graphical clustering.
        page.locator('#scrub').fill('0')
        page.locator('#pinA').click()
        page.locator('#scrub').fill('8000')
        page.locator('#compare').click()
        assert '30,000 added' in page.locator('#diffsummary').inner_text(),page.locator('#diffsummary').inner_text()
        assert '0 removed' in page.locator('#diffsummary').inner_text()
        page.locator('#compare').click()
        page.locator('#hotspots .hotspot-button').first.click()
        assert page.locator('#inspectpath').inner_text().endswith('.py')
        page.locator('#search').fill('file_00001.py')
        page.wait_for_timeout(60)
        assert not errors,errors
        assert not network,network
        # Compress data must remain fully local, no external APIs or images.
    else:
        assert not errors,errors
        assert not network,network
    result={'engine':label,'startup_seconds':init_seconds,'render_median_ms':median_ms,
            'draw_runs_ms':[round(x,3) for x in durations[-6:]],
            'javascript_errors':errors,'network_requests':network}
    page.close()
    return result


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline-html',type=Path,default=OLD,help='Standalone v0.4 viewer using identical 8k/30k fixture data (optional)')
    args=parser.parse_args()
    assert LARGE.is_file(), 'First run scripts/scale_v5.py to generate a real 8k/30k dataset'
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
        # Run the baseline first to avoid the new viewer warming old code unfairly.
        legacy=run(browser,args.baseline_html,'v0.4') if args.baseline_html.is_file() else None
        current=run(browser,LARGE,'v0.5')
        browser.close()
    result={'status':'PASS', 'fixture':'8,000 real Git commits / 30,000 files / 69,995 events',
            'measurement':'Timing is per scheduled Canvas draw callback; includes density drawing and bucket construction',
            'v04':legacy,'v05':current,
            'render_speedup_x':round(legacy['render_median_ms']/current['render_median_ms'],3) if legacy else None,
            'disclaimer':'Single Chromium environment; measurements vary by hardware, viewport, filters, and file distribution.'}
    LOG.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__':main()
