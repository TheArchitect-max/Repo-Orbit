# Security and data handling

This product is an **offline Git metadata viewer**, not a safe arbitrary-code analysis sandbox. It does not execute source code from the selected repository; however, it invokes the locally installed Git program and writes sensitive metadata unless explicitly redacted.

- Treat a normal-mode exported HTML/JSON report as sensitive as the commit metadata it contains.
- `--redact` hides original identifiers but reveals hierarchy, file categories, activity and opaque object-equivalence patterns; it is not verified anonymization. Inspect generated outputs before distribution.
- `--exclude` removes paths from the displayed report only; full Git tree integrity remains checked.
- Avoid analyzing hostile repositories on shared/public servers. Git stdout is now bounded while it is produced and oversized/blocked Git commands are terminated. Git stderr is still redirected to a temporary file without a strict byte cap; the Git process itself has no dedicated CPU/memory sandbox. Git configuration and external-executable trust remain considerations.
- Gzip-compressed HTML is **not encrypted**; use `--redact` and review metadata before sharing. Legacy browsers without `DecompressionStream` require `--html-format plain`.
- The generated HTML has a restrictive CSP and does not require external JavaScript/network access. Untrusted Git labels are escaped in HTML and placed into browser text nodes.
- To report suspected vulnerabilities, prefer a private communication channel established by the project owner before any public issue. No official public security contact or service-level promise has been designated yet.

Public release remains on HOLD pending approval and security/privacy acceptance.
