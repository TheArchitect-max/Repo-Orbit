$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
if (-not $IsWindows -and $PSVersionTable.PSVersion.Major -ge 6) {
  throw 'Native Windows required; WSL/Linux does not qualify.'
}
py -3 scripts/run_native_matrix.py --targets requests flask uv --runs 21 --commits 60 300 1000 --verify sample --out external-results/native-windows
if ($LASTEXITCODE -ne 0) { throw "External benchmark incomplete or failed ($LASTEXITCODE). See external-results/native-windows/RUN_STATUS.json" }
Write-Host 'Native Windows results are in external-results/native-windows'
# Test-only Playwright installation is required separately for this step.
py -3 scripts/run_native_browser.py --out external-results/browser_Windows.json
if ($LASTEXITCODE -ne 0) { throw 'Native Chromium browser acceptance was not PASS.' }
