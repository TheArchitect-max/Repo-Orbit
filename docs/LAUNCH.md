# GitHub launch decision framework (not a promise of viral reach)

## Competitive reality

Gource is a longstanding established Git history visualizer; GourceView and similar browser-based replayers exist. Repo Orbit therefore must not market itself as the first or only Git visualization tool. Its proposed positioning is **"Turn a local repo into an offline, explorable history report with snapshot comparisons and redacted sharing."** Test whether real developers value these specific capabilities before extending scope.

## Release blockers / decision gates

1. Owner explicitly approves open-source licensing (MIT proposed; not granted in this draft) and selected copyright wording.
2. Security and privacy review checks all packaged artifacts, especially demo data and screenshot/video metadata.
3. Run reproducible unit, integrity, Python package install and browser checks; document exact environment and failures rather than claim blanket cross-platform PASS.
4. Run installation and smoke checks on Windows, macOS, Linux; verify at least one stable browser per platform. Record any platform-specific limitations, including managed-browser `file://` policies.
5. Independently verify licensing of every shipped artifact and third-party material; keep optional development tooling unbundled.
6. Publish tagged release only after checks PASS and a final artifact hash is recorded. Do not use GitHub Actions as a SaaS/application runtime. A static README/GIF is fine; the runtime is local HTML.

## Launch assets already in the ZIP

- Real 12-step animated browser GIF (synthetic Git repository, not simulation).
- Screenshot from actual Chromium.
- Standalone downloadable HTML demonstration.
- CLI usage examples, docs, tests and a structured evidence manifest.

## Distribution and honest growth measurement

Potential channels after explicit approval: an isolated GitHub repository, targeted developer forums, repository visualization discussions and developer demonstrations. Respect community self-promotion rules. Measure: unique documented trials, issues, reproduction of usage, contribution quality, ease of first run, stars, forks, and whether people return after initial curiosity. Stars are a vanity signal on their own and do not demonstrate business value or commercial return.

**STOP / REDESIGN trigger:** if first-time users cannot generate a useful HTML report quickly, if output leaks sensitive data despite chosen configuration, if visualizations fail on ordinary repositories, or if competing tools already solve the exact same workflow materially better. Do not claim viral success or "factorial" performance without comparative metrics.


## v0.7.0 release-readiness update

The local v0.7 candidate now supports bare mirrors and linked worktrees, enforces Git stdout byte limits while Git runs, provides a bounded keyboard-accessible file search, and emits XML 1.0-safe SVG labels. This does **not** constitute a broad accessibility certification or independent security review. Baseline/upgrade canonical JSON matched in a same-fixture test. The separately requested open-source license decision, full cross-platform acceptance and external value validation are still HOLD. No GitHub publication occurred.
