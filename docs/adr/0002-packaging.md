# 0002. Native Linux packages, and Nuitka with an installer for Windows

- **Status:** Accepted
- **Date:** 2026-11-04

## Context

Lacis targets investigators, journalists and analysts, not Python developers. Installing it must not require pip, a virtual environment or a terminal. Each release publishes:

- a `.deb` package for Debian and its derivatives;
- an `.rpm` package for Fedora and its derivatives;
- a `.pkg.tar.zst` package for Arch Linux;
- a source archive;
- a Windows installer `.exe`.

The application is written in Python with PySide6 (see [0001](0001-technology.md)). Qt alone weighs more than 100 MB when bundled, so where the bundle comes from matters.

## Options

| Option | Linux | Windows | Drawbacks |
|---|---|---|---|
| **Native packages that depend on the distribution's PySide6** | Small packages, security updates of Qt come from the distribution, integrates with the system theme and accessibility stack | Not applicable | One package recipe per family; requires a recent enough PySide6 in the distribution |
| PyInstaller bundle | Works, but ships a private copy of Qt | Works, frequent antivirus false positives, slow startup of one-file builds | Large downloads, Qt never updated by the system |
| Nuitka compilation | Possible, but unnecessary when the distribution ships PySide6 | Native executable, faster startup, fewer antivirus false positives, official PySide6 support | Longer build time |
| Flatpak or AppImage | Single build for every distribution | Not applicable | Runtime of several hundred MB, not the formats requested, sandboxing complicates file access |
| Publishing to PyPI only | Requires pip and a terminal | Requires pip and a terminal | Not suitable for the target users |

## Decision

**Linux: native packages that depend on the distribution's PySide6.**

| Package | Distribution | PySide6 dependency |
|---|---|---|
| `.deb` | Debian 13 "trixie" and later, and derivatives that ship PySide6 6.8 or later | `python3-pyside6.qtcore`, `python3-pyside6.qtgui`, `python3-pyside6.qtsvg`, `python3-pyside6.qtwidgets` |
| `.rpm` | Supported Fedora releases, one package per release since each depends on the Python version of its release | `python3-pyside6` |
| `.pkg.tar.zst` | Arch Linux | `pyside6`, `qt6-svg` |

The packages contain the pure Python wheel of Lacis, a `.desktop` entry, the icons and the AppStream metadata. They are built in the CI inside a container of each target distribution, then installed and launched there as a smoke test.

**Windows: Nuitka, then an Inno Setup installer.** Nuitka compiles Lacis and its dependencies into a standalone folder with a native `lacis.exe`. Inno Setup wraps it into a per-user or per-machine installer, with a Start menu entry, an uninstaller and a French interface. It installs Lacis for the current user by default, without administrator rights. Uninstalling removes the application but keeps the investigations, which live in the data folder of the user. The build runs on a Windows runner in the CI.

**Source archive:** the sdist built by hatchling (`lacis-X.Y.Z.tar.gz`), which contains everything needed to build and test Lacis.

Every artifact is attached to the GitHub release created from the version tag, with a `SHA256SUMS` file.

## Consequences

- Linux packages stay small, and Qt security fixes reach users through their distribution.
- The minimum supported versions follow PySide6 availability: a distribution with an older PySide6 is not supported by the native packages, and its users install from source.
- Windows users get a native executable and do not need Python.
- Arch Linux is a rolling release: the package installs Lacis into the `site-packages` of the Python version Arch ships when it is built, so it stops working when Arch moves to a new Python version, until it is rebuilt. Its `PKGBUILD` builds from the source archive of the release, so the same recipe can be published on the AUR, where users rebuild it themselves.
- The release workflow needs one job per package format. It is built and tested in the v0.1.0 milestone, before the first release.
- Code signing of the Windows installer is not part of v0.1.0. Until it is in place, Windows SmartScreen may warn on first launch, and the documentation explains how to check the `SHA256SUMS` file.
