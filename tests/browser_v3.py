"""Real Chromium acceptance for exact object identity vs transient touch activity."""
from __future__ import annotations
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from repoorbit.core import analyze
from repoorbit.render import render

def git(repo,*args):
    subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)


def main():
    with tempfile.TemporaryDirectory(prefix='orbit-browser-v3-') as temp:
        repo=Path(temp)
        git(repo,'init','-q');git(repo,'config','user.email','accept@example.invalid')
        git(repo,'config','user.name','Acceptance Robot')
        code=repo/'code.py';code.write_text('start\n')
        git(repo,'add','-A');git(repo,'commit','-qm','initial commit')
        code.write_text('temporary version\n')
        git(repo,'add','-A');git(repo,'commit','-qm','intermediate update')
        code.write_text('start\n')
        git(repo,'add','-A');git(repo,'commit','-qm','restore original')
        data=analyze(repo,verification='full')
        assert data['verified_frames']==3
        assert data['commits'][0]['versions'][0]==data['commits'][2]['versions'][0]
        html=render(data)
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1360,'height':920})
            errors=[];requests=[]
            page.on('pageerror',lambda exc:errors.append(str(exc)))
            page.on('request',lambda r: requests.append(r.url) if r.url.startswith(('http:','https:')) else None)
            page.set_content(html)
            assert 'Hotspot explorer' in page.content()
            assert page.locator('#statcommits').inner_text()=='3'
            page.locator('#scrub').fill('1')
            assert page.locator('#statfiles').inner_text()=='1'
            page.locator('#pinA').click()
            page.locator('#scrub').fill('2')
            page.locator('#compare').click()
            assert '1 changed' in page.locator('#diffsummary').inner_text(),page.locator('#diffsummary').inner_text()
            page.locator('#scrub').fill('3')
            page.locator('#compare').click()
            assert '0 changed' in page.locator('#diffsummary').inner_text(),page.locator('#diffsummary').inner_text()
            assert 'No net object/mode changes' in page.locator('#diffdetails').inner_text()
            page.locator('#hotspots .hotspot-button').first.click()
            assert page.locator('#inspectpath').inner_text()=='code.py'
            assert page.locator('#timeposition').inner_text()=='FRAME 3 / 3'
            assert page.locator('#inspectcount').inner_text()=='3 events'
            # Keyboard step-back from a non-input target.
            page.locator('body').click(position={'x':3,'y':3})
            page.keyboard.press('ArrowLeft')
            assert page.locator('#timeposition').inner_text()=='FRAME 2 / 3'
            assert not errors,errors
            assert not requests,requests
            browser.close()
        print('Browser v3: PASS — exact changed/reverted semantics, hotspots, inspector, keyboard, offline, no JS exceptions')

if __name__=='__main__':main()
