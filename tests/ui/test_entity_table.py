import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QIcon
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from lacis.design.icons import IconFactory
from lacis.details import BadgeTone
from lacis.signals.signal import Severity
from lacis.storage.entities import EntityKind
from lacis.tables import EntityRow, EntityStatus
from lacis.ui.data_table import IDENTIFIER_ROLE, SORT_ROLE, TONE_ROLE, badge_colours
from lacis.ui.entity_table import EntitiesTab, EntityColumn

ROWS = (
    EntityRow(
        "company:1",
        EntityKind.COMPANY,
        "DUPONT SERVICES",
        EntityStatus("Fermée", BadgeTone.CLOSED),
        Severity.HIGH,
        0.85,
        3,
    ),
    EntityRow(
        "company:2",
        EntityKind.COMPANY,
        "ACME PLOMBERIE",
        EntityStatus("Active", BadgeTone.ACTIVE),
        Severity.MEDIUM,
        0.9,
        5,
    ),
    EntityRow("person:1", EntityKind.PERSON, "Jean DUPONT", None, Severity.HIGH, 0.6, 1),
    EntityRow("address:1", EntityKind.ADDRESS, "12 RUE DES LILAS", None, None, None, 4),
    EntityRow(
        "foreign_company:1",
        EntityKind.FOREIGN_COMPANY,
        "DUPONT INVEST LTD",
        EntityStatus("Étranger", BadgeTone.OUTLINE),
        None,
        None,
        1,
    ),
)


@pytest.fixture
def tab(qtbot: QtBot, icon_factory: IconFactory) -> EntitiesTab:
    tab = EntitiesTab(icon_factory.colours_provider)
    qtbot.addWidget(tab)
    tab.resize(420, 500)
    tab.show_rows(ROWS)
    tab.show()
    return tab


def shown_labels(tab: EntitiesTab) -> list[str]:
    return [tab.proxy.index(row, 0).data() for row in range(tab.proxy.rowCount())]


def test_the_entities_are_sorted_by_score_by_default(tab: EntitiesTab) -> None:
    assert shown_labels(tab)[:3] == ["DUPONT SERVICES", "Jean DUPONT", "ACME PLOMBERIE"]
    assert set(shown_labels(tab)[3:]) == {"12 RUE DES LILAS", "DUPONT INVEST LTD"}
    assert tab.sort_box.currentText() == "Score"
    assert tab.summary_label.text() == "5 entités · 3 signalées"


def test_the_entities_are_sorted_by_name_kind_and_status(tab: EntitiesTab) -> None:
    tab.sort_box.setCurrentText("Nom")
    assert shown_labels(tab) == [
        "12 RUE DES LILAS",
        "ACME PLOMBERIE",
        "DUPONT INVEST LTD",
        "DUPONT SERVICES",
        "Jean DUPONT",
    ]
    tab.sort_box.setCurrentText("Type")
    kinds = [tab.proxy.index(row, EntityColumn.KIND).data() for row in range(tab.proxy.rowCount())]
    assert kinds == sorted(kinds, key=str.casefold)
    tab.sort_box.setCurrentText("État")
    statuses = [
        tab.proxy.index(row, EntityColumn.STATUS).data() for row in range(tab.proxy.rowCount())
    ]
    assert statuses == ["Active", "Étranger", "Fermée", "", ""]


def test_sorting_from_the_header_follows_in_the_sort_choice(tab: EntitiesTab) -> None:
    tab.table.sortByColumn(EntityColumn.NAME, Qt.SortOrder.DescendingOrder)
    assert tab.sort_box.currentText() == "Nom"
    assert shown_labels(tab)[0] == "Jean DUPONT"
    tab.table.sortByColumn(EntityColumn.LINKS, Qt.SortOrder.DescendingOrder)
    assert tab.sort_box.currentText() == "Nom"
    assert shown_labels(tab)[0] == "ACME PLOMBERIE"


def test_the_entities_are_filtered_to_the_flagged_ones_and_by_name(tab: EntitiesTab) -> None:
    tab.flagged_box.setChecked(True)
    assert sorted(shown_labels(tab)) == ["ACME PLOMBERIE", "DUPONT SERVICES", "Jean DUPONT"]
    tab.filter_field.setText(" dupont ")
    assert sorted(shown_labels(tab)) == ["DUPONT SERVICES", "Jean DUPONT"]
    tab.flagged_box.setChecked(False)
    assert sorted(shown_labels(tab)) == ["DUPONT INVEST LTD", "DUPONT SERVICES", "Jean DUPONT"]
    tab.filter_field.clear()
    assert len(shown_labels(tab)) == 5


def test_choosing_a_row_chooses_its_entity(qtbot: QtBot, tab: EntitiesTab) -> None:
    with qtbot.waitSignal(tab.entity_chosen) as chosen:
        tab.table.selectRow(2)
    assert chosen.args == ["company:2"]
    tab.table.setFocus()
    with qtbot.waitSignal(tab.entity_chosen) as chosen:
        QTest.keyClick(tab.table, Qt.Key.Key_Down)
    assert chosen.args[0] in {"address:1", "foreign_company:1"}


def test_a_selection_made_elsewhere_is_marked_without_being_chosen_again(
    qtbot: QtBot, tab: EntitiesTab
) -> None:
    with qtbot.assertNotEmitted(tab.entity_chosen):
        tab.mark_selected("person:1")
    assert tab.selected_identifier() == "person:1"
    assert tab.table.selectionModel().selectedRows()[0].data() == "Jean DUPONT"
    with qtbot.assertNotEmitted(tab.entity_chosen):
        tab.show_rows(ROWS)
    assert tab.selected_identifier() == "person:1"
    tab.mark_selected("person:404")
    assert tab.table.selectionModel().selectedRows() == []
    tab.mark_selected(None)
    assert tab.selected_identifier() is None
    tab.choose_current(QModelIndex(), QModelIndex())


def test_the_table_speaks_its_cells_and_is_reached_with_the_keyboard(tab: EntitiesTab) -> None:
    assert tab.table.accessibleName() == "Entités de l'enquête"
    assert tab.filter_field.accessibleName() == "Filtrer les entités par nom"
    assert tab.flagged_box.accessibleName() == "N'afficher que les entités signalées"
    assert tab.sort_box.accessibleName() == "Trier les entités par"
    assert not tab.table.tabKeyNavigation()
    assert tab.table.isColumnHidden(EntityColumn.KIND)
    assert tab.filter_field.nextInFocusChain() is tab.sort_box
    model = tab.model
    dupont = model.index(0, EntityColumn.NAME)
    spoken = Qt.ItemDataRole.AccessibleTextRole
    assert dupont.data(spoken) == "DUPONT SERVICES, Entreprise"
    assert isinstance(dupont.data(Qt.ItemDataRole.DecorationRole), QIcon)
    assert dupont.data(IDENTIFIER_ROLE) == "company:1"
    assert dupont.data(TONE_ROLE) is None
    assert model.index(0, EntityColumn.STATUS).data(TONE_ROLE) == "closed"
    assert model.index(0, EntityColumn.SCORE).data() == "0,85"
    assert model.index(0, EntityColumn.SCORE).data(TONE_ROLE) == "high"
    assert model.index(0, EntityColumn.SCORE).data(spoken) == "score 0,85, gravité forte"
    assert model.index(0, EntityColumn.SCORE).data(Qt.ItemDataRole.TextAlignmentRole) == (
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    assert model.index(0, EntityColumn.LINKS).data(spoken) == "3 liens"
    assert model.index(2, EntityColumn.LINKS).data(spoken) == "1 lien"
    assert model.index(2, EntityColumn.STATUS).data(spoken) == "sans état"
    assert model.index(2, EntityColumn.KIND).data(spoken) == "Personne"
    assert model.index(3, EntityColumn.LINKS).data(SORT_ROLE) == 4.0
    assert model.index(0, EntityColumn.NAME).data(Qt.ItemDataRole.EditRole) is None
    assert model.data(QModelIndex()) is None
    assert model.rowCount(dupont) == 0
    assert model.columnCount(dupont) == 0
    assert [model.headerData(column, Qt.Orientation.Horizontal) for column in EntityColumn] == [
        "Entité",
        "Type",
        "État",
        "Score",
        "Liens",
    ]
    assert model.headerData(0, Qt.Orientation.Vertical) is None


def test_the_badges_are_painted_in_both_themes(
    tab: EntitiesTab, icon_factory: IconFactory
) -> None:
    tab.table.grab()
    colours = icon_factory.colours_provider()
    assert badge_colours(colours, "unknown") == (None, colours.strong_border, colours.muted_text)
    assert badge_colours(colours, "information")[2] == colours.information
    assert tab.model.kind_icons.icon(EntityKind.PERSON) is tab.model.kind_icons.icon(
        EntityKind.PERSON
    )
