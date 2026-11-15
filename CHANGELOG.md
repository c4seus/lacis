# Changelog

All notable changes to Lacis are listed here, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and version numbers follow the [versioning policy](docs/versioning.md).

## [Unreleased]

### Added

- The details of a person list the homonym decisions that concern them, with their date, and the « Retirer » button withdraws one at any time, even after the investigation was closed. The proposal comes back to the review queue, and the signals are computed again.
- A website, https://c4seus.github.io/lacis/, that presents Lacis and holds its user guide, in French. The AppStream metadata, the packages and the notes of each release link to it. The website counts its visits with GoatCounter, without cookies, and its privacy page says what is counted.
- The details of a company show how many of its directors the register withholds, such as « 1 dirigeant non diffusible », without any detail about them.
- The `excluded_legal_forms` setting of the `creation_burst` rule leaves the companies of some legal forms, such as the SCI, out of the bursts. None is left out by default.

### Changed

- Aide › Documentation and F1 open the user guide of the website, in French, instead of the README.

### Fixed

- The details of a company under foreign law registered in France show the « Droit étranger » badge and its country, with what gives it: the address of the registered office or the legal form in its name.
- Two directors with the same name are never one person without a decision of the investigator. Each company lists its directors as separate people, and exact homonyms, with the same name and month of birth or without a month of birth, become homonym proposals. A confirmed person lends the companies of each of its members to the proposals of the group. Investigations created with 0.1.0 split their people by company when they are opened, and keep the decisions that can be attributed, as [ADR 0003](docs/adr/0003-person-identity.md) explains.
- A burst of creations under one director or at one address keeps the severity of the settings, « faible » by default, and is raised one step only from twice the threshold. A holding that creates three SCI on the same day no longer gives a medium signal.
- An expansion of a person or an address that stops after the first 100 results of the register says so in its notification, and the entity stays among the leads with the reason « Seuls les 100 premiers résultats sur … ont été lus ».
- The « Transfert du siège à l'étranger » signal reads the country of the new registered office only, so a move within France to a street such as « rue d'Italie » no longer flags it. Investigations created with an older version read their notices again when they are opened.

## [0.1.0] - 2026-11-13

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
