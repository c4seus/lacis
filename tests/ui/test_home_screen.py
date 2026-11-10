import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from accessibility_checks import interactive_widgets_without_accessible_name, tab_order
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.storage.investigations import DATABASE_FILE_NAME, InvestigationLibrary
from lacis.ui.home_screen import (
    DELETION_DETAILS,
    HomeScreen,
    InvestigationCard,
    actions_name,
    counted,
    deletion_question,
)
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
    home_screen.activateWindow()
    qtbot.waitUntil(home_screen.isActiveWindow)
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
    home_screen.create_first_button.click()
    assert home_screen.new_investigation_panel.isVisible()
    assert not home_screen.empty_state.isVisible()
    assert home_screen.new_investigation_panel.fields.name_field.input.hasFocus()


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


def test_the_new_investigation_button_opens_the_creation_form_above_the_cards(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    assert not home_screen.new_investigation_panel.isVisible()
    home_screen.new_investigation_button.click()
    panel = home_screen.new_investigation_panel
    assert panel.isVisible()
    assert panel.parentWidget() is home_screen.cards[0].parentWidget()
    assert panel.y() < home_screen.cards[0].y()


def test_cancelling_the_first_creation_brings_the_invitation_back(
    qtbot: QtBot, tmp_path: Path, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, InvestigationLibrary(tmp_path / "vide"), icon_factory)
    home_screen.create_first_button.click()
    home_screen.new_investigation_panel.cancel_button.click()
    assert home_screen.empty_state.isVisible()
    assert home_screen.create_first_button.hasFocus()


def test_cancelling_a_creation_gives_the_focus_back_to_the_new_investigation_button(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    home_screen.new_investigation_button.click()
    home_screen.new_investigation_panel.cancel_button.click()
    assert home_screen.new_investigation_button.hasFocus()
    assert not home_screen.empty_state.isVisible()


def open_main_window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> MainWindow:
    main_window = MainWindow(settings, theme_controller, library=library)
    qtbot.addWidget(main_window)
    main_window.show()
    main_window.activateWindow()
    qtbot.waitUntil(main_window.isActiveWindow)
    return main_window


def card_named(main_window: MainWindow, name: str) -> InvestigationCard:
    return next(card for card in main_window.home_screen.cards if card.summary.name == name)


def test_a_created_investigation_is_opened(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller, library)
    main_window.home_screen.new_investigation_button.click()
    fields = main_window.home_screen.new_investigation_panel.fields
    fields.fill("rafale-marseille", "Qui a créé quatre sociétés en trois semaines ?")
    main_window.home_screen.new_investigation_panel.create_button.click()
    assert main_window.current_investigation == "rafale-marseille"
    assert main_window.investigation_page.question_label.text() == (
        "Qui a créé quatre sociétés en trois semaines ?"
    )
    assert card_named(main_window, "rafale-marseille") is main_window.home_screen.cards[0]


def test_the_file_menu_starts_a_creation_from_any_page(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller, library)
    main_window.open_investigation("fournisseur-acme")
    main_window.main_menu_bar.new_investigation_action.trigger()
    assert main_window.pages.currentWidget() is main_window.home_screen
    assert main_window.current_investigation is None
    assert main_window.home_screen.new_investigation_panel.isVisible()
    main_window.main_menu_bar.new_investigation_action.trigger()
    assert main_window.home_screen.new_investigation_panel.fields.name_field.input.hasFocus()


def test_clicking_a_card_opens_its_investigation(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller, library)
    QTest.mouseClick(card_named(main_window, "faux-plombiers-31"), Qt.MouseButton.LeftButton)
    assert main_window.current_investigation == "faux-plombiers-31"
    assert main_window.pages.currentWidget() is main_window.investigation_page
    assert main_window.investigation_page.name_label.text() == "faux-plombiers-31"
    assert main_window.investigation_page.question_label.text() == (
        "Qui se cache derrière les plombiers du 12 rue des Lilas ?"
    )
    assert [label.text() for label in main_window.header_bar.breadcrumb.step_labels] == [
        "Enquêtes",
        "faux-plombiers-31",
    ]


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space])
def test_a_focused_card_opens_with_the_keyboard(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
    key: Qt.Key,
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller, library)
    card = card_named(main_window, "serie-montpellier")
    card.setFocus()
    QTest.keyClick(card, key)
    assert main_window.current_investigation == "serie-montpellier"


def test_cards_are_reached_with_tab(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller, library)
    order = tab_order(main_window)
    cards = main_window.home_screen.cards
    assert order[-6:] == [widget for card in cards for widget in (card, card.more_button)]
    assert interactive_widgets_without_accessible_name(main_window) == []


def test_other_keys_and_buttons_do_not_open_a_card(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller, library)
    card = card_named(main_window, "serie-montpellier")
    card.setFocus()
    QTest.keyClick(card, Qt.Key.Key_A)
    QTest.mouseClick(card, Qt.MouseButton.RightButton)
    assert main_window.current_investigation is None


def test_going_back_shows_the_home_screen_again(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller, library)
    main_window.open_investigation("fournisseur-acme")
    main_window.investigation_page.back_button.click()
    assert main_window.current_investigation is None
    assert main_window.pages.currentWidget() is main_window.home_screen
    assert [label.text() for label in main_window.header_bar.breadcrumb.step_labels] == [
        "Enquêtes"
    ]


def test_an_investigation_that_cannot_be_opened_is_reported(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text: warnings.append((title, text)),
    )
    main_window = open_main_window(qtbot, settings, theme_controller, library)
    database = library.directory_of("fournisseur-acme") / DATABASE_FILE_NAME
    database.write_bytes(b"pas une base SQLite")
    main_window.open_investigation("fournisseur-acme")
    main_window.open_investigation("absente")
    assert warnings == [
        (
            "Impossible d'ouvrir l'enquête",
            "La base de données de cette enquête est illisible.",
        ),
        ("Impossible d'ouvrir l'enquête", "L'enquête « absente » est introuvable."),
    ]
    assert main_window.current_investigation is None


def test_each_card_has_an_actions_button_named_after_its_investigation(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    card = home_screen.cards[0]
    assert card.more_button.accessibleName() == "Actions de l'enquête faux-plombiers-31"
    assert actions_name("serie-montpellier") == "Actions de l'enquête serie-montpellier"
    assert card.more_button.menu() is card.actions_menu
    assert card.edit_action.text() == "&Modifier le nom ou la question…"
    assert card.edit_action.isEnabled()
    assert card.delete_action.text() == "&Supprimer…"


def test_clicking_the_actions_button_does_not_open_the_investigation(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    opened: list[str] = []
    home_screen.investigation_opened.connect(opened.append)
    card = home_screen.cards[0]
    card.actions_menu.aboutToShow.connect(card.actions_menu.close)
    QTest.mouseClick(card.more_button, Qt.MouseButton.LeftButton)
    assert opened == []


def test_editing_a_card_opens_the_edit_dialog_with_its_investigation(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    home_screen.card_named("serie-montpellier").edit_action.trigger()
    dialog = home_screen.edit_dialog
    assert dialog is not None
    assert dialog.isVisible()
    assert dialog.fields.name() == "serie-montpellier"
    assert dialog.fields.question() == (
        "Le gérant de MOREAU BATIMENT enchaîne-t-il les sociétés ?"
    )


def test_a_saved_edit_updates_the_cards_and_focuses_the_edited_one(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    home_screen = open_home_screen(qtbot, library, icon_factory)
    home_screen.edit_investigation("fournisseur-acme")
    dialog = home_screen.edit_dialog
    assert dialog is not None
    dialog.fields.fill("fournisseur-acme-2026", "Ce fournisseur paie-t-il ses dettes ?")
    dialog.save_button.click()
    card = home_screen.card_named("fournisseur-acme-2026")
    assert card.question_label.text() == "Ce fournisseur paie-t-il ses dettes ?"
    assert len(home_screen.cards) == 3
    assert home_screen.focusWidget() is card


def test_an_unreadable_investigation_cannot_be_edited(
    qtbot: QtBot, library: InvestigationLibrary, icon_factory: IconFactory
) -> None:
    broken = library.directory_of("fournisseur-acme") / DATABASE_FILE_NAME
    broken.write_bytes(b"pas une base SQLite")
    home_screen = open_home_screen(qtbot, library, icon_factory)
    assert not home_screen.card_named("fournisseur-acme").edit_action.isEnabled()


Question = tuple[str, str, str, str]


def answer_deletion(monkeypatch: pytest.MonkeyPatch, confirmed: bool) -> list[Question]:
    questions: list[Question] = []

    def answered(box: QMessageBox) -> int:
        default_button = box.defaultButton()
        questions.append(
            (
                box.windowTitle(),
                box.text(),
                box.informativeText(),
                default_button.text() if default_button is not None else "",
            )
        )
        role = (
            QMessageBox.ButtonRole.DestructiveRole
            if confirmed
            else QMessageBox.ButtonRole.RejectRole
        )
        next(button for button in box.buttons() if box.buttonRole(button) == role).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", answered)
    return questions


@pytest.fixture
def trash(tmp_path: Path) -> Path:
    return tmp_path / "corbeille"


@pytest.fixture
def trashing_library(library: InvestigationLibrary, trash: Path) -> InvestigationLibrary:
    def move_to_trash(path: Path) -> bool:
        trash.mkdir(exist_ok=True)
        path.rename(trash / path.name)
        return True

    return InvestigationLibrary(library.root, move_to_trash=move_to_trash)


def test_deleting_asks_for_a_confirmation_that_names_the_investigation(
    qtbot: QtBot,
    trashing_library: InvestigationLibrary,
    icon_factory: IconFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    questions = answer_deletion(monkeypatch, confirmed=False)
    home_screen = open_home_screen(qtbot, trashing_library, icon_factory)
    home_screen.card_named("serie-montpellier").delete_action.trigger()
    assert questions == [
        (
            "Supprimer l'enquête",
            "Supprimer l'enquête « serie-montpellier » ?",
            DELETION_DETAILS,
            "Annuler",
        )
    ]
    assert deletion_question("x") == "Supprimer l'enquête « x » ?"
    assert DELETION_DETAILS.startswith("Elle sera placée dans la corbeille du système")


def test_a_refused_confirmation_keeps_the_investigation(
    qtbot: QtBot,
    trashing_library: InvestigationLibrary,
    icon_factory: IconFactory,
    monkeypatch: pytest.MonkeyPatch,
    trash: Path,
) -> None:
    answer_deletion(monkeypatch, confirmed=False)
    home_screen = open_home_screen(qtbot, trashing_library, icon_factory)
    home_screen.delete_investigation("serie-montpellier")
    assert "serie-montpellier" in trashing_library.names()
    assert len(home_screen.cards) == 3
    assert not trash.exists()


def test_a_confirmed_deletion_moves_the_investigation_to_the_trash(
    qtbot: QtBot,
    trashing_library: InvestigationLibrary,
    icon_factory: IconFactory,
    monkeypatch: pytest.MonkeyPatch,
    trash: Path,
) -> None:
    answer_deletion(monkeypatch, confirmed=True)
    home_screen = open_home_screen(qtbot, trashing_library, icon_factory)
    home_screen.delete_investigation("serie-montpellier")
    assert trashing_library.names() == ["faux-plombiers-31", "fournisseur-acme"]
    assert (trash / "serie-montpellier" / DATABASE_FILE_NAME).is_file()
    assert [card.summary.name for card in home_screen.cards] == [
        "faux-plombiers-31",
        "fournisseur-acme",
    ]
    assert home_screen.new_investigation_button.hasFocus()


def test_deleting_the_last_investigation_brings_the_invitation_back(
    qtbot: QtBot,
    trashing_library: InvestigationLibrary,
    icon_factory: IconFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_deletion(monkeypatch, confirmed=True)
    home_screen = open_home_screen(qtbot, trashing_library, icon_factory)
    for name in trashing_library.names():
        home_screen.delete_investigation(name)
    assert home_screen.cards == []
    assert home_screen.empty_state.isVisible()
    assert home_screen.create_first_button.hasFocus()


def test_a_trash_failure_is_reported_and_keeps_the_investigation(
    qtbot: QtBot,
    library: InvestigationLibrary,
    icon_factory: IconFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_deletion(monkeypatch, confirmed=True)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda parent, title, text: warnings.append((title, text))
    )
    failing_library = InvestigationLibrary(library.root, move_to_trash=lambda path: False)
    home_screen = open_home_screen(qtbot, failing_library, icon_factory)
    home_screen.delete_investigation("fournisseur-acme")
    assert warnings == [
        (
            "Impossible de supprimer l'enquête",
            "Impossible de placer l'enquête « fournisseur-acme » dans la corbeille.",
        )
    ]
    assert len(home_screen.cards) == 3


def test_an_unreadable_investigation_can_still_be_deleted(
    qtbot: QtBot,
    trashing_library: InvestigationLibrary,
    icon_factory: IconFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_deletion(monkeypatch, confirmed=True)
    broken = trashing_library.directory_of("fournisseur-acme") / DATABASE_FILE_NAME
    broken.write_bytes(b"pas une base SQLite")
    home_screen = open_home_screen(qtbot, trashing_library, icon_factory)
    card = home_screen.card_named("fournisseur-acme")
    assert card.delete_action.isEnabled()
    card.delete_action.trigger()
    assert "fournisseur-acme" not in trashing_library.names()
