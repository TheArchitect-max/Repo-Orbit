"""Single-commit 80,000-file bound test using genuine Git tree objects."""
from __future__ import annotations
import json
import resource
import sys
import tempfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
from scale_v5 import create_fixture
from repoorbit.core import MAX_PATHS, analyze
from repoorbit.render import render


def main():
    if MAX_PATHS!=80000:raise AssertionError('Expected cap 80,000')
    with tempfile.TemporaryDirectory(prefix='orbit-v5-80k-') as directory:
        root=Path(directory)/'Synthetic80k'
        started=time.perf_counter()
        create_fixture(root,commits=1,paths=80000,changes=0)
        setup_s=round(time.perf_counter()-started,3)
        started=time.perf_counter()
        data=analyze(root,limit=1,verification='full')
        analysis_s=round(time.perf_counter()-started,3)
        if data['files_final']!=80000 or data['changes_total']!=80000 or data['verified_frames']!=1:
            raise AssertionError('80k exact bound was not faithfully replayed')
        html=render(data)
        report={'status':'PASS','fixture':'1 genuine Git root commit with 80,000 distinct tracked files',
                'files_final':data['files_final'],'changes_total':data['changes_total'],
                'verification':data['verification'],'verified_frames':data['verified_frames'],
                'git_build_seconds':setup_s,'analyze_seconds':analysis_s,'html_bytes':len(html.encode()),
                'python_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'disclaimer':'Synthetic local Linux fixture. Not a guarantee at 8,000 commits plus 80,000 paths.'}
        out=ROOT/'evidence'/'stress_80k.json'
        out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2,sort_keys=True))

if __name__=='__main__':main()
