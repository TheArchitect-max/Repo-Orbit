"""Create a truthful animated GitHub README preview from the REAL browser viewer.

Optional development dependencies: Playwright and Pillow. Both absent at runtime.
"""
from __future__ import annotations
import io
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'demo'/'RepoOrbit_Demo.html'
TARGET=ROOT/'demo'/'RepoOrbit_Replay.gif'


def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    frames=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1300,'height':850},device_scale_factor=1)
        try:page.goto(DOC.as_uri())
        except Exception as error:
            if 'ERR_BLOCKED_BY_ADMINISTRATOR' not in str(error):raise
            page.close()
            page=browser.new_page(viewport={'width':1300,'height':850},device_scale_factor=1)
            page.set_content(DOC.read_text(encoding='utf-8'),wait_until='load')
        page.wait_for_timeout(70)
        for n in [0,1,3,6,9,12,16,20,24,28,32,32]:
            page.locator('#scrub').fill(str(n))
            # Screenshots are captured from the real renderer, not painted simulations.
            page.wait_for_timeout(70)
            png=page.locator('.workspace').screenshot(type='png',animations='disabled')
            photo=Image.open(io.BytesIO(png)).convert('RGB')
            photo.thumbnail((1050,520),Image.Resampling.LANCZOS)
            pal=photo.quantize(colors=96,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
            frames.append(pal)
        browser.close()
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    frames[0].save(TARGET,save_all=True,append_images=frames[1:],loop=0,
                   duration=[850]+[480]*10+[1100],optimize=True,disposal=2)
    with Image.open(TARGET) as check:
        assert 10<=check.n_frames<=len(frames)
    print(f'Generated REAL 12-frame GIF: {TARGET} ({TARGET.stat().st_size:,} bytes)')

if __name__=='__main__':main()
