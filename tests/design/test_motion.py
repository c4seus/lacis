from collections.abc import Callable, Iterator
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from lacis.design import motion
from lacis.design.motion import (
    REDUCED_MOTION_SETTING_KEY,
    UI_EFFECTS,
    MotionController,
    is_reduced_motion,
    motion_hints_of,
)

REDUCED_MOTION = SimpleNamespace(name="ReducedMotion")
NO_PREFERENCE = SimpleNamespace(name="NoPreference")
QT_TELLS_THE_SYSTEM_MOTION = hasattr(Qt, "MotionPreference")
ANIMATED_MENU = Qt.UIEffect.UI_AnimateMenu

ControllerFactory = Callable[[], MotionController]


@pytest.fixture
def create_motion_controller(
    qapp: QApplication, settings: QSettings
) -> Iterator[ControllerFactory]:
    created: list[MotionController] = []

    def create() -> MotionController:
        controller = MotionController(qapp, settings)
        created.append(controller)
        return controller

    yield create
    for controller in created:
        controller.stop()


@pytest.fixture
def animated_menus() -> Iterator[None]:
    effects = (Qt.UIEffect.UI_General, ANIMATED_MENU)
    enabled = {effect: QApplication.isEffectEnabled(effect) for effect in effects}
    for effect in effects:
        QApplication.setEffectEnabled(effect, True)
    yield
    for effect, was_enabled in enabled.items():
        QApplication.setEffectEnabled(effect, was_enabled)


def test_motion_is_kept_by_default(create_motion_controller: ControllerFactory) -> None:
    controller = create_motion_controller()
    assert not controller.chosen
    assert not controller.reduced


def test_choosing_reduced_motion_turns_the_effects_of_qt_off_and_back_on(
    qtbot: QtBot, animated_menus: None, create_motion_controller: ControllerFactory
) -> None:
    controller = create_motion_controller()
    assert QApplication.isEffectEnabled(ANIMATED_MENU)
    with qtbot.waitSignal(controller.reduced_changed) as reduced:
        controller.set_chosen(True)
    assert reduced.args == [True]
    assert controller.reduced
    assert not any(QApplication.isEffectEnabled(effect) for effect in UI_EFFECTS)
    controller.set_chosen(False)
    assert QApplication.isEffectEnabled(ANIMATED_MENU)
    controller.set_chosen(True)
    controller.stop()
    assert QApplication.isEffectEnabled(ANIMATED_MENU)


def test_choosing_the_same_motion_again_changes_nothing(
    qtbot: QtBot, create_motion_controller: ControllerFactory
) -> None:
    controller = create_motion_controller()
    with qtbot.assertNotEmitted(controller.reduced_changed):
        controller.set_chosen(False)


def test_the_choice_stays_in_place_after_a_restart(
    settings: QSettings, create_motion_controller: ControllerFactory
) -> None:
    create_motion_controller().set_chosen(True)
    assert settings.value(REDUCED_MOTION_SETTING_KEY, type=bool) is True
    assert create_motion_controller().reduced


def test_the_system_can_ask_for_reduced_motion(
    create_motion_controller: ControllerFactory,
) -> None:
    controller = create_motion_controller()
    controller.follow_system(REDUCED_MOTION)
    assert controller.system_reduced
    assert controller.reduced
    controller.set_chosen(True)
    controller.follow_system(NO_PREFERENCE)
    assert controller.reduced
    controller.set_chosen(False)
    assert not controller.reduced


@pytest.mark.skipif(not QT_TELLS_THE_SYSTEM_MOTION, reason="Qt tells the system motion lately")
def test_the_system_motion_comes_from_qt(
    qapp: QApplication, create_motion_controller: ControllerFactory
) -> None:
    controller = create_motion_controller()
    style_hints = qapp.styleHints()
    hints = style_hints.accessibility()
    hints.motionPreferenceChanged.emit(Qt.MotionPreference.ReducedMotion)
    assert controller.reduced
    hints.motionPreferenceChanged.emit(Qt.MotionPreference.NoPreference)
    assert not controller.reduced


def test_without_a_system_motion_from_qt_only_the_choice_counts(
    monkeypatch: pytest.MonkeyPatch, create_motion_controller: ControllerFactory
) -> None:
    assert motion_hints_of(object()) is None
    assert motion_hints_of(SimpleNamespace(accessibility=SimpleNamespace)) is None
    monkeypatch.setattr(motion, "motion_hints_of", lambda style_hints: None)
    controller = create_motion_controller()
    assert controller.hints is None
    assert not controller.reduced
    controller.set_chosen(True)
    assert controller.reduced


def test_only_the_reduced_preference_counts_as_reduced_motion() -> None:
    assert is_reduced_motion(REDUCED_MOTION)
    assert not is_reduced_motion(NO_PREFERENCE)
    assert not is_reduced_motion(None)
