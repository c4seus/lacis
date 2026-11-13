# Changelog

All notable changes to Lacis are listed here, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and version numbers follow the [versioning policy](docs/versioning.md).

## [Unreleased]

The first release brings the capabilities of the former web prototype to a native desktop application for Linux and Windows.

### Added

- Investigations, each stored in its own SQLite file with its starting question. An investigation created by an older version is migrated when it is opened.
- Search in the national company register by name, SIREN, SIRET, director or address, from the header bar.
- Pivots from a company to its establishments, addresses and directors, from a person to every company they run, and from an address to every company registered there, with a depth from 1 to 3 and a cap on new entities. Expansions run in the background and can be cancelled.
- BODACC notices of each company, grouped by family, with the court, the judgment, a link to bodacc.fr and the fingerprint of the response.
- Evidence for every fact: each entity and link lists the raw responses it came from, stored with their SHA-256 fingerprint, and a collection log records every request.
- Homonym review with « certain », « probable » and « faible » matches and their reasons. The decisions of the investigator are remembered and can be undone.
- Foreign entities: foreign companies that run a French company, and companies under foreign law registered in France.
- Warning signals from five rules whose thresholds are set in a TOML file: mass domiciliation, serial short-lived companies, phoenix scheme, burst of creations and registered office moved abroad.
- The investigation window: the « À examiner » review queue, the interactive graph, the details panel with its « Fiche », « Entités » and « Journal » tabs, keyboard shortcuts and the progress of collections.
- Light and dark themes, following the system by default.
- Keyboard and screen reader foundations: accessible names, a logical focus order and a visible focus everywhere.
- A demonstration mode, `lacis --demo`, on fictional companies and without network.
- Packages for Debian, Fedora, Arch Linux and Windows, with a desktop entry, icons and AppStream metadata.
