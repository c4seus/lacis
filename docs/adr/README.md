# Architecture decision records

This folder records the decisions that shape Lacis, with their context, the options considered and their consequences. A record is never rewritten once accepted: a later record supersedes it and links back to it.

| Number | Decision | Status |
|---|---|---|
| [0001](0001-technology.md) | Python, PySide6 and Qt Widgets for the desktop application | Accepted |
| [0002](0002-packaging.md) | Native Linux packages, and Nuitka with an installer for Windows | Accepted |

## Writing a new record

1. Copy the structure of an existing record: Context, Options, Decision, Consequences.
2. Number it after the last one, with a short kebab-case name.
3. Open a pull request with the `documentation` label. The record is accepted when the pull request is merged.
