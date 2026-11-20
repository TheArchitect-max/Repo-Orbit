"""Large, reproducible, fully synthetic Git-object scale acceptance."""
from __future__ import annotations
import json,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from repoorbit.core import analyze
from repoorbit.render import render

def git(p,*a):
    subprocess.run(['git','-C',str(p),*a],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)

def main():
    with tempfile.TemporaryDirectory(prefix='orbit-stress-') as t:
        p=Path(t)
        git(p,'init','-q');git(p,'config','user.name','Stress Bot');git(p,'config','user.email','synthetic@example.invalid')
        for c in range(100):
            for k in range(100):
                file=p/'pkg'/f'mod_{c%10}'/f'file_{c:03d}_{k:03d}.py'
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text(f'# synthetic {c}-{k}\n')
            git(p,'add','-A');git(p,'commit','-qm',f'fixture {c}')
        started=time.perf_counter()
        obj=analyze(p,limit=100,verification='sample')
        analysis_ms=round((time.perf_counter()-started)*1000)
        html=render(obj)
        assert obj['files_final']==10000,obj['files_final']
        assert obj['changes_total']==10000,obj['changes_total']
        assert obj['verified_frames']==3
        assert len(html.encode('utf-8'))<32*1024*1024
        report={'fixture':'100 real Git commits * 100 new tracked paths each',
           'paths_final':obj['files_final'],'events':obj['changes_total'],
           'verified_frames':obj['verified_frames'],
           'analysis_ms':analysis_ms,'html_bytes':len(html.encode('utf-8')),
           'platform':sys.platform,'python':sys.version.split()[0],
           'scope':'Single synthetic fixture; not a general throughput or browser-load guarantee.'}
        (ROOT/'evidence'/'stress_10k.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
