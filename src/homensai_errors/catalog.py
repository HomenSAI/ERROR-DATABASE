# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Каталог кодов ошибок: загрузка, поиск записи, тексты на языке, ответ API, страница помощи, поиск (ARCHITECTURE.md §7).

Источник каталога — папка одного из двух видов:
- исходники базы: `codes/<NS>/<AREA>.json` + `namespaces.json` (этот репозиторий);
- выпуск: `errors.<NS>.json` или `errors.json` (`dist/` или `vendor/errors/` продукта).

Манифест продукта `errors.manifest.json` задаёт пространства, языки, диапазон версии и переходный период §12.
Если рядом есть `errors.lock`, SHA-256 файлов сверяются с ним (§7.1). Внешних зависимостей нет.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping

from . import _texts
from ._texts import LANGS, LABELS
from .errors import FALLBACK_CODE, AppError, CatalogError, IntegrityError, ParamsError, UnknownCodeError, log

DATABASE = "HomenSAI/Error-database"
SITE_URL = "https://homensai.github.io/ERROR-DATABASE"
PROBLEM_CONTENT_TYPE = "application/problem+json"
FORMAT = 1
ALWAYS_NAMESPACES = ("COMMON",)

ENTRY_FIELDS = ("code", "key", "aliases", "level", "audience", "title", "cause", "action", "escalation", "params",
                "retryable", "http_status", "help", "related", "since", "deprecated", "replaced_by", "tags", "fixed_in",
                "examples")
STEP_FIELDS = ("to", "when", "assistant", "prompt", "channel", "data")
_PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_CHANGELOG_RE = re.compile(r"^## (\d+\.\d+\.\d+)\b", re.M)
_CODE_RE = re.compile(r"^([A-Z][A-Z0-9]{1,9})-([A-Z0-9]{2,8})-[0-9]{3}$")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class Entry:
    """Запись об ошибке (§4). Поля только для чтения; тексты — отображения язык → строка."""

    code: str
    key: str
    level: str
    audience: str
    title: Mapping[str, str]
    cause: Mapping[str, str]
    action: Mapping[str, str]
    escalation: tuple[Mapping[str, Any], ...]
    retryable: bool
    help: str
    since: str
    aliases: tuple[str, ...] = ()
    params: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    http_status: int | None = None
    related: tuple[str, ...] = ()
    deprecated: str | None = None
    replaced_by: str | None = None
    tags: tuple[str, ...] = ()
    fixed_in: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    examples: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Entry:
        unknown = set(data) - set(ENTRY_FIELDS)
        if unknown:
            raise CatalogError(f"{data.get('code', '?')}: неизвестные поля {sorted(unknown)}")
        try:
            return cls(**{k: _freeze(v) for k, v in data.items()})
        except TypeError as exc:
            raise CatalogError(f"{data.get('code', '?')}: неполная запись ({exc})") from None

    @property
    def namespace(self) -> str:
        return self.code.split("-", 1)[0]

    @property
    def area(self) -> str:
        return self.code.split("-")[1]

    @property
    def legacy_codes(self) -> tuple[str, ...]:
        """Прежние коды продуктов (`aliases`), §12."""
        return self.aliases

    def as_dict(self) -> dict[str, Any]:
        """Запись в каноническом порядке полей схемы и языков — для выпуска."""
        out: dict[str, Any] = {}
        for name in ENTRY_FIELDS:
            value = getattr(self, name)
            if value is None or (name in ("aliases", "params", "related", "tags", "fixed_in") and not value):
                continue
            if name in ("title", "cause", "action"):
                value = {lang: value[lang] for lang in LANGS if lang in value}
            elif name == "escalation":
                value = [{k: _thaw(step[k]) for k in STEP_FIELDS if k in step} for step in value]
            out[name] = _thaw(value)
        return out


@dataclass(frozen=True)
class Rendered:
    """Тексты ошибки на одном языке с подстановками (§7.2, §12). `str()` — блок «новый код, старый код, описание»."""

    code: str
    key: str
    lang: str
    level: str
    title: str
    cause: str
    action: str
    escalation: tuple[str, ...]
    legacy_codes: tuple[str, ...]
    retryable: bool
    help_url: str
    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True)
class Hit:
    """Результат поиска: чем больше `score`, тем точнее совпадение."""

    code: str
    key: str
    title: str
    score: int


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def changelog_version(root: Path) -> str | None:
    """Версия базы — первый заголовок `## X.Y.Z` в `CHANGELOG.md` или `None`."""
    path = Path(root) / "CHANGELOG.md"
    if not path.is_file():
        return None
    match = _CHANGELOG_RE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def make_lock(directory: Path, version: str, files: list[str] | None = None) -> dict[str, Any]:
    """Содержимое `errors.lock` продукта: версия и SHA-256 файлов выпуска в `directory` (по умолчанию — все errors*.json)."""
    directory = Path(directory)
    names = files if files is not None else sorted(p.name for p in directory.glob("errors*.json"))
    return {"database": DATABASE, "version": version, "files": {n: sha256_file(directory / n) for n in sorted(names)}}


def _version_ok(spec: str, version: str) -> bool:
    """Простая проверка диапазона манифеста: `^X.Y.Z` (та же major, не ниже), `X.Y.Z` (точно), `*`."""
    if spec in ("", "*"):
        return True
    want = _VERSION_RE.match(spec.lstrip("^=~"))
    have = _VERSION_RE.match(version)
    if not want or not have:
        return False
    w, h = tuple(map(int, want.groups())), tuple(map(int, have.groups()))
    if spec.startswith("^"):
        return h[0] == w[0] and h >= w
    if spec.startswith("~"):
        return h[:2] == w[:2] and h >= w
    return h == w


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CatalogError(f"{path}: не читается как JSON ({exc})") from None


def _find_near(path: Path, name: str) -> Path | None:
    for directory in (path, path.parent, path.parent.parent):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _substitute(text: str, params: Mapping[str, Any]) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: str(params[m.group(1)]) if m.group(1) in params else m.group(0), text)


class Catalog:
    """Каталог кодов: поиск по `code`, `key` и `aliases`; тексты, RFC 9457, помощь, поиск.

    `strict=True` — для тестов продукта: неизвестный код и неверные подстановки — исключение.
    `strict=False` — для работы: неизвестный код заменяется на `COMMON-SYS-001` с записью в журнал, недостающие
    подстановки остаются как `{имя}`.
    """

    def __init__(self, entries: list[Entry] | tuple[Entry, ...], *, namespaces: Mapping[str, Any] | None = None,
                 languages: tuple[str, ...] | list[str] = LANGS, version: str | None = None,
                 show_legacy_codes: bool = True, strict: bool = False, site_url: str = SITE_URL,
                 fallback_lang: str = "en"):
        bad = [lang for lang in languages if lang not in LANGS]
        if bad or not languages:
            raise CatalogError(f"языки каталога — подмножество {LANGS}, получено {list(languages)}")
        self.languages: tuple[str, ...] = tuple(lang for lang in LANGS if lang in languages)
        self.version = version
        self.show_legacy_codes = show_legacy_codes
        self.strict = strict
        self.site_url = site_url.rstrip("/")
        self.fallback_lang = fallback_lang if fallback_lang in self.languages else self.languages[0]
        self.namespaces: dict[str, Any] = {k: _thaw(v) for k, v in (namespaces or {}).items()}
        self._entries: dict[str, Entry] = {}
        self._names: dict[str, str] = {}
        for entry in sorted(entries, key=lambda e: e.code):
            if not _CODE_RE.match(entry.code):
                raise CatalogError(f"{entry.code}: код должен иметь вид NS-AREA-NNN")
            if entry.code in self._entries:
                raise CatalogError(f"{entry.code}: код встречается дважды")
            for field_name in ("title", "cause", "action"):
                missing = [lang for lang in self.languages if lang not in getattr(entry, field_name)]
                if missing:
                    raise CatalogError(f"{entry.code}: {field_name} без языков {missing}")
            self._entries[entry.code] = entry
            for name in (entry.code, entry.key, *entry.aliases):
                owner = self._names.setdefault(name, entry.code)
                if owner != entry.code:
                    raise CatalogError(f"{entry.code}: имя {name} уже занято кодом {owner}")

    # --- загрузка -------------------------------------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path = ".", *, manifest: str | Path | Mapping[str, Any] | bool | None = None,
             lock: str | Path | bool | None = None, require_lock: bool = False, strict: bool = False,
             site_url: str = SITE_URL, fallback_lang: str = "en") -> Catalog:
        """Загрузить каталог из исходников базы или из выпуска.

        `manifest`/`lock`: путь или `None` — искать `errors.manifest.json`/`errors.lock` в папке и до двух уровней
        выше (`vendor/errors` → корень продукта); `False` — не использовать. Манифест может быть и словарём.
        Пространство `COMMON` загружается всегда: в нём запасной код `COMMON-SYS-001`.
        """
        root = Path(path)
        if not root.is_dir():
            raise CatalogError(f"{root}: папки каталога нет")
        man = cls._manifest(root, manifest)
        wanted = None
        if man.get("namespaces") is not None:
            wanted = set(man["namespaces"]) | set(ALWAYS_NAMESPACES)
        if (root / "codes").is_dir():
            entries, namespaces, version, files = cls._load_source(root, wanted)
        else:
            entries, namespaces, version, files = cls._load_dist(root, wanted)
        lock_path = None if lock is False else (Path(lock) if lock not in (None, True) else _find_near(root, "errors.lock"))
        if lock_path is not None:
            version = cls._verify_lock(root, lock_path, files) or version
        elif require_lock:
            raise IntegrityError(f"{root}: нет errors.lock, а сверка SHA-256 обязательна")
        spec = str(man.get("version", ""))
        if spec and version and not _version_ok(spec, version):
            raise CatalogError(f"версия базы {version} не подходит под {spec!r} из манифеста")
        transition = man.get("transition") or {}
        show_legacy = transition.get("show_legacy_codes", True)
        if not isinstance(show_legacy, bool):
            raise CatalogError("transition.show_legacy_codes в манифесте — true или false")
        return cls(entries, namespaces=namespaces, languages=tuple(man.get("languages") or LANGS), version=version,
                   show_legacy_codes=show_legacy, strict=strict, site_url=site_url, fallback_lang=fallback_lang)

    @staticmethod
    def _manifest(root: Path, manifest: Any) -> dict[str, Any]:
        if manifest is False:
            return {}
        if isinstance(manifest, Mapping):
            data = dict(manifest)
        else:
            found = Path(manifest) if manifest not in (None, True) else _find_near(root, "errors.manifest.json")
            if found is None:
                return {}
            data = _read_json(found)
        if not isinstance(data, dict):
            raise CatalogError("errors.manifest.json — объект JSON")
        for name in ("namespaces", "languages"):
            value = data.get(name)
            if value is not None and (not isinstance(value, list) or not all(isinstance(v, str) for v in value)):
                raise CatalogError(f"errors.manifest.json: {name} — список строк")
        return data

    @staticmethod
    def _load_source(root: Path, wanted: set[str] | None):
        namespaces = _read_json(root / "namespaces.json") if (root / "namespaces.json").is_file() else {}
        entries, files = [], []
        for path in sorted((root / "codes").glob("*/*.json")):
            if wanted is not None and path.parent.name not in wanted:
                continue
            data = _read_json(path)
            entries += [Entry.from_dict(item) for item in data.get("codes", [])]
            files.append(path.relative_to(root).as_posix())
        if wanted is not None:
            missing = sorted(wanted - set(namespaces))
            if missing:
                raise CatalogError(f"пространства {missing} не объявлены в namespaces.json")
            namespaces = {k: v for k, v in namespaces.items() if k in wanted}
        return entries, namespaces, changelog_version(root), files

    @staticmethod
    def _load_dist(root: Path, wanted: set[str] | None):
        per_ns = {p.name[len("errors."):-len(".json")]: p for p in sorted(root.glob("errors.*.json"))}
        full = root / "errors.json"
        if wanted is None:
            sources = [full] if full.is_file() else list(per_ns.values())
        elif all(ns in per_ns for ns in wanted):
            sources = [per_ns[ns] for ns in sorted(wanted)]
        elif full.is_file():
            sources = [full]
        else:
            missing = sorted(ns for ns in wanted if ns not in per_ns)
            raise CatalogError(f"{root}: нет файлов пространств {missing} (errors.<NS>.json)")
        if not sources:
            raise CatalogError(f"{root}: нет ни codes/, ни errors*.json")
        entries, namespaces, versions = [], {}, set()
        for path in sources:
            data = _read_json(path)
            if data.get("format") != FORMAT:
                raise CatalogError(f"{path.name}: формат выпуска {data.get('format')!r}, библиотека понимает {FORMAT}")
            versions.add(data.get("version"))
            for ns, info in (data.get("namespaces") or {}).items():
                if wanted is None or ns in wanted:
                    namespaces[ns] = info
            entries += [Entry.from_dict(item) for item in data.get("codes", [])
                        if wanted is None or item.get("code", "").split("-", 1)[0] in wanted]
        if wanted is not None:
            missing = sorted(wanted - set(namespaces))
            if missing:
                raise CatalogError(f"{root}: в выпуске нет пространств {missing}")
        if len(versions) > 1:
            raise CatalogError(f"{root}: файлы выпуска разных версий {sorted(map(str, versions))}")
        return entries, namespaces, versions.pop() if versions else None, [p.name for p in sources]

    @staticmethod
    def _verify_lock(root: Path, lock_path: Path, loaded: list[str]) -> str | None:
        data = _read_json(lock_path)
        listed = data.get("files") if isinstance(data, dict) else None
        if not isinstance(listed, dict):
            raise IntegrityError(f"{lock_path}: нет списка files с SHA-256")
        for name, digest in sorted(listed.items()):
            target = root / name
            if not target.is_file():
                raise IntegrityError(f"{name}: файла из errors.lock нет в {root}")
            if sha256_file(target) != digest:
                raise IntegrityError(f"{name}: SHA-256 не совпадает с errors.lock")
        unlisted = sorted(set(loaded) - set(listed))
        if unlisted:
            raise IntegrityError(f"файлы {unlisted} загружены, но не закреплены в errors.lock")
        return data.get("version")

    # --- поиск записи ---------------------------------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[Entry]:
        return iter(self._entries.values())

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._names

    def codes(self) -> list[str]:
        return list(self._entries)

    def find(self, name: str) -> Entry | None:
        """Запись по коду, `key` или старому коду (`aliases`); `None`, если нет."""
        code = self._names.get(name) if isinstance(name, str) else None
        if code is None and isinstance(name, str):
            code = self._names.get(name.strip().upper())
        return self._entries.get(code) if code else None

    def get(self, name: str) -> Entry:
        """Запись по коду, `key` или старому коду; нет — `UnknownCodeError`."""
        entry = self.find(name)
        if entry is None:
            raise UnknownCodeError(name)
        return entry

    def _resolve(self, name: str) -> tuple[Entry, bool]:
        entry = self.find(name)
        if entry is not None:
            return entry, False
        if self.strict or FALLBACK_CODE not in self._entries:
            raise UnknownCodeError(name)
        log.error("неизвестный код ошибки %s заменён на %s", name, FALLBACK_CODE)
        return self._entries[FALLBACK_CODE], True

    def lang(self, lang: str | None) -> str:
        """Язык каталога для запрошенного (`uk-UA` → `uk`); нет такого — запасной (`en` или первый язык манифеста)."""
        base = (lang or "").replace("_", "-").split("-")[0].lower()
        return base if base in self.languages else self.fallback_lang

    # --- подстановки ----------------------------------------------------------------------------------------------

    @staticmethod
    def placeholders(entry: Entry) -> set[str]:
        found: set[str] = set()
        for field_name in ("title", "cause", "action"):
            for text in getattr(entry, field_name).values():
                found |= set(_PLACEHOLDER_RE.findall(text))
        return found

    def check_params(self, name: str, params: Mapping[str, Any] | None) -> None:
        """Сверить подстановки с `params` записи: лишние и недостающие — `ParamsError`."""
        entry = self.get(name)
        given = set(params or {})
        declared = set(entry.params) | self.placeholders(entry)
        missing, extra = sorted(declared - given), sorted(given - declared)
        if missing or extra:
            raise ParamsError(f"{entry.code}: подстановки не совпадают — нет {missing}, лишние {extra}")

    def _params(self, entry: Entry, params: Mapping[str, Any] | None, fallback: bool) -> Mapping[str, Any]:
        if fallback:
            return {}
        params = dict(params or {})
        if self.strict:
            self.check_params(entry.code, params)
        return params

    # --- тексты ---------------------------------------------------------------------------------------------------

    def help_url(self, name: str, lang: str | None = None) -> str:
        """Адрес страницы помощи на сайте-справочнике; с языком — `<сайт>/<lang>/errors/<код>`."""
        entry = self.get(name)
        return f"{self.site_url}/{self.lang(lang)}/{entry.help}" if lang else f"{self.site_url}/{entry.help}"

    def legacy_line(self, entry: Entry, lang: str) -> str:
        """Строка «КОД (прежний код: …)» по правилу переходного периода §12."""
        if not (self.show_legacy_codes and entry.aliases):
            return entry.code
        label = LABELS[lang]["legacy_one" if len(entry.aliases) == 1 else "legacy_many"]
        return f"{entry.code} ({label}: {', '.join(entry.aliases)})"

    def render(self, name: str, lang: str = "en", params: Mapping[str, Any] | None = None) -> Rendered:
        """Тексты на языке с подстановками: что случилось, почему, что делать, кому передать (§7.2, §12)."""
        entry, fallback = self._resolve(name)
        lang = self.lang(lang)
        values = self._params(entry, params, fallback)
        title, cause, action = (_substitute(getattr(entry, f)[lang], values) for f in ("title", "cause", "action"))
        steps = tuple(_texts.STEPS[lang][step["to"]] for step in entry.escalation)
        labels = LABELS[lang]
        text = "\n".join([
            self.legacy_line(entry, lang),
            title,
            f"{labels['why']}: {cause} · {labels['todo']}: {' '.join(action.splitlines())} · "
            f"{labels['escalate']}: {' → '.join(steps)}",
        ])
        return Rendered(code=entry.code, key=entry.key, lang=lang, level=entry.level, title=title, cause=cause,
                        action=action, escalation=steps,
                        legacy_codes=entry.aliases if self.show_legacy_codes else (), retryable=entry.retryable,
                        help_url=self.help_url(entry.code, lang), text=text)

    def to_problem(self, error: str | AppError, lang: str = "en", *, status: int | None = None,
                   instance: str | None = None, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Ответ API по RFC 9457 (`Content-Type: application/problem+json`, §6.3).

        `type` — адрес кода на сайте-справочнике без языка (устойчивый идентификатор), `title`/`detail` — на языке,
        `status` — переданный или `http_status` записи (нет обоих — поле не выводится), расширения `code`, `key`,
        `retryable` и в переходный период `legacy_codes`.
        """
        if isinstance(error, AppError):
            name, params = error.code, error.params if params is None else params
        else:
            name = error
        entry, fallback = self._resolve(name)
        lang = self.lang(lang)
        values = self._params(entry, params, fallback)
        problem: dict[str, Any] = {"type": self.help_url(entry.code), "title": _substitute(entry.title[lang], values)}
        status = status if status is not None else entry.http_status
        if status is not None:
            problem["status"] = int(status)
        problem["detail"] = _substitute(entry.cause[lang], values)
        if instance is not None:
            problem["instance"] = instance
        problem.update(code=entry.code, key=entry.key, retryable=entry.retryable)
        if self.show_legacy_codes and entry.aliases:
            problem["legacy_codes"] = list(entry.aliases)
        return problem

    def help_page(self, name: str, lang: str = "en", params: Mapping[str, Any] | None = None, *,
                  heading: int = 1, link_suffix: str = ".md") -> str:
        """Страница помощи в Markdown на языке; язык не из каталога — запасной (§7.3).

        Подстановки необязательны: без них в тексте остаются `{имя}`. Связанные коды — относительные ссылки
        `<код><link_suffix>` (в выпуске — соседние файлы `help/<lang>/`).
        """
        entry = self.get(name)
        lang = self.lang(lang)
        values = dict(params or {})
        labels, h = LABELS[lang], "#" * heading
        yes_no = labels["yes" if entry.retryable else "no"]
        lines = [f"{h} {entry.code} — {_substitute(entry.title[lang], values)}", ""]
        if self.show_legacy_codes and entry.aliases:
            label = labels["legacy_one" if len(entry.aliases) == 1 else "legacy_many"]
            lines += [f"{label[0].upper()}{label[1:]}: {', '.join(f'`{a}`' for a in entry.aliases)}", ""]
        lines += [f"**{labels['level']}:** {_texts.LEVELS[lang][entry.level]} · "
                  f"**{labels['audience']}:** {_texts.AUDIENCES[lang][entry.audience]} · "
                  f"**{labels['retryable']}:** {yes_no}", ""]
        lines += [f"{h}# {labels['why']}", "", _substitute(entry.cause[lang], values), ""]
        lines += [f"{h}# {labels['todo']}", "", _substitute(entry.action[lang], values), ""]
        lines += [f"{h}# {labels['escalate']}", ""]
        for number, step in enumerate(entry.escalation, 1):
            when = f" — {step['when']}" if lang == _texts.WHEN_LANG and step.get("when") else ""
            lines.append(f"{number}. {_texts.STEPS[lang][step['to']]}{when}")
        lines.append("")
        if entry.related:
            lines += [f"{h}# {labels['related']}", ""]
            for code in entry.related:
                other = self.find(code)
                title = f" — {other.title[lang]}" if other else ""
                lines.append(f"- [{code}]({code}{link_suffix}){title}")
            lines.append("")
        meta = [f"`{entry.key}`", f"{labels['since']} {entry.since}"]
        if entry.deprecated:
            meta.append(f"{labels['deprecated']} {entry.deprecated}")
        if entry.replaced_by:
            meta.append(f"{labels['replaced_by']} [{entry.replaced_by}]({entry.replaced_by}{link_suffix})")
        if entry.fixed_in:
            meta.append(f"{labels['fixed_in']}: " + ", ".join(f"{p} {v}" for p, v in sorted(entry.fixed_in.items())))
        lines += ["---", "", " · ".join(meta), ""]
        return "\n".join(lines)

    # --- поиск ----------------------------------------------------------------------------------------------------

    def search_doc(self, entry: Entry, lang: str) -> dict[str, Any]:
        """Запись индекса поиска на языке — общая для `search` и `dist/search.<lang>.json`."""
        lang = self.lang(lang)
        return {
            "code": entry.code,
            "key": entry.key,
            "aliases": list(entry.aliases),
            "level": entry.level,
            "title": entry.title[lang],
            "title_terms": _texts.terms(entry.title[lang]),
            "terms": _texts.terms(" ".join([entry.cause[lang], entry.action[lang], " ".join(entry.tags),
                                            entry.key.replace("_", " ")])),
        }

    def search(self, query: str, lang: str = "en", limit: int = 20) -> list[Hit]:
        """Поиск по коду, старому коду, `key` и словам текста на языке.

        Точное имя — первым; начало кода (`RENT-DR`) — все коды области; слова — все слова запроса должны найтись
        (сравнение по простой основе слова), слово в заголовке весит больше.
        """
        lang = self.lang(lang)
        raw = query.strip()
        if not raw:
            return []
        scores: dict[str, int] = {}
        exact = self.find(raw)
        if exact is not None:
            scores[exact.code] = 1000
        prefix = raw.upper()
        if "-" in prefix:
            for code in self._entries:
                if code.startswith(prefix) and code not in scores:
                    scores[code] = 500
        tokens = _texts.normalize(raw).split()
        if tokens:
            for entry in self:
                doc = self.search_doc(entry, lang)
                names = [_texts.normalize(n) for n in (entry.code, entry.key, *entry.aliases)]
                score = 0
                for token in tokens:
                    base = _texts.stem(token)
                    if any(token in n for n in names):
                        score += 5
                    elif any(t.startswith(base) for t in doc["title_terms"]):
                        score += 3
                    elif any(t.startswith(base) for t in doc["terms"]):
                        score += 1
                    else:
                        score = 0
                        break
                if score:
                    scores[entry.code] = max(scores.get(entry.code, 0), score)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:max(limit, 0)]
        return [Hit(code=c, key=self._entries[c].key, title=self._entries[c].title[lang], score=s) for c, s in ranked]
