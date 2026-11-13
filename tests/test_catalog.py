# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Catalog: загрузка из исходников и выпуска, манифест, lock, поиск записи по code/key/aliases (ARCHITECTURE.md §7)."""

from __future__ import annotations

import json

import pytest

import validate
from conftest import ROOT, entry, write_source
from homensai_errors import Catalog, CatalogError, UnknownCodeError, __version__, changelog_version


def test_base_validates_and_loads_every_code(catalog):
    assert validate.validate(ROOT) == []
    count = sum(len(json.loads(p.read_text("utf-8"))["codes"]) for p in (ROOT / "codes").glob("*/*.json"))
    assert len(catalog) == count
    assert catalog.version == changelog_version(ROOT) == __version__
    assert catalog.codes() == sorted(catalog.codes())


def test_entries_match_schema_fields(catalog):
    """Запись библиотеки повторяет поля schema/error-file.schema.json: обязательные есть, лишних нет."""
    schema = json.loads((ROOT / "schema" / "error-file.schema.json").read_text("utf-8"))["$defs"]["entry"]
    for item in catalog:
        data = item.as_dict()
        assert set(schema["required"]) <= set(data), item.code
        assert set(data) <= set(schema["properties"]), item.code
        assert list(data["title"]) == ["ru", "uk", "en", "de"]


def test_lookup_by_code_key_and_alias(catalog):
    by_code = catalog.get("RENT-DR-001")
    assert catalog.get("BACKUP_PASSWORD_CHECK_OVERDUE") is by_code
    assert catalog.get("DR-270-OVERDUE") is by_code
    assert catalog.find(" rent-dr-001 ") is by_code
    assert "RENT-DR-001" in catalog and "DR-270-OVERDUE" in catalog and 42 not in catalog
    assert by_code.namespace == "RENT" and by_code.area == "DR" and by_code.legacy_codes == ("DR-270-OVERDUE",)
    assert catalog.find("RENT-DR-999") is None
    with pytest.raises(UnknownCodeError):
        catalog.get("RENT-DR-999")


def test_entries_are_read_only(catalog):
    item = catalog.get("RENT-DR-001")
    with pytest.raises(Exception):
        item.title["ru"] = "x"
    with pytest.raises(Exception):
        item.code = "x"


def test_manifest_filters_namespaces_and_languages(tmp_path):
    root = write_source(tmp_path / "base", {("COMMON", "SYS"): [entry("COMMON-SYS-001", "UNKNOWN_ERROR")],
                                            ("RENT", "DR"): [entry("RENT-DR-001", "COPY_OLD")],
                                            ("JP", "MAIL"): [entry("JP-MAIL-001", "MAIL_DOWN")]})
    cat = Catalog.load(root, manifest={"namespaces": ["RENT"], "languages": ["ru", "en"],
                                       "transition": {"show_legacy_codes": False}})
    assert cat.codes() == ["COMMON-SYS-001", "RENT-DR-001"]  # COMMON всегда: запасной код
    assert cat.languages == ("ru", "en") and cat.show_legacy_codes is False
    assert cat.lang("de") == "en" and cat.lang("ru-RU") == "ru"
    with pytest.raises(CatalogError, match="не объявлены"):
        Catalog.load(root, manifest={"namespaces": ["NOPE"]})
    with pytest.raises(CatalogError, match="подмножество"):
        Catalog.load(root, manifest={"languages": ["fr"]})


def test_manifest_file_found_next_to_vendor_dir(tmp_path):
    root = write_source(tmp_path / "product" / "vendor" / "errors",
                        {("COMMON", "SYS"): [entry("COMMON-SYS-001", "UNKNOWN_ERROR")],
                         ("RENT", "DR"): [entry("RENT-DR-001", "COPY_OLD")]})
    (tmp_path / "product" / "errors.manifest.json").write_text(json.dumps({"namespaces": ["COMMON"]}), "utf-8")
    assert Catalog.load(root).codes() == ["COMMON-SYS-001"]
    assert len(Catalog.load(root, manifest=False)) == 2


def test_duplicate_names_rejected(tmp_path):
    root = write_source(tmp_path, {("RENT", "DR"): [entry("RENT-DR-001", "SAME"), entry("RENT-DR-002", "SAME")]})
    with pytest.raises(CatalogError, match="уже занято"):
        Catalog.load(root)


def test_unknown_field_and_missing_language_rejected(tmp_path):
    root = write_source(tmp_path / "a", {("RENT", "DR"): [entry("RENT-DR-001", "A_B", secret="x")]})
    with pytest.raises(CatalogError, match="неизвестные поля"):
        Catalog.load(root)
    broken = entry("RENT-DR-001", "A_B")
    del broken["title"]["de"]
    root = write_source(tmp_path / "b", {("RENT", "DR"): [broken]})
    with pytest.raises(CatalogError, match="без языков"):
        Catalog.load(root)
    assert Catalog.load(root, manifest={"languages": ["ru", "en"]}).languages == ("ru", "en")


def test_missing_folder_and_empty_folder(tmp_path):
    with pytest.raises(CatalogError):
        Catalog.load(tmp_path / "nope")
    with pytest.raises(CatalogError, match="ни codes"):
        Catalog.load(tmp_path, manifest=False, lock=False)
