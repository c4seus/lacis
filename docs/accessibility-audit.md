# Accessibility audit grid

This grid audits Lacis against the level AA of the [Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/), applied to a desktop application as the W3C note [WCAG2ICT](https://www.w3.org/TR/wcag2ict-22/) describes. It lists every criterion of levels A and AA, says why some of them do not apply to Lacis, and adapts the others to it.

The interface of Lacis is in French, so the grid quotes its texts in French, as they appear on the screen.

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

### 1.3.1 Info and relationships

Level A. What the layout shows, the screen reader tells: labels of fields, titles of sections, groups, lists, tables and trees.

### 1.3.2 Meaningful sequence

Level A. The screen reader reads the content in an order that keeps its meaning.

### 1.3.3 Sensory characteristics

Level A. No instruction relies only on a shape, a colour, a size, a position or a sound.

### 1.3.4 Orientation

Level AA. Lacis works whatever the orientation of the screen.

### 1.4.1 Use of colour

Level A. No information is given by colour alone.

### 1.4.3 Contrast (minimum)

Level AA. Text reaches a contrast of 4.5:1 with its background, and large text 3:1: 24 pixels, or 18.7 pixels in bold. Disabled controls are left out.

### 1.4.4 Resize text

Level AA. Text can be enlarged up to 200 % without losing content or function.

### 1.4.5 Images of text

Level AA. Text is written as text, not drawn in an image, except the logo.

### 1.4.10 Reflow

Level AA, adapted. WCAG asks for content that reflows in a width of 320 pixels without scrolling in two directions. A desktop window cannot shrink that far, so the grid checks the smallest window that Lacis allows, and the text enlarged on a small screen, as WCAG2ICT suggests.

### 1.4.11 Non-text contrast

Level AA. The borders of controls, the focus, the icons and the drawings of the graph reach a contrast of 3:1 with what surrounds them.

### 1.4.13 Content on hover or focus

Level AA. A tooltip or a popup that appears on hover or focus can be dismissed without moving, can be hovered, and stays until it is dismissed or no longer relevant.

## Operable

### 2.1.1 Keyboard

Level A. Everything can be done with the keyboard.

### 2.1.2 No keyboard trap

Level A. The focus can always leave a widget with the keyboard.

### 2.1.4 Character key shortcuts

Level A. A shortcut made of a single character key can be turned off or changed, or works only when its widget has the focus.

### 2.2.1 Timing adjustable

Level A. A time limit can be turned off, adjusted or extended, unless it is essential.

### 2.2.2 Pause, stop, hide

Level A. What moves for more than five seconds can be paused, stopped or hidden.

### 2.3.1 Three flashes or below threshold

Level A. Nothing flashes more than three times per second.

### 2.4.2 Page titled

Level A. Each window has a title that tells its subject.

### 2.4.3 Focus order

Level A. The focus moves in an order that keeps the meaning and the use of the window.

### 2.4.4 Link purpose (in context)

Level A. The name of each link, with its context, tells where it leads.

### 2.4.6 Headings and labels

Level AA. Titles and labels describe their topic or their purpose.

### 2.4.7 Focus visible

Level AA. The focus is always visible.

### 2.4.11 Focus not obscured (minimum)

Level AA. The focused widget is never hidden entirely by something else.

### 2.5.1 Pointer gestures

Level A. What a gesture with several fingers or a path does, a single click can do too.

### 2.5.2 Pointer cancellation

Level A. A click acts when the button is released, and moving away before releasing cancels it.

### 2.5.3 Label in name

Level A. The name read by the screen reader contains the text written on the control, in the same order.

### 2.5.7 Dragging movements

Level AA. What is done by dragging can also be done with single clicks, without dragging.

### 2.5.8 Target size (minimum)

Level AA. Each target for the pointer measures at least 24 × 24 pixels, or has enough space around it.

## Understandable

### 3.1.1 Language of page

Level A. The screen reader knows that the interface is in French.

### 3.2.1 On focus

Level A. Giving the focus to a widget never changes the context: no window opens, the focus does not jump, and no setting changes.

### 3.2.2 On input

Level A. Typing or changing a setting never changes the context without warning.

### 3.3.1 Error identification

Level A. An error is found, named and described in text.

### 3.3.2 Labels or instructions

Level A. Each field has a label, and the instructions it needs.

### 3.3.3 Error suggestion

Level AA. An error message says how to correct the error.

### 3.3.4 Error prevention (legal, financial, data)

Level AA. An action that deletes or changes the data of the user can be checked, confirmed or undone.

### 3.3.7 Redundant entry

Level A. What the user already entered is not asked again in the same process.

## Robust

### 4.1.2 Name, role, value

Level A. Each control tells the screen reader its name, its role, its state and its value, and the changes of its state.

### 4.1.3 Status messages

Level AA. The screen reader announces the messages of status without moving the focus.
