# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Библиотека базы кодов ошибок HomenS.AI (ARCHITECTURE.md §7.2).

    from homensai_errors import Catalog, AppError, Errors, configure

    catalog = Catalog.load("vendor/errors")             # по errors.manifest.json и errors.lock рядом
    configure(catalog)                                  # каталог для AppError
    catalog.render("RENT-DR-001", lang="uk", params={"days": 3})
    catalog.to_problem("RENT-DR-001", lang="en", status=409, params={"days": 3})
    catalog.help_page("RENT-DR-001", lang="ru")
    catalog.search("пароль копий", lang="ru")
    raise AppError(Errors.RENT_DR_001, days=3)
"""

from .catalog import (DATABASE, PROBLEM_CONTENT_TYPE, SITE_URL, Catalog, Entry, Hit, Rendered, changelog_version,
                      make_lock, sha256_file)
from .codes import CODES, Errors
from .errors import (FALLBACK_CODE, AppError, CatalogError, IntegrityError, ParamsError, UnknownCodeError, configure,
                     default_catalog)
from ._texts import LANGS

__version__ = "1.1.0"

__all__ = [
    "AppError", "CODES", "Catalog", "CatalogError", "DATABASE", "Entry", "Errors", "FALLBACK_CODE", "Hit",
    "IntegrityError", "LANGS", "PROBLEM_CONTENT_TYPE", "ParamsError", "Rendered", "SITE_URL", "UnknownCodeError",
    "__version__", "changelog_version", "configure", "default_catalog", "make_lock", "sha256_file",
]
