from pytestqt.qtbot import QtBot

from lacis.design.icons import IconFactory
from lacis.overview import InvestigationOverview
from lacis.ui.investigation_columns import (
    DETAILS_MINIMUM_WIDTH,
    GRAPH_MINIMUM_WIDTH,
    QUEUE_MINIMUM_WIDTH,
    DetailsPanel,
    GraphArea,
    QueueColumn,
    QueueRail,
    queue_summary,
)


def overview() -> InvestigationOverview:
    return InvestigationOverview(9, 8, 1, 0, 2, None, "")


def test_the_queue_column_sums_up_what_is_left_to_examine(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    column = QueueColumn(icon_factory)
    qtbot.addWidget(column)
    assert column.title_label.text() == "À EXAMINER"
    assert column.title_label.accessibleName() == "À examiner"
    assert column.minimumWidth() == QUEUE_MINIMUM_WIDTH
    column.show_overview(overview())
    assert column.summary_label.text() == "signaux indisponibles, 0 homonyme, 2 pistes"


def test_the_queue_summary_counts_signals_homonyms_and_leads() -> None:
    assert queue_summary(InvestigationOverview(9, 8, 1, 2, 1, None, "")) == (
        "signaux indisponibles, 2 homonymes, 1 piste"
    )


def test_the_graph_area_waits_for_the_graph(qtbot: QtBot) -> None:
    area = GraphArea()
    qtbot.addWidget(area)
    assert area.minimumWidth() == GRAPH_MINIMUM_WIDTH
    assert area.empty_label.text() == "Le graphe de l'enquête s'affichera ici."


def test_the_details_panel_has_its_four_tabs(qtbot: QtBot) -> None:
    panel = DetailsPanel()
    qtbot.addWidget(panel)
    assert panel.minimumWidth() == DETAILS_MINIMUM_WIDTH
    assert [panel.tabs.tabText(index) for index in range(panel.tabs.count())] == [
        "Fiche",
        "Signaux",
        "Entités",
        "Journal",
    ]
    assert panel.tabs.accessibleName() == "Panneau de détails"


def test_the_queue_column_can_be_collapsed_with_a_named_button(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    column = QueueColumn(icon_factory)
    qtbot.addWidget(column)
    assert column.collapse_button.accessibleName() == "Replier la colonne À examiner"
    assert column.collapse_button.toolTip() == "Replier"


def test_the_rail_shows_the_signal_count_and_describes_the_queue(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    rail = QueueRail(icon_factory)
    qtbot.addWidget(rail)
    rail.show()
    assert rail.accessibleName() == "Colonne À examiner repliée"
    assert rail.expand_button.accessibleName() == "Déplier la colonne À examiner"
    rail.show_overview(InvestigationOverview(9, 8, 1, 0, 2, None, ""))
    assert not rail.count_label.isVisible()
    assert rail.expand_button.accessibleDescription() == (
        "signaux indisponibles, 0 homonyme, 2 pistes"
    )
