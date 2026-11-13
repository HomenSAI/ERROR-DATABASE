# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Исключения библиотеки и `AppError` — единственный способ продукта сообщить об ошибке (ARCHITECTURE.md §7.2).

`AppError` принимает только код из каталога:
- строка не вида `NS-AREA-NNN` (ключ, старый код, текст) — сразу `ValueError`;
- код верного вида, но которого нет в каталоге (самодельный), — в строгом режиме `UnknownCodeError`,
  в обычном — замена на `COMMON-SYS-001` и запись в журнал разработчика (логгер `homensai_errors`).

Какой каталог проверяет код: заданный `configure(catalog)`; если не задан — встроенные константы `codes.CODES`
(строгий режим). Продукт в работе вызывает `configure(Catalog.load(...))` с `strict=False`, тесты продукта — со
`strict=True`, чтобы самодельный код ронял тест.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .catalog import Catalog

CODE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}-[A-Z0-9]{2,8}-[0-9]{3}$")
FALLBACK_CODE = "COMMON-SYS-001"
log = logging.getLogger("homensai_errors")


class CatalogError(Exception):
    """Каталог не загружен: нет файлов, неверный манифест, повтор кода или имени."""


class IntegrityError(CatalogError):
    """SHA-256 файла каталога не совпадает с `errors.lock` или файла нет в lock."""


class UnknownCodeError(LookupError):
    """Кода, ключа или старого кода нет в каталоге."""

    def __init__(self, name: str):
        super().__init__(f"кода {name!r} нет в каталоге ошибок")
        self.name = name


class ParamsError(ValueError):
    """Подстановки не совпадают с объявленными в `params` записи: лишние или недостающие."""


class _State:
    catalog: Catalog | None = None
    strict: bool = True


_state = _State()


def configure(catalog: Catalog | None, *, strict: bool | None = None) -> None:
    """Задать каталог по умолчанию для `AppError` и `AppError.to_problem`/`render`.

    `strict` по умолчанию берётся из каталога; `configure(None)` возвращает встроенные константы и строгий режим.
    """
    _state.catalog = catalog
    if strict is not None:
        _state.strict = strict
    else:
        _state.strict = catalog.strict if catalog is not None else True


def default_catalog() -> Catalog | None:
    """Каталог, заданный `configure`, или `None`."""
    return _state.catalog


def _known_codes() -> frozenset[str] | Catalog:
    if _state.catalog is not None:
        return _state.catalog
    from . import codes

    return codes.CODES


class AppError(Exception):
    """Ошибка продукта с кодом из каталога: `raise AppError("RENT-DR-001", days=3)` или `AppError(Errors.RENT_DR_001)`."""

    def __init__(self, code: str, /, **params: Any):
        if not isinstance(code, str) or not CODE_RE.match(code):
            raise ValueError(f"AppError принимает только код вида NS-AREA-NNN из каталога, получено {code!r}")
        self.params: dict[str, Any] = dict(params)
        self.original_code: str | None = None
        known = _known_codes()
        if code not in known:
            if _state.strict:
                raise UnknownCodeError(code)
            log.error("самодельный или неизвестный код ошибки %s заменён на %s", code, FALLBACK_CODE)
            self.original_code, code, self.params = code, FALLBACK_CODE, {}
        elif _state.strict and _state.catalog is not None:
            _state.catalog.check_params(code, self.params)
        self.code: str = code
        super().__init__(code)

    def __str__(self) -> str:
        return self.code

    def __reduce__(self):  # pickle: восстановить без повторной проверки каталога
        return (_restore, (type(self), dict(self.__dict__)))

    def _catalog(self, catalog: Catalog | None) -> Catalog:
        catalog = catalog or _state.catalog
        if catalog is None:
            raise CatalogError("каталог не задан: передайте catalog= или вызовите homensai_errors.configure(catalog)")
        return catalog

    def render(self, lang: str = "en", *, catalog: Catalog | None = None):
        """Тексты ошибки на языке (`Catalog.render`)."""
        return self._catalog(catalog).render(self.code, lang=lang, params=self.params)

    def to_problem(self, lang: str = "en", *, catalog: Catalog | None = None, **kwargs: Any) -> dict[str, Any]:
        """Ответ API по RFC 9457 (`Catalog.to_problem`)."""
        return self._catalog(catalog).to_problem(self, lang=lang, **kwargs)


def _restore(cls: type[AppError], state: dict[str, Any]) -> AppError:
    obj = cls.__new__(cls)
    Exception.__init__(obj, state.get("code"))
    obj.__dict__.update(state)
    return obj
