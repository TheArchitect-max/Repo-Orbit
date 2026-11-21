# REPO ORBIT — accessibility remediation and validation boundaries

## Reproduced issue and bounded correction

On the previously native-accepted R4 commit `d655f1aabf0b322fe0f75283d2ff0a0e0a89cf86`, a Chromium/Playwright accessibility snapshot announced the view-mode toggle as **button "View"**, despite the visible caption `◈ Atlas view`. The associated `<label for="viewmode">View</label>` took precedence in its accessible-name computation. The action was ambiguous to a screen-reader user.

The R5 candidate explicitly assigns the button action `aria-label="Switch to atlas view"` **during existing JavaScript initialization**, and updates that label to `Switch to constellation view` when toggled, restoring the previous action label when toggled back. The accepted HTML template remains byte-for-byte frozen because the R9 integrity gate forbids modifying it. Its visible text, control placement, underlying view-mode logic and Git dataset remain unchanged. The tooltip is updated with the active action for consistency.

`tests/test_accessible_view_toggle.py` performs dependency-free structural checks on the actual sources. `tests/browser_v7.py` performs actual Chromium accessible-role lookup and keyboard `Enter` activation in both directions, and is already a mandatory part of each native browser job. The local supplementary browser smoke checks search, slider, canvas naming, keyboard selection and snapshot pinning.

## Conditions and honesty

- This is a **specific, independently reproduced defect correction**, not proof of general WCAG conformance.
- Chromium automation cannot establish VoiceOver, NVDA, keyboard-only usability for all flows or accessible interpretation of 80,000 Canvas elements.
- Full independent accessibility and AT acceptance remains **HOLD** until representative assistive-technology testing is documented and accepted.
- Changing `viewer.js` and browser tests produces a new source SHA. The original R4 six-job native acceptance is historical; all six same-SHA native CLI and Chromium jobs must pass again on R5 before this can be merged.
- Security/privacy, third-party IP/licensing and explicit release approval remain separate gates. This change does not activate a public license or a hosted service.
