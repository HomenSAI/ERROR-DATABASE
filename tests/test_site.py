# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Сайт-справочник site/ (ARCHITECTURE.md §6.4): страницы всех кодов на всех языках, рабочие ссылки, адрес `type`
RFC 9457, детерминизм, только свои скрипты и стили, контраст темы; поиск на JS совпадает с `Catalog.search`
(через node, если он установлен). Сеть не нужна."""

from __future__ import annotations

import json
import posixpath
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest

import build_dist
import build_site
from conftest import ROOT
from homensai_errors import Catalog
from homensai_errors.catalog import SITE_URL

LANGS = ("ru", "uk", "en", "de")
BASE = SITE_URL.rstrip("/") + "/"
BASE_PATH = urlsplit(BASE).path
EXTERNAL_OK = ("https://github.com/HomenSAI", "https://homensai.com/")


class _Page(HTMLParser):
    """Ссылки, id, скрипты и стили одной страницы."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.ids: set[str] = set()
        self.lang = None
        self.h1 = 0
        self.canonical = None
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            assert a["id"] not in self.ids, f"повтор id {a['id']}"
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self._in_title = True
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a["href"]
        for name in ("href", "src", "action"):
            if a.get(name) is not None:
                self.links.append((tag, a[name]))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


@pytest.fixture(scope="module")
def site():
    files = build_site.build()
    pages = {}
    for name, data in files.items():
        if name.endswith(".html"):
            parser = _Page()
            parser.feed(data.decode("utf-8"))
            pages[name] = parser
    return files, pages


def _target(files, page: str, link: str) -> tuple[str, str] | None:
    """Файл сайта и якорь, на которые ведёт ссылка; None — разрешённая внешняя ссылка."""
    parts = urlsplit(link)
    if parts.scheme in ("http", "https"):
        if link.startswith(EXTERNAL_OK):
            return None
        assert link.startswith(BASE), f"{page}: внешняя ссылка {link}"
        path = link[len(BASE):]
    elif parts.path.startswith("/"):
        assert parts.path.startswith(BASE_PATH), f"{page}: ссылка вне сайта {link}"
        path = parts.path[len(BASE_PATH):]
    else:
        assert not parts.scheme and not parts.netloc, f"{page}: ссылка {link}"
        path = posixpath.normpath(posixpath.join(posixpath.dirname(page), parts.path)) if parts.path else page
        assert not path.startswith(".."), f"{page}: ссылка за пределы сайта {link}"
    path = path.rstrip("/")
    if path in ("", "."):
        path = "index.html"
    elif path not in files and f"{path}/index.html" in files:
        path = f"{path}/index.html"  # папка — её index.html
    elif path not in files and f"{path}.html" in files:
        path = f"{path}.html"  # GitHub Pages отдаёт x.html по адресу x
    return path, parts.fragment


def test_every_code_has_pages(site, catalog):
    files, pages = site
    for code in catalog.codes():
        assert f"errors/{code}.html" in files
        for lang in LANGS:
            assert f"{lang}/errors/{code}.html" in files
    for lang in LANGS:
        assert f"{lang}/index.html" in files and f"search.{lang}.json" in files
        assert {f"{lang}/ns/{ns}.html" for ns in catalog.namespaces} <= set(files)
    assert {"index.html", "404.html", "sitemap.xml", "robots.txt", "llms.txt", "errors.json",
            "assets/site.css", "assets/site.js", "assets/theme.js"} <= set(files)
    # Все файлы выпуска dist/ лежат на сайте под теми же именами.
    assert set(build_dist.build()) <= set(files)
    expected = 1 + 1 + len(catalog) * 5 + len(LANGS) * (1 + len(catalog.namespaces))
    assert len(pages) == expected


def test_code_page_is_rfc9457_type(site, catalog):
    """`type` ответа API (§6.3) — адрес страницы кода на сайте: файл errors/<код>.html, канонический адрес."""
    files, pages = site
    for code in catalog.codes():
        problem_type = catalog.to_problem(code, "en")["type"]
        assert problem_type == f"{BASE}errors/{code}"
        target, _ = _target(files, "index.html", problem_type)
        assert target == f"errors/{code}.html"
        page = pages[target]
        assert page.lang == "en" and page.canonical == problem_type and page.h1 == 1
        assert page.title.startswith(f"{code} — ")
        for lang in LANGS:
            assert pages[f"{lang}/errors/{code}.html"].canonical == catalog.help_url(code, lang)


def test_pages_language_and_texts(site, catalog):
    files, pages = site
    entry = catalog.get("RENT-DR-001")
    for lang in LANGS:
        page = pages[f"{lang}/errors/RENT-DR-001.html"]
        assert page.lang == lang and page.h1 == 1
        text = files[f"{lang}/errors/RENT-DR-001.html"].decode()
        title = entry.title[lang].replace("'", "&#x27;")
        assert f"<h1>RENT-DR-001 — {title}</h1>" in text
        assert "DR-270-OVERDUE" in text  # прежний код в переходный период (§12)
        assert 'aria-current="page"' in text and 'class="skip" href="#main"' in text
    ns = files["ru/ns/RENT.html"].decode()
    assert 'id="RENT-DR"' in ns and "копии и восстановление" in ns
    assert all(f'href="../errors/{code}.html"' in ns for code in catalog.codes() if code.startswith("RENT-"))


def test_all_links_work(site):
    files, pages = site
    checked = 0
    for name, page in pages.items():
        for tag, link in page.links:
            target = _target(files, name, link)
            if target is None:
                continue
            path, fragment = target
            assert path in files, f"{name}: битая ссылка {link} → {path}"
            if fragment and path.endswith(".html"):
                assert fragment in pages[path].ids, f"{name}: нет якоря {link}"
            checked += 1
    assert checked > 10000


def test_only_own_scripts_styles_no_trackers(site):
    files, pages = site
    for name, page in pages.items():
        for tag, link in page.links:
            if tag in ("script", "link") and not link.startswith(("https://homensai.github.io/",)):
                assert not urlsplit(link).scheme, f"{name}: внешний ресурс {link}"
    banned = re.compile(rb"googletagmanager|google-analytics|gtag\(|fonts\.googleapis|cdn\.|@import|url\(http"
                        rb"|<script>|style=", re.I)
    for name, data in files.items():
        if name.endswith((".html", ".css", ".js")):
            assert not banned.search(data), f"{name}: внешний ресурс, трекер или встроенный код"
    assert b"script-src 'self'" in files["index.html"]


def test_rebuild_is_byte_identical(site):
    files, _ = site
    assert build_site.build() == files


def test_markdown_escapes_and_links():
    html = build_site.markdown("# A <b> & `K_1`\n\n1. one {days}\n2. **two**\n\n- [AB-CD-001](AB-CD-001.html) — t\n\n---")
    assert html == ('<h1>A &lt;b&gt; &amp; <code>K_1</code></h1>\n<ol><li>one <var>{days}</var></li>'
                    '<li><strong>two</strong></li></ol>\n<ul><li><a href="AB-CD-001.html">AB-CD-001</a> — t</li></ul>\n'
                    "<hr>\n")
    # Ссылка не на код — остаётся текстом.
    assert "<a " not in build_site.markdown("[x](javascript:alert(1))")


def _luminance(color: str) -> float:
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_theme_contrast_wcag_aa():
    css = (ROOT / "tools" / "site" / "site.css").read_text("utf-8")
    blocks = re.findall(r"(:root[^{]*)\{([^}]*)\}", css)
    themes = [dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-f]{6})", body)) for _, body in blocks]
    themes = [t for t in themes if t]
    assert len(themes) == 3 and themes[1] == themes[2]  # тёмная: по системе и по выбору — одинаковые
    for theme in themes:
        for fg, bg in [("fg", "bg"), ("fg", "surface"), ("muted", "bg"), ("muted", "surface"), ("link", "bg"),
                       ("link", "surface"), ("info-fg", "info-bg"), ("warn-fg", "warn-bg"),
                       ("error-fg", "error-bg"), ("alarm-fg", "alarm-bg")]:
            assert _contrast(theme[fg], theme[bg]) >= 4.5, (fg, bg, theme[fg], theme[bg])
        assert _contrast(theme["focus"], theme["bg"]) >= 3 and _contrast(theme["focus"], theme["surface"]) >= 3


def test_cli_writes_site(tmp_path):
    out = tmp_path / "site"
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "build_site.py"), "--out", str(out)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert (out / "errors" / "RENT-DR-001.html").is_file() and (out / "SHA256SUMS").is_file()


QUERIES = ["пароль копий", "пароля", "RENT-DR", "rent-dr-001", "DR-270-OVERDUE", "backup password",
           "BACKUP_PASSWORD_CHECK_OVERDUE", "Passwort", "Größe", "пам'ять", "ключ відновлення", "", "   ",
           "nothing-like-this", "RENT", "копии", "network", "Netzwerk", "VPN-ADV", "{days}", "ё"]


@pytest.mark.skipif(shutil.which("node") is None, reason="нет node — поиск на JS не проверить")
def test_js_search_matches_python(tmp_path):
    """Поиск сайта (tools/site/site.js) даёт те же коды и баллы, что Catalog.search, на всех языках."""
    catalog = Catalog.load(ROOT, manifest=False, lock=False)
    files = build_dist.build()
    queries = list(QUERIES)
    for lang in LANGS:
        for entry in list(catalog)[::17]:
            queries.append(entry.title[lang])
            queries.append(" ".join(entry.action[lang].split()[1:3]))
    script = tmp_path / "check.js"
    script.write_text(
        "const s = require(process.argv[2]);\n"
        "const fs = require('fs');\n"
        "const queries = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));\n"
        "const out = {};\n"
        "for (const lang of ['ru', 'uk', 'en', 'de']) {\n"
        "  const p = s.prepare(JSON.parse(fs.readFileSync(process.argv[4] + '/search.' + lang + '.json', 'utf8')));\n"
        "  out[lang] = queries.map(q => s.search(p, q, 1000));\n"
        "}\n"
        "process.stdout.write(JSON.stringify(out));\n", "utf-8")
    (tmp_path / "queries.json").write_text(json.dumps(queries, ensure_ascii=False), "utf-8")
    dist = tmp_path / "dist"
    build_dist.write(dist, files)
    run = subprocess.run(["node", str(script), str(ROOT / "tools" / "site" / "site.js"),
                          str(tmp_path / "queries.json"), str(dist)], capture_output=True, text=True,
                         encoding="utf-8")
    assert run.returncode == 0, run.stderr
    got = json.loads(run.stdout)
    for lang in LANGS:
        for query, hits in zip(queries, got[lang]):
            expected = [[h.code, h.score] for h in catalog.search(query, lang, limit=1000)]
            assert hits == expected, (lang, query)
