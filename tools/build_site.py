#!/usr/bin/env python3
# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Сборка сайта-справочника `site/` для GitHub Pages (ARCHITECTURE.md §6.4, §11.1; решения 28.10-288, 28.10-321).

Сайт строится из того же каталога, что и выпуск: файлы `dist/` берутся из `build_dist.build()`, тексты страниц —
из `Catalog.help_page` (Markdown → HTML небольшим преобразователем ниже), поиск на клиенте — по `search.<lang>.json`
той же нормализацией, что `Catalog.search` (`tools/site/site.js`). Без внешних зависимостей.

Адреса (от `SITE_URL`, GitHub Pages отдаёт `x.html` и по адресу `x` без расширения):
- `/` — главная на английском, `/<lang>/` — главная на языке (RU, UK, EN, DE): поиск и пространства кодов;
- `/errors/<код>` — страница кода на английском с переключателем языка; это `type` ответа RFC 9457 (§6.3);
- `/<lang>/errors/<код>` — страница кода на языке; `/<lang>/ns/<NS>` — список кодов пространства по областям;
- `/search.<lang>.json`, `/errors.json`, `/llms.txt`, `/help/…` и остальные файлы выпуска `dist/` — рядом;
- `/404.html` — переход с `/errors/<key>`, `/errors/<прежний код>` и адресов в нижнем регистре.

Сборка детерминирована (без дат, порядок по коду, UTF-8 и `\\n`); `SHA256SUMS` покрывает все файлы сайта.
Без трекеров, внешних шрифтов и CDN: политика `Content-Security-Policy` разрешает только свой адрес.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from homensai_errors.catalog import DATABASE, SITE_URL, Catalog, Entry  # noqa: E402
from homensai_errors._texts import LABELS, LANGS, LEVELS  # noqa: E402

import build_dist  # noqa: E402

ASSETS = ROOT / "tools" / "site"
DEFAULT_LANG = "en"
AUTHOR = "HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI"
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
       "object-src 'none'; base-uri 'none'; form-action 'self'")
SEARCH_LIMIT = 100

LANG_NAMES = {"ru": "Русский", "uk": "Українська", "en": "English", "de": "Deutsch"}

SITE: dict[str, dict[str, str]] = {
    "ru": {
        "site": "Коды ошибок HomenS.AI", "home": "Главная", "skip": "Перейти к содержимому", "language": "Язык",
        "intro": "Справочник кодов ошибок продуктов HomenSAI: что случилось, почему и что делать — на русском, "
                 "украинском, английском и немецком. Ищите по коду, прежнему коду или словам.",
        "search": "Поиск по коду, прежнему коду или словам", "find": "Найти",
        "placeholder": "например, RENT-DR-001 или пароль копий",
        "found": "Найдено: {n}", "first": "показаны первые {n}", "none": "Ничего не найдено.",
        "failed": "Не удалось загрузить индекс поиска.",
        "noscript": "Поиск работает с включённым JavaScript. Ниже — все коды по пространствам.",
        "namespaces": "Пространства кодов", "codes": "кодов: {n}", "empty": "Кодов пока нет.",
        "common": "Общие для всех продуктов", "theme": "Тема", "auto": "как в системе", "light": "светлая",
        "dark": "тёмная", "developers": "Для разработчиков", "type": "Идентификатор (type, RFC 9457)",
        "problem": "Пример ответа API (RFC 9457)", "data": "Данные", "source": "Исходники",
        "notfound": "Страница не найдена", "notfound_text": "Такой страницы нет. Если это адрес кода — проверьте код "
        "или найдите его поиском.", "breadcrumbs": "Навигация", "key": "Машинное имя (key)",
    },
    "uk": {
        "site": "Коди помилок HomenS.AI", "home": "Головна", "skip": "Перейти до вмісту", "language": "Мова",
        "intro": "Довідник кодів помилок продуктів HomenSAI: що сталося, чому і що робити — російською, "
                 "українською, англійською та німецькою. Шукайте за кодом, попереднім кодом або словами.",
        "search": "Пошук за кодом, попереднім кодом або словами", "find": "Знайти",
        "placeholder": "наприклад, RENT-DR-001 або пароль копій",
        "found": "Знайдено: {n}", "first": "показано перші {n}", "none": "Нічого не знайдено.",
        "failed": "Не вдалося завантажити індекс пошуку.",
        "noscript": "Пошук працює з увімкненим JavaScript. Нижче — усі коди за просторами.",
        "namespaces": "Простори кодів", "codes": "кодів: {n}", "empty": "Кодів поки немає.",
        "common": "Спільні для всіх продуктів", "theme": "Тема", "auto": "як у системі", "light": "світла",
        "dark": "темна", "developers": "Для розробників", "type": "Ідентифікатор (type, RFC 9457)",
        "problem": "Приклад відповіді API (RFC 9457)", "data": "Дані", "source": "Вихідний код",
        "notfound": "Сторінку не знайдено", "notfound_text": "Такої сторінки немає. Якщо це адреса коду — "
        "перевірте код або знайдіть його пошуком.", "breadcrumbs": "Навігація", "key": "Машинне ім'я (key)",
    },
    "en": {
        "site": "HomenS.AI error codes", "home": "Home", "skip": "Skip to content", "language": "Language",
        "intro": "Reference of HomenSAI product error codes: what happened, why, and what to do — in Russian, "
                 "Ukrainian, English and German. Search by code, former code or words.",
        "search": "Search by code, former code or words", "find": "Search",
        "placeholder": "e.g. RENT-DR-001 or backup password",
        "found": "Found: {n}", "first": "showing the first {n}", "none": "Nothing found.",
        "failed": "Could not load the search index.",
        "noscript": "Search needs JavaScript. All codes are listed by namespace below.",
        "namespaces": "Code namespaces", "codes": "{n} codes", "empty": "No codes yet.",
        "common": "Shared by all products", "theme": "Theme", "auto": "system", "light": "light", "dark": "dark",
        "developers": "For developers", "type": "Identifier (type, RFC 9457)",
        "problem": "Example API response (RFC 9457)", "data": "Data", "source": "Source",
        "notfound": "Page not found", "notfound_text": "This page does not exist. If this is a code address, check "
        "the code or find it with search.", "breadcrumbs": "Breadcrumbs", "key": "Machine name (key)",
    },
    "de": {
        "site": "HomenS.AI-Fehlercodes", "home": "Start", "skip": "Zum Inhalt springen", "language": "Sprache",
        "intro": "Verzeichnis der Fehlercodes der HomenSAI-Produkte: was passiert ist, warum und was zu tun ist — "
                 "auf Russisch, Ukrainisch, Englisch und Deutsch. Suche nach Code, früherem Code oder Wörtern.",
        "search": "Suche nach Code, früherem Code oder Wörtern", "find": "Suchen",
        "placeholder": "z. B. RENT-DR-001 oder Backup-Passwort",
        "found": "Gefunden: {n}", "first": "die ersten {n} werden angezeigt", "none": "Nichts gefunden.",
        "failed": "Der Suchindex konnte nicht geladen werden.",
        "noscript": "Die Suche benötigt JavaScript. Unten sind alle Codes nach Namensraum aufgelistet.",
        "namespaces": "Code-Namensräume", "codes": "{n} Codes", "empty": "Noch keine Codes.",
        "common": "Für alle Produkte", "theme": "Design", "auto": "System", "light": "hell", "dark": "dunkel",
        "developers": "Für Entwickler", "type": "Kennung (type, RFC 9457)",
        "problem": "Beispiel einer API-Antwort (RFC 9457)", "data": "Daten", "source": "Quellcode",
        "notfound": "Seite nicht gefunden", "notfound_text": "Diese Seite gibt es nicht. Ist es die Adresse eines "
        "Codes, prüfen Sie den Code oder suchen Sie ihn.", "breadcrumbs": "Navigationspfad",
        "key": "Maschinenname (key)",
    },
}

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([A-Z][A-Z0-9]{1,9}-[A-Z0-9]{2,8}-[0-9]{3})\.html\)")
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
_HEADING_RE = re.compile(r"^(#{1,6}) (.*)$")
_OL_RE = re.compile(r"^(\d+)\. (.*)$")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


# --- Markdown страницы помощи → HTML ---------------------------------------------------------------------------

def _inline(text: str) -> str:
    """Строка Markdown из help_page: экранирование, `код`, **жирный**, ссылки на коды, подстановки {имя}."""
    out = esc(text)
    out = _CODE_SPAN_RE.sub(r"<code>\1</code>", out)
    out = _BOLD_RE.sub(r"<strong>\1</strong>", out)
    out = _LINK_RE.sub(r'<a href="\2.html">\1</a>', out)
    return _PLACEHOLDER_RE.sub(r"<var>{\1}</var>", out)


def markdown(text: str) -> str:
    """HTML для подмножества Markdown, которое пишет `Catalog.help_page`: заголовки, абзацы, списки, черта."""
    blocks = [block.split("\n") for block in re.split(r"\n{2,}", text.strip()) if block.strip()]
    out: list[str] = []
    for lines in blocks:
        heading = _HEADING_RE.match(lines[0])
        if len(lines) == 1 and heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif lines == ["---"]:
            out.append("<hr>")
        elif all(_OL_RE.match(line) for line in lines):
            first = int(_OL_RE.match(lines[0]).group(1))
            start = f' start="{first}"' if first != 1 else ""
            items = "".join(f"<li>{_inline(_OL_RE.match(line).group(2))}</li>" for line in lines)
            out.append(f"<ol{start}>{items}</ol>")
        elif all(line.startswith("- ") for line in lines):
            out.append("<ul>" + "".join(f"<li>{_inline(line[2:])}</li>" for line in lines) + "</ul>")
        else:
            out.append("<p>" + "<br>\n".join(_inline(line) for line in lines) + "</p>")
    return "\n".join(out) + "\n"


# --- страницы ----------------------------------------------------------------------------------------------------

class Site:
    """Сборщик страниц: один каталог, адреса и общий шаблон."""

    def __init__(self, catalog: Catalog, version: str):
        self.catalog = catalog
        self.version = version
        self.base = SITE_URL.rstrip("/") + "/"
        self.base_path = urlsplit(self.base).path
        # Страницы, у которых есть версия без языка в корне сайта (на английском): главная и страницы кодов.
        self.root_pages = {"index.html", *(f"errors/{code}.html" for code in catalog.codes())}

    # Адрес файла сайта → канонический адрес без `.html` (`index.html` → папка).
    def url(self, path: str) -> str:
        if path == "index.html" or path.endswith("/index.html"):
            return self.base + path[: -len("index.html")]
        return self.base + path.removesuffix(".html")

    def ns_title(self, ns: str, lang: str) -> str:
        title = self.catalog.namespaces.get(ns, {}).get("title", ns)
        if lang == "ru" or title.startswith("HomenS.AI"):
            return title
        return SITE[lang]["common"] if ns == "COMMON" else ns

    def area_caption(self, ns: str, area: str, lang: str) -> str:
        # Подписи областей в namespaces.json есть только по-русски (как в справочнике errors.<lang>.md).
        caption = self.catalog.namespaces.get(ns, {}).get("areas", {}).get(area, "") if lang == "ru" else ""
        return f"{ns}-{area}" + (f" — {caption}" if caption else "")

    def entries(self, ns: str) -> list[Entry]:
        return [entry for entry in self.catalog if entry.namespace == ns]

    def page(self, path: str, lang: str, *, title: str, body: str, description: str, lang_path: str | None,
             crumbs: list[tuple[str, str | None]] | None = None, home_search: bool = False,
             alternates: bool = True, absolute: bool = False) -> str:
        """Общий шаблон. `path` — файл сайта; `lang_path` — путь внутри языка для переключателя (None — нет)."""
        up = self.base_path if absolute else "../" * path.count("/")
        site = SITE[lang]
        home = f"{up}{lang}/index.html" if path.startswith(f"{lang}/") else f"{up}index.html"
        if absolute:
            home = up
        head = [
            f"<!-- {AUTHOR} -->",
            "<!doctype html>",
            f'<html lang="{lang}">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">',
            '<meta name="referrer" content="no-referrer">',
            '<meta name="color-scheme" content="light dark">',
            f"<title>{esc(title)}</title>",
            f'<meta name="description" content="{esc(description)}">',
            '<meta name="author" content="Serhii Khomenko">',
        ]
        if not absolute:
            head.append(f'<link rel="canonical" href="{esc(self.url(path))}">')
        if alternates and lang_path is not None:
            for other in LANGS:
                head.append(f'<link rel="alternate" hreflang="{other}" href="{esc(self.url(f"{other}/{lang_path}"))}">')
            default = lang_path if lang_path in self.root_pages else f"{DEFAULT_LANG}/{lang_path}"
            head.append(f'<link rel="alternate" hreflang="x-default" href="{esc(self.url(default))}">')
        head += [
            f'<link rel="icon" href="{up}assets/favicon.svg" type="image/svg+xml">',
            f'<link rel="stylesheet" href="{up}assets/site.css">',
            f'<script src="{up}assets/theme.js"></script>',
            f'<script src="{up}assets/site.js" defer></script>',
            "</head>",
        ]
        body_attr = f' data-notfound-base="{esc(self.base_path)}"' if absolute else ""
        top = [f"<body{body_attr}>", f'<a class="skip" href="#main">{esc(site["skip"])}</a>',
               '<header class="top"><div class="wrap">',
               f'<a class="brand" href="{home}">HomenS.AI <span>Error-database</span></a>']
        if not home_search:
            top += [f'<form class="mini-search" role="search" action="{home}" method="get">',
                    f'<label class="vh" for="top-q">{esc(site["search"])}</label>',
                    f'<input id="top-q" name="q" type="search" placeholder="{esc(site["placeholder"])}">',
                    f'<button type="submit">{esc(site["find"])}</button>', "</form>"]
        if lang_path is not None:
            top.append(f'<nav class="langs" aria-label="{esc(site["language"])}"><ul>')
            for other in LANGS:
                name = LANG_NAMES[other]
                if other == lang:
                    top.append(f'<li><span aria-current="page" lang="{other}" title="{esc(name)}">'
                               f'{other.upper()}</span></li>')
                else:
                    top.append(f'<li><a href="{up}{other}/{lang_path}" hreflang="{other}" lang="{other}" '
                               f'title="{esc(name)}">{other.upper()}</a></li>')
            top.append("</ul></nav>")
        top += [f'<button type="button" id="theme" class="theme" hidden data-label="{esc(site["theme"])}" '
                f'data-auto="{esc(site["auto"])}" data-light="{esc(site["light"])}" '
                f'data-dark="{esc(site["dark"])}">{esc(site["theme"])}</button>', "</div></header>"]
        main = ['<main id="main" class="wrap" tabindex="-1">']
        if crumbs:
            main.append(f'<nav class="crumbs" aria-label="{esc(site["breadcrumbs"])}"><ol>')
            for label, href in crumbs:
                if href is None:
                    main.append(f'<li><span aria-current="page">{label}</span></li>')
                else:
                    main.append(f'<li><a href="{href}">{label}</a></li>')
            main.append("</ol></nav>")
        main += [body.rstrip("\n"), "</main>"]
        foot = [
            '<footer class="wrap foot">',
            f'<p>{esc(site["data"])}: <a href="{up}errors.json">errors.json</a> · '
            f'<a href="{up}llms.txt">llms.txt</a> · <a href="{up}errors.{lang}.md">errors.{lang}.md</a> · '
            f'{esc(site["source"])}: <a href="https://github.com/{DATABASE}">github.com/{DATABASE}</a> · '
            f'{esc(LABELS[lang]["version"])} {esc(self.version)}</p>',
            '<p>HomenS.AI Error-database · © 2026 Serhii Khomenko · '
            '<a href="https://homensai.com/">homensai.com</a> · '
            '<a href="https://github.com/HomenSAI">github.com/HomenSAI</a></p>',
            "</footer>",
            "</body>",
            "</html>",
        ]
        return "\n".join(head + top + main + foot) + "\n"

    def legacy(self, entry: Entry, lang: str) -> str:
        if not (self.catalog.show_legacy_codes and entry.aliases):
            return ""
        label = LABELS[lang]["legacy_one" if len(entry.aliases) == 1 else "legacy_many"]
        return f' <span class="legacy">({esc(label)}: {esc(", ".join(entry.aliases))})</span>'

    def code_item(self, entry: Entry, lang: str, href: str) -> str:
        level = LEVELS[lang][entry.level]
        return (f'<li><a href="{href}"><code>{entry.code}</code> — {esc(entry.title[lang])}</a> '
                f'<span class="badge level-{entry.level}">{esc(level)}</span>{self.legacy(entry, lang)}</li>')

    # --- виды страниц --------------------------------------------------------------------------------------------

    def home(self, lang: str, root: bool) -> str:
        site = SITE[lang]
        path = "index.html" if root else f"{lang}/index.html"
        lang_dir = f"{lang}/" if root else ""  # от страницы к папке языка
        index = "search.en.json" if root else f"../search.{lang}.json"
        labels = {k: site[k] for k in ("found", "first", "none", "failed")}
        labels |= {"levels": LEVELS[lang], "legacy_one": LABELS[lang]["legacy_one"],
                   "legacy_many": LABELS[lang]["legacy_many"]}
        body = [
            f"<h1>{esc(site['site'])}</h1>",
            f'<p class="intro">{esc(site["intro"])}</p>',
            f'<form id="search" class="search" role="search" method="get" action="" data-index="{index}" '
            f'data-pages="errors/" data-limit="{SEARCH_LIMIT}" '
            f"data-labels=\"{esc(json.dumps(labels, ensure_ascii=False, sort_keys=True))}\">",
            f'<label for="q">{esc(site["search"])}</label>',
            f'<input id="q" name="q" type="search" autocomplete="off" spellcheck="false" '
            f'placeholder="{esc(site["placeholder"])}">',
            f'<button type="submit">{esc(site["find"])}</button>',
            "</form>",
            f'<noscript><p>{esc(site["noscript"])}</p></noscript>',
            '<p id="search-status" class="status" role="status" aria-live="polite"></p>',
            '<ul id="search-results" class="codes"></ul>',
            f'<h2 id="namespaces">{esc(site["namespaces"])}</h2>',
            '<ul class="ns-list">',
        ]
        for ns in self.catalog.namespaces:
            entries = self.entries(ns)
            count = site["codes"].format(n=len(entries))
            areas = sorted({e.area for e in entries})
            body.append(f'<li><h3><a href="{lang_dir}ns/{ns}.html">{ns}</a> — {esc(self.ns_title(ns, lang))}</h3>')
            body.append(f'<span class="count">{esc(count)}</span>')
            if areas:
                body.append('<ul class="areas">' + "".join(
                    f'<li><a href="{lang_dir}ns/{ns}.html#{ns}-{area}">{ns}-{area}</a></li>' for area in areas)
                    + "</ul>")
            body.append("</li>")
        body.append("</ul>")
        return self.page(path, lang, title=f"{site['site']} — {LABELS[lang]['reference']}",
                         description=site["intro"], lang_path="index.html", body="\n".join(body),
                         home_search=True)

    def namespace(self, ns: str, lang: str) -> str:
        site = SITE[lang]
        path = f"{lang}/ns/{ns}.html"
        entries = self.entries(ns)
        title = f"{ns} — {self.ns_title(ns, lang)}"
        body = [f"<h1>{esc(title)}</h1>", f'<p class="count">{esc(site["codes"].format(n=len(entries)))}</p>']
        if not entries:
            body.append(f"<p>{esc(site['empty'])}</p>")
        for area in sorted({e.area for e in entries}):
            body.append(f'<h2 id="{ns}-{area}">{esc(self.area_caption(ns, area, lang))}</h2>')
            body.append('<ul class="codes">')
            body += [self.code_item(e, lang, f"../errors/{e.code}.html") for e in entries if e.area == area]
            body.append("</ul>")
        crumbs = [(esc(site["home"]), "../index.html"), (esc(ns), None)]
        return self.page(path, lang, title=f"{title} · {site['site']}", description=title, crumbs=crumbs,
                         lang_path=f"ns/{ns}.html", body="\n".join(body))

    def code(self, entry: Entry, lang: str, root: bool) -> str:
        site = SITE[lang]
        path = f"errors/{entry.code}.html" if root else f"{lang}/errors/{entry.code}.html"
        lang_dir = f"../{lang}/" if root else "../"  # от страницы кода к папке языка
        up = "../" * path.count("/")  # к корню сайта (файлы выпуска)
        article = markdown(self.catalog.help_page(entry.code, lang, link_suffix=".html"))
        problem = json.dumps(self.catalog.to_problem(entry.code, lang), ensure_ascii=False, indent=2)
        body = [
            f'<article class="entry" data-level="{entry.level}">',
            article.rstrip("\n"),
            "</article>",
            '<section class="dev" aria-labelledby="dev">',
            f'<h2 id="dev">{esc(site["developers"])}</h2>',
            "<dl>",
            f'<dt>{esc(site["type"])}</dt><dd><code>{esc(self.catalog.help_url(entry.code))}</code></dd>',
            f'<dt>{esc(site["key"])}</dt><dd><code>{esc(entry.key)}</code></dd>',
            f'<dt>JSON</dt><dd><a href="{up}errors.{entry.namespace}.json">errors.{entry.namespace}.json'
            f'</a> · <a href="{up}help/{lang}/{entry.code}.md">help/{lang}/{entry.code}.md</a></dd>',
            "</dl>",
            f'<h3>{esc(site["problem"])}</h3>',
            f"<pre><code>{html.escape(problem, quote=False)}</code></pre>",
            "</section>",
        ]
        crumbs = [(esc(site["home"]), f"{lang_dir}index.html"),
                  (esc(entry.namespace), f"{lang_dir}ns/{entry.namespace}.html"),
                  (esc(f"{entry.namespace}-{entry.area}"), f"{lang_dir}ns/{entry.namespace}.html#{entry.namespace}-"
                                                          f"{entry.area}"),
                  (f"<code>{entry.code}</code>", None)]
        return self.page(path, lang, title=f"{entry.code} — {entry.title[lang]} · {site['site']}",
                         description=f"{entry.title[lang]}. {entry.cause[lang]}", crumbs=crumbs,
                         lang_path=f"errors/{entry.code}.html", body="\n".join(body))

    def not_found(self) -> str:
        lang = DEFAULT_LANG
        body = [f"<h1>{esc(SITE[lang]['notfound'])}</h1>", f"<p>{esc(SITE[lang]['notfound_text'])}</p>", "<ul>"]
        for other in LANGS:
            body.append(f'<li lang="{other}"><a href="{self.base_path}{other}/" hreflang="{other}">'
                        f'{esc(SITE[other]["notfound"])} — {esc(SITE[other]["home"])}</a></li>')
        body.append("</ul>")
        return self.page("404.html", lang, title=f"{SITE[lang]['notfound']} · {SITE[lang]['site']}",
                         description=SITE[lang]["notfound"], body="\n".join(body), lang_path=None,
                         alternates=False, absolute=True)

    def sitemap(self, paths: list[str]) -> str:
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        lines += [f"<url><loc>{esc(self.url(p))}</loc></url>" for p in paths]
        return "\n".join(lines + ["</urlset>"]) + "\n"


def build() -> dict[str, bytes]:
    """Собрать сайт в память: путь в site/ → байты (без SHA256SUMS). Включает все файлы выпуска dist/."""
    files = build_dist.build()
    version = json.loads(files["errors.json"])["version"]
    # Тексты — из того же каталога, что и выпуск; не strict: в примерах подстановки остаются «{имя}».
    catalog = Catalog.load(ROOT, manifest=False, lock=False)
    site = Site(catalog, version)
    pages: dict[str, str] = {"index.html": site.home(DEFAULT_LANG, root=True)}
    for entry in catalog:
        pages[f"errors/{entry.code}.html"] = site.code(entry, DEFAULT_LANG, root=True)
    for lang in LANGS:
        pages[f"{lang}/index.html"] = site.home(lang, root=False)
        for ns in catalog.namespaces:
            pages[f"{lang}/ns/{ns}.html"] = site.namespace(ns, lang)
        for entry in catalog:
            pages[f"{lang}/errors/{entry.code}.html"] = site.code(entry, lang, root=False)
    pages["404.html"] = site.not_found()
    listed = sorted(p for p in pages if p != "404.html")
    pages["sitemap.xml"] = site.sitemap(listed)
    pages["robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: {site.base}sitemap.xml\n"
    for name, data in pages.items():
        if name in files:
            raise SystemExit(f"{name}: файл сайта совпадает с файлом выпуска")
        files[name] = data.encode("utf-8")
    for asset in sorted(ASSETS.iterdir()):
        if asset.is_file():
            files[f"assets/{asset.name}"] = asset.read_bytes().replace(b"\r\n", b"\n")
    return dict(sorted(files.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сборка сайта-справочника site/ для GitHub Pages")
    parser.add_argument("--out", type=Path, default=ROOT / "site", help="папка сайта (по умолчанию site/)")
    args = parser.parse_args(argv)
    files = build()
    build_dist.write(args.out, files)
    pages = sum(1 for name in files if name.endswith(".html"))
    print(f"сайт: страниц {pages}, файлов {len(files) + 1} в {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
