# Third-party materials and toolchain

The included REPO ORBIT application code, HTML, CSS, SVG exports and synthetic demo assets are authored for this project. **No Gource, GourceView or GitDiagram code/assets are copied or included.** The example repository is generated locally with synthetic data only.

Runtime: Python standard library, an existing Git executable, and standard browser APIs. Git is an external installed tool and remains subject to its own license. No third-party Python runtime library is bundled.

Optional development tools *not included as source in this package*: setuptools for packaging; Playwright and Chromium for browser acceptance; Pillow for generating the animated GIF. Review their current licenses when distributing any third-party binaries or integrating these tools into future automated builds. The GIF consists of screenshots produced by our own demo renderer; it does not bundle these development tools.

This notice is a provenance statement, not an external security audit, SBOM scan or guarantee of licence compliance in every environment.

## R8 test-only Playwright and Chromium

R8 CircleCI browser acceptance optionally installs `playwright==1.65.2` into a
separate disposable virtual environment and downloads Playwright-managed
Chromium. These third-party test tools and binaries are **not distributed**
inside REPO ORBIT or required at application runtime. Playwright's upstream
source is published under Apache License 2.0; Chromium contains multiple
upstream licensed components. A separate dependency/license review is required
if any third-party binaries are redistributed in a future release.
