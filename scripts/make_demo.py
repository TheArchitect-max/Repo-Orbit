"""Build a fully synthetic sample Git repo with actual commits and render the viewer.

No personal repositories, user data, or external downloads are involved.
"""
from __future__ import annotations
import subprocess
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repoorbit.core import analyze
from repoorbit.render import render


_COMMIT_INDEX = 0


def git(repo: Path, *args: str) -> None:
    global _COMMIT_INDEX
    # This fixture must reproduce the exact committed HTML independently of
    # the operator's Colab/Git identity, signing settings or global config.
    # Inherited GIT_* values override `git config user.*` and can silently
    # change the SHA of every one of the 32 real synthetic commits.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_DEFAULT_HASH="sha1",
        GIT_AUTHOR_NAME="Demo Contributor",
        GIT_AUTHOR_EMAIL="demo@example.invalid",
        GIT_COMMITTER_NAME="Demo Contributor",
        GIT_COMMITTER_EMAIL="demo@example.invalid",
    )
    if args and args[0] == 'commit':
        epoch = str(1700000000 + _COMMIT_INDEX)
        env.update(GIT_AUTHOR_DATE=epoch + ' +0000',
                   GIT_COMMITTER_DATE=epoch + ' +0000')
        _COMMIT_INDEX += 1
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, env=env)


def build(target: Path) -> None:
    global _COMMIT_INDEX
    _COMMIT_INDEX = 0  # Every invocation must reproduce the same 32 Git commits.
    with tempfile.TemporaryDirectory(prefix="orbit-demo-") as temporary:
        repo=Path(temporary)/"Polaris-Engine";repo.mkdir()
        git(repo,"init","-q")
        git(repo,"config","user.email","demo@example.invalid")
        git(repo,"config","user.name","Demo Contributor")
        git(repo,"config","core.autocrlf","false")
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
                file=repo/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(body,encoding="utf-8",newline="\n")
            for name in deletions:(repo/name).unlink()
            git(repo,"add","-A")
            git(repo,"commit","-q","-m",message)
        data=analyze(repo,limit=len(scenes),share_safe=False)
        # Git 2.43 serializes %aI's UTC offset as +00:00, while newer Git
        # releases can serialize the same instant as Z.  The 32-commit sample
        # has a byte-exact HTML SHA pin, so canonicalize this semantic alias
        # *only* in the synthetic fixture (never in real project history).
        # +00:00 is five bytes longer than Z, explaining the 160-byte
        # difference observed on Colab, without changing commit object IDs.
        for commit in data["commits"]:
            if commit["date"].endswith("+00:00"):
                commit["date"] = commit["date"][:-6] + "Z"
        if data["history_window"] != len(scenes) or data["files_final"] < 200:
            raise AssertionError(f"Unexpected demo data: {data['history_window']}, {data['files_final']}")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(render(data),encoding="utf-8",newline="\n")
        print(f"Generated {target} ({target.stat().st_size:,} bytes) from {len(scenes)} real Git commits")

if __name__ == '__main__':
    build(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'demo'/'RepoOrbit_Demo.html')
