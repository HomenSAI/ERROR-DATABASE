# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Общие фикстуры тестов библиотеки и сборки. Сеть не нужна: всё из исходников базы и временных папок."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for extra in (ROOT / "src", ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import homensai_errors  # noqa: E402
from homensai_errors import Catalog  # noqa: E402


def entry(code: str, key: str, **extra) -> dict:
    """Вымышленная запись по схеме для маленьких каталогов в тестах."""
    text = {lang: f"{lang}: {code}" for lang in ("ru", "uk", "en", "de")}
    data = {"code": code, "key": key, "level": "error", "audience": "user", "title": dict(text),
            "cause": dict(text), "action": dict(text), "escalation": [{"to": "self"}], "retryable": False,
            "help": f"errors/{code}", "since": "1.0.0"}
    data.update(extra)
    return data


def write_source(root: Path, files: dict[tuple[str, str], list[dict]], namespaces: dict | None = None) -> Path:
    """Мини-база в виде исходников: codes/<NS>/<AREA>.json + namespaces.json."""
    ns_doc = namespaces or {}
    for (ns, area), codes in files.items():
        ns_doc.setdefault(ns, {"title": ns, "areas": {}})["areas"][area] = area
        path = root / "codes" / ns / f"{area}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"namespace": ns, "area": area, "codes": codes}, ensure_ascii=False), "utf-8")
    (root / "namespaces.json").write_text(json.dumps(ns_doc, ensure_ascii=False), "utf-8")
    return root


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return Catalog.load(ROOT, manifest=False, lock=False)


@pytest.fixture(scope="session")
def strict_catalog() -> Catalog:
    return Catalog.load(ROOT, manifest=False, lock=False, strict=True)


@pytest.fixture(autouse=True)
def _reset_default_catalog():
    yield
    homensai_errors.configure(None)
