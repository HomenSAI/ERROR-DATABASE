# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Цифровой код `PPP-AAA-NNN` (ARCHITECTURE.md §3.1): проверка, поиск записи и поиск по тексту, выпуск и сайт."""

from __future__ import annotations

import json

import pytest

import build_dist
import build_site
import validate
from conftest import ROOT, entry, write_source
from homensai_errors import Catalog
from homensai_errors._texts import LANGS


def _base(tmp_path, numbers: dict[str, str] | None = None, namespaces: dict | None = None):
    """Мини-база RENT-DR (003-001), RENT-FX (003-002) с цифровыми кодами; `numbers` подменяет номера записей."""
    numbers = numbers or {}
    codes = {("RENT", "DR"): [entry("RENT-DR-001", "COPY_OLD", number=numbers.get("RENT-DR-001", "003-001-001")),
                              entry("RENT-DR-002", "COPY_BAD", number=numbers.get("RENT-DR-002", "003-001-002"))],
             ("RENT", "FX"): [entry("RENT-FX-001", "RATE_NONE", number=numbers.get("RENT-FX-001", "003-002-001"))]}
    ns = namespaces if namespaces is not None else {
        "RENT": {"title": "Rent", "number": "003", "areas": {}, "area_numbers": {"DR": "001", "FX": "002"}}}
    return write_source(tmp_path, codes, ns)


def test_real_base_numbers_follow_namespaces(catalog):
    namespaces = json.loads((ROOT / "namespaces.json").read_text("utf-8"))
    assert {ns: info["number"] for ns, info in namespaces.items()} == {
        "COMMON": "001", "CORE": "002", "RENT": "003", "JP": "004", "VPN": "005", "SEC": "006"}
    rent = namespaces["RENT"]["area_numbers"]
    assert list(rent) == list(namespaces["RENT"]["areas"]) and rent["DR"] == "001" and rent["FX"] == "012"
    assert rent["LOG"] == "023"
    assert catalog.get("RENT-FX-003").number == "003-012-003"
    assert catalog.get("COMMON-SYS-001").number == "001-001-001"
    numbers = [e.number for e in catalog]
    assert len(set(numbers)) == len(numbers) and all(numbers)


def test_validator_accepts_good_base(tmp_path):
    assert validate.validate(_base(tmp_path)) == []


def test_validator_catches_wrong_number(tmp_path):
    errors = validate.validate(_base(tmp_path, {"RENT-DR-002": "003-002-002"}))
    assert any("RENT-DR-002" in e and "не совпадает с вычисленным" in e and "003-001-002" in e for e in errors)


def test_validator_catches_bad_format_and_missing_number(tmp_path):
    errors = validate.validate(_base(tmp_path, {"RENT-DR-001": "3-1-1"}))
    assert any("RENT-DR-001" in e and "PPP-AAA-NNN" in e for e in errors)
    root = _base(tmp_path / "x")
    path = root / "codes" / "RENT" / "FX.json"
    data = json.loads(path.read_text("utf-8"))
    del data["codes"][0]["number"]
    path.write_text(json.dumps(data), "utf-8")
    assert any("RENT-FX-001" in e and "нет поля number" in e for e in validate.validate(root))


def test_validator_catches_duplicate_number(tmp_path):
    # у двух записей один number — и несовпадение с вычисленным, и дубль
    errors = validate.validate(_base(tmp_path, {"RENT-DR-002": "003-001-001"}))
    assert any("RENT-DR-002" in e and "уже у кода RENT-DR-001" in e for e in errors)


def test_validator_checks_namespace_and_area_numbers(tmp_path):
    ns = {"RENT": {"title": "R", "number": "003", "areas": {}, "area_numbers": {"DR": "001"}},
          "JP": {"title": "J", "number": "003", "areas": {}, "area_numbers": {}}}
    errors = validate.validate(_base(tmp_path / "a", namespaces=ns))
    assert any("номер 003 у пространств" in e for e in errors)
    assert any("у области RENT-FX нет номера" in e for e in errors)
    ns = {"RENT": {"title": "R", "areas": {}, "area_numbers": {"DR": "001", "FX": "001"}}}
    errors = validate.validate(_base(tmp_path / "b", namespaces=ns))
    assert any("у пространства RENT нет номера number" in e for e in errors)
    assert any("номер области 001 в RENT у DR и FX" in e for e in errors)
    ns = {"RENT": {"title": "R", "number": "03", "areas": {}, "area_numbers": {"DR": "01", "FX": "002"}}}
    errors = validate.validate(_base(tmp_path / "c", namespaces=ns))
    assert any("номер области RENT-DR" in e for e in errors) and any("number из трёх цифр" in e for e in errors)


@pytest.mark.parametrize("query", ["003-012-003", "003012003", "003 012 003", " 003  012-003 ", "003-012 003"])
def test_catalog_finds_by_numeric_code(catalog, query):
    assert catalog.get(query).code == "RENT-FX-003"
    assert catalog.find(query) is catalog.get("RENT-FX-003")
    assert catalog.search(query, "ru")[0].code == "RENT-FX-003"


def test_catalog_numeric_lookup_does_not_match_garbage(catalog):
    for query in ("003-012", "999-999-999", "03-012-003", "00301200", "0030120033"):
        assert catalog.find(query) is None, query
    assert "003-012-003" in catalog and "003012003" not in catalog  # `in` — только точные имена


def test_catalog_numeric_prefix_search(catalog):
    fx = [c for c in catalog.codes() if c.startswith("RENT-FX-")]
    for query in ("003-012", "003 012", "003012"):
        assert [h.code for h in catalog.search(query, "en", limit=100)[:len(fx)]] == fx, query
    assert catalog.search("12", "en") == [] or all(h.score < 500 for h in catalog.search("12", "en"))


def test_catalog_duplicate_and_bad_numbers_rejected(tmp_path):
    from homensai_errors import CatalogError
    root = write_source(tmp_path / "a", {("RENT", "DR"): [entry("RENT-DR-001", "A_A", number="003-001-001"),
                                                            entry("RENT-DR-002", "B_B", number="003-001-001")]})
    with pytest.raises(CatalogError, match="уже занято"):
        Catalog.load(root)
    root = write_source(tmp_path / "b", {("RENT", "DR"): [entry("RENT-DR-001", "A_A", number="3-1-1")]})
    with pytest.raises(CatalogError, match="PPP-AAA-NNN"):
        Catalog.load(root)


def test_entry_without_number_still_works(tmp_path):
    """Выпуски до 1.2.0 без `number`: запись читается, цифровой код пустой и не попадает в as_dict."""
    root = write_source(tmp_path, {("RENT", "DR"): [entry("RENT-DR-001", "A_A")]})
    cat = Catalog.load(root)
    item = cat.get("RENT-DR-001")
    assert item.number == "" and "number" not in item.as_dict()
    assert str(cat.render("RENT-DR-001", "en")).splitlines()[0] == "RENT-DR-001"
    assert "number" not in cat.to_problem("RENT-DR-001")


def test_texts_show_numeric_code(catalog):
    assert str(catalog.render("RENT-FX-003", "en")).splitlines()[0].startswith("RENT-FX-003 · 003-012-003")
    assert catalog.to_problem("RENT-FX-003")["number"] == "003-012-003"
    labels = {"ru": "Цифровой код", "uk": "Цифровий код", "en": "Numeric code", "de": "Numerischer Code"}
    for lang, label in labels.items():
        page = catalog.help_page("RENT-FX-003", lang)
        assert f"{label}: `003-012-003`" in page
        assert page.index("003-012-003") < page.index("## ")
    doc = catalog.search_doc(catalog.get("RENT-FX-003"), "en")
    assert doc["number"] == "003-012-003"


def test_dist_has_numeric_code():
    tree = build_dist.build()
    for name in ("errors.json", "errors.RENT.json"):
        codes = {c["code"]: c for c in json.loads(tree[name])["codes"]}
        assert codes["RENT-FX-003"]["number"] == "003-012-003" and list(codes["RENT-FX-003"])[:2] == ["code", "number"]
    ns = json.loads(tree["errors.RENT.json"])["namespaces"]["RENT"]
    assert ns["number"] == "003" and ns["area_numbers"]["FX"] == "012"
    assert "number: 003-012-003" in tree["llms.txt"].decode() and "PPP-AAA-NNN" in tree["llms.txt"].decode()
    for lang in LANGS:
        docs = {d["code"]: d for d in json.loads(tree[f"search.{lang}.json"])["docs"]}
        assert docs["RENT-FX-003"]["number"] == "003-012-003"
        assert "003-012-003" in tree[f"help/{lang}/RENT-FX-003.md"].decode()
        assert "003-012-003" in tree[f"errors.{lang}.md"].decode()


def test_catalog_from_dist_finds_numeric_code(tmp_path):
    out = tmp_path / "dist"
    build_dist.write(out, build_dist.build())
    cat = Catalog.load(out, manifest=False, lock=False)
    assert cat.get("003 012 003").code == "RENT-FX-003"


def test_site_has_numeric_code():
    files = build_site.build()
    labels = {"ru": "Цифровой код", "uk": "Цифровий код", "en": "Numeric code", "de": "Numerischer Code"}
    for lang, label in labels.items():
        page = files[f"{lang}/errors/RENT-FX-003.html"].decode()
        assert label in page and "<code>003-012-003</code>" in page
        assert 'class="num">003-012-003</code>' in files[f"{lang}/ns/RENT.html"].decode()
    hints = {"ru": "цифровому коду", "uk": "цифровим кодом", "en": "numeric code", "de": "numerischem Code"}
    for lang, hint in hints.items():
        assert hint in files[f"{lang}/index.html"].decode()
    assert "numeric code" in files["index.html"].decode()
