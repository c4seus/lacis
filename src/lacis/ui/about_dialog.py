from html import escape

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from lacis import __version__
from lacis.design.icons import IconFactory
from lacis.product import (
    BUNDLED_ASSETS,
    LICENSE_NAME,
    LICENSE_URL,
    PRODUCT_DESCRIPTION,
    PRODUCT_NAME,
    REPOSITORY_URL,
    RESOURCE_DIRECTORY,
    BundledAsset,
)
from lacis.ui.header_bar import IconMark

ABOUT_DIALOG_TITLE = "À propos de Lacis"
ABOUT_LOGO_SIZE = QSize(48, 48)
BUNDLED_ASSETS_HEADING = "Composants intégrés"
WEB_ADDRESS_PREFIX = "https://"


def html_text(text: str) -> str:
    return escape(text, quote=False)


def link(address: str, text: str) -> str:
    return f'<a href="{address}">{html_text(text)}</a>'


def version_text(version: str) -> str:
    return f"Version {version}"


def license_text() -> str:
    return f"Logiciel libre publié sous la {link(LICENSE_URL, LICENSE_NAME)}."


def source_code_text() -> str:
    return f"Code source\u00a0: {link(REPOSITORY_URL, REPOSITORY_URL)}"


def license_address(asset: BundledAsset) -> QUrl:
    if asset.license_location.startswith(WEB_ADDRESS_PREFIX):
        return QUrl(asset.license_location)
    return QUrl.fromLocalFile(str(RESOURCE_DIRECTORY / asset.license_location))


def bundled_asset_text(asset: BundledAsset) -> str:
    return (
        f"{html_text(asset.name)}, {html_text(asset.author)}, sous "
        f"{link(license_address(asset).toString(), asset.license_name)}"
    )


def link_label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(True)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    return label


class AboutDialog(QDialog):
    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(ABOUT_DIALOG_TITLE)
        self.setMinimumWidth(480)

        self.logo_mark = IconMark(icon_factory.logo(), ABOUT_LOGO_SIZE, parent=self)
        self.name_label = QLabel(PRODUCT_NAME, self)
        self.name_label.setProperty("tone", "heading")
        self.version_label = QLabel(version_text(__version__), self)
        self.version_label.setProperty("tone", "muted")
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.description_label = QLabel(PRODUCT_DESCRIPTION, self)
        self.description_label.setWordWrap(True)
        self.license_label = link_label(license_text(), self)
        self.source_code_label = link_label(source_code_text(), self)
        self.bundled_assets_heading = QLabel(BUNDLED_ASSETS_HEADING, self)
        self.bundled_assets_heading.setProperty("tone", "current")
        self.bundled_asset_labels = [
            link_label(bundled_asset_text(asset), self) for asset in BUNDLED_ASSETS
        ]
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_button = self.button_box.button(QDialogButtonBox.StandardButton.Close)
        close_button.setText("Fermer")
        self.button_box.rejected.connect(self.reject)
        self.arrange()

    def arrange(self) -> None:
        identity_layout = QVBoxLayout()
        identity_layout.setSpacing(2)
        identity_layout.addWidget(self.name_label)
        identity_layout.addWidget(self.version_label)
        heading_layout = QHBoxLayout()
        heading_layout.setSpacing(16)
        heading_layout.addWidget(self.logo_mark)
        heading_layout.addLayout(identity_layout, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)
        layout.addLayout(heading_layout)
        layout.addWidget(self.description_label)
        layout.addWidget(self.license_label)
        layout.addWidget(self.source_code_label)
        layout.addSpacing(8)
        layout.addWidget(self.bundled_assets_heading)
        for asset_label in self.bundled_asset_labels:
            layout.addWidget(asset_label)
        layout.addSpacing(8)
        layout.addWidget(self.button_box)
