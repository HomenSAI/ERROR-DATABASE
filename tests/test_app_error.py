# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""AppError: только коды из каталога, самодельный код — ошибка (ARCHITECTURE.md §7.2, §7.4)."""

from __future__ import annotations

import logging
import pickle

import pytest

from homensai_errors import (CODES, FALLBACK_CODE, AppError, CatalogError, Errors, ParamsError, UnknownCodeError,
                             configure, default_catalog)


@pytest.mark.parametrize("bad", ["BACKUP_PASSWORD_CHECK_OVERDUE", "DR-270-OVERDUE", "rent-dr-001", "RENT-DR-1", "", 42])
def test_not_a_code_is_rejected(bad):
    with pytest.raises(ValueError, match="NS-AREA-NNN"):
        AppError(bad)


def test_self_made_code_fails_without_catalog():
    assert default_catalog() is None
    with pytest.raises(UnknownCodeError):
        AppError("RENT-ZZZ-999")
    err = AppError(Errors.RENT_DR_001, days=3)
    assert err.code == "RENT-DR-001" == Errors.BACKUP_PASSWORD_CHECK_OVERDUE and err.params == {"days": 3}
    assert str(err) == "RENT-DR-001" and err.original_code is None


def test_strict_catalog_checks_params(strict_catalog):
    configure(strict_catalog)
    with pytest.raises(UnknownCodeError):
        AppError("RENT-ZZZ-999")
    with pytest.raises(ParamsError):
        AppError("RENT-DR-001")
    assert AppError("RENT-DR-001", days=1).code == "RENT-DR-001"


def test_lenient_catalog_falls_back_and_logs(catalog, caplog):
    configure(catalog)
    with caplog.at_level(logging.ERROR, logger="homensai_errors"):
        err = AppError("RENT-ZZZ-999", secret_param="x")
    assert err.code == FALLBACK_CODE and err.original_code == "RENT-ZZZ-999" and err.params == {}
    assert "RENT-ZZZ-999" in caplog.text
    assert err.render("ru").code == FALLBACK_CODE


def test_render_requires_catalog():
    err = AppError("RENT-DR-001", days=1)
    with pytest.raises(CatalogError, match="каталог не задан"):
        err.render("ru")


def test_raise_catch_and_pickle(catalog):
    configure(catalog)
    with pytest.raises(AppError) as info:
        raise AppError("RENT-DR-001", days=2)
    copy = pickle.loads(pickle.dumps(info.value))
    assert (copy.code, copy.params, copy.original_code) == ("RENT-DR-001", {"days": 2}, None)


def test_constants_cover_catalog(catalog):
    assert CODES == frozenset(catalog.codes())
    for item in catalog:
        assert getattr(Errors, item.code.replace("-", "_")) == item.code
        assert getattr(Errors, item.key) == item.code
