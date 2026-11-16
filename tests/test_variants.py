# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Версии и ветви сценариев (ARCHITECTURE.md §4.4): поля `parent` и `variants` — проверка, поиск, показ."""

from __future__ import annotations

import json

import validate
from conftest import entry, write_source
from homensai_errors import Catalog

NS = {"VPN": {"title": "VPN", "number": "005", "areas": {}, "area_numbers": {"FLT": "011", "SET": "005"}}}


def _base(tmp_path, flt: list[dict], extra: dict | None = None):
    files = {("VPN", "FLT"): flt}
    files.update(extra or {})
    ns = json.loads(json.dumps(NS))
    ns["VPN"]["area_numbers"] = {a: n for a, n in ns["VPN"]["area_numbers"].items() if ("VPN", a) in files}
    return write_source(tmp_path, files, ns)


def _flt(n: int, key: str, **kw) -> dict:
    return entry(f"VPN-FLT-{n:03d}", key, number=f"005-011-{n:03d}", **kw)


def test_good_branch_and_variants(tmp_path):
    root = _base(tmp_path, [_flt(1, "PLUG_A", aliases=["PLUG-P4"], variants=["PLUG-P4.1"]),
                            _flt(2, "PLUG_B", aliases=["PLUG-P4L"], parent="VPN-FLT-001", variants=["PLUG-P4.2", "PLUG-P4.2.1"])])
    assert validate.validate(root) == []
    cat = Catalog.load(root, manifest=False, lock=False)
    assert cat.get("PLUG-P4.2").code == "VPN-FLT-002" and cat.get("plug-p4.2.1").code == "VPN-FLT-002"
    assert cat.get("PLUG-P4.1").code == "VPN-FLT-001"
    e = cat.get("VPN-FLT-002")
    assert e.parent == "VPN-FLT-001" and e.variants == ("PLUG-P4.2", "PLUG-P4.2.1")
    assert e.legacy_codes == ("PLUG-P4L",)                       # versions are never shown as former codes
    assert "PLUG-P4.2" not in str(cat.render("VPN-FLT-002", "en"))
    assert e.as_dict()["parent"] == "VPN-FLT-001" and e.as_dict()["variants"] == ["PLUG-P4.2", "PLUG-P4.2.1"]
    assert "variants" not in cat.get("VPN-FLT-001").as_dict() or cat.get("VPN-FLT-001").as_dict()["variants"] == ["PLUG-P4.1"]
    page = cat.help_page("VPN-FLT-002", "en")
    assert "branch of [VPN-FLT-001]" in page and "scenario versions: PLUG-P4.2, PLUG-P4.2.1" in page
    assert cat.search("P4.2", "en")[0].code == "VPN-FLT-002"


def test_variant_name_must_be_unique_across_names(tmp_path):
    root = _base(tmp_path, [_flt(1, "PLUG_A", variants=["PLUG-P3.2"]), _flt(2, "PLUG_B", variants=["PLUG-P3.2"])])
    assert any("PLUG-P3.2" in e and "уже занято" in e for e in validate.validate(root))
    root = _base(tmp_path / "b", [_flt(1, "PLUG_A", aliases=["PLUG-P3.2"]), _flt(2, "PLUG_B", variants=["PLUG-P3.2"])])
    assert any("PLUG-P3.2" in e for e in validate.validate(root))


def test_variant_format_and_duplicates(tmp_path):
    for bad in (["PLUG-P3"], ["plug-p3.2"], ["PLUG-P3."], [], "PLUG-P3.2"):
        root = _base(tmp_path / str(abs(hash(str(bad)))), [_flt(1, "PLUG_A", variants=bad)])
        assert any("variants" in e for e in validate.validate(root)), bad
    root = _base(tmp_path / "dup", [_flt(1, "PLUG_A", variants=["PLUG-P3.2", "PLUG-P3.2"])])
    assert any("повтор" in e for e in validate.validate(root))


def test_parent_rules(tmp_path):
    cases = {
        "self": [_flt(1, "PLUG_A", parent="VPN-FLT-001")],
        "missing": [_flt(1, "PLUG_A", parent="VPN-FLT-009")],
        "cycle": [_flt(1, "PLUG_A", parent="VPN-FLT-002"), _flt(2, "PLUG_B", parent="VPN-FLT-001")],
    }
    want = {"self": "сам на себя", "missing": "несуществующий", "cycle": "цикл parent"}
    for name, flt in cases.items():
        errors = validate.validate(_base(tmp_path / name, flt))
        assert any(want[name] in e for e in errors), (name, errors)
    other = {("VPN", "SET"): [entry("VPN-SET-001", "SET_A", number="005-005-001")]}
    errors = validate.validate(_base(tmp_path / "area", [_flt(1, "PLUG_A", parent="VPN-SET-001")], other))
    assert any("другой области" in e for e in errors)


def test_real_base_plug_tree(catalog):
    """Реальная база: P4 разделился на VPN-FLT-046 (P4.1, «Стоп» прерван) и VPN-FLT-054 (P4.2, «Стоп» завершён)."""
    e = catalog.get("VPN-FLT-054")
    assert e.number == "005-011-054" and e.parent == "VPN-FLT-046" and e.variants == ("PLUG-P4.2",)
    assert catalog.get("PLUG-P4.1").code == "VPN-FLT-046"
    assert [catalog.get(f"PLUG-P3.{v}").code for v in (1, 2, 3)] == ["VPN-FLT-045"] * 3
    assert catalog.get("PLUG-P8.1").code == "VPN-FLT-050" and "VPN-FLT-046" in catalog.get("VPN-FLT-050").related
    assert catalog.get("PLUG-P23.3").code == "VPN-FLT-053"
