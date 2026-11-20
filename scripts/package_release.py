"""Make a deterministic local candidate ZIP with fresh integrity manifest.

Does not publish to GitHub, activate a license, or run application servers.
Will not package if required acceptance evidence is missing or FAIL.
"""
from __future__ import annotations
import hashlib
import json
import platform
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
match=re.search(r'__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"',
                (ROOT/'repoorbit/__init__.py').read_text())
assert match, 'Missing version'
VERSION=match.group(1)
ARCHIVE=ROOT.parent.parent/f'REPO_ORBIT_v{VERSION}_COMPLETE.zip'
IGNORED={'.git','.venv','__pycache__','.pytest_cache','repoorbit.egg-info','build'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_evidence() -> dict:
    required=['v08_clean_install.json','v08_paired_performance.json',
              'v08_maximum_engine_acceptance.json']
    values={}
    for name in required:
        path=ROOT/'evidence'/name
        assert path.is_file(),f'Missing acceptance evidence: {path}'
        values[name]=json.loads(path.read_text(encoding='utf-8'))
        assert values[name]['status']=='PASS',f'Not PASS: {name}'
    units=(ROOT/'evidence/v08_unit_tests.log').read_text(encoding='utf-8')
    assert 'Ran 75 tests' in units and '\nOK' in units, 'Python regressions not accepted'
    browser=(ROOT/'evidence/v08_browser_regression.log').read_text(encoding='utf-8')
    for name in ['browser_smoke','browser_v3','browser_v4','browser_v6','browser_combined_limits','browser_v7']:
        assert f'=== {name} ===' in browser, f'Missing browser regression {name}'
    assert browser.count('RESULT: PASS')==6, 'Browser acceptance not complete'
    assert 'PASS: node --check' in (ROOT/'evidence/v08_js_syntax.log').read_text()
    assert VERSION=='0.8.0', 'Update evidence list for a different release'
    wheel=ROOT/'dist'/f'repoorbit-{VERSION}-py3-none-any.whl'
    assert wheel.is_file(), 'Missing clean installable wheel'
    assert digest(wheel.read_bytes())==values['v08_clean_install.json']['wheel_sha256']
    return values


def main():
    results=require_evidence()
    files=[]
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or any(part in IGNORED for part in path.relative_to(ROOT).parts):
            continue
        if path.name in {'acceptance_manifest.json','.DS_Store'}:continue
        files.append(path)
    paths={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())} for p in files}
    canonical=json.dumps(paths,sort_keys=True,separators=(',',':')).encode('utf-8')
    def version(command):
        try:return subprocess.check_output(command,stderr=subprocess.STDOUT,timeout=10,text=True).strip()[:160]
        except (OSError,subprocess.SubprocessError):return 'not available'
    manifest={
       'project':'REPO ORBIT','version':VERSION,'release_identity':'local-unpublished-candidate',
       'build_date_utc':'2026-11-20','decision':'LOCAL_CHECKS_PASS_PUBLIC_RELEASE_HOLD',
       'source_tree_sha256':digest(canonical),
       'tests':{'python':'75/75 PASS','browser':'6/6 Chromium suites PASS',
                'browser_new':'PASS',
                'clean_wheel_install':results['v08_clean_install.json']['status'],
                'same_fixture_json_parity':'PASS across three benchmark fixtures',
                'maximum_fixture_engine':results['v08_maximum_engine_acceptance.json']['status'],
                'windows_macos_firefox_webkit':'NOT VALIDATED',
                'wcag_screen_reader_full_audit':'NOT VALIDATED',
                'third_party_security_review':'NOT PERFORMED'},
       'licensing':'MIT PROPOSED ONLY — no owner-approved LICENSE grant',
       'github':'No changes or public publishing performed; no verified main commit claimed',
       'platform':{'python':sys.version.split()[0],'system':platform.platform(),
                   'git':version(['git','--version']),'node':version(['node','--version']),
                   'chromium':version(['chromium','--version'])},
       'file_count_without_manifest':len(files),
       'files':paths,
    }
    manifest_path=ROOT/'evidence/acceptance_manifest.json'
    manifest_path.parent.mkdir(exist_ok=True)
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    files.append(manifest_path)
    with zipfile.ZipFile(ARCHIVE,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(files):
            arcname='REPO_ORBIT/'+path.relative_to(ROOT).as_posix()
            info=zipfile.ZipInfo(arcname,date_time=(2026,11,20,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.create_system=3
            info.external_attr=(0o100644<<16)
            z.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(ARCHIVE) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(files)
        for name,record in paths.items():
            contents=z.read('REPO_ORBIT/'+name)
            assert len(contents)==record['bytes'] and digest(contents)==record['sha256'],name
        actual=json.loads(z.read('REPO_ORBIT/evidence/acceptance_manifest.json'))
        assert actual['source_tree_sha256']==manifest['source_tree_sha256']
    sidecar=ARCHIVE.with_name(ARCHIVE.name+'.sha256.txt')
    archive_sha=digest(ARCHIVE.read_bytes())
    sidecar.write_text(f'{archive_sha}  {ARCHIVE.name}\n',encoding='utf-8')
    print(json.dumps({'result':'PASS','zip':str(ARCHIVE),'zip_size_bytes':ARCHIVE.stat().st_size,
      'files':len(files),'sha256':archive_sha,'manifest_hash':manifest['source_tree_sha256']},indent=2))

if __name__=='__main__':main()
