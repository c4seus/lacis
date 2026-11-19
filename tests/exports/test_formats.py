import json
from datetime import UTC, datetime
from pathlib import Path

from graph_scenario import plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.exports.formats import EXPORT_FORMATS, JSON_FORMAT, export_format
from lacis.exports.json_export import FORMAT_NAME, ExportScope
from lacis.storage.investigations import InvestigationLibrary

EXPORTED_AT = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)


def test_every_format_has_a_key_a_menu_entry_and_an_extension() -> None:
    assert [candidate.key for candidate in EXPORT_FORMATS] == ["json"]
    assert JSON_FORMAT.menu_text == "&JSON…"
    assert JSON_FORMAT.extension == ".json"
    assert export_format("json") is JSON_FORMAT


def test_the_json_format_writes_the_investigation_opened(tmp_path: Path) -> None:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create("faux-plombiers-31", "Qui se cache derrière les plombiers ?")
    destination = tmp_path / "faux-plombiers-31.json"
    with library.open("faux-plombiers-31") as opened:
        scenario = plumbers_scenario(InvestigationBuilder(opened.connection))
        JSON_FORMAT.write(opened, None, ExportScope(), destination, EXPORTED_AT)
    document = json.loads(destination.read_text(encoding="utf-8"))
    assert document["format"] == FORMAT_NAME
    assert document["investigation"]["name"] == "faux-plombiers-31"
    assert document["exported_at"] == "2026-11-19T10:00:00+00:00"
    assert scenario.acme in {entity["identifier"] for entity in document["entities"]}
    assert document["signals"] == []
