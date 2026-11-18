from typing import Any

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtWidgets import QApplication

REDUCED_MOTION_SETTING_KEY = "appearance/reduced_motion"
REDUCED_MOTION_NAME = "ReducedMotion"
UI_EFFECTS = (
    Qt.UIEffect.UI_General,
    Qt.UIEffect.UI_AnimateMenu,
    Qt.UIEffect.UI_FadeMenu,
    Qt.UIEffect.UI_AnimateCombo,
    Qt.UIEffect.UI_AnimateTooltip,
    Qt.UIEffect.UI_FadeTooltip,
    Qt.UIEffect.UI_AnimateToolBox,
)


def is_reduced_motion(preference: object) -> bool:
    return getattr(preference, "name", None) == REDUCED_MOTION_NAME


def motion_hints_of(style_hints: object) -> Any:
    accessibility = getattr(style_hints, "accessibility", None)
    hints = None if accessibility is None else accessibility()
    return hints if hasattr(hints, "motionPreference") else None


class MotionController(QObject):
    reduced_changed = Signal(bool)

    def __init__(
        self, application: QApplication, settings: QSettings, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.application = application
        self.settings = settings
        self.chosen = settings.value(REDUCED_MOTION_SETTING_KEY, False, type=bool) is True
        self.style_hints = application.styleHints()
        self.hints = motion_hints_of(self.style_hints)
        self.system_reduced = False
        if self.hints is not None:
            self.system_reduced = is_reduced_motion(self.hints.motionPreference())
            self.hints.motionPreferenceChanged.connect(self.follow_system)
        self.default_effects = {
            effect: QApplication.isEffectEnabled(effect) for effect in UI_EFFECTS
        }
        self.apply()

    @property
    def reduced(self) -> bool:
        return self.chosen or self.system_reduced

    def set_chosen(self, chosen: bool) -> None:
        if chosen == self.chosen:
            return
        self.chosen = chosen
        self.settings.setValue(REDUCED_MOTION_SETTING_KEY, chosen)
        self.settings.sync()
        self.apply()

    def follow_system(self, preference: object) -> None:
        self.system_reduced = is_reduced_motion(preference)
        self.apply()

    def apply(self) -> None:
        for effect, enabled in self.default_effects.items():
            QApplication.setEffectEnabled(effect, enabled and not self.reduced)
        self.reduced_changed.emit(self.reduced)

    def stop(self) -> None:
        if self.hints is not None:
            self.hints.motionPreferenceChanged.disconnect(self.follow_system)
            self.hints = None
        for effect, enabled in self.default_effects.items():
            QApplication.setEffectEnabled(effect, enabled)
