# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Тексты на языке: render (§7.2, §12), to_problem (RFC 9457, §6.3), help_page (§7.3), search."""

from __future__ import annotations

import logging

import pytest

from conftest import entry, write_source
from homensai_errors import SITE_URL, AppError, Catalog, ParamsError, UnknownCodeError


def test_render_with_legacy_code_first(catalog):
    text = catalog.render("RENT-DR-001", lang="uk", params={"days": 3})
    assert text.title == "Пароль копій давно не перевірявся"
    assert "3 дн." in text.cause and "{days}" not in text.cause
    lines = str(text).splitlines()
    assert lines[0] == "RENT-DR-001 (попередній код: DR-270-OVERDUE)"
    assert lines[1] == text.title
    assert lines[2].startswith("Чому: ") and " · Що робити: 1. " in lines[2] and "Кому передати: " in lines[2]
    assert text.legacy_codes == ("DR-270-OVERDUE",)
    assert text.help_url == f"{SITE_URL}/uk/errors/RENT-DR-001"


def test_render_without_transition(tmp_path):
    root = write_source(tmp_path, {("RENT", "DR"): [entry("RENT-DR-001", "COPY_OLD", aliases=["A-1", "B-2"])]})
    on = Catalog.load(root)
    assert str(on.render("RENT-DR-001", "en")).splitlines()[0] == "RENT-DR-001 (former codes: A-1, B-2)"
    off = Catalog.load(root, manifest={"transition": {"show_legacy_codes": False}})
    assert str(off.render("RENT-DR-001", "en")).splitlines()[0] == "RENT-DR-001"
    assert "legacy_codes" not in off.to_problem("RENT-DR-001")


def test_params_strict_and_lenient(catalog, strict_catalog):
    with pytest.raises(ParamsError, match="нет \\['days'\\]"):
        strict_catalog.render("RENT-DR-001", "ru")
    with pytest.raises(ParamsError, match="лишние \\['extra'\\]"):
        strict_catalog.render("RENT-DR-001", "ru", params={"days": 1, "extra": 2})
    assert "{days}" in catalog.render("RENT-DR-001", "ru").cause


def test_unknown_code_fallback_and_strict(catalog, strict_catalog, caplog):
    with caplog.at_level(logging.ERROR, logger="homensai_errors"):
        text = catalog.render("RENT-ZZZ-999", "ru")
    assert text.code == "COMMON-SYS-001" and "RENT-ZZZ-999" in caplog.text
    with pytest.raises(UnknownCodeError):
        strict_catalog.render("RENT-ZZZ-999", "ru")
    with pytest.raises(UnknownCodeError):
        strict_catalog.to_problem("RENT-ZZZ-999")


def test_problem_rfc9457(catalog):
    problem = catalog.to_problem("RENT-DR-001", lang="en", status=409, instance="/security#backups",
                                 params={"days": 3})
    assert problem == {
        "type": f"{SITE_URL}/errors/RENT-DR-001",
        "title": "Backup password not checked for a while",
        "status": 409,
        "detail": "The check was due 3 days ago. If the password is forgotten, backups cannot be opened.",
        "instance": "/security#backups",
        "code": "RENT-DR-001",
        "key": "BACKUP_PASSWORD_CHECK_OVERDUE",
        "retryable": True,
        "legacy_codes": ["DR-270-OVERDUE"],
    }
    assert list(problem)[:5] == ["type", "title", "status", "detail", "instance"]
    # type не зависит от языка: это идентификатор вида ошибки (RFC 9457 §3.1.1).
    assert catalog.to_problem("RENT-DR-001", lang="de")["type"] == problem["type"]


def test_problem_status_from_entry_or_absent(catalog):
    assert catalog.to_problem("COMMON-SYS-001")["status"] == 500
    no_status = next(e for e in catalog if e.http_status is None and not e.params)
    assert "status" not in catalog.to_problem(no_status.code)


def test_problem_from_app_error(catalog):
    from homensai_errors import configure

    configure(catalog)
    err = AppError("RENT-DR-001", days=5)
    problem = err.to_problem(lang="ru", status=409)
    assert problem["code"] == "RENT-DR-001" and "5 дн." in problem["detail"] and problem["status"] == 409
    assert catalog.to_problem(err, lang="ru")["detail"] == problem["detail"]


def test_help_page_language_and_fallback(catalog):
    page = catalog.help_page("RENT-DR-001", lang="ru")
    assert page.startswith("# RENT-DR-001 — Пароль копий давно не проверялся\n")
    for part in ("Прежний код: `DR-270-OVERDUE`", "## Почему", "## Что делать", "## Кому передать",
                 "1. Сами по шагам выше — всегда первым", "`BACKUP_PASSWORD_CHECK_OVERDUE` · с версии 1.0.0"):
        assert part in page
    assert catalog.help_page("RENT-DR-001", lang="fr") == catalog.help_page("RENT-DR-001", lang="en")
    en = catalog.help_page("RENT-DR-001", lang="en")
    assert "## What to do" in en and "всегда первым" not in en  # поле when — только по-русски
    assert "3 days" in catalog.help_page("RENT-DR-001", "en", params={"days": 3})


def test_help_page_related_deprecated_fixed_in(tmp_path):
    root = write_source(tmp_path, {("RENT", "DR"): [
        entry("RENT-DR-001", "OLD_ONE", related=["RENT-DR-002"], deprecated="1.2.0", replaced_by="RENT-DR-002",
              fixed_in={"rent": "1.4.2"}),
        entry("RENT-DR-002", "NEW_ONE"),
    ]})
    page = Catalog.load(root).help_page("RENT-DR-001", "de")
    assert "## Verwandte Codes" in page and "- [RENT-DR-002](RENT-DR-002.md) — de: RENT-DR-002" in page
    assert "veraltet seit Version 1.2.0" in page and "ersetzt durch [RENT-DR-002](RENT-DR-002.md)" in page
    assert "behoben in Version: rent 1.4.2" in page


def test_search_by_code_alias_key_and_words(catalog):
    assert catalog.search("RENT-DR-001", "ru")[0].code == "RENT-DR-001"
    assert catalog.search("DR-270-OVERDUE", "ru")[0].code == "RENT-DR-001"
    assert catalog.search("backup_password_check_overdue", "en")[0].code == "RENT-DR-001"
    hits = catalog.search("пароль копий", lang="ru")
    assert "RENT-DR-001" in [h.code for h in hits[:5]]
    assert all(h.score > 0 for h in hits)
    assert catalog.search("Backup password", "en")[0].code in {h.code for h in catalog.search("backup", "en")}
    pins = [code for code in catalog.codes() if code.startswith("RENT-PIN-")]
    area = catalog.search("RENT-PIN", "en", limit=100)
    assert [h.code for h in area[:len(pins)]] == pins  # начало кода — вся область первой
    assert catalog.search("", "ru") == [] and catalog.search("абвгдежзик", "ru") == []
    assert len(catalog.search("ошибка", "ru", limit=3)) <= 3


def test_search_is_language_specific_and_deterministic(catalog):
    de = catalog.search("Passwort", "de")
    assert de and catalog.search("Passwort", "de") == de
    assert catalog.search("пароль", "de") == []
    assert [h.code for h in catalog.search("пам'ятаєте пароль", "uk")] == \
        [h.code for h in catalog.search("памятаєте пароль", "uk")]
