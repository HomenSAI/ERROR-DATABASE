# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/
"""Каждый файл codes/*/*.json проходит JSON-схему schema/error-file.schema.json (ревью 14.11.2026: validate.py проверяет
не всё — http_status, tags, examples, prompt, channel; схема — единственный полный договор формата)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "error-file.schema.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", sorted((ROOT / "codes").glob("*/*.json")), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_code_file_matches_schema(path: Path) -> None:
    jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), SCHEMA)


def test_schema_rejects_bad_entry() -> None:
    bad = {"namespace": "RENT", "area": "DR", "codes": [{"code": "RENT-DR-001", "http_status": 200}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)
