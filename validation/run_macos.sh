#!/bin/sh
set -eu
[ "$(uname -s)" = Darwin ] || { echo 'Native macOS kernel required.' >&2; exit 1; }
cd "$(dirname "$0")/.."
python3 scripts/run_native_matrix.py --targets requests flask uv --runs 21 --commits 60 300 1000 --verify sample --out external-results/native-macos
# Optional, test-only Playwright must already be installed.
python3 scripts/run_native_browser.py --out external-results/browser_Darwin.json
