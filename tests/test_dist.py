# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Сборка выпуска dist/ (ARCHITECTURE.md §6.2): состав, детерминизм, контрольные суммы; загрузка выпуска с errors.lock (§7.1)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

import build_dist
from conftest import ROOT
from homensai_errors import Catalog, CatalogError, IntegrityError, make_lock


def _tree(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("dist")
    files = build_dist.build()
    build_dist.write(base / "a", files)
    build_dist.archive(base / "a.tar.gz", files, "homensai-errors-x")
    return base, files


def test_dist_contents(built, catalog):
    base, files = built
    tree = _tree(base / "a")
    namespaces = json.loads((ROOT / "namespaces.json").read_text("utf-8"))
    expected = {"errors.json", "llms.txt", "SHA256SUMS", "prompts/analyze-error/v1.md"}
    expected |= {f"errors.{ns}.json" for ns in namespaces}
    for lang in ("ru", "uk", "en", "de"):
        expected |= {f"errors.{lang}.md", f"search.{lang}.json"}
        expected |= {f"help/{lang}/{code}.md" for code in catalog.codes()}
    assert set(tree) == expected
    full = json.loads(tree["errors.json"])
    assert full["version"] == catalog.version and full["format"] == 1
    assert [e["code"] for e in full["codes"]] == catalog.codes()
    per_ns = [e["code"] for ns in namespaces for e in json.loads(tree[f"errors.{ns}.json"])["codes"]]
    assert sorted(per_ns) == catalog.codes()
    index = json.loads(tree["search.uk.json"])
    assert len(index["docs"]) == len(catalog) and index["docs"][0]["help"].startswith("help/uk/")
    llms = tree["llms.txt"].decode()
    assert llms.startswith("# HomenS.AI Error-database ") and "### RENT-DR-001 BACKUP_PASSWORD_CHECK_OVERDUE" in llms
    assert "- de: Backup-Passwort länger nicht geprüft — 1. Öffnen Sie" in llms
    ref = tree["errors.ru.md"].decode()
    assert "#### RENT-DR-001 — Пароль копий давно не проверялся" in ref and "### RENT-DR — копии и восстановление" in ref
    assert tree["help/en/RENT-DR-001.md"].decode() == catalog.help_page("RENT-DR-001", "en")
    assert all(b"\r\n" not in data for data in tree.values())


def test_sha256sums_cover_every_file(built):
    base, _ = built
    tree = _tree(base / "a")
    lines = tree.pop("SHA256SUMS").decode().splitlines()
    sums = dict(reversed(line.split("  ", 1)) for line in lines)
    assert sums == {name: hashlib.sha256(data).hexdigest() for name, data in tree.items()}


def test_rebuild_is_byte_identical(built, tmp_path):
    base, files = built
    again = build_dist.build()
    build_dist.write(tmp_path / "b", again)
    build_dist.archive(tmp_path / "b.tar.gz", again, "homensai-errors-x")
    assert _tree(base / "a") == _tree(tmp_path / "b")
    assert (base / "a.tar.gz").read_bytes() == (tmp_path / "b.tar.gz").read_bytes()
    # Повторная запись в ту же папку тоже не меняет байты и не оставляет лишнего.
    (tmp_path / "b" / "stale.txt").write_text("old")
    build_dist.write(tmp_path / "b", again)
    assert _tree(base / "a") == _tree(tmp_path / "b")


def test_archive_contents(built):
    base, files = built
    with tarfile.open(base / "a.tar.gz") as tar:
        members = {m.name: m for m in tar.getmembers()}
        assert all(m.mtime == 0 and m.uid == 0 for m in members.values())
        assert tar.extractfile(members["homensai-errors-x/errors.json"]).read() == files["errors.json"]
        assert "homensai-errors-x/SHA256SUMS" in members


def test_write_refuses_foreign_folder(tmp_path):
    (tmp_path / "keep.txt").write_text("x")
    with pytest.raises(SystemExit):
        build_dist.write(tmp_path, {"errors.json": b"{}"})
    assert (tmp_path / "keep.txt").exists()


def test_cli_check_tag_and_notes(tmp_path, catalog):
    out, notes = tmp_path / "dist", tmp_path / "notes.md"
    run = [sys.executable, str(ROOT / "tools" / "build_dist.py"), "--out", str(out)]
    bad = subprocess.run(run + ["--check-tag", "v0.0.0"], capture_output=True, text=True)
    assert bad.returncode == 1 and not out.exists()
    good = subprocess.run(run + ["--check-tag", f"v{catalog.version}", "--notes", str(notes)], capture_output=True,
                          text=True)
    assert good.returncode == 0, good.stderr
    assert (out / "SHA256SUMS").is_file() and notes.read_text("utf-8").strip()


def _dist(tmp_path: Path) -> Path:
    out = tmp_path / "vendor" / "errors"
    build_dist.write(out, build_dist.build())
    return out


def test_load_from_dist_with_lock(tmp_path, catalog):
    out = _dist(tmp_path)
    full = Catalog.load(out, manifest=False, lock=False)
    assert full.codes() == catalog.codes() and full.version == catalog.version
    assert full.get("RENT-DR-001") == catalog.get("RENT-DR-001")
    manifest = {"version": f"^{catalog.version}", "namespaces": ["RENT", "CORE"], "languages": ["ru", "uk", "en", "de"]}
    lock = make_lock(out, catalog.version, ["errors.COMMON.json", "errors.CORE.json", "errors.RENT.json"])
    (out / "errors.lock").write_text(json.dumps(lock), "utf-8")
    pinned = Catalog.load(out, manifest=manifest, require_lock=True)
    assert set(pinned.namespaces) == {"COMMON", "CORE", "RENT"}
    assert all(code.split("-")[0] in ("COMMON", "RENT") for code in pinned.codes())
    # Подменённый файл — сборка продукта должна остановиться.
    data = (out / "errors.RENT.json").read_bytes()
    (out / "errors.RENT.json").write_bytes(data.replace(b"BACKUP_PASSWORD_CHECK_OVERDUE", b"BACKUP_PASSWORD_CHECK_OVERDUX"))
    with pytest.raises(IntegrityError, match="SHA-256"):
        Catalog.load(out, manifest=manifest)
    (out / "errors.RENT.json").write_bytes(data)
    # Пространство загружено, но не закреплено.
    with pytest.raises(IntegrityError, match="не закреплены"):
        Catalog.load(out, manifest={"namespaces": ["SEC"]})
    (out / "errors.lock").unlink()
    with pytest.raises(IntegrityError, match="нет errors.lock"):
        Catalog.load(out, manifest=manifest, require_lock=True)


def test_dist_version_range_and_missing_namespace(tmp_path, catalog):
    out = _dist(tmp_path)
    with pytest.raises(CatalogError, match="не подходит"):
        Catalog.load(out, manifest={"version": "^9.0.0"}, lock=False)
    (out / "errors.SEC.json").unlink()
    (out / "errors.json").unlink()
    with pytest.raises(CatalogError, match="нет файлов пространств"):
        Catalog.load(out, manifest={"namespaces": ["SEC"]}, lock=False)
