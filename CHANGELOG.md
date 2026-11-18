# Changelog

All notable changes to Lacis are listed here, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and version numbers follow the [versioning policy](docs/versioning.md).

## [Unreleased]

### Added

- The accessibility audit grid, in `docs/accessibility-audit.md`, applies WCAG 2.2 level AA to Lacis, says why some criteria do not apply, and gives the keyboard steps that check the others in the « faux plombiers » demo investigation, with a result for Orca on Linux and NVDA on Windows, in the light and dark themes, and in high contrast and at 200 % text where they matter.
- Lacis reduces motion when the system asks for it, or from View › Réduire les animations: the busy bar of running collections disappears, its written progress stays, and the effects of menus and tooltips stop. Zoom, fit and layout changes stay instant in both modes.
- No information relies on colour alone. The severity rings of the graph are double for a strong signal, single for a medium one and dashed for a weak one; hovering an entity writes its kind, its state and its severity; the score of the Entities tab writes the severity next to it; and each notification shows an icon for its kind. Tests check the graph colours against protanopia, deuteranopia and tritanopia simulations.
- High contrast themes, light and dark, where text reaches 7:1 and borders, icons and graph colours 4.5:1. They apply when the system is in high contrast mode and the theme follows the system, and « Contraste élevé » in View › Thème forces them.
- Lacis follows the font size of the system, and View › Taille du texte enlarges every text from 100 % to 200 %. At 200 %, on a 1280 × 800 screen, no text is cut and every control remains reachable: long lines wrap, and buttons that no longer fit side by side move to the next line.
- The graph has a list view, for screen readers and the keyboard. The « Vue liste » button above the graph, or Ctrl+L, shows its entities grouped by kind, each with its links, and screen readers hear each entity with its kind and its number of links. Moving through the list selects the entity in the graph and opens its details, Enter on a link goes to the entity it leads to, and the list follows the filters of the graph.
- After an expansion or a decision, screen readers hear what is new to examine, such as « À examiner : 2 nouveaux signaux d'alerte et 1 nouvel homonyme à vérifier ». The announcement is polite, and the changes found within a second are grouped into one.
- Screen readers learn the role, state and value of the widgets that Lacis draws itself: entity chips are links to their entity and tell its kind, signal cards are groups with their explanation and score, the BODACC timeline is a list of notices, and the buttons that fold the « À examiner » column or the provenance of a link tell whether it is open.

### Changed

- The link colour of the graph is slightly stronger in the light and dark themes, so that links stay visible to colour blind eyes.
- The « même personne » colour of the light theme is slightly darker, so that its labels on the graph reach 4.5:1.
- The provenance button of a « Même personne » link reads « Provenance · Décision », shorter, so that it fits with a larger text. Its accessible name still says « Décision de l'enquêteur ».

## [0.2.0] - 2026-11-17

This version fixes the issues raised by the first users of 0.1.0: directors are never merged on their name alone, and every link and decision can be traced and undone. Investigations opened with 0.2.0 are migrated and can no longer be opened with 0.1.0.

### Added

- Each link in the details of an entity has a « Provenance » button, which shows the responses the link comes from, with their date, their SHA-256 fingerprint and their raw response. A « Même personne » link shows the decision of the investigator and its date.
- The details of a person list the homonym decisions that concern them, with their date, and the « Retirer » button withdraws one at any time, even after the investigation was closed. The proposal comes back to the review queue, and the signals are computed again.
- A website, https://c4seus.github.io/lacis/, that presents Lacis and holds its user guide, in French. The AppStream metadata, the packages and the notes of each release link to it. The website counts its visits with GoatCounter, without cookies, and its privacy page says what is counted.
- The details of a company show how many of its directors the register withholds, such as « 1 dirigeant non diffusible », without any detail about them.
- The `excluded_legal_forms` setting of the `creation_burst` rule leaves the companies of some legal forms, such as the SCI, out of the bursts. None is left out by default.

### Changed

- Aide › Documentation and F1 open the user guide of the website, in French, instead of the README.

### Fixed

- The details of a company under foreign law registered in France show the « Droit étranger » badge and its country, with what gives it: the address of the registered office or the legal form in its name.
- Two directors with the same name are never one person without a decision of the investigator. Each company lists its directors as separate people, and exact homonyms, with the same name and month of birth or without a month of birth, become homonym proposals. A confirmed person lends the companies of each of its members to the proposals of the group. Investigations created with 0.1.0 split their people by company when they are opened, and keep the decisions that can be attributed, as [ADR 0003](https://github.com/c4seus/lacis/blob/main/docs/adr/0003-person-identity.md) explains.
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
