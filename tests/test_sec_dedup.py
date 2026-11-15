# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Один код для ошибок защиты — SEC (решение владельца Rent 28.10-342, версия базы 1.4.0).

Защита переехала из Rent в модуль безопасности, поэтому у 68 кодов `RENT-…` есть код `SEC-…` с тем же смыслом
(связаны полем `related` в 1.3.0). Теперь коды `RENT-…` устарели: `deprecated` + `replaced_by` кода SEC, номера не
переиспользуются, а прежние имена Rent (`aliases`) переходят к коду SEC — поиск по старому имени находит код SEC
(ARCHITECTURE.md §5, §12). Здесь же правила `replaced_by` в `tools/validate.py`."""

from __future__ import annotations

import json

import validate
from conftest import ROOT, entry, write_source
from homensai_errors import Catalog

DEDUP_VERSION = "1.4.0"


def _codes(ns: str) -> dict[str, dict]:
    return {e["code"]: e for p in sorted((ROOT / "codes" / ns).glob("*.json"))
            for e in json.loads(p.read_text("utf-8"))["codes"]}


def test_every_rent_duplicate_of_a_sec_code_is_deprecated_and_replaced() -> None:
    sec, rent = _codes("SEC"), _codes("RENT")
    pairs = {code: [r for r in e.get("related", []) if r.startswith("RENT-")] for code, e in sec.items()}
    assert sum(len(v) for v in pairs.values()) == 68
    for code, related in pairs.items():
        for old in related:
            assert rent[old].get("deprecated") == DEDUP_VERSION, old
            assert rent[old].get("replaced_by") == code, old
            assert not rent[old].get("aliases"), f"{old}: прежние имена Rent должны перейти к {code}"
            assert rent[old]["number"].startswith("003-"), "номер устаревшего кода не меняется"
    # больше ничего не устарело, а SEC-коды сами не устаревшие
    deprecated = {c for c, e in rent.items() if e.get("deprecated")}
    assert deprecated == {r for v in pairs.values() for r in v}
    assert not any(e.get("deprecated") or e.get("replaced_by") for e in sec.values())


def test_former_rent_names_move_to_the_sec_code(catalog: Catalog) -> None:
    old = catalog.get("RENT-AUTH-003")
    assert old is not None
    assert old.deprecated == DEDUP_VERSION
    assert old.replaced_by == "SEC-AUTH-001"
    new = catalog.get("webauthn_format")  # прежнее имя Rent и модуля
    assert new is not None
    assert new.code == "SEC-AUTH-001"
    assert "webauthn_format" in new.aliases
    assert catalog.get("WEBAUTHN_FORMAT").code == "RENT-AUTH-003"  # key не меняется
    assert catalog.get("003-013-003").code == "RENT-AUTH-003"  # цифровой код не меняется


def _mini(tmp_path, **old_extra):
    codes = {("RENT", "DR"): [entry("RENT-DR-001", "COPY_OLD", number="003-001-001", **old_extra),
                              entry("RENT-DR-002", "COPY_NEW", number="003-001-002")]}
    ns = {"RENT": {"title": "Rent", "number": "003", "areas": {}, "area_numbers": {"DR": "001"}}}
    return write_source(tmp_path, codes, ns)


def test_validator_accepts_deprecated_with_replacement(tmp_path) -> None:
    assert validate.validate(_mini(tmp_path, deprecated="1.4.0", replaced_by="RENT-DR-002")) == []


def test_validator_requires_deprecated_for_replaced_by(tmp_path) -> None:
    errors = validate.validate(_mini(tmp_path, replaced_by="RENT-DR-002"))
    assert any("RENT-DR-001" in e and "replaced_by" in e and "deprecated" in e for e in errors)


def test_validator_rejects_replacement_by_itself_or_by_deprecated_code(tmp_path) -> None:
    errors = validate.validate(_mini(tmp_path, deprecated="1.4.0", replaced_by="RENT-DR-001"))
    assert any("RENT-DR-001" in e and "сам на себя" in e for e in errors)
    root = tmp_path / "chain"
    codes = {("RENT", "DR"): [entry("RENT-DR-001", "A", number="003-001-001", deprecated="1.4.0", replaced_by="RENT-DR-002"),
                              entry("RENT-DR-002", "B", number="003-001-002", deprecated="1.4.0", replaced_by="RENT-DR-003"),
                              entry("RENT-DR-003", "C", number="003-001-003")]}
    ns = {"RENT": {"title": "Rent", "number": "003", "areas": {}, "area_numbers": {"DR": "001"}}}
    errors = validate.validate(write_source(root, codes, ns))
    assert any("RENT-DR-001" in e and "устаревший" in e and "RENT-DR-002" in e for e in errors)


def test_validator_rejects_replacement_by_unknown_code(tmp_path) -> None:
    errors = validate.validate(_mini(tmp_path, deprecated="1.4.0", replaced_by="RENT-DR-009"))
    assert any("RENT-DR-001" in e and "RENT-DR-009" in e for e in errors)
