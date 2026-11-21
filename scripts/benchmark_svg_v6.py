"""Paired five-run SVG benchmark, identical embedded Git data for v0.5/v0.6.

Requires test-only Playwright and Chromium. No network, cloud or user data.
"""
from pathlib import Path
from statistics import median
from playwright.sync_api import sync_playwright
from xml.etree import ElementTree as ET
import json,re,time,hashlib,platform
R=Path(__file__).resolve().parents[1]
old=(R/'demo/RepoOrbit_CombinedMaximum_v05_reference.html').read_text(encoding='utf8')
newhtml=(R/'demo/RepoOrbit_CombinedMaximum.html').read_text(encoding='utf8')
def payload_bytes(html):
    match=re.search(r'<script type="application/json"[^>]*id="dataset">(.*?)</script>',html,re.S)
    assert match,'Missing embedded dataset'
    return match.group(1).encode('utf8')
assert payload_bytes(old)==payload_bytes(newhtml), 'v0.5 and v0.6 were not benchmarked on identical Git data'
input_payload_sha256=hashlib.sha256(payload_bytes(old)).hexdigest()
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-gpu','--js-flags=--max-old-space-size=3072'])
 result={'environment':{'python':platform.python_version(),'platform':platform.platform(),'chromium':b.version},'fixture':'Same v0.5.0 verified synthetic data: 8,000 commits, 80,000 files, 900,000 diff events','samples':5,'identical_dataset_sha256':input_payload_sha256}
 for key,content,buttons in [('v05',old,['exportsvg']),('v06',newhtml,['exportsvg','exportsvgexact'])]:
  page=b.new_page(viewport={'width':1300,'height':800},reduced_motion='reduce')
  errors=[];network=[]
  page.on('pageerror',lambda err: errors.append(str(err)))
  page.on('request',lambda req: network.append(req.url) if req.url.startswith(('http:', 'https:')) else None)
  page.set_content(content,wait_until='domcontentloaded',timeout=120000)
  page.wait_for_function("document.getElementById('statcommits').textContent==='8,000'",timeout=120000)
  page.locator('#scrub').fill('8000')
  page.wait_for_function("document.getElementById('statfiles').textContent==='80,000'",timeout=120000)
  page.evaluate("""() => {window.__svgBlobs=[];const original=URL.createObjectURL.bind(URL);URL.createObjectURL=b=>{window.__svgBlobs.push(b);return original(b)};HTMLAnchorElement.prototype.click=function(){};}""")
  result[key]={}
  for button in buttons:
   values=[]
   for i in range(5):
    elapsed=page.evaluate('''(id) => {const start=performance.now();document.getElementById(id).click();return performance.now()-start;}''',button)
    values.append(round(elapsed,3))
   xml=page.evaluate('window.__svgBlobs.at(-1).text()')
   root=ET.fromstring(xml)
   ns={'s':'http://www.w3.org/2000/svg'}
   bins=root.findall('s:rect',ns)
   bins=[x for x in bins if 'data-count' in x.attrib]
   represented=sum(int(el.attrib['data-count']) for el in bins)
   exact_nodes=root.findall('s:circle',ns)
   report={'bytes':len(xml.encode('utf-8')),'xml_wellformed':True,'density_cells':len(bins),'density_represented_nodes':represented,'exact_path_nodes':len(exact_nodes),'filename_present':('src/cluster_00/file_00000.py' in xml),'median_ms':round(median(values),3),'runs_ms':values,'sha256':hashlib.sha256(xml.encode('utf-8')).hexdigest()}
   result[key][button]=report
   print(key,button,json.dumps(report),flush=True)
  result[key]['page_errors']=errors;result[key]['external_network_requests']=network
  assert not errors and not network,(errors,network)
  page.close()
 b.close()
 oldr=result['v05']['exportsvg']; agg=result['v06']['exportsvg'];exact=result['v06']['exportsvgexact']
 result['improvement']={'overview_speed_x':round(oldr['median_ms']/agg['median_ms'],2),'overview_size_x':round(oldr['bytes']/agg['bytes'],2),'exact_speed_x':round(oldr['median_ms']/exact['median_ms'],2)}
 assert agg['density_represented_nodes']==80000
 assert agg['density_cells']<80000
 assert agg['exact_path_nodes']==0
 assert not agg['filename_present']
 assert exact['exact_path_nodes']==80000
 assert exact['filename_present']
 assert result['improvement']['overview_speed_x']>=10
 assert result['improvement']['overview_size_x']>=10
 report=R/'evidence/svg_comparison_v06.json'
 report.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
 print('COMPARISON_PASS',json.dumps(result['improvement']),flush=True)
