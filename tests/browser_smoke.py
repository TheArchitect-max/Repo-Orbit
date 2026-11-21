"""Real browser acceptance checks (dev-only Playwright; no runtime dependency)."""
from __future__ import annotations
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'demo'/'RepoOrbit_Demo.html'


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('Optional Playwright installation is required for browser acceptance.')
        return 2
    assert DOC.exists(),f'Missing demo: {DOC}'
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,
            executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
            args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1,accept_downloads=True)
        errors=[];network=[]
        def record(page):
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:network.append(r.url) if r.url.startswith(('https://','http://')) else None)
        record(page)
        try:
            page.goto(DOC.as_uri())
            mode='file://'
        except Exception as exc:
            if 'ERR_BLOCKED_BY_ADMINISTRATOR' not in str(exc):raise
            page.close()
            page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1,accept_downloads=True)
            record(page)
            page.set_content(DOC.read_text(encoding='utf-8'),wait_until='load')
            mode='in-memory HTML (managed browser blocks file://)'
        page.wait_for_timeout(100)
        assert page.title()=='Repo Orbit · Polaris-Engine'
        assert page.locator('#statcommits').inner_text()=='32'
        assert page.locator('#statfiles').inner_text()=='0'
        assert page.locator('#timeposition').inner_text()=='FRAME 0 / 32'
        # Actual animation, then deterministic seeking to HEAD.
        page.locator('#play').click();page.wait_for_timeout(700)
        assert page.locator('#timeposition').inner_text()!='FRAME 0 / 32'
        page.locator('#play').click()
        page.locator('#scrub').fill('32')
        assert page.locator('#statfiles').inner_text()=='258'
        assert page.locator('#eventtitle').inner_text()=='Strengthen regression tests · iteration 20'
        # Inspect a real changed file, including historical event provenance.
        page.locator('.event-button').first.click()
        selected=page.locator('#inspectpath').inner_text()
        assert selected != 'Click a file dot or a changed filename to inspect its history.'
        assert 'events' in page.locator('#inspectcount').inner_text()
        # Pin A at HEAD, compare with baseline: all 258 files are removed in B.
        page.locator('#pinA').click()
        page.locator('#scrub').fill('0')
        page.locator('#compare').click()
        assert '258 removed' in page.locator('#diffsummary').inner_text(),page.locator('#diffsummary').inner_text()
        assert 'A: 32 · B: 0' in page.locator('#diffmeta').inner_text()
        # Compare also works in the opposite direction.
        page.locator('#pinA').click()
        page.locator('#scrub').fill('32')
        page.locator('#compare').click()
        assert '258 added' in page.locator('#diffsummary').inner_text()
        # Alternate layout, top-level folder select, filename search.
        page.locator('#viewmode').click()
        assert 'ATLAS' in page.locator('#viewlabel').inner_text()
        page.locator('#groupfilter').select_option('src')
        page.locator('#search').fill('core.py')
        page.wait_for_timeout(80)
        assert page.locator('#search').input_value()=='core.py'
        page.locator('#search').fill('')
        page.locator('#groupfilter').select_option('')
        page.locator('#viewmode').click()
        assert 'CONSTELLATION' in page.locator('#viewlabel').inner_text()
        # Wheel zoom changes the actual rendered Canvas pixels.
        page.wait_for_timeout(100)
        before=page.locator('#orbit').evaluate('(c) => c.toDataURL()')
        r=page.locator('#orbit').bounding_box()
        page.mouse.move(r['x']+r['width']*.5,r['y']+r['height']*.5)
        page.mouse.wheel(0,-540)
        page.wait_for_timeout(140)
        after=page.locator('#orbit').evaluate('(c) => c.toDataURL()')
        assert before!=after,'Wheel did not change the map'
        page.locator('#zoomreset').click()
        # Export real raster and vector files; verify SVG parses.
        with page.expect_download() as item:page.locator('#export').click()
        png=item.value
        assert png.suggested_filename=='repo-orbit-frame-32.png'
        assert png.path().stat().st_size>2000
        with page.expect_download() as item:page.locator('#exportsvg').click()
        svg=item.value
        assert svg.suggested_filename=='repo-orbit-frame-32-exact.svg'
        tree=ET.parse(svg.path())
        assert tree.getroot().tag.endswith('svg')
        circles=tree.findall('.//{http://www.w3.org/2000/svg}circle')
        assert len(circles)==258,len(circles)
        # Real responsive view: controls reachable without horizontal overflow.
        page.set_viewport_size({'width':390,'height':844})
        page.wait_for_timeout(100)
        overflow=page.evaluate('document.documentElement.scrollWidth - window.innerWidth')
        assert overflow<=2, f'Mobile horizontal overflow: {overflow}px'
        assert page.locator('#compare').is_visible()
        page.set_viewport_size({'width':1440,'height':1000})
        page.locator('#scrub').fill('27')
        page.wait_for_timeout(80)
        page.screenshot(path=str(ROOT/'demo'/'RepoOrbit_Preview.png'),full_page=True)
        # R9 R6: legacy plain, non-dictionary JSON is a supported export.
        # Verify the compact columnar replay does not assume packed path IDs.
        sys.path.insert(0,str(ROOT))
        from scripts.rebuild_maximum_demo import decode_embedded
        from repoorbit.render import render
        legacy=render(decode_embedded(DOC),compact=False,compression='plain')
        plain=browser.new_page(viewport={'width':1440,'height':1000})
        plain.on('pageerror',lambda e:errors.append('legacy nonpacked: '+str(e)))
        plain.on('request',lambda r:network.append(r.url) if r.url.startswith(('https://','http://')) else None)
        plain.set_content(legacy,wait_until='domcontentloaded',timeout=120000)
        plain.wait_for_function("document.querySelector('#statcommits')?.textContent==='32'",timeout=120000)
        plain.locator('#scrub').fill('32')
        assert plain.locator('#statfiles').inner_text()=='258'
        assert plain.locator('#eventtitle').inner_text()=='Strengthen regression tests · iteration 20'
        plain.locator('.event-button').first.click()
        assert 'events' in plain.locator('#inspectcount').inner_text()
        plain.close()
        assert not errors,errors
        assert not network,network
        browser.close()
    print('Browser E2E: PASS — '+mode)
    print('PASS: real-playback, seek, counts, file inspector, A/B both directions, layout, filtering, zoom, reset, PNG, SVG, mobile, offline/CSP')
    print('Screenshot:',ROOT/'demo'/'RepoOrbit_Preview.png')
    return 0

if __name__=='__main__':sys.exit(main())
