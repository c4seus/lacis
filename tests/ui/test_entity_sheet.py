import sqlite3
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QWidget
from pytestqt.qtbot import QtBot

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.icons import IconFactory
from lacis.details import EntityDetails, entity_details
from lacis.signals.signal import Severity
from lacis.ui.entity_sheet import EntitySheet
from lacis.ui.flow_layout import FlowLayout


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    return plumbers_scenario(builder)


@pytest.fixture
def opened_urls() -> list[QUrl]:
    return []


@pytest.fixture
def sheet(qtbot: QtBot, icon_factory: IconFactory, opened_urls: list[QUrl]) -> EntitySheet:
    sheet = EntitySheet(icon_factory, open_url=opened_urls.append)
    qtbot.addWidget(sheet)
    sheet.resize(420, 900)
    sheet.show()
    return sheet


def details_of(
    builder: InvestigationBuilder, scenario: PlumbersScenario, identifier: str
) -> EntityDetails:
    details = entity_details(builder.connection, identifier, phoenix_report(scenario))
    assert details is not None
    return details


def shown(
    sheet: EntitySheet,
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    identifier: str,
) -> EntityDetails:
    details = details_of(builder, scenario, identifier)
    sheet.show_details(details)
    return details


def test_an_empty_sheet_waits_for_a_selection(sheet: EntitySheet) -> None:
    assert sheet.details is None
    assert sheet.empty_label.text() == "La fiche de l'entité sélectionnée s'affichera ici."
    assert sheet.accessibleName() == "Fiche de l'entité"


def test_a_company_sheet_shows_its_head(
    sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    details = shown(sheet, builder, scenario, scenario.dupont_services)
    assert sheet.kind_label.text() == "Entreprise"
    assert [label.text() for label in sheet.badge_labels] == ["Fermée"]
    assert sheet.badge_labels[0].property("tone") == "badge-closed"
    assert sheet.name_label.text() == "DUPONT SERVICES"
    assert [label.text() for label in sheet.fact_labels] == list(details.facts)
    assert sheet.expand_button.text() == "Étendre"
    assert sheet.expand_button.isVisible()
    assert sheet.directory_button.isVisible()
    assert sheet.copy_button.text() == "Copier le SIREN"
    assert not sheet.expanded_label.isVisible()


def test_an_expanded_entity_offers_to_expand_it_again(
    sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    jean = builder.person("Jean", "DUPONT", expanded=True)
    shown(sheet, builder, scenario, jean)
    assert sheet.expand_button.text() == "Étendre à nouveau"
    assert sheet.expanded_label.isVisible()
    assert sheet.expanded_label.text().startswith("Étendue le ")


@pytest.mark.parametrize(
    "expected",
    [
        ("acme_office", "Établissement", False, True),
        ("jean", "Personne", True, True),
        ("address", "Adresse", True, True),
        ("invest", "Entreprise étrangère", False, False),
    ],
)
def test_each_kind_has_its_sheet(
    sheet: EntitySheet,
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    expected: tuple[str, str, bool, bool],
) -> None:
    entity, kind_label, expandable, with_directory = expected
    shown(sheet, builder, scenario, getattr(scenario, entity))
    assert sheet.kind_label.text() == kind_label
    assert sheet.expand_button.isVisible() is expandable
    assert sheet.directory_button.isVisible() is with_directory


def test_the_depth_menu_chooses_how_far_to_expand(
    qtbot: QtBot, sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    shown(sheet, builder, scenario, scenario.dupont_services)
    actions = sheet.depth_menu.actions()
    assert [action.text() for action in actions] == [
        "Profondeur 1",
        "Profondeur 2",
        "Profondeur 3",
    ]
    with qtbot.waitSignal(sheet.expansion_requested) as requested:
        actions[2].trigger()
    assert requested.args == [scenario.dupont_services, "DUPONT SERVICES", 3, False]
    with qtbot.waitSignal(sheet.expansion_requested) as requested:
        sheet.expand_button.click()
    assert requested.args == [scenario.dupont_services, "DUPONT SERVICES", 1, False]


def test_expanding_again_refreshes_the_entity(
    qtbot: QtBot, sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    jean = builder.person("Jean", "DUPONT", expanded=True)
    shown(sheet, builder, scenario, jean)
    with qtbot.waitSignal(sheet.expansion_requested) as requested:
        sheet.depth_menu.actions()[1].trigger()
    assert requested.args == [jean, "Jean DUPONT", 2, True]


def test_the_directory_link_opens_the_entity_page(
    sheet: EntitySheet,
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    opened_urls: list[QUrl],
) -> None:
    details = shown(sheet, builder, scenario, scenario.dupont_services)
    sheet.directory_button.click()
    assert opened_urls == [QUrl(details.directory_url)]


def test_copying_puts_the_identifier_in_the_clipboard(
    qtbot: QtBot, sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    details = shown(sheet, builder, scenario, scenario.dupont_services)
    with qtbot.waitSignal(sheet.copied) as copied:
        sheet.copy_button.click()
    assert QGuiApplication.clipboard().text() == details.copy_value
    assert copied.args == [f"« {details.copy_value} » copié dans le presse-papiers."]


def test_actions_without_an_entity_do_nothing(
    qtbot: QtBot, sheet: EntitySheet, opened_urls: list[QUrl]
) -> None:
    with qtbot.assertNotEmitted(sheet.expansion_requested), qtbot.assertNotEmitted(sheet.copied):
        sheet.expand(1)
        sheet.copy()
        sheet.open_directory()
    assert opened_urls == []


def test_the_signals_name_the_entities_that_justify_them(
    qtbot: QtBot, sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    shown(sheet, builder, scenario, scenario.dupont_services)
    [card] = sheet.signal_cards
    assert card.property("severity") == "high"
    assert card.severity_badge.text() == "Forte"
    assert card.severity_badge.property("tone") == "badge-high"
    assert card.title_label.text() == "Schéma phénix"
    assert card.score_label.text() == "score 0,85"
    assert [chip.label.text() for chip in card.chips] == [
        "ACME PLOMBERIE",
        "Jean DUPONT",
        "Jean Pierre DUPONT",
    ]
    assert card.chips[0].accessibleName() == "Sélectionner ACME PLOMBERIE"
    assert sheet.section_titles[0].accessibleName() == "Signaux d'alerte, 1"


def test_clicking_a_justifying_entity_selects_it(
    qtbot: QtBot, sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    shown(sheet, builder, scenario, scenario.dupont_services)
    chip = sheet.signal_cards[0].chips[0]
    with qtbot.waitSignal(sheet.entity_chosen) as chosen:
        QTest.mouseClick(chip, Qt.MouseButton.LeftButton)
    assert chosen.args == [scenario.acme]
    for key in (Qt.Key.Key_Return, Qt.Key.Key_Space):
        with qtbot.waitSignal(sheet.entity_chosen) as chosen:
            QTest.keyClick(chip, key)
        assert chosen.args == [scenario.acme]
    with qtbot.assertNotEmitted(sheet.entity_chosen, wait=10):
        QTest.keyClick(chip, Qt.Key.Key_A)
        QTest.mouseClick(chip, Qt.MouseButton.RightButton)
    assert chip.focusPolicy() & Qt.FocusPolicy.TabFocus


def test_the_links_of_the_entity_are_listed(
    qtbot: QtBot, sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    shown(sheet, builder, scenario, scenario.dupont_services)
    assert [(row.role_label.text(), row.chip.label.text()) for row in sheet.link_rows] == [
        ("Président", "Jean DUPONT"),
        ("Siège social", "12 RUE DES LILAS 31000 TOULOUSE"),
        ("Établissement", "Siège — TOULOUSE"),
    ]
    closed = sheet.link_rows[2]
    assert [label.text() for label in closed.findChildren(QLabel)].count("Fermé") == 1
    with qtbot.waitSignal(sheet.entity_chosen) as chosen:
        QTest.mouseClick(sheet.link_rows[0].chip, Qt.MouseButton.LeftButton)
    assert chosen.args == [scenario.jean]


def test_medium_and_low_signals_have_their_own_colour(
    sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    details = details_of(builder, scenario, scenario.dupont_services)
    for severity in (Severity.MEDIUM, Severity.LOW):
        card = replace(details.signals[0], severity=severity)
        sheet.show_details(replace(details, signals=(card,)))
        assert sheet.signal_cards[0].property("severity") == severity.value


def test_an_entity_without_signals_or_links_shows_only_its_head(
    sheet: EntitySheet, builder: InvestigationBuilder
) -> None:
    lonely = builder.address("1 PLACE DU CAPITOLE 31000 TOULOUSE")
    details = entity_details(builder.connection, lonely, None)
    assert details is not None
    sheet.show_details(details)
    assert sheet.section_titles == []
    assert not sheet.facts.isVisible()


def test_a_flow_layout_wraps_its_widgets(qtbot: QtBot) -> None:
    container = QWidget()
    qtbot.addWidget(container)
    layout = FlowLayout(container, horizontal_spacing=4, vertical_spacing=2)
    labels = [QLabel(f"Élément {index}", container) for index in range(6)]
    for label in labels:
        label.setFixedSize(60, 20)
        layout.addWidget(label)
    assert layout.count() == 6
    assert layout.heightForWidth(1000) == 20
    assert layout.heightForWidth(130) == 3 * 20 + 2 * 2
    assert layout.minimumSize().width() == 60
    assert layout.sizeHint() == layout.minimumSize()
    assert layout.expandingDirections() == Qt.Orientation(0)
    container.resize(130, 64)
    container.show()
    assert labels[2].y() == 22
    assert layout.itemAt(9) is None
    assert layout.takeAt(9) is None
    taken = layout.takeAt(0)
    assert taken is not None
    assert layout.count() == 5
    labels[1].hide()
    assert layout.heightForWidth(130) == 2 * 20 + 2
