# 0001. Python, PySide6 and Qt Widgets for the desktop application

- **Status:** Accepted
- **Date:** 2026-11-04

## Context

Lacis is a desktop OSINT tool for French company data. It replaces a local web application whose interface already set the visual direction: a review queue, a central link graph and a tabbed details panel, in a light and a dark theme. The desktop application must reproduce that interface faithfully and run on Linux and Windows.

The decision weighs these needs:

- **A polished, custom interface.** Design tokens, custom-painted widgets, a light and a dark theme that match the design target pixel for pixel.
- **A fast, interactive graph.** Hundreds of nodes, smooth zoom and pan, selection, signal rings, edge labels, with the layout computed off the interface thread.
- **Accessibility.** Screen reader support on Linux (AT-SPI) and Windows (UI Automation), keyboard navigation, visible focus.
- **Data work.** HTTP clients with rate limiting and retries, SQLite, graph algorithms, rule evaluation, hashing and provenance.
- **Packaging.** Native packages for Debian, Fedora and Arch Linux, and an installer for Windows.
- **Maintainability.** Code that a reviewer can read quickly, strict typing, a fast test suite that runs in the CI without a display.
- **License.** Compatible with GPL-3.0-or-later.

## Options

Five stacks were compared. Electron and Tauri were excluded from the start because the project leaves web technologies behind. GTK 4 was excluded because its Windows support and its accessibility on Windows lag behind Qt.

| Criterion | Python 3.12 + PySide6 (Qt Widgets) | C++20 + Qt 6 (Qt Widgets) | Kotlin + JavaFX | Rust + Slint | C# + Avalonia |
|---|---|---|---|---|---|
| Custom, polished interface | Excellent: style sheets, custom painting, full Qt widget set | Excellent: same toolkit | Good: CSS styling, smaller widget ecosystem | Good: declarative, but young widget set | Good: XAML styling |
| Interactive graph | Very good: `QGraphicsView`, layout in a worker thread | Excellent: same, with native speed | Good: `Canvas` or scene graph | Fair: no scene graph, custom rendering needed | Fair: custom rendering needed |
| Accessibility on Linux and Windows | Very good: Qt accessibility bridge on both | Very good: same | Fair on Linux | Partial: still maturing | Fair on Linux |
| Data ecosystem (HTTP, SQLite, graphs) | Excellent: httpx, sqlite3, networkx, numpy | Fair: more code to write and maintain | Good: JVM libraries | Good, but more code for graph analysis | Good |
| Code review and maintainability | Excellent: short, readable code, mypy strict | Fair: memory safety and build complexity weigh on every review | Good | Good, steep learning curve for contributors | Good |
| Tests without a display | Excellent: pytest-qt with the offscreen platform | Good: Qt Test, slower build | Good: TestFX | Fair | Good: headless platform |
| Linux packaging | Very good: distributions ship PySide6 | Very good | Fair: bundled runtime | Good | Fair: bundled runtime |
| Windows packaging | Good: Nuitka compiles to a native executable | Excellent | Good | Excellent | Excellent |
| Startup time and footprint | Good | Excellent | Fair | Excellent | Good |
| License compatibility with GPL-3.0 | Yes (LGPL-3.0) | Yes (LGPL-3.0) | Yes (GPL-2.0 with Classpath exception) | Yes (GPL-3.0 edition) | Yes (MIT) |

The two finalists were **Python with PySide6** and **C++20 with Qt 6**. They share the same toolkit, so the interface, the graph and the accessibility support would be identical. They differ in everything around it.

## Decision

Lacis is written in **Python 3.12 or later**, with **PySide6** and **Qt Widgets**.

- **Maintainability.** Most of Lacis is data work: collecting, normalising, linking, scoring and explaining. Python expresses that work in a fraction of the code C++ needs, and every line is easier to review. With mypy in strict mode, the type safety gap with C++ is small.
- **Review.** A reviewer reads intent instead of memory management. Memory safety bugs, undefined behaviour and build system issues are out of scope by construction.
- **Ecosystem.** httpx, sqlite3, networkx and numpy cover the collectors, the storage, the graph layout and the analysis. In C++, each of these would be a dependency to vendor or code to write.
- **Same interface quality.** PySide6 is the official Qt binding, maintained by the Qt Company. The interface uses the same widgets, the same painting API and the same accessibility bridge as a C++ application.

Qt Widgets is preferred over Qt Quick: the interface is a dense, keyboard-driven work tool, where Widgets give mature accessibility and native behaviour without a separate declarative language.

The dependency is `PySide6-Essentials`, not the `PySide6` meta-package, which would also install Qt WebEngine and other modules Lacis does not use.

## Consequences

- The graph layout runs in a worker thread with numpy and networkx, so the interface stays responsive. Hot paths are measured before any optimisation.
- Startup time is longer than a C++ build. The Windows build is compiled with Nuitka to reduce it (see [0002](0002-packaging.md)).
- The interface is tested with pytest-qt on the offscreen platform, on Linux and Windows, in the CI.
- Custom-painted widgets must provide their own `QAccessibleInterface`, so screen readers can describe them.
- If profiling one day shows a bottleneck Python cannot handle, that part can move to a compiled extension without changing the rest of the application.
