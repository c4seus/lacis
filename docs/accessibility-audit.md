# Accessibility audit grid

This grid audits Lacis against the level AA of the [Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/), applied to a desktop application as the W3C note [WCAG2ICT](https://www.w3.org/TR/wcag2ict-22/) describes. It lists every criterion of levels A and AA, says why some of them do not apply to Lacis, and gives for the others the steps to check them in the « faux plombiers » investigation of the demo mode.

An audit runs the grid with a screen reader and the keyboard only: Orca on Linux, NVDA on Windows.

The interface of Lacis is in French, so the steps quote its texts in French, as they appear on the screen.

## Before you start

### Linux, with Orca

1. Use a GNOME session, where Orca is installed. Start Orca with <kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd>.
2. Start Lacis in a terminal with `lacis --demo`, after Orca. If Orca says nothing in Lacis, close it and start it again with `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 lacis --demo`.
3. Orca reads the focused widget as it changes. Its « Where am I » command repeats the name, role and state of the focused widget: <kbd>Numpad Enter</kbd> with the desktop layout, <kbd>Orca</kbd>+<kbd>Enter</kbd> with the laptop layout.

### Windows, with NVDA

1. Install NVDA from [nvaccess.org](https://www.nvaccess.org/download/) and start it.
2. Open its speech viewer, from the NVDA menu (<kbd>NVDA</kbd>+<kbd>N</kbd>) › Tools › Speech viewer: it writes everything NVDA says, which makes it easy to copy into an issue.
3. Start Lacis in PowerShell with `& "$env:LOCALAPPDATA\Programs\Lacis\lacis.exe" --demo`, or with `$env:ProgramFiles` instead of `$env:LOCALAPPDATA\Programs` if Lacis is installed for every user.
4. <kbd>NVDA</kbd>+<kbd>Tab</kbd> repeats the focused widget, and <kbd>NVDA</kbd>+<kbd>T</kbd> reads the title of the window.

### On both platforms

- **Use the keyboard only.** Put the mouse and the touchpad aside. The few checks that need a pointer say so.
- **The demo mode starts empty each time.** Its investigations live in a temporary folder, deleted when Lacis closes, and its companies and people are fictional: the audit never touches a real investigation. The theme, the text size and the reduced motion setting are those of your usual Lacis, so write them down before the audit and set them back after it.

## The demo investigation

The steps below build the « faux plombiers » investigation and visit every part of the interface. Each criterion of the grid refers to them by their number, such as S4. Run them in order, once in each theme: a step only works after the steps before it.

The menus open with <kbd>Alt</kbd> and the underlined letter of their name: <kbd>Alt</kbd>+<kbd>F</kbd> for **Fichier**, <kbd>Alt</kbd>+<kbd>A</kbd> for **Affichage**, <kbd>Alt</kbd>+<kbd>E</kbd> for **Enquête**, <kbd>Alt</kbd>+<kbd>D</kbd> for **Aide**. When a step says « Tab to » a widget, press <kbd>Tab</kbd> until the screen reader reads its name, and count the presses if they seem many.

### S1. Start Lacis

Start the demo mode. The window is titled « Lacis — démonstration », and shows the « Enquêtes » screen with « Aucune enquête pour l'instant » and the **Créer une première enquête** button.

### S2. Make mistakes in the form of a new investigation

1. Press <kbd>Ctrl</kbd>+<kbd>N</kbd>. The form of a new investigation opens, with the focus in its **Nom** field.
2. Type `Faux Plombiers`. A problem appears under the field, as soon as the first capital letter is typed: the name accepts only lowercase letters without accents, digits and hyphens.
3. Erase the field, then press <kbd>Enter</kbd>. The problem says that the name is required, and the focus stays in the field.
4. Press <kbd>Escape</kbd>. The form closes, and the focus goes to the button **Créer une première enquête**.

### S3. Create the investigation

1. Press <kbd>Ctrl</kbd>+<kbd>N</kbd>, and type `faux-plombiers-31` in **Nom**.
2. Press <kbd>Tab</kbd>, and type `Qui se cache derrière les plombiers du 12 rue des Lilas ?` in **Question**.
3. Press <kbd>Enter</kbd>. The investigation opens, with its question at the top, and the focus goes to the search field.

### S4. Search the register

1. The focus is in the field « Rechercher une entreprise ». Elsewhere, <kbd>Ctrl</kbd>+<kbd>F</kbd> or <kbd>/</kbd> brings it back.
2. Type `12 rue des Lilas`, then wait. The list of results opens under the field: ACME PLOMBERIE, DUPONT SERVICES and LILAS BOULANGERIE. The number of results is announced, and the first result is the current one.
3. Press <kbd>Enter</kbd> to add ACME PLOMBERIE. A notification confirms it, and the result now reads « Déjà dans l'enquête ».
4. Press <kbd>↓</kbd> to move to DUPONT SERVICES, and <kbd>Enter</kbd> to add it. Do not add LILAS BOULANGERIE.
5. Press <kbd>Escape</kbd>. The list closes, and the two companies are in the graph.

### S5. Expand a company from the graph

1. Tab to the graph, which the screen reader names « Graphe de l'enquête ».
2. Press the arrow keys until ACME PLOMBERIE is selected. The first arrow selects an entity, the next ones go to the neighbouring entity in their direction, and the sheet of the selected entity opens in the details panel, on the right.
3. Press <kbd>Ctrl</kbd>+<kbd>E</kbd>. The panel « Collectes en cours » shows the expansion, with an **Annuler** button, and a notification announces its end and the number of entities added.

### S6. Expand a company from the review column

1. Tab to the row of DUPONT SERVICES, among the « Pistes non étendues » of the « À examiner » column, on the left.
2. Tab to its button, read « Étendre DUPONT SERVICES », and press <kbd>Space</kbd>. The expansion runs as in S5.
3. When it ends, Lacis announces what is new to examine: a homonym to check.

### S7. Decide on the homonym

1. Tab to the row « Jean DUPONT (1980-05) ↔ Jean Pierre DUPONT (1980-05) », among the « Homonymes à vérifier » of the review column.
2. Tab to its button **Même personne** and press <kbd>Space</kbd>. A notification confirms the decision, and Lacis announces a new warning signal: a « Schéma phénix » now heads the review column.
3. Press <kbd>Ctrl</kbd>+<kbd>Z</kbd>. The decision is undone, and the homonym returns to the column.
4. Press <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd>. The decision is made again, and the signal returns.

### S8. Browse the graph as a list

1. Press <kbd>Ctrl</kbd>+<kbd>L</kbd>. The list view replaces the graph and takes the focus. It groups the entities by kind: companies, people, addresses, establishments and foreign companies.
2. Move with <kbd>↓</kbd> and <kbd>↑</kbd>. Each entity is read with its kind and its number of links, and its sheet opens in the details panel.
3. On DUPONT SERVICES, press <kbd>→</kbd>. Its links unfold under it, such as « Président : Jean DUPONT ».
4. On a link, press <kbd>Enter</kbd>. The list goes to the entity of the link.
5. Go back to DUPONT SERVICES and leave it selected. Press <kbd>Ctrl</kbd>+<kbd>L</kbd> to come back to the graph.

### S9. Read the sheet of a company

The sheet of DUPONT SERVICES is open. Tab through it, from **Étendre à nouveau** to its last **Réponse brute** button, and read it with the review commands of the screen reader: Orca's flat review, NVDA's object navigation.

1. The head of the sheet gives its kind, state, SIREN, dates, NAF code and the date of its last expansion. Its buttons are **Étendre à nouveau**, **Annuaire** and **Copier le SIREN**.
2. Open the depth menu of **Étendre à nouveau**, which proposes the depths 1 to 3, then close it with <kbd>Escape</kbd>.
3. Press **Copier le SIREN**. A notification says what was copied.
4. Read the section « Signaux d'alerte »: the card of the « Schéma phénix », with its severity, its score and its explanation.
5. Read the section « Annonces BODACC »: each notice with its date, its family, its summary and the court, then its buttons **bodacc.fr ↗** and **Réponse brute**. Press **Rafraîchir**: a notification counts the new and withdrawn notices.
6. Press **Réponse brute** on a notice. The window « Réponse brute n° » opens with the response. Read it, press <kbd>Tab</kbd> to leave the text, and close the window with <kbd>Escape</kbd>. The focus returns to the button.
7. In the section « Liens », Tab to the button **Provenance** of a link and press <kbd>Space</kbd>. The provenance unfolds under the link, then folds again with a second <kbd>Space</kbd>.
8. In the section « Provenance », Tab to the fingerprint of a response, and try to read it whole.

### S10. Follow a link to a foreign company

1. Select ACME PLOMBERIE, in the graph or in the list view.
2. In the section « Liens » of its sheet, Tab to the chip « Sélectionner DUPONT INVEST LTD » and press <kbd>Enter</kbd>. Its sheet opens: a foreign company, with its country, its links and no **Étendre** button.

### S11. Use the tabs of the details panel

1. Press <kbd>Alt</kbd>+<kbd>3</kbd> to open the tab **Entités**. Type `dupont` in « Filtrer les entités », change the sort, check « Signalées seulement », then Tab to the table and move through its rows and cells with the arrow keys.
2. Press <kbd>Alt</kbd>+<kbd>4</kbd> to open the tab **Journal**. Move through the requests in the table, and press <kbd>Enter</kbd> on one of them to open its raw response. Close it with <kbd>Escape</kbd>.
3. Press <kbd>Ctrl</kbd>+<kbd>Page Up</kbd> and <kbd>Ctrl</kbd>+<kbd>Page Down</kbd> to move between the tabs, then <kbd>Alt</kbd>+<kbd>1</kbd> to come back to the sheet.

### S12. Use the tools of the graph

1. Tab to the button **Filtres**, open it, hide the addresses, then show them again with **Tout afficher**.
2. Tab to the buttons « Zoom avant », « Zoom arrière », « Ajuster à la fenêtre » and « Réorganiser le graphe », and press each of them.
3. In the graph, press <kbd>Shift</kbd>+arrows to move the view, <kbd>Alt</kbd>+arrows to move the selected entity, <kbd>+</kbd>, <kbd>-</kbd> and <kbd>0</kbd> to zoom, and <kbd>Escape</kbd> to deselect the entity.
4. Press <kbd>Ctrl</kbd>+<kbd>1</kbd> twice: the review column hides, then shows again. Tab to the button « Replier la colonne À examiner » and press <kbd>Space</kbd> twice.

### S13. Expand an address

1. In the review column, Tab to the lead « 12 RUE DES LILAS 31000 TOULOUSE » and to its button **Étendre**, and press <kbd>Space</kbd>.
2. While the expansion runs, Tab to the button **Annuler** of the panel « Collectes en cours ». If the expansion ends first, write it down: the check of this button is then « Not tested ».

### S14. Use the menus and the dialogs

1. Open each menu with <kbd>Alt</kbd> and its letter, move through its items with the arrow keys, and close it with <kbd>Escape</kbd>.
2. Press <kbd>Ctrl</kbd>+<kbd>/</kbd>. The window « Raccourcis clavier » opens. Move through its list, then close it with **Fermer** or <kbd>Escape</kbd>.
3. Open **Aide › À propos de Lacis**, read it, and close it.
4. Tab to the button « Thème de l'interface », open its menu, and close it with <kbd>Escape</kbd>.
5. Open **Affichage › Taille du texte** and **Affichage › Réduire les animations**, without changing them.

### S15. Manage the investigation from the home screen

1. Press <kbd>Ctrl</kbd>+<kbd>W</kbd>. The investigation closes, and the « Enquêtes » screen shows its card.
2. Tab to the card of `faux-plombiers-31`, which reads its name, its question and its counters. Tab to its button « Actions de l'enquête faux-plombiers-31 » and open it.
3. Choose **Modifier le nom ou la question…**. The window « Modifier l'enquête » shows the current name and question. Close it with **Annuler**.
4. Open the actions again and choose **Supprimer…**. The window « Supprimer l'enquête » asks for a confirmation. Close it without deleting.
5. Tab back to the card, and press <kbd>Enter</kbd> to open the investigation again.
6. Press <kbd>Ctrl</kbd>+<kbd>Q</kbd> to quit Lacis.

## Criteria that do not apply

| Criterion | Level | Why it does not apply |
| --- | --- | --- |
| 1.2.1 Audio-only and video-only (prerecorded) | A | Lacis plays no audio and no video |
| 1.2.2 Captions (prerecorded) | A | Lacis plays no audio and no video |
| 1.2.3 Audio description or media alternative (prerecorded) | A | Lacis plays no audio and no video |
| 1.2.4 Captions (live) | AA | Lacis plays no audio and no video |
| 1.2.5 Audio description (prerecorded) | AA | Lacis plays no audio and no video |
| 1.3.5 Identify input purpose | AA | No field of Lacis asks for information about its user: they take an investigation name, a question and search terms |
| 1.4.2 Audio control | A | Lacis plays no audio |
| 1.4.12 Text spacing | AA | Neither Linux nor Windows lets users set the line, paragraph, letter and word spacing of an application, which WCAG2ICT requires for this criterion to apply. The size of the text is checked by 1.4.4 |
| 2.4.1 Bypass blocks | A | WCAG2ICT applies it to the blocks repeated in a set of programs, and Lacis is a single program. The shortcuts that reach each region of the window are checked by 2.4.3 |
| 2.4.5 Multiple ways | AA | WCAG2ICT applies it to a set of programs, and Lacis is a single program |
| 2.5.4 Motion actuation | A | Nothing in Lacis reacts to the motion of the device |
| 3.1.2 Language of parts | AA | Every text of the interface is in French. The other languages appear only in proper names, such as DUPONT INVEST LTD, which the criterion leaves out |
| 3.2.3 Consistent navigation | AA | WCAG2ICT applies it to a set of programs, and Lacis is a single program |
| 3.2.4 Consistent identification | AA | WCAG2ICT applies it to a set of programs, and Lacis is a single program |
| 3.2.6 Consistent help | A | WCAG2ICT applies it to a set of programs, and Lacis is a single program |
| 3.3.8 Accessible authentication (minimum) | AA | Lacis asks for no account and no password |

Criterion 4.1.1 Parsing was removed from WCAG 2.2, and is not in the grid.

## Perceivable

### 1.1.1 Non-text content

Level A. Every icon and every drawing has a text alternative, and a picture that only decorates is ignored by the screen reader.

1. In S4, Tab through the header: the icon buttons are read « Aide » and « Thème de l'interface ».
2. In S12, the icon buttons of the graph are read with their action: « Zoom avant », « Zoom arrière », « Ajuster à la fenêtre » and « Réorganiser le graphe ».
3. In S5, the graph is read « Graphe de l'enquête », and each entity selected with the arrow keys is read with its name, its kind and its state.
4. In S4 and S7, the icon of a notification is not read alone, as « image » or by a file name: its message says what happened.
5. In S14, the logo of the window « À propos de Lacis » is read « Lacis », or skipped.

No control may be read as a bare « bouton », « button », or by the name of a file.

### 1.3.1 Info and relationships

Level A. What the layout shows, the screen reader tells: labels of fields, titles of sections, groups, lists, tables and trees.

1. In S2, each field is read with its label, « Nom » or « Question », and with its hint, such as « Minuscules sans accent, chiffres et tirets ».
2. In S6 and S7, the screen reader tells in which section a row of the review column is, « Homonymes à vérifier » or « Pistes non étendues », and the name of each button tells which row it acts on.
3. In S9, the titles of the sections « Signaux d'alerte », « Annonces BODACC », « Liens » and « Provenance » are read with the review commands. The signal card is read as a group, with its explanation and its score, and the notices as a list, with their number.
4. In S8, the list view is read as a tree: each entity with its level, and whether its links are folded or unfolded.
5. In S11, moving through the tables **Entités** and **Journal** reads the title of the column of each cell.
6. In S14, the window « Raccourcis clavier » reads each shortcut with its group.

### 1.3.2 Meaningful sequence

Level A. The screen reader reads the content in an order that keeps its meaning.

1. In S9, read the sheet from top to bottom with the review commands: the sections come in the order of the screen, and each value comes after its label.
2. In S4, the results are read in the order of the list, each with its name, its state, its SIREN, its NAF code, its city and its date.
3. In S14, the windows « Raccourcis clavier » and « À propos de Lacis » read their texts in the order of the screen.

### 1.3.3 Sensory characteristics

Level A. No instruction relies only on a shape, a colour, a size, a position or a sound.

1. Read every hint, placeholder, empty state and message met in S1 to S15, such as « La fiche de l'entité sélectionnée s'affichera ici. » or « ↑ ↓ pour naviguer · Entrée pour ajouter ».
2. Each instruction must make sense without seeing the screen: it names what to use, not only « le bouton rouge » or « à droite ».

### 1.3.4 Orientation

Level AA. Lacis works whatever the orientation of the screen.

1. Turn the screen to portrait in the display settings of the system, with a width of at least 1080 pixels.
2. Run S1 to S5: Lacis does not ask to turn the screen back, and its window fits the screen.

If the screen cannot be turned, write « Not tested ».

### 1.4.1 Use of colour

Level A. No information is given by colour alone.

1. In S7, the graph shows the entity kinds by their shape, the closed companies by their dashed border, and the severity of a signal by its ring: double for a strong signal, single for a medium one, dashed for a weak one. The legend repeats these shapes.
2. In S2, a problem in a field is written under it, not only shown by a red border.
3. In S4, the state of each result is written, « Active » or « Fermée ».
4. In S9, the notices of a difficulty, such as a « Procédure collective », write their family, and not only their red colour.
5. In S4 and S7, each notification shows an icon of its kind.
6. To check without the colours, turn on the grayscale filter of Windows, in Settings › Accessibility › Color filters. On Linux, take a screenshot and desaturate it, for example in GIMP with Colors › Desaturate.

### 1.4.3 Contrast (minimum)

Level AA. Text reaches a contrast of 4.5:1 with its background, and large text 3:1: 24 pixels, or 18.7 pixels in bold. Disabled controls are left out.

1. Measure the contrast with the [Colour Contrast Analyser](https://www.tpgi.com/color-contrast-checker/) on Windows, or with the [Contrast](https://flathub.org/apps/org.gnome.design.Contrast) application on Linux, and its colour picker.
2. Measure at least: the placeholder of the search field (S4), the hints under the fields of the form (S2), the problems of the form (S2), the secondary texts of the results (S4), the titles of the sections of the review column and of the sheet (S7, S9), the summaries and the withdrawn notices (S9), the labels of the graph and of the legend (S7), the labels of the tabs (S11), the text of the notifications (S4), and the tooltips (S12).
3. In high contrast, Lacis aims at 7:1 for text: write any text under 7:1 in the issue, even when it passes 4.5:1.

### 1.4.4 Resize text

Level AA. Text can be enlarged up to 200 % without losing content or function.

1. Set the text to 200 %, with **Affichage › Taille du texte › 200 %**, and run S2 to S15.
2. No text is cut or covered, and every control can still be reached and used. Long texts wrap, and buttons that no longer fit side by side move to the next line.
3. Enlarge also the text of the system, in Settings › Accessibility › Text size on Windows, or with Large Text in the accessibility settings of GNOME: Lacis follows it.

### 1.4.5 Images of text

Level AA. Text is written as text, not drawn in an image, except the logo.

1. In S1 to S15, look for a picture that holds words, such as an icon with letters.
2. Any text found must be selectable as text or read by the screen reader as text.

### 1.4.10 Reflow

Level AA, adapted. WCAG asks for content that reflows in a width of 320 pixels without scrolling in two directions. A desktop window cannot shrink that far, so the grid checks the smallest window that Lacis allows, and the text enlarged on a small screen, as WCAG2ICT suggests.

1. Resize the window to its smallest size, 1024 × 640, and run S2 to S11.
2. Set the text to 200 % on a screen of 1280 × 800, and run S2 to S11 again.
3. The form, the review column, the sheet, the dialogs and the notifications scroll in one direction only, and no text is cut. The graph, the tables **Entités** and **Journal**, and the raw responses may scroll in both directions: their layout needs two dimensions.

### 1.4.11 Non-text contrast

Level AA. The borders of controls, the focus, the icons and the drawings of the graph reach a contrast of 3:1 with what surrounds them.

1. Measure with the same tools as for 1.4.3: the borders of the fields and of the buttons (S2), the focus indicator (S4 to S15), the check boxes and their state (S11, S12), the icons of the header, of the graph and of the notifications (S4, S12), the shapes of the entities, the lines of the links and the rings of the signals (S7).
2. In high contrast, Lacis aims at 4.5:1 for borders, icons and the colours of the graph: write any value under 4.5:1 in the issue.

### 1.4.13 Content on hover or focus

Level AA. A tooltip or a popup that appears on hover or focus can be dismissed without moving, can be hovered, and stays until it is dismissed or no longer relevant.

This check needs the mouse.

1. Hover an entity of the graph (S7), a fingerprint of the section « Provenance » (S9), a row of the journal (S11), and the buttons of the graph (S12).
2. For each tooltip: <kbd>Escape</kbd> hides it without moving the pointer; the pointer can move onto the tooltip without hiding it; the tooltip stays as long as the pointer stays, without disappearing after a delay.

## Operable

### 2.1.1 Keyboard

Level A. Everything can be done with the keyboard.

1. Run S1 to S15 with the keyboard only.
2. Check in particular: choosing the depth of an expansion (S9, step 2), the menu **Filtres** (S12), moving an entity (S12), the button **Annuler** of an expansion (S13), and the actions of a card (S15).
3. What a tooltip shows must also be reachable by keyboard: the full fingerprint of a response (S9, step 8), and the details of a request of the journal (S11).

### 2.1.2 No keyboard trap

Level A. The focus can always leave a widget with the keyboard.

1. In S4 to S15, press <kbd>Tab</kbd> and <kbd>Shift</kbd>+<kbd>Tab</kbd> in each region: the search field and its list of results, the review column, the graph, the list view, the tabs of the details panel, the tables, the text of a raw response, the menus and the dialogs.
2. The focus leaves each of them, and goes around the whole window back to where it started.

### 2.1.4 Character key shortcuts

Level A. A shortcut made of a single character key can be turned off or changed, or works only when its widget has the focus.

1. In the graph, <kbd>+</kbd>, <kbd>-</kbd> and <kbd>0</kbd> zoom: check that they do nothing when the focus is elsewhere, for example on a button of the sheet.
2. <kbd>/</kbd> brings the focus to the search field (S4). Press it with the focus on the graph, on a button of the sheet and in a table: write where it works, and whether it can be turned off or changed.

### 2.2.1 Timing adjustable

Level A. A time limit can be turned off, adjusted or extended, unless it is essential.

1. In S4, S7 and S9, the notifications of a success or an information disappear after a few seconds. Write down each message, and how long it stays.
2. For each of them, check that the screen reader announced it, and that its content can be found again elsewhere, such as the entity added in the graph or the decision in the sheet.
3. The notifications of an error stay until they are closed.

### 2.2.2 Pause, stop, hide

Level A. What moves for more than five seconds can be paused, stopped or hidden.

1. In S13, an expansion shows a moving bar in the panel « Collectes en cours ».
2. Check **Affichage › Réduire les animations**, and run S13 again: the bar disappears, the written progress stays, and the menus and tooltips open without effect.
3. Uncheck it afterwards, if it was not checked before the audit.

### 2.3.1 Three flashes or below threshold

Level A. Nothing flashes more than three times per second.

1. Watch the screen during S1 to S15, and especially during the expansions of S5, S6 and S13.
2. Nothing flashes: the blinking cursor of a field is left out.

### 2.4.2 Page titled

Level A. Each window has a title that tells its subject.

1. Read the title of each window, with <kbd>NVDA</kbd>+<kbd>T</kbd>, or when Orca reads it as the window gets the focus: the main window in S1 and S3, the window « Réponse brute n° » in S9, the windows « Raccourcis clavier » and « À propos de Lacis » in S14, « Modifier l'enquête » and « Supprimer l'enquête » in S15.
2. Each title says what the window holds.

### 2.4.3 Focus order

Level A. The focus moves in an order that keeps the meaning and the use of the window.

1. In S4, with two companies in the graph, press <kbd>Tab</kbd> from the search field until the focus comes back to it. Write down the order: it must follow the window, from the header to the review column, the graph and the details panel, and reach the rows of the review column and the buttons of the sheet in their region.
2. Do the same with <kbd>Shift</kbd>+<kbd>Tab</kbd>: the order is reversed.
3. After an action, the focus stays on something that makes sense: in S3, it goes to the search field; in S7, when the row of the homonym disappears, it goes to a neighbouring row; in S9 and S15, when a dialog closes, it returns to the button that opened it.
4. The shortcuts reach each region without going through the others: <kbd>Ctrl</kbd>+<kbd>F</kbd> the search field, <kbd>Ctrl</kbd>+<kbd>L</kbd> the list view, <kbd>Alt</kbd>+<kbd>1</kbd> to <kbd>Alt</kbd>+<kbd>4</kbd> the tabs of the details panel.

### 2.4.4 Link purpose (in context)

Level A. The name of each link, with its context, tells where it leads.

1. In S9, read the name of **Annuaire**, of each **bodacc.fr ↗**, of each **Réponse brute**, and of the chips of the section « Liens ».
2. Each name tells where the link leads, such as « Ouvrir l'annonce du 03/02/2025 sur bodacc.fr » or « Sélectionner DUPONT INVEST LTD ».

### 2.4.6 Headings and labels

Level AA. Titles and labels describe their topic or their purpose.

1. Read the titles of the sections of the review column (S6, S7) and of the sheet (S9), the labels of the fields (S2, S11), the names of the tabs (S11) and the titles of the dialogs (S9, S14, S15).
2. Each of them tells what follows it, or what the field expects.

### 2.4.7 Focus visible

Level AA. The focus is always visible.

1. In S1 to S15, at each <kbd>Tab</kbd>, find the focus on the screen without the help of the screen reader.
2. Check in particular: the graph and its selected entity (S5), the list view (S8), the rows of the review column (S6), the chips and the buttons **Provenance** (S9), the tabs and the cells of the tables (S11), the items of the menus (S14), and the card of the home screen (S15).

### 2.4.11 Focus not obscured (minimum)

Level AA. The focused widget is never hidden entirely by something else.

1. In S4, S7 and S9, while notifications are on the screen, Tab to the widgets they cover, such as the last buttons of the sheet.
2. In S13, Tab through the review column while the panel « Collectes en cours » is shown.
3. In S9, Tab to the bottom of the sheet: it scrolls to show the focused widget.
4. The focused widget stays at least partly visible.

### 2.5.1 Pointer gestures

Level A. What a gesture with several fingers or a path does, a single click can do too.

This check needs a touchpad.

1. Pinch to zoom in the graph, if the touchpad allows it.
2. The buttons « Zoom avant », « Zoom arrière » and « Ajuster à la fenêtre » do the same with a single click.

### 2.5.2 Pointer cancellation

Level A. A click acts when the button is released, and moving away before releasing cancels it.

This check needs the mouse.

1. Press the button of the mouse on each kind of control, move the pointer away, and release it: a button (S9), a result of the search (S4), a row of the review column (S6), a chip of the section « Liens » (S10), a card of the home screen (S15), and an entity of the graph (S5).
2. Nothing happens. Pressing and releasing on the same control does its action.

### 2.5.3 Label in name

Level A. The name read by the screen reader contains the text written on the control, in the same order.

1. In S4 to S15, compare the name read for each control with its visible text. For example, the button **Étendre** of a lead is read « Étendre DUPONT SERVICES », and the button **Provenance · 1 réponse** of a link is read « Provenance du lien Président Jean DUPONT : 1 réponse ».
2. The visible words appear in the name, in the same order, best at its start.
3. On Windows 11, Voice Access can check it: saying « click » and the visible text activates the control.

### 2.5.7 Dragging movements

Level AA. What is done by dragging can also be done with single clicks, without dragging.

This check needs the mouse.

1. Drag an entity of the graph to move it, and drag the background of the graph to move the view (S12).
2. For each, find a way to do the same with clicks only. The keyboard does not count for this criterion.

### 2.5.8 Target size (minimum)

Level AA. Each target for the pointer measures at least 24 × 24 pixels, or has enough space around it.

1. Measure the targets with PowerToys Screen Ruler on Windows, or on a screenshot in GIMP with its measure tool on Linux, with the system at a scale of 100 %.
2. Measure at least: the button closing a notification (S4), the arrow of the depth menu (S9), the buttons **Provenance** and the chips of the section « Liens » (S9), the buttons of the graph (S12), the button « Replier la colonne À examiner » (S12), and the button of the actions of a card (S15).
3. A smaller target passes when a circle of 24 pixels centred on it touches no other target.

## Understandable

### 3.1.1 Language of page

Level A. The screen reader knows that the interface is in French.

1. Set the screen reader to an English voice, with its automatic switch of language turned on: in NVDA, Settings › Speech › Automatic language switching.
2. Run S1 to S4: the texts of Lacis are read with a French voice.

### 3.2.1 On focus

Level A. Giving the focus to a widget never changes the context: no window opens, the focus does not jump, and no setting changes.

1. Tab through the whole window in S4 to S15.
2. Moving through the list view (S8) and the tables (S11) opens the sheet of the entity in the details panel: the focus stays where it is.

### 3.2.2 On input

Level A. Typing or changing a setting never changes the context without warning.

1. In S4, typing in the search field opens the list of results: the focus stays in the field, and the number of results is announced.
2. In S2, typing in the name shows a problem without moving the focus.
3. In S11 and S12, the filter field, the sort, the check box « Signalées seulement » and the menu **Filtres** change what is shown, without opening a window or moving the focus.

### 3.3.1 Error identification

Level A. An error is found, named and described in text.

1. In S2, a name with capital letters and an empty name each show a problem under the field, read by the screen reader, and the field is marked by more than its colour.
2. In S15, before quitting, press <kbd>Ctrl</kbd>+<kbd>N</kbd>, create an investigation named `essai`, and close it with <kbd>Ctrl</kbd>+<kbd>W</kbd>. Then open the actions of `faux-plombiers-31`, choose **Modifier le nom ou la question…**, and type `essai` as its name. The problem says that an investigation of this name already exists.
3. In S4, search `zzz`: the list says « Aucun résultat dans le registre national », and the screen reader announces it.

### 3.3.2 Labels or instructions

Level A. Each field has a label, and the instructions it needs.

1. Read the fields of S2, S4 and S11: « Nom », « Question », « Rechercher une entreprise » and « Filtrer les entités ».
2. Each has a visible label or an instruction that stays visible while typing, and the screen reader reads it. A placeholder that disappears while typing is not enough on its own.

### 3.3.3 Error suggestion

Level AA. An error message says how to correct the error.

1. Read the problems of S2 and of the check 3.3.1.
2. Each says what is expected, such as the characters allowed in a name.

### 3.3.4 Error prevention (legal, financial, data)

Level AA. An action that deletes or changes the data of the user can be checked, confirmed or undone.

1. In S15, **Supprimer…** asks for a confirmation, and the deleted investigation goes to the trash of the system.
2. In S7, a decision on a homonym is undone with <kbd>Ctrl</kbd>+<kbd>Z</kbd>, and withdrawn from the sheet of a person with **Retirer**.

### 3.3.7 Redundant entry

Level A. What the user already entered is not asked again in the same process.

1. In S15, the window « Modifier l'enquête » shows the current name and question.
2. In S4, adding a result keeps the search and its list, to add the next result without typing it again.

## Robust

### 4.1.2 Name, role, value

Level A. Each control tells the screen reader its name, its role, its state and its value, and the changes of its state.

1. In S1 to S15, at each <kbd>Tab</kbd>, write down what the screen reader reads. Each control has a name, and the right role: button, link, check box, menu button, tab, tree item, table cell.
2. The widgets drawn by Lacis tell their role and state: the chips of the section « Liens » are links (S9), the cards of the signals are groups (S9), the timeline of the notices is a list (S9), the button « Replier la colonne À examiner » and the buttons **Provenance** say whether they are folded or unfolded (S9, S12), the button **Vue liste** says whether it is on (S8), the button **Filtres** says what it filters (S12), and the card of an investigation reads its name and question (S15).
3. The changes are announced: unfolding a provenance (S9), checking a filter (S12), changing the tab (S11), selecting an entity in the graph (S5).

### 4.1.3 Status messages

Level AA. The screen reader announces the messages of status without moving the focus.

1. Write down what the screen reader announces, and when: the number of results in S4, the start and the end of an expansion in S5 and S13, what is new to examine in S6 and S7, the decision and its undo in S7, the copied SIREN and the refreshed notices in S9, the problems of the form in S2.
2. Each message is announced once, without moving the focus, and without cutting the sentence the screen reader was reading. An error is announced at once.
