"""Chromium acceptance for v0.4 growth trend and non-empty bounded history."""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from repoorbit.core import analyze
from repoorbit.render import render

def git(repo,*args):subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)

def main():
    with tempfile.TemporaryDirectory(prefix='orbit-v4-browser-') as tmp:
        repo=Path(tmp)
        git(repo,'init','-q');git(repo,'config','user.name','CI');git(repo,'config','user.email','ci@example.invalid')
        for index in range(3):
            if index==0:
                (repo/'a.py').write_text('a');(repo/'b.py').write_text('b')
            elif index==1:(repo/'c.py').write_text('c')
            else:(repo/'a.py').unlink()
            git(repo,'add','-A');git(repo,'commit','-qm',f'event {index}')
        report=analyze(repo,limit=2,verification='full')
        assert report['baseline']==['a.py','b.py']
        assert report['files_final']==2
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1280,'height':860})
            errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append(r.url) if r.url.startswith(('https:','http:')) else None)
            page.set_content(render(report))
            assert page.locator('#growth').get_attribute('aria-pressed')=='true'
            before=page.locator('#activity').evaluate('(c)=>c.toDataURL()')
            page.locator('#growth').click()
            after=page.locator('#activity').evaluate('(c)=>c.toDataURL()')
            assert before!=after,'The growth overlay toggle did not change the chart'
            assert page.locator('#growth').get_attribute('aria-pressed')=='false'
            page.locator('#growth').click()
            assert page.locator('#growth').get_attribute('aria-pressed')=='true'
            assert page.locator('#statfiles').inner_text()=='2'
            page.locator('#scrub').fill('1')
            assert page.locator('#statfiles').inner_text()=='3'
            page.locator('#scrub').fill('2')
            assert page.locator('#statfiles').inner_text()=='2'
            page.locator('#pinA').click()
            page.locator('#scrub').fill('0')
            page.locator('#compare').click()
            assert '1 added' in page.locator('#diffsummary').inner_text()
            assert '1 removed' in page.locator('#diffsummary').inner_text()
            assert not errors,errors
            assert not requests,requests
            browser.close()
        print('Browser v4: PASS — growth overlay toggles, nonempty baseline count, file lifecycle, A/B, offline, no JS exceptions')
if __name__=='__main__':main()
