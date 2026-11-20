# Contributing (pre-publication draft)

REPO ORBIT is one standalone source tree. Do not import IP or code from other private projects. Before contributing to a future open-source release, the owner must explicitly approve the MIT (or alternative) license and publish a contribution policy.

Developer workflow: create tests that demonstrate the bug; run `python -m unittest discover -s tests -v`; verify synthetic end-to-end behavior through `python scripts/make_demo.py`; when Chromium/Playwright are available run `python tests/browser_smoke.py`; record environment-specific evidence and limitations. Keep the generated HTML fully offline, preserve the first-parent Git semantics, and do not add runtime dependencies without a supply-chain review.

No feature is accepted solely because tests are green: compare against an independent Git oracle, challenge privacy risks, ensure documentation matches behavior, and validate on a clean installed package. No release or merge without evidence-based acceptance.
