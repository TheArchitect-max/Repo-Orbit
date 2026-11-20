"""v0.7 Chromium acceptance: accessible search, hostile XML and maximum viewer."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from repoorbit.render import render
from test_v6 import fixture

REPORT=ROOT/'evidence/v07_browser.json'


def main():
    report={'status':'HOLD','browser':None,'cases':{},'javascript_errors':[], 'network_requests':[]}
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
        report['browser']=b.version
        page=b.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce',accept_downloads=True)
        page.on('pageerror',lambda e:report['javascript_errors'].append(str(e)))
        page.on('request',lambda r:report['network_requests'].append(r.url) if r.url.startswith(('http://','https://')) else None)
        page.set_content((ROOT/'demo/RepoOrbit_Demo.html').read_text(encoding='utf8'),wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#statcommits').textContent==='32'",timeout=30000)
        search=page.locator('#search')
        search.fill('core.py')
        assert page.locator('#matchpanel').is_visible()
        count=page.locator('#matchcount').inner_text()
        assert 'matching files' in count and page.locator('.match-button').count()>0,count
        target=page.locator('.match-button').first
        expected=target.inner_text()
        target.focus()
        page.keyboard.press('Enter')
        assert page.locator('#inspectpath').inner_text()==expected
        assert page.locator('#inspectcount').inner_text().endswith('events')
        report['cases']['keyboard_accessible_file_search']={'status':'PASS','selected_file':expected}
        search.fill('unlikely_nonexistent_file_path')
        assert page.locator('#matchcount').inner_text()=='No matching files'
        assert page.locator('.match-button').count()==0
        search.fill('')
        assert not page.locator('#matchpanel').is_visible()
        report['cases']['bounded_search_states']='PASS'
        # Controls are relevant to keyboard users also when the selected file is absent.
        page.locator('#scrub').fill('0')
        search.fill('core.py')
        page.locator('.match-button').first.focus()
        page.keyboard.press('Enter')
        assert page.locator('#inspectpath').inner_text()=='src/core.py'
        assert 'FRAME' in page.locator('#timeposition').inner_text()
        report['cases']['keyboard_latest_event_navigation']='PASS'
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth-window.innerWidth')<=2
        assert page.locator('.match-button').first.is_visible()
        report['cases']['mobile_search_accessible']='PASS'

        bad=fixture()
        nasty='src/new\x01line\ufffe & <script> "name".py'
        bad['commits'][0]['changes'][0][1]=nasty
        bad['top_paths']=[[nasty,1]]
        page.set_content(render(bad,compression='plain'),wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#statcommits').textContent==='1'")
        page.locator('#scrub').fill('1')
        with page.expect_download() as d:
            page.locator('#exportsvgexact').click()
        xml=d.value.path().read_text(encoding='utf-8')
        document=ET.fromstring(xml)
        labels=[e.text for e in document.findall('.//{http://www.w3.org/2000/svg}circle/{http://www.w3.org/2000/svg}title')]
        assert labels==[nasty.replace('\x01','\ufffd').replace('\ufffe','\ufffd')],labels
        assert '&lt;script&gt;' in xml and '&amp;' in xml and '\x01' not in xml
        report['cases']['xml10_hostile_git_filename']={'status':'PASS','escaped_xml_bytes':len(xml.encode('utf-8'))}

        page.close()
        page=b.new_page(viewport={'width':1380,'height':900},reduced_motion='reduce',accept_downloads=True)
        page.on('pageerror',lambda e:report['javascript_errors'].append(str(e)))
        page.on('request',lambda r:report['network_requests'].append(r.url) if r.url.startswith(('http://','https://')) else None)
        page.set_content((ROOT/'demo/RepoOrbit_CombinedMaximum.html').read_text(encoding='utf8'),wait_until='domcontentloaded',timeout=120000)
        page.wait_for_function("document.querySelector('#statcommits').textContent==='8,000'",timeout=120000)
        page.locator('#scrub').fill('8000')
        page.wait_for_function("document.querySelector('#statfiles').textContent==='80,000'",timeout=120000)
        search=page.locator('#search')
        search.fill('src/cluster_')
        assert page.locator('.match-button').count()==24
        assert '80,000 matching' in page.locator('#matchcount').inner_text(),page.locator('#matchcount').inner_text()
        page.locator('.match-button').first.focus()
        page.keyboard.press('Enter')
        assert page.locator('#inspectpath').inner_text().startswith('src/cluster_')
        report['cases']['eighty_thousand_file_search']={'status':'PASS','result_dom_count':24}
        search.fill('')
        page.screenshot(path=str(ROOT/'demo/RepoOrbit_Preview.png'),full_page=True)
        assert not report['javascript_errors'],report['javascript_errors']
        assert not report['network_requests'],report['network_requests']
        b.close()
    report['status']='PASS'
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
