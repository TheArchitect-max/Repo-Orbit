"""Rebuild the v0.7 viewer from the bundled prior synthetic dataset.

No GitHub or network access. The synthetic fixture is preserved; the viewer
code is refreshed without rerunning a million-event Git fixture generator.
This script is a development/release helper, not a runtime requirement.
"""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from repoorbit.render import render, _packed_payload


def decode_embedded(path: Path) -> dict:
    source=path.read_text(encoding='utf-8')
    match=re.search(r'<script type="application/json" data-encoding="([^"]+)" id="dataset">(.*?)</script>',source,re.S)
    if not match: raise ValueError('No recognized embedded dataset')
    kind,content=match.groups()
    if kind=='gzip-base64':
        data=json.loads(gzip.decompress(base64.b64decode(content)))
    elif kind=='plain-json':
        data=json.loads(content)
    else:raise ValueError('Unsupported encoding '+kind)
    if data.get('packed')=='path-index-v1':
        paths=data.pop('paths');data.pop('packed')
        data['baseline']=[paths[i] for i in data['baseline']]
        data['top_paths']=[[paths[i],n] for i,n in data['top_paths']]
        for row in data['commits']:
            changes=row['changes']
            row['changes']=[[code,paths[id]] for code,id,*_ in changes]
            row['versions']=[v for _code,_id,v in changes]
    return data


def main():
    dest=ROOT/'demo/RepoOrbit_CombinedMaximum.html'
    data=decode_embedded(dest)
    before=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    assert len(data['commits'])==8000 and data['paths_total']==80000 and data['changes_total']==900000
    dest.write_text(render(data,compression='auto'),encoding='utf-8')
    roundtrip=decode_embedded(dest)
    after=json.dumps(roundtrip,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    assert before==after,'Data changed during viewer rebuild'
    report={'status':'PASS','cases':'8,000 synthetic commits / 80,000 unique paths / 900,000 events',
            'canonical_json_sha256':hashlib.sha256(before).hexdigest(),
            'bytes':dest.stat().st_size,'type':'retained prior synthetic dataset; not newly revalidated against Git trees'}
    (ROOT/'evidence/v07_dataset_rebuild.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
