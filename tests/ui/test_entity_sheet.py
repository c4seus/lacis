import sqlite3

import pytest
from PySide6.QtCore import Qt
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
def sheet(qtbot: QtBot, icon_factory: IconFactory) -> EntitySheet:
    sheet = EntitySheet(icon_factory)
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
    assert not sheet.expanded_label.isVisible()


def test_an_expanded_entity_tells_when(
    sheet: EntitySheet, builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    jean = builder.person("Jean", "DUPONT", expanded=True)
    shown(sheet, builder, scenario, jean)
    assert sheet.expanded_label.isVisible()
    assert sheet.expanded_label.text().startswith("Étendue le ")


@pytest.mark.parametrize(
    ("entity", "kind_label"),
    [
        ("acme_office", "Établissement"),
        ("jean", "Personne"),
        ("address", "Adresse"),
        ("invest", "Entreprise étrangère"),
    ],
)
def test_each_kind_has_its_sheet(
    sheet: EntitySheet,
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    entity: str,
    kind_label: str,
) -> None:
    shown(sheet, builder, scenario, getattr(scenario, entity))
    assert sheet.kind_label.text() == kind_label


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
