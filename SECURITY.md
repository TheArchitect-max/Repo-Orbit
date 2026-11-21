# Security and data handling

This product is an **offline Git metadata viewer**, not a safe arbitrary-code analysis sandbox. It does not execute source code from the selected repository; however, it invokes the locally installed Git program and writes sensitive metadata unless explicitly redacted.

- Treat a normal-mode exported HTML/JSON report as sensitive as the commit metadata it contains.
- `--redact` hides original identifiers but reveals hierarchy, file categories, activity and opaque object-equivalence patterns; it is not verified anonymization. Inspect generated outputs before distribution.
- `--exclude` removes paths from the displayed report only; full Git tree integrity remains checked.
- Avoid analyzing hostile repositories on shared/public servers. Git stdout is now bounded while it is produced and oversized/blocked Git commands are terminated. Git stderr is now drained concurrently into a bounded diagnostic sample, and Git is terminated after more than 1 MiB of stderr output; it is no longer written into an unbounded temporary file. Git still has no dedicated CPU/memory sandbox, and its exit/status policy is unchanged for otherwise valid commands. Git configuration and external-executable trust remain considerations.
- Gzip-compressed HTML is **not encrypted**; use `--redact` and review metadata before sharing. Legacy browsers without `DecompressionStream` require `--html-format plain`.
- The generated HTML has a restrictive CSP and does not require external JavaScript/network access. Untrusted Git labels are escaped in HTML and placed into browser text nodes.
- To report suspected vulnerabilities, prefer a private communication channel established by the project owner before any public issue. No official public security contact or service-level promise has been designated yet.

Public release remains on HOLD pending approval and security/privacy acceptance.

## R9 follow-up: bounded standalone gzip payloads (current candidate)

A gzip-compressed standalone HTML report may be much smaller than its
uncompressed JSON. The browser used to decode the entire expansion before
parsing. The new viewer now counts decompressed bytes while streaming; it
rejects inputs above **64 MiB** and decodes UTF-8 with a strict `TextDecoder`.
The offline evidence parser also reads no more than 64 MiB + 1 byte before
rejecting an oversized gzip stream. This is resource hardening, **not a
sandbox**; a large but accepted report can still consume substantial browser
memory, and a malicious, independently edited HTML file can contain arbitrary
script beyond the scope of this utility.

A required synthetic Chromium adversarial suite checks the normal small demo,
a valid gzip expansion over the limit and malformed UTF-8. The complete native
OS matrix must be repeated for the current source SHA. The independent
security/privacy review and explicit public release decision remain HOLD.
