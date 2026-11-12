import sqlite3

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QWidget
from pytestqt.qtbot import QtBot

from graph_scenario import PlumbersScenario, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.icons import IconFactory
from lacis.details import EntityDetails, entity_details
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
    details = entity_details(builder.connection, identifier)
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


def test_an_entity_without_facts_hides_them(
    sheet: EntitySheet, builder: InvestigationBuilder
) -> None:
    lonely = builder.address("1 PLACE DU CAPITOLE 31000 TOULOUSE")
    details = entity_details(builder.connection, lonely)
    assert details is not None
    sheet.show_details(details)
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
