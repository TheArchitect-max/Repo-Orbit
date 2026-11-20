"""v0.6 browser acceptance: exact/aggregated SVG, privacy boundary and replay.

Requires: chromium and playwright (test-only, never runtime dependencies).
"""
from __future__ import annotations
import hashlib
import json
import platform
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from repoorbit.render import render
from test_v6 import fixture

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence'/'browser_v6.json'
NS={'s':'http://www.w3.org/2000/svg'}


def capture(page, selector):
    page.evaluate("""() => {window.__captures=[];const original=URL.createObjectURL.bind(URL);URL.createObjectURL=b=>{window.__captures.push(b);return original(b)};HTMLAnchorElement.prototype.click=function(){};}""")
    page.locator(selector).click(timeout=60000)
    text=page.evaluate('window.__captures.at(-1).text()')
    doc=ET.fromstring(text)
    assert doc.tag.endswith('svg')
    return text,doc


def main():
    results={'chromium':'','source':'repoorbit-v0.6.0','case_results':{},'network_requests':[], 'errors':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True, executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
            args=['--no-sandbox','--disable-gpu','--js-flags=--max-old-space-size=3072'])
        results['chromium']=browser.version
        context=browser.new_context(viewport={'width':1300,'height':800}, reduced_motion='reduce')
        page=context.new_page()
        page.on('pageerror',lambda exc:results['errors'].append(str(exc)))
        page.on('request',lambda req:results['network_requests'].append(req.url) if req.url.startswith(('http:','https:')) else None)
        page.set_content((ROOT/'demo/RepoOrbit_Demo.html').read_text(encoding='utf8'), wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#statcommits').textContent === '32'",timeout=60000)
        assert page.locator('#statfiles').inner_text()=='0'
        page.locator('#scrub').fill('32')
        page.wait_for_function("document.querySelector('#statfiles').textContent !== '0'")
        small_exact,parsed=capture(page,'#exportsvgexact')
        nodes=parsed.findall('s:circle',NS)
        assert len(nodes)==int(page.locator('#statfiles').inner_text().replace(',','')),(len(nodes),page.locator('#statfiles').inner_text())
        assert len(nodes)>200
        assert all(e.find('s:title',NS) is not None for e in nodes)
        results['case_results']['small_exact_svg']={'status':'PASS','nodes':len(nodes),'bytes':len(small_exact.encode())}
        page.locator('#scrub').fill('1')
        page.locator('#pinA').click()
        page.locator('#scrub').fill('32')
        page.locator('#compare').click()
        assert 'added' in page.locator('#diffsummary').inner_text()
        results['case_results']['snapshot_comparison']='PASS'
        page.locator('#viewmode').click()
        assert 'ATLAS' in page.locator('#viewlabel').inner_text()
        page.locator('#search').fill('src/core.py')
        page.locator('#exportsvg').click()
        results['case_results']['atlas_and_filter']='PASS'

        # Adversarial input: source metadata must never execute or corrupt XML.
        attack=render(fixture(),compression='plain')
        page.set_content(attack,wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#statcommits').textContent === '1'")
        page.locator('#scrub').fill('1')
        malicious,doc=capture(page,'#exportsvgexact')
        names=[node.text for node in doc.findall('.//s:circle/s:title',NS)]
        expected=fixture()['commits'][0]['changes'][0][1]
        assert names==[expected],names
        assert not page.evaluate('Boolean(window.XSS)')
        assert '&lt;tag&gt;' in malicious and '&amp;' in malicious
        results['case_results']['adversarial_xml_escape']={'status':'PASS','exact_name_preserved':True,'bytes':len(malicious.encode())}
        page.close()

        page=context.new_page()
        page.on('pageerror',lambda exc:results['errors'].append(str(exc)))
        page.on('request',lambda req:results['network_requests'].append(req.url) if req.url.startswith(('http:','https:')) else None)
        page.set_content((ROOT/'demo/RepoOrbit_CombinedMaximum.html').read_text(encoding='utf8'), wait_until='domcontentloaded', timeout=120000)
        page.wait_for_function("document.querySelector('#statcommits').textContent === '8,000'",timeout=120000)
        assert page.locator('#statchanges').inner_text()=='900,000'
        page.locator('#scrub').fill('8000')
        page.wait_for_function("document.querySelector('#statfiles').textContent === '80,000'",timeout=120000)
        overview,doc=capture(page,'#exportsvg')
        rects=[x for x in doc.findall('s:rect',NS) if 'data-count' in x.attrib]
        represented=sum(int(el.attrib['data-count']) for el in rects)
        assert represented==80000,represented
        assert not doc.findall('s:circle',NS)
        assert 'src/cluster_00/file_00000.py' not in overview
        assert len(overview.encode())<250000
        results['case_results']['max_density_export']={'status':'PASS','represented_nodes':represented,'cells':len(rects),'bytes':len(overview.encode())}
        # Zooming in means the user is asking for an exact export; the button
        # safely switches back to exact paths rather than pretending a lossy
        # overview is a full snapshot.
        page.locator('#orbit').hover()
        for _ in range(7):
            page.locator('#orbit').dispatch_event('wheel',{'deltaY':-120})
        page.wait_for_timeout(180)
        zoomed,doc=capture(page,'#exportsvg')
        circle_count=len(doc.findall('s:circle',NS))
        assert circle_count>0 and not any('data-count' in el.attrib for el in doc.findall('s:rect',NS))
        results['case_results']['zoom_exact_fallback']={'status':'PASS','visible_circles':circle_count}
        assert not results['errors'],results['errors']
        assert not results['network_requests'],results['network_requests']
        context.close();browser.close()
    results['status']='PASS';results['platform']=platform.platform()
    OUT.write_text(json.dumps(results,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps(results,indent=2,sort_keys=True),flush=True)

if __name__=='__main__':main()
