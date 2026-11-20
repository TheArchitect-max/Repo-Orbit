"""Build a fully synthetic sample Git repo with actual commits and render the viewer.

No personal repositories, user data, or external downloads are involved.
"""
from __future__ import annotations
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repoorbit.core import analyze
from repoorbit.render import render


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def build(target: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="orbit-demo-") as temporary:
        repo=Path(temporary)/"Polaris-Engine";repo.mkdir()
        git(repo,"init","-q")
        git(repo,"config","user.email","demo@example.invalid")
        git(repo,"config","user.name","Demo Contributor")
        scenes=[
            ("First light: a new idea",{"README.md":"# Polaris Engine\n", ".gitignore":"__pycache__/\n"},[]),
            ("Lay the foundations",{"src/core.py":"def orbit(): return 1\n","src/settings.py":"MODE = 'demo'\n"},[]),
            ("Document our flight plan",{"docs/architecture.md":"# Architecture\n","docs/roadmap.md":"# Roadmap\n"},[]),
            ("Build the first instrument panel",{"web/index.html":"<h1>Polaris</h1>\n","web/style.css":"body {color: white}\n"},[]),
            ("Tests start telling the truth",{"tests/test_core.py":"assert 1 == 1\n","src/core.py":"def orbit(): return 2\n"},[]),
            ("Expand the star map",{"assets/sky.json":"{\"stars\": 300}\n","src/render.py":"def render(): return 'sky'\n"},[]),
            ("Fix navigation drift",{"src/navigation.py":"def navigate(): return True\n","tests/test_navigation.py":"assert True\n"},[]),
            ("Ship a working preview",{"web/app.js":"console.log('hello orbit')\n","web/index.html":"<h1>Polaris Live</h1>\n"},[]),
            ("Retire the old settings file",{"src/config.py":"MODE = 'stable'\n"},["src/settings.py"]),
            ("Add an engine diagnostics module",{"src/telemetry.py":"def health(): return 'ok'\n","tests/test_telemetry.py":"assert 'ok' == 'ok'\n"},[]),
            ("Write the integration guide",{"docs/integration.md":"# Integration guide\n","README.md":"# Polaris Engine\nA sample codebase.\n"},[]),
            ("Release 1.0: ready for exploration",{"CHANGELOG.md":"# 1.0\n","src/core.py":"def orbit(): return 3\n","web/style.css":"body {color: mintcream}\n"},[]),
        ]
        # More realistic scale: 20 additional commits create many real files,
        # modifications and deletions. The viewer never consumes mock events.
        areas=['navigation','rendering','storage','telemetry','api','editor','pipeline','search','geometry','testing']
        for step in range(20):
            area=areas[step % len(areas)]
            created={}
            for n in range(12):
                seq=step*12+n
                if n<7:
                    path=f'src/{area}/module_{seq:03d}.py'
                    body=f'"""Synthetic module {seq}."""\ndef build_{seq}(): return {seq}\n'
                elif n<10:
                    path=f'tests/{area}/test_module_{seq:03d}.py'
                    body=f'def test_{seq}(): assert {seq} >= 0\n'
                elif n==10:
                    path=f'docs/{area}/guide_{step:02d}.md'
                    body=f'# {area.title()} guide {step}\nThis is synthetic demo material.\n'
                else:
                    path=f'assets/{area}/theme_{step:02d}.json'
                    body='{"synthetic":true}\n'
                created[path]=body
            # Repeatedly update genuine historical files, not only add them.
            created['src/core.py']=f'def orbit(): return {step + 4}\n'
            scene_title=[
                'Stabilize module boundaries','Introduce the navigation contracts',
                'Design the rendering primitives','Constrain storage access',
                'Improve runtime introspection','Expand client capabilities',
                'Expose public module APIs','Add targeted integration coverage',
                'Rework geometry transforms','Strengthen regression tests',
            ][step % 10]
            scenes.append((f'{scene_title} · iteration {step+1}',created,[]))
        for index,(message,changes,deletions) in enumerate(scenes):
            for name,body in changes.items():
                file=repo/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(body)
            for name in deletions:(repo/name).unlink()
            git(repo,"add","-A")
            git(repo,"commit","-q","-m",message)
        data=analyze(repo,limit=len(scenes),share_safe=False)
        if data["history_window"] != len(scenes) or data["files_final"] < 200:
            raise AssertionError(f"Unexpected demo data: {data['history_window']}, {data['files_final']}")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(render(data),encoding="utf-8")
        print(f"Generated {target} ({target.stat().st_size:,} bytes) from {len(scenes)} real Git commits")

if __name__ == '__main__':
    build(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'demo'/'RepoOrbit_Demo.html')
