import sqlite3
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.icons import IconFactory
from lacis.overview import overview_of
from lacis.review import ReviewQueue, review_queue
from lacis.storage.homonym_decisions import HomonymDecision
from lacis.ui.review_queue import ReviewQueueList


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    scenario = plumbers_scenario(builder)
    builder.person("Marie", "DUPONT")
    builder.person("Marie Claire", "DUPONT")
    return scenario


@pytest.fixture
def queue(builder: InvestigationBuilder, scenario: PlumbersScenario) -> ReviewQueue:
    overview = overview_of(builder.connection, None)
    return review_queue(replace(overview, report=phoenix_report(scenario)))


@pytest.fixture
def review_list(qtbot: QtBot, icon_factory: IconFactory, queue: ReviewQueue) -> ReviewQueueList:
    review_list = ReviewQueueList(icon_factory.colours_provider)
    qtbot.addWidget(review_list)
    review_list.resize(320, 800)
    review_list.show()
    review_list.show_queue(queue)
    return review_list


def test_the_queue_shows_its_three_sections(
    review_list: ReviewQueueList, queue: ReviewQueue
) -> None:
    assert review_list.group_titles == [
        "Schéma phénix · forte",
        "Homonymes à vérifier",
        "Pistes non étendues",
    ]
    assert [label.text() for label in review_list.group_labels] == [
        "SCHÉMA PHÉNIX · FORTE",
        "HOMONYMES À VÉRIFIER",
        "PISTES NON ÉTENDUES",
    ]
    assert [row.entity.identifier for row in review_list.rows] == queue.entity_identifiers()


def test_a_signal_row_shows_the_entity_its_score_and_explanation(
    review_list: ReviewQueueList, scenario: PlumbersScenario
) -> None:
    row = next(row for row in review_list.rows if row.entity.identifier == scenario.acme)
    assert row.title_label.text() == "ACME PLOMBERIE"
    assert row.score_label.text() == "0,85"
    assert row.detail_label.text() == "Indice du signal sur DUPONT SERVICES"
    assert row.accessibleName() == "ACME PLOMBERIE, entreprise, score 0,85"
    assert row.accessibleDescription() == "Indice du signal sur DUPONT SERVICES"


def test_a_homonym_row_offers_both_decisions(
    qtbot: QtBot, review_list: ReviewQueueList, queue: ReviewQueue
) -> None:
    [entry] = queue.homonyms
    same, different = review_list.decision_buttons
    assert (same.text(), different.text()) == ("Même personne", "Personne différente")
    assert same.accessibleName() == f"Même personne : {entry.title}"
    people = (entry.first.identifier, entry.second.identifier)
    labels = (entry.first.label, entry.second.label)
    with qtbot.waitSignal(review_list.decision_requested) as decided:
        same.click()
    assert decided.args == [people, labels, HomonymDecision.SAME_PERSON]
    with qtbot.waitSignal(review_list.decision_requested) as decided:
        different.click()
    assert decided.args == [people, labels, HomonymDecision.DIFFERENT_PERSON]
    row = next(row for row in review_list.rows if row.title_label.text() == entry.title)
    assert row.accessibleName() == f"{entry.title}, confiance probable"
    assert not row.score_label.isVisible()


def test_a_lead_row_offers_to_expand_it(
    qtbot: QtBot, review_list: ReviewQueueList, scenario: PlumbersScenario
) -> None:
    button = review_list.expand_buttons[scenario.holding]
    assert button.text() == "Étendre"
    assert button.accessibleName() == "Étendre HOLDING DUPONT"
    with qtbot.waitSignal(review_list.expansion_requested) as requested:
        button.click()
    assert requested.args == [scenario.holding, "HOLDING DUPONT"]


def test_a_running_expansion_disables_its_button_until_it_ends(
    review_list: ReviewQueueList, queue: ReviewQueue, scenario: PlumbersScenario
) -> None:
    review_list.show_expanding({scenario.holding})
    button = review_list.expand_buttons[scenario.holding]
    assert (button.isEnabled(), button.text()) == (False, "Extension…")
    review_list.show_queue(queue)
    assert not review_list.expand_buttons[scenario.holding].isEnabled()
    review_list.show_expanding(set())
    assert review_list.expand_buttons[scenario.holding].isEnabled()


def test_choosing_a_row_with_the_mouse_or_the_keyboard_tells_who_listens(
    qtbot: QtBot, review_list: ReviewQueueList, scenario: PlumbersScenario
) -> None:
    row = next(row for row in review_list.rows if row.entity.identifier == scenario.acme)
    with qtbot.waitSignal(review_list.entity_chosen) as chosen:
        QTest.mouseClick(row, Qt.MouseButton.LeftButton)
    assert chosen.args == [scenario.acme]
    for key in (Qt.Key.Key_Return, Qt.Key.Key_Space):
        with qtbot.waitSignal(review_list.entity_chosen) as chosen:
            QTest.keyClick(row, key)
        assert chosen.args == [scenario.acme]
    with qtbot.assertNotEmitted(review_list.entity_chosen, wait=10):
        QTest.keyClick(row, Qt.Key.Key_A)
        QTest.mouseClick(row, Qt.MouseButton.RightButton)
    assert row.focusPolicy() & Qt.FocusPolicy.TabFocus


def test_the_selected_entity_is_highlighted_in_the_queue(
    review_list: ReviewQueueList, queue: ReviewQueue, scenario: PlumbersScenario
) -> None:
    review_list.mark_selected(scenario.jean)
    selected = [row.entity.identifier for row in review_list.rows if row.property("selected")]
    assert selected == [scenario.jean, scenario.jean]
    review_list.mark_selected(scenario.jean)
    review_list.show_queue(queue)
    assert [row.entity.identifier for row in review_list.rows if row.property("selected")] == [
        scenario.jean,
        scenario.jean,
    ]
    review_list.mark_selected(None)
    assert not any(row.property("selected") for row in review_list.rows)


def test_an_empty_queue_says_there_is_nothing_to_examine(review_list: ReviewQueueList) -> None:
    review_list.show_queue(ReviewQueue((), (), ()))
    assert review_list.group_titles == [
        "Aucun signal",
        "Homonymes à vérifier",
        "Pistes non étendues",
    ]
    assert [label.text() for label in review_list.empty_labels] == [
        "Aucun rapprochement en attente",
        "Aucune piste à étendre",
    ]
    assert review_list.rows == []


def test_unavailable_signals_are_explained(review_list: ReviewQueueList) -> None:
    review_list.show_queue(ReviewQueue((), (), (), "Le fichier signals.toml est invalide."))
    assert review_list.group_titles[0] == "Signaux indisponibles"
    assert review_list.empty_labels[0].text() == "Le fichier signals.toml est invalide."
