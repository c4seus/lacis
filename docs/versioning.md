# Versioning policy

Lacis follows [semantic versioning](https://semver.org/): every version number is `MAJOR.MINOR.PATCH`, and every release is a git tag `vMAJOR.MINOR.PATCH` on `main`.

The version of the package is read from that tag. It is never written in the code.

## Before 1.0.0

Lacis is in its `0.y.z` phase: the interface, the investigation format and the rule configuration can still change.

| Version | When | Example |
|---|---|---|
| `0.MINOR.0` | A milestone is complete. New capabilities, and breaking changes if needed | `v0.2.0` closes the « Accessibility » milestone |
| `0.MINOR.PATCH` | Bug and security fixes only, without new capability and without change to the investigation schema | `v0.3.1` fixes a bug of `v0.3.0` |

## From 1.0.0

| Version | When | Example |
|---|---|---|
| `MAJOR.0.0` | A breaking change for users | `v2.0.0` changes the format of the rule configuration |
| `MAJOR.MINOR.0` | New capabilities, without breaking change | `v1.1.0` adds an export format |
| `MAJOR.MINOR.PATCH` | Bug and security fixes only | `v1.0.1` fixes a crash of `v1.0.0` |

### What counts as a breaking change

- Removing a capability, a command line option or an export format
- Changing the rule configuration file so that an existing file is refused or behaves differently
- Changing an export format so that existing tools can no longer read it
- Dropping a supported platform, distribution or Python version

### What does not

- **Opening an investigation created by an older version.** Lacis always migrates older investigations when it opens them, in every version. Opening an investigation in an older version than the one that last wrote it is refused with a clear message, never attempted.
- Changing the wording, layout or look of the interface
- Adding a field to an export format, as long as existing fields keep their meaning
- Fixing a rule whose results were wrong

## Pre-releases

A pre-release lets users test a minor or major version before it is released. It is tagged `vMAJOR.MINOR.PATCHrcN`, in the format of Python package versions ([PEP 440](https://peps.python.org/pep-0440/)), so the tag and the version of the package are always identical.

| Tag | Package version |
|---|---|
| `v0.2.0rc1` | `0.2.0rc1` |
| `v0.2.0rc2` | `0.2.0rc2` |
| `v0.2.0` | `0.2.0` |

Pre-releases are published as GitHub pre-releases, with the same packages as a release. They receive no fixes: the next pre-release or the release replaces them.

## Development versions

Between two tags, the version of the package says how far it is from the last tag, for example `0.3.2.dev4+g1a2b3c4`: four commits after `v0.3.1`, at commit `1a2b3c4`. These versions are never published.

## Milestones

Each minor version has a milestone on GitHub, named after it: `v0.2.0 - Accessibility`. A patch version only gets a milestone when several issues make it up.

## Supported versions

Only the latest release receives fixes, including security fixes. A fix for an older version is released as a new patch version of the latest minor version.

## Tags

Tags are annotated and created on `main` only. A pushed tag is never moved or deleted: a mistake in a release is fixed by the next version.

## Criteria for 1.0.0

Version 1.0.0 is not tied to a date. It is released when all of these are true:

- The investigation format has not changed for at least one minor version
- The accessibility audit is complete, with no blocking issue left
- Packages are published and tested for every supported platform
- The user documentation covers every capability

The release processes are described in the [contributing guide](../CONTRIBUTING.md#releases).
