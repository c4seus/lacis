# Contributing to Lacis

Thank you for your interest in Lacis. This guide explains how the project is organised and what every contribution must follow. The rules are strict on purpose: most of them are checked by the CI, and a pull request is merged only when every check is green.

## Ground rules

- **Languages.** Code, commits, issues, pull requests and documentation are in English. The user interface is in French, because Lacis is built for French company data and a French audience.
- **No real personal data.** Test data, screenshots, issues and logs use fictional companies, people and identifiers only.
- **Every change starts from an issue.** Open or pick an issue before writing code, so the scope is agreed first.
- **Small pull requests.** One issue per pull request, one commit per task of the issue.

## Development setup

Lacis needs Python 3.12 or later.

### Linux

```bash
git clone https://github.com/c4seus/lacis.git
cd lacis
python3 -m venv .venv
. .venv/bin/activate
make install
make check
```

On a minimal system, Qt needs a few runtime libraries. On Debian and Ubuntu:

```bash
sudo apt install libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3
```

### Windows

```powershell
git clone https://github.com/c4seus/lacis.git
cd lacis
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ruff check . ; ruff format --check . ; python scripts/check_no_comments.py ; mypy ; pytest --cov
```

### Make targets

| Target | What it does |
|---|---|
| `make install` | Installs Lacis in editable mode with the development tools |
| `make lint` | Runs ruff, the format check and the no-comments check |
| `make format` | Fixes lint issues and formats the code |
| `make types` | Runs mypy in strict mode |
| `make test` | Runs the tests on the offscreen Qt platform |
| `make coverage` | Runs the tests with the coverage report and threshold |
| `make check` | Runs everything the CI runs. Run it before every push |

## Labels

Every issue gets exactly one type label, one or more area labels, and a priority label once it is planned in a milestone.

| Family | Labels |
|---|---|
| Type | `bug`, `enhancement`, `documentation`, `refactor`, `test`, `ci`, `build`, `chore` |
| Planning | `epic` |
| Area | `collectors`, `storage`, `graph`, `identity`, `signals`, `interface`, `design`, `accessibility`, `packaging` |
| Priority | `priority: critical`, `priority: high`, `priority: medium`, `priority: low` |
| Status | `triage`, `question`, `blocked` |
| Resolution | `duplicate`, `invalid`, `wontfix` |
| Other | `dependencies`, `security`, `no-tests-needed`, `good first issue`, `help wanted` |

| Priority | Meaning |
|---|---|
| `priority: critical` | Crashes the application, loses or corrupts data, or exposes a security flaw. Fixed before anything else, even outside the current milestone. |
| `priority: high` | Required for the milestone, and other issues depend on it. Worked on first. |
| `priority: medium` | Required for the milestone. Worked on once the high priority issues are done. |
| `priority: low` | Improves the milestone but is not required. Moves to the next milestone if time runs short. |

An epic groups the issues of one capability. Its description lists its sub-issues as a task list, and it is closed when all of them are.

## Branches

| Branch | Role |
|---|---|
| `develop` | Integration branch. Every feature branch starts from it and every pull request targets it. |
| `main` | Released code only. It receives `develop` at each release, and every commit on it is a released version. |

Name feature branches after the issue: `feat/42-search-panel`, `fix/57-graph-zoom`, `docs/63-install-guide`.

```bash
git switch develop && git pull
git switch -c feat/42-search-panel
```

## Commit convention

Every commit subject follows this format:

```
type(ticket): Imperative description
```

| Part | Rule |
|---|---|
| `type` | One of the types below |
| `ticket` | The number of the issue the commit belongs to. It is required |
| `Imperative description` | Starts with a capital letter and an imperative verb (`Add`, `Fix`, `Remove`), in English, without accented letters, without a final period |
| Length | 72 characters at most for the whole subject |

| Type | Use it for |
|---|---|
| `feat` | A new capability for users |
| `fix` | A bug fix |
| `refactor` | A code change that neither fixes a bug nor adds a capability |
| `docs` | Documentation only |
| `test` | Tests only |
| `ci` | CI workflows and the scripts they run |
| `build` | Packaging, dependencies and build configuration |
| `chore` | Repository maintenance that fits nowhere else |

When an issue lists several tasks, each task gets its own commit, in the order of the list. The body of a commit is optional; when present, it explains why the change was made, not what it does.

```
feat(42): Add the search panel to the main window
fix(57): Keep the graph zoom level after a refresh
test(57): Cover the zoom level after a refresh
```

These subjects are rejected:

```
Added search panel              no type and no ticket
feat: Add the search panel      no ticket
feat(42): add the search panel  no capital letter
feat(42): Adds the search panel not imperative
feat(42): Ajouté le panneau     not in English
```

The `Commit convention` job of the CI runs `scripts/check_commits.py` on every commit of a pull request. Run it locally before pushing:

```bash
python scripts/check_commits.py develop HEAD
```

## Code style

### PEP 8

Python code follows [PEP 8](https://peps.python.org/pep-0008/), the style guide of the Python standard library. ruff enforces it on every pull request:

| PEP 8 topic | Enforced by |
|---|---|
| Indentation, whitespace, blank lines, line breaks around operators | `ruff format`, and the `E` and `W` rules (pycodestyle) |
| Naming: `snake_case` functions and variables, `CapWords` classes, `UPPER_CASE` constants | the `N` rules (pep8-naming) |
| Import order and grouping | the `I` rules (isort) |
| Comparisons to `None`, type checks, simplifiable expressions | the `E7` rules and the `SIM` rules |
| Maximum line length | `ruff format` and the `E501` rule, set to 99 characters |

PEP 8 recommends 79 characters, and allows up to 99 when a team agrees on it. Lacis uses 99: names are explicit and never abbreviated, and a 79 character limit would split many lines and make them harder to read.

### No comments

Lacis code carries no comments and no docstrings. If a piece of code needs an explanation, rename it or extract it until it explains itself: a well-named function replaces a comment, and a well-named constant replaces a magic number.

The only accepted comments are tool directives: `# type: ignore[...]`, `# noqa: ...` and `# pragma: no cover`, each with the narrowest scope possible. The `Lint` job of the CI runs `scripts/check_no_comments.py` and fails on any other comment.

### Explicit names, no abbreviations

Variables, functions, methods, classes and constants say what they hold or do, in full words.

| Instead of | Write |
|---|---|
| `cfg`, `conf` | `configuration` |
| `idx`, `i` | `index`, `row_index` |
| `btn` | `button`, `search_button` |
| `msg` | `message` |
| `resp`, `res` | `response`, `result` |
| `addr` | `address` |
| `co`, `comp` | `company` |
| `dt` | `creation_date` |
| `tmp` | the real role of the value |

Established acronyms of the domain stay as they are: `siren`, `siret`, `naf`, `bodacc`, `url`, `http`, `sql`, `id` in compound names such as `company_id`.

### Tools

- **ruff** lints and formats the code. The configuration is in `pyproject.toml`.
- **mypy** runs in strict mode on `src`, `tests` and `scripts`. `Any` and `# type: ignore` need a reason visible in the code around them.

## Tests

- **Every pull request that changes `src/` also changes `tests/`.** The `Tests required` job of the CI enforces it. A maintainer can add the `no-tests-needed` label when a change really cannot be tested, for example a pure resource update, and explains why in the review.
- **Tests mirror the source tree.** The tests of `src/lacis/graph/layout.py` live in `tests/graph/test_layout.py`.
- **Test names are sentences.** `test_a_closed_company_keeps_its_directors` says what is checked.
- **Interface tests use pytest-qt.** They run on the offscreen platform, on Linux and Windows. Interact with widgets through `qtbot`, never with sleeps.
- **Coverage stays above 85 %** on code outside `src/lacis/ui`. The interface is covered by pytest-qt tests, not by the threshold.
- **No network in tests.** Collectors are tested against a fake API with fictional data.

## User interface

- **Text is in French**, with French typography: non-breaking space before `:`, `;`, `?` and `!`, French quotation marks « ».
- **Colours, spacing and fonts come from the design tokens.** No hard-coded colour in a widget.
- **Accessibility is part of the definition of done.** Every interactive widget has an accessible name, is reachable with the keyboard in a logical order and shows a visible focus. A custom-painted widget provides a `QAccessibleInterface`. A test checks that every interactive widget has a name.
- **Both themes are checked.** A visible change comes with screenshots in the light and the dark theme.

## Pull requests

1. Push the branch and open a pull request against `develop`.
2. Fill in the template: summary, changes, how to test, checklist, and `Closes #N`.
3. Wait for every check to be green. `CI passed` and `Analyze Python` are required.
4. The pull request is merged with **Rebase and merge**, so every commit lands on `develop` as written.

## Releases

Lacis follows [semantic versioning](https://semver.org/). Before 1.0.0, a minor version may contain breaking changes.

1. Update the version in `src/lacis/__init__.py` on `develop`, through a pull request.
2. Open a pull request from `develop` to `main`, titled `Release X.Y.Z`.
3. Merge it with **Create a merge commit**. Never rebase or squash a release: `main` and `develop` must share the same commits.
4. Tag the merge commit `vX.Y.Z` and push the tag.
5. The release workflow builds the packages and attaches them to the GitHub release.

## Dependencies

Dependabot opens pull requests against `develop` every week for Python dependencies and GitHub Actions. They are reviewed like any other pull request.

## Security

Never report a vulnerability in a public issue. Follow [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the [GNU General Public License v3.0 or later](LICENSE).
