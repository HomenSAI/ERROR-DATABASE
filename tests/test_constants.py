# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Константы кодов для Python и TypeScript (ARCHITECTURE.md §11.2): актуальность codes.py, вид, фильтр по манифесту."""

from __future__ import annotations

import json

import gen_constants
from conftest import ROOT
from homensai_errors.constants import python_module, typescript_module


def test_committed_constants_are_current(catalog):
    assert (ROOT / "src" / "homensai_errors" / "codes.py").read_text("utf-8") == python_module(catalog)
    assert gen_constants.main(["--check"]) == 0


def test_generated_constants_compile_and_ts_shape(tmp_path, catalog):
    py, ts = tmp_path / "codes.py", tmp_path / "codes.ts"
    assert gen_constants.main(["--py", str(py), "--ts", str(ts)]) == 0
    namespace: dict = {}
    exec(compile(py.read_text("utf-8"), str(py), "exec"), namespace)
    assert namespace["Errors"].RENT_DR_001 == "RENT-DR-001" and len(namespace["CODES"]) == len(catalog)
    text = ts.read_text("utf-8")
    assert '  RENT_DR_001: "RENT-DR-001", // BACKUP_PASSWORD_CHECK_OVERDUE' in text
    assert "export type ErrorCode" in text and text == typescript_module(catalog)
    assert gen_constants.main(["--py", str(py), "--ts", str(ts), "--check"]) == 0
    ts.write_text("stale")
    assert gen_constants.main(["--py", str(py), "--ts", str(ts), "--check"]) == 1


def test_constants_for_product_manifest(tmp_path):
    manifest = tmp_path / "errors.manifest.json"
    manifest.write_text(json.dumps({"namespaces": ["SEC"]}), "utf-8")
    py = tmp_path / "codes.py"
    assert gen_constants.main(["--manifest", str(manifest), "--py", str(py)]) == 0
    text = py.read_text("utf-8")
    assert "COMMON_SYS_001: Final" in text and "RENT_DR_001: Final" not in text
