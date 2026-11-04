# Security policy

## Supported versions

Only the latest release receives security fixes, as a new patch version, following the [versioning policy](docs/versioning.md#supported-versions). Lacis has not been released yet: until v0.1.0 is out, fixes land on `develop`.

## Reporting a vulnerability

Use GitHub private vulnerability reporting: **Security → Report a vulnerability** on the repository page. Do not open a public issue.

Include the affected version, the platform, the impact and the steps to reproduce. You will receive an answer within 7 days. Once a fix is released, the advisory is published with credit to the reporter, unless they prefer to stay anonymous.

## Scope

In scope:

- the storage of investigations and the chain of evidence: tampering, loss of provenance, corrupted hashes;
- the handling of data returned by public APIs: injection into the interface, the database or exported files;
- the collectors: request forgery, unsafe redirects, credential or token leaks;
- the installers and packages published in the GitHub releases.

Out of scope:

- vulnerabilities of the public APIs Lacis queries;
- attacks that require an attacker to already run code under the user's account.
