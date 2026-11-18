from pytestqt.qtbot import QtBot

from lacis.design.theme_controller import TEXT_SIZES, ThemeController
from lacis.ui.text_size_menu import SIZE_LABELS, TextSizeMenu


def create_menu(qtbot: QtBot, theme_controller: ThemeController) -> TextSizeMenu:
    menu = TextSizeMenu(theme_controller)
    qtbot.addWidget(menu)
    return menu


def test_the_menu_offers_the_text_sizes_from_100_to_200_percent(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu = create_menu(qtbot, theme_controller)
    assert menu.title() == "Taille du te&xte"
    assert [action.text().replace("&", "") for action in menu.actions()] == [
        f"{size}\u00a0%" for size in TEXT_SIZES
    ]
    assert set(SIZE_LABELS) == set(TEXT_SIZES)


def test_the_current_text_size_is_checked(qtbot: QtBot, theme_controller: ThemeController) -> None:
    menu = create_menu(qtbot, theme_controller)
    assert [action.isChecked() for action in menu.actions()] == [True, False, False, False, False]


def test_choosing_a_text_size_applies_and_checks_it(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu = create_menu(qtbot, theme_controller)
    menu.size_actions[175].trigger()
    assert theme_controller.text_size == 175
    assert menu.size_actions[175].isChecked()
    assert not menu.size_actions[100].isChecked()
    theme_controller.set_text_size(125)
    assert menu.size_actions[125].isChecked()
    theme_controller.set_text_size(100)
