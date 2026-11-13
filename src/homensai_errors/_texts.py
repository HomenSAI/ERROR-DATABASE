# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Подписи интерфейса на 4 языках, нормализация текста и простая основа слова для поиска.

Нормализация общая для `Catalog.search` и индекса `dist/search.<lang>.json`, поэтому поиск в программе и на сайте
находит одно и то же.
"""

from __future__ import annotations

import re

LANGS: tuple[str, ...] = ("ru", "uk", "en", "de")

LABELS: dict[str, dict[str, str]] = {
    "ru": {
        "legacy_one": "прежний код", "legacy_many": "прежние коды", "why": "Почему", "todo": "Что делать",
        "escalate": "Кому передать", "related": "Связанные коды", "level": "Уровень", "audience": "Для кого",
        "retryable": "Можно повторить позже", "yes": "да", "no": "нет", "since": "с версии",
        "deprecated": "устарел с версии", "replaced_by": "заменён кодом", "fixed_in": "исправлено в версии",
        "reference": "Справочник кодов ошибок HomenS.AI", "version": "версия",
    },
    "uk": {
        "legacy_one": "попередній код", "legacy_many": "попередні коди", "why": "Чому", "todo": "Що робити",
        "escalate": "Кому передати", "related": "Пов'язані коди", "level": "Рівень", "audience": "Для кого",
        "retryable": "Можна повторити пізніше", "yes": "так", "no": "ні", "since": "з версії",
        "deprecated": "застарів з версії", "replaced_by": "замінено кодом", "fixed_in": "виправлено у версії",
        "reference": "Довідник кодів помилок HomenS.AI", "version": "версія",
    },
    "en": {
        "legacy_one": "former code", "legacy_many": "former codes", "why": "Why", "todo": "What to do",
        "escalate": "Who to contact", "related": "Related codes", "level": "Level", "audience": "For",
        "retryable": "Can be retried later", "yes": "yes", "no": "no", "since": "since version",
        "deprecated": "deprecated since version", "replaced_by": "replaced by", "fixed_in": "fixed in version",
        "reference": "HomenS.AI error code reference", "version": "version",
    },
    "de": {
        "legacy_one": "früherer Code", "legacy_many": "frühere Codes", "why": "Warum", "todo": "Was tun",
        "escalate": "An wen wenden", "related": "Verwandte Codes", "level": "Stufe", "audience": "Für",
        "retryable": "Später wiederholbar", "yes": "ja", "no": "nein", "since": "seit Version",
        "deprecated": "veraltet seit Version", "replaced_by": "ersetzt durch", "fixed_in": "behoben in Version",
        "reference": "HomenS.AI Fehlercode-Referenz", "version": "Version",
    },
}

LEVELS: dict[str, dict[str, str]] = {
    "ru": {"info": "к сведению", "warn": "внимание", "error": "ошибка", "alarm": "тревога"},
    "uk": {"info": "до відома", "warn": "увага", "error": "помилка", "alarm": "тривога"},
    "en": {"info": "info", "warn": "warning", "error": "error", "alarm": "alarm"},
    "de": {"info": "Hinweis", "warn": "Warnung", "error": "Fehler", "alarm": "Alarm"},
}

AUDIENCES: dict[str, dict[str, str]] = {
    "ru": {"user": "пользователь", "admin": "администратор", "developer": "разработчик"},
    "uk": {"user": "користувач", "admin": "адміністратор", "developer": "розробник"},
    "en": {"user": "user", "admin": "administrator", "developer": "developer"},
    "de": {"user": "Benutzer", "admin": "Administrator", "developer": "Entwickler"},
}

STEPS: dict[str, dict[str, str]] = {
    "ru": {"self": "Сами по шагам выше", "admin": "Администратор", "ai": "Помощник-нейросеть",
           "developer": "Разработчик (пакет поддержки)"},
    "uk": {"self": "Самостійно за кроками вище", "admin": "Адміністратор", "ai": "Помічник-нейромережа",
           "developer": "Розробник (пакет підтримки)"},
    "en": {"self": "Yourself, following the steps above", "admin": "Administrator", "ai": "AI assistant",
           "developer": "Developer (support bundle)"},
    "de": {"self": "Selbst anhand der Schritte oben", "admin": "Administrator", "ai": "KI-Assistent",
           "developer": "Entwickler (Support-Paket)"},
}

# Поле `when` ступени escalation в базе пишется только по-русски, поэтому показывается только на RU.
WHEN_LANG = "ru"

_PLACEHOLDER_RE = re.compile(r"\{[a-z_][a-z0-9_]*\}")
_APOSTROPHES_RE = re.compile(r"['’ʼ`]")
_SPLIT_RE = re.compile(r"[\W_]+")


def normalize(text: str) -> str:
    """Строка для поиска: без подстановок, регистр сложен, «ё» → «е», апострофы убраны, слова через пробел."""
    text = _PLACEHOLDER_RE.sub(" ", text).casefold().replace("ё", "е")
    text = _APOSTROPHES_RE.sub("", text)
    return " ".join(part for part in _SPLIT_RE.split(text) if part)


def stem(token: str) -> str:
    """Простая основа слова: длинные слова сравниваются без 1–2 последних букв («пароль» ~ «пароля», «копий» ~ «копии»)."""
    if len(token) >= 7:
        return token[:-2]
    if len(token) >= 5:
        return token[:-1]
    return token


def terms(text: str) -> list[str]:
    """Отсортированные уникальные слова текста после `normalize`."""
    return sorted(set(normalize(text).split()))
