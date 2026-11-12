from dataclasses import dataclass
from pathlib import Path

PRODUCT_NAME = "Lacis"
APPLICATION_ID = "io.github.c4seus.lacis"
PRODUCT_DESCRIPTION = (
    "Cartographie des entreprises françaises, de leurs dirigeants et de leurs adresses."
)
REPOSITORY_URL = "https://github.com/c4seus/lacis"
LICENSE_NAME = "GNU General Public License v3.0 ou ultérieure"
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"
RESOURCE_DIRECTORY = Path(__file__).resolve().parent / "resources"


@dataclass(frozen=True)
class BundledAsset:
    name: str
    author: str
    license_name: str
    license_location: str


BUNDLED_ASSETS = (
    BundledAsset(
        name="Police Inter 4.1 (Regular, Medium, SemiBold)",
        author="The Inter Project Authors",
        license_name="SIL Open Font License 1.1",
        license_location="fonts/OFL.txt",
    ),
    BundledAsset(
        name="Icônes de l'interface et logo",
        author="créés pour Lacis",
        license_name=LICENSE_NAME,
        license_location=LICENSE_URL,
    ),
)
