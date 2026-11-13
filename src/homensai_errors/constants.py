# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Генерация констант кодов для продукта: Python (`codes.py`) и TypeScript (`codes.ts`), ARCHITECTURE.md §11.2.

Для каждого кода — две константы с одним значением: по коду (`Errors.RENT_DR_001`) и по `key`
(`Errors.BACKUP_PASSWORD_CHECK_OVERDUE`). Опечатка в имени ловится проверкой типов до запуска.
Вывод детерминирован: порядок по коду, без даты и версии, поэтому файл меняется только при изменении кодов.
"""

from __future__ import annotations

from .catalog import Catalog

AUTHOR = "HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI"
NOTICE = "Сгенерировано tools/gen_constants.py из базы HomenSAI/Error-database — не править вручную."


def _pairs(catalog: Catalog) -> list[tuple[str, str, str]]:
    """(имя константы, код, комментарий) — сначала по коду, затем по key; повтор имени — ошибка."""
    rows: list[tuple[str, str, str]] = []
    seen: dict[str, str] = {}
    for entry in catalog:
        note = entry.key
        if entry.deprecated:
            note += f"; устарел с {entry.deprecated}" + (f", замена {entry.replaced_by}" if entry.replaced_by else "")
        for name, comment in ((entry.code.replace("-", "_"), note), (entry.key, entry.code)):
            if seen.setdefault(name, entry.code) != entry.code:
                raise ValueError(f"имя константы {name} занято кодами {seen[name]} и {entry.code}")
            rows.append((name, entry.code, comment))
    return rows


def python_module(catalog: Catalog) -> str:
    rows = _pairs(catalog)
    lines = [f"# {AUTHOR}", f'"""Константы кодов ошибок. {NOTICE}', "",
             'Использование: `raise AppError(Errors.RENT_DR_001, days=3)`."""', "",
             "from __future__ import annotations", "", "from typing import Final", "", "",
             "class Errors:", '    """Коды ошибок: по коду (`RENT_DR_001`) и по key (`BACKUP_PASSWORD_CHECK_OVERDUE`)."""', ""]
    lines += [f'    {name}: Final = "{code}"  # {comment}' for name, code, comment in rows]
    if not rows:
        lines.append("    pass")
    lines += ["", "", "CODES: Final[frozenset[str]] = frozenset({"]
    lines += [f'    "{entry.code}",' for entry in catalog]
    lines += ["})", ""]
    return "\n".join(lines)


def typescript_module(catalog: Catalog) -> str:
    rows = _pairs(catalog)
    lines = [f"// {AUTHOR}", f"// Константы кодов ошибок. {NOTICE}", "",
             "export const Errors = {"]
    lines += [f'  {name}: "{code}", // {comment}' for name, code, comment in rows]
    lines += ["} as const;", "", "export type ErrorCode = (typeof Errors)[keyof typeof Errors];", "",
              "export const CODES: ReadonlySet<ErrorCode> = new Set<ErrorCode>(["]
    lines += [f'  "{entry.code}",' for entry in catalog]
    lines += ["]);", ""]
    return "\n".join(lines)
