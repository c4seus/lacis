import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.storage.investigations import DATABASE_FILE_NAME, InvestigationLibrary
from lacis.ui.home_screen import HomeScreen, counted
from lacis.ui.main_window import MainWindow

INVESTIGATIONS = (
    ("fournisseur-acme", "Ce fournisseur est-il fiable avant de signer ?", 28, 10),
    ("faux-plombiers-31", "Qui se cache derrière les plombiers du 12 rue des Lilas ?", 2, 11),
    ("serie-montpellier", "Le gérant de MOREAU BATIMENT enchaîne-t-il les sociétés ?", 1, 11),
)


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    for name, question, day, month in INVESTIGATIONS:
        investigation = library.create(name, question)
        modified_at = datetime(2026, month, day, 12, tzinfo=UTC).timestamp()
        os.utime(investigation.directory / DATABASE_FILE_NAME, (modified_at, modified_at))
    return library


def open_home_screen(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> HomeScreen:
    home_screen = HomeScreen(library, icon_factory)
    qtbot.addWidget(home_screen)
    home_screen.resize(1200, 800)
    home_screen.show()
    qtbot.waitExposed(home_screen)
    return home_screen


def test_investigations_are_shown_as_cards_the_most_recent_first(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    assert [card.name_label.text() for card in home_screen.cards] == [
        "faux-plombiers-31",
        "serie-montpellier",
        "fournisseur-acme",
    ]


def test_a_card_shows_the_question_counts_and_last_change(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    card = home_screen.cards[0]
    assert card.question_label.text() == (
        "Qui se cache derrière les plombiers du 12 rue des Lilas ?"
    )
    assert card.entity_count_label.text() == "<b>0</b> entité"
    assert card.link_count_label.text() == "<b>0</b> lien"
    assert card.modification_label.text() == "Modifiée le 02/11/2026"
    assert card.accessibleName() == "Enquête faux-plombiers-31"
    assert card.accessibleDescription() == (
        "Qui se cache derrière les plombiers du 12 rue des Lilas ? "
        "0 entité, 0 lien, Modifiée le 02/11/2026."
    )


def test_cards_are_laid_out_in_two_columns(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    first, second, third = home_screen.cards
    assert first.y() == second.y()
    assert first.x() < second.x()
    assert third.x() == first.x()
    assert third.y() > first.y()


def test_refreshing_the_home_screen_shows_new_investigations(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    library.create("rafale-marseille", "Qui a créé quatre sociétés en trois semaines ?")
    home_screen.refresh()
    assert home_screen.cards[0].name_label.text() == "rafale-marseille"
    assert len(home_screen.cards) == 4


def test_a_problem_replaces_the_question_on_its_card(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    broken = library.directory_of("fournisseur-acme") / DATABASE_FILE_NAME
    broken.write_bytes(b"pas une base SQLite")
    home_screen = open_home_screen(qtbot, library, icon_factory)
    card = next(card for card in home_screen.cards if card.summary.name == "fournisseur-acme")
    assert card.question_label.text() == "La base de données de cette enquête est illisible."
    assert card.question_label.property("tone") == "muted"


def test_counts_are_plural_from_two() -> None:
    assert counted(2, "entité", "entités") == "<b>2</b> entités"
    assert counted(1, "lien", "liens") == "<b>1</b> lien"


def test_the_main_window_opens_on_the_home_screen(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    main_window = MainWindow(settings, theme_controller, library=library)
    qtbot.addWidget(main_window)
    main_window.show()
    assert main_window.home_screen.isVisible()
    assert main_window.home_screen.title_label.text() == "Enquêtes"
    assert len(main_window.home_screen.cards) == 3


def test_an_empty_library_shows_an_invitation_to_create_an_investigation(
    qtbot: QtBot, tmp_path: Path, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, InvestigationLibrary(tmp_path / "vide"), icon_factory)
    assert home_screen.cards == []
    assert home_screen.empty_state.isVisible()
    assert home_screen.create_first_button.text() == "Créer une première enquête"
    with qtbot.waitSignal(home_screen.creation_requested):
        home_screen.create_first_button.click()


def test_the_invitation_disappears_once_an_investigation_exists(
    qtbot: QtBot, tmp_path: Path, icon_factory: IconFactory
) -> None:
    library = InvestigationLibrary(tmp_path / "vide")
    home_screen = open_home_screen(qtbot, library, icon_factory)
    library.create("faux-plombiers-31", "")
    home_screen.refresh()
    assert not home_screen.empty_state.isVisible()
    assert len(home_screen.cards) == 1


def test_investigations_hide_the_invitation(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    assert not home_screen.empty_state.isVisible()


def test_the_new_investigation_button_asks_for_a_creation(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    with qtbot.waitSignal(home_screen.creation_requested):
        home_screen.new_investigation_button.click()
