import re
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
QT_MODULE = re.compile(r"^(?:from|import) PySide6\.Qt(\w+)", re.MULTILINE)


def imported_qt_modules(*directories: str) -> set[str]:
    return {
        module.lower()
        for directory in directories
        for path in (REPOSITORY / directory).rglob("*.py")
        for module in QT_MODULE.findall(path.read_text(encoding="utf-8"))
    }
