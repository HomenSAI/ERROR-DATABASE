# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Версии и ветви сценариев розетки Auto VPN без новых полей (ARCHITECTURE.md §4.4): метки в `tags`, родитель в `related`."""

from __future__ import annotations

import re

PLUG = re.compile(r"^plug-p\d+(-\d+)+$")


def test_plug_version_tags(catalog):
    want = {"VPN-FLT-043": ["plug-p1-1"], "VPN-FLT-044": ["plug-p2-1", "plug-p2-2", "plug-p2-3"],
            "VPN-FLT-045": ["plug-p3-1", "plug-p3-2", "plug-p3-3"], "VPN-FLT-046": ["plug-p4-1"], "VPN-FLT-047": ["plug-p5-1"],
            "VPN-FLT-048": ["plug-p6-1"], "VPN-FLT-049": ["plug-p7-1"], "VPN-FLT-050": ["plug-p8-1"], "VPN-FLT-051": ["plug-p9-1"],
            "VPN-FLT-052": ["plug-p10-1"], "VPN-FLT-053": ["plug-p23-1", "plug-p23-2", "plug-p23-3"], "VPN-FLT-054": ["plug-p4-2"]}
    seen: dict[str, str] = {}
    for entry in catalog:
        for tag in entry.tags:
            if tag.startswith("plug-"):
                assert PLUG.match(tag), (entry.code, tag)
                assert tag not in seen, (tag, seen.get(tag), entry.code)   # одна версия — один код
                seen[tag] = entry.code
    assert {code: sorted(t for t in catalog.get(code).tags if t.startswith("plug-")) for code in want} == {
        code: sorted(tags) for code, tags in want.items()}


def test_branch_p4_2(catalog):
    e = catalog.get("VPN-FLT-054")
    assert e.number == "005-011-054" and e.key == "PLUG_P4_STOP_DONE" and e.aliases == ("PLUG-P4L",)
    assert "VPN-FLT-046" in e.related and "branch-of-vpn-flt-046" in e.tags
    assert all("VPN-FLT-046" in e.cause[lang] for lang in ("ru", "uk", "en", "de"))
    p8 = catalog.get("VPN-FLT-050")
    assert "VPN-FLT-046" in p8.related and all("P8.1" in p8.cause[lang] for lang in ("ru", "uk", "en", "de"))
    # поиск по словам: метка находит запись (рядом — родственный VPN-FLT-046, у него те же слова plug/p4)
    assert "VPN-FLT-054" in [h.code for h in catalog.search("plug-p4-2", "en")[:2]]
