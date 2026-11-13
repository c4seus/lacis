from pytestqt.qtbot import QtBot

from lacis.design.icons import IconFactory
from lacis.graph.leads import Lead
from lacis.identity.homonyms import (
    Confidence,
    FirstNameRelation,
    HomonymPair,
    HomonymProposal,
    PersonIdentity,
)
from lacis.overview import InvestigationOverview
from lacis.storage.entities import EntityKind
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


def person(index: int) -> PersonIdentity:
    return PersonIdentity(f"person:{index}", f"Jean DUPONT {index}", "DUPONT", ("JEAN",), None)


def overview_with(homonyms: int, leads: int) -> InvestigationOverview:
    proposals = tuple(
        HomonymProposal(
            HomonymPair(person(2 * index), person(2 * index + 1), FirstNameRelation.SAME),
            Confidence.WEAK,
            ("Même nom de famille",),
        )
        for index in range(homonyms)
    )
    unexpanded = tuple(
        Lead(f"company:10000000{index}", EntityKind.COMPANY, f"SOCIETE {index}", "Raison")
        for index in range(leads)
    )
    return InvestigationOverview(9, 8, 1, None, proposals=proposals, unexpanded=unexpanded)


def overview() -> InvestigationOverview:
    return overview_with(homonyms=0, leads=2)


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
    assert queue_summary(overview_with(homonyms=2, leads=1)) == (
        "signaux indisponibles, 2 homonymes, 1 piste"
    )


def test_the_graph_area_waits_for_the_graph(qtbot: QtBot, icon_factory: IconFactory) -> None:
    area = GraphArea(icon_factory)
    qtbot.addWidget(area)
    area.show()
    assert area.minimumWidth() == GRAPH_MINIMUM_WIDTH
    assert area.empty_label.text() == "Le graphe de l'enquête s'affichera ici."
    assert area.empty_label.isVisible()
    assert not area.legend.isVisible()


def test_the_details_panel_has_its_four_tabs(qtbot: QtBot, icon_factory: IconFactory) -> None:
    panel = DetailsPanel(icon_factory)
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
    rail.show_overview(overview_with(homonyms=0, leads=2))
    assert not rail.count_label.isVisible()
    assert rail.expand_button.accessibleDescription() == (
        "signaux indisponibles, 0 homonyme, 2 pistes"
    )
