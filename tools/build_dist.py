#!/usr/bin/env python3
# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Сборка выпуска `dist/` из исходников базы (ARCHITECTURE.md §6.2). Без внешних зависимостей.

Состав `dist/`:
- `errors.json` — все коды; `errors.<NS>.json` — по пространствам (файл есть у каждого пространства из namespaces.json);
- `errors.<lang>.md` — справочник для людей; `help/<lang>/<код>.md` — страницы помощи;
- `search.<lang>.json` — индекс поиска для сайта; `llms.txt` — вся база одним текстом для нейросети;
- `prompts/<имя>/vN.md` — шаблоны запросов к нейросети (ступень `ai` в escalation);
- `SHA256SUMS` — контрольные суммы всех файлов (`sha256sum -c SHA256SUMS`).

Сборка детерминирована: без дат, порядок по коду, `\\n`, UTF-8 — повторная сборка даёт те же байты.
`--archive` дополнительно пишет воспроизводимый `tar.gz` всей папки (время файлов 0, владелец 0).
`--check-tag vX.Y.Z` — выход 1, если тег не совпадает с версией из CHANGELOG.md (задание выпуска в CI).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from homensai_errors.catalog import DATABASE, FORMAT, SITE_URL, Catalog  # noqa: E402
from homensai_errors._texts import LABELS, LANGS  # noqa: E402

import validate  # noqa: E402

_NOTES_RE = re.compile(r"^## (\d+\.\d+\.\d+)[^\n]*\n(.*?)(?=^## |\Z)", re.M | re.S)


def _json(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _payload(catalog: Catalog, version: str, namespaces: list[str]) -> dict:
    return {
        "format": FORMAT,
        "database": DATABASE,
        "version": version,
        "languages": list(LANGS),
        "namespaces": {ns: catalog.namespaces[ns] for ns in namespaces},
        "codes": [entry.as_dict() for entry in catalog if entry.namespace in namespaces],
    }


def _reference(catalog: Catalog, version: str, lang: str) -> str:
    labels = LABELS[lang]
    lines = [f"# {labels['reference']} — {labels['version']} {version}", ""]
    for ns, info in catalog.namespaces.items():
        entries = [e for e in catalog if e.namespace == ns]
        if not entries:
            continue
        lines += [f"## {ns} — {info.get('title', ns)}", ""]
        for area in sorted({e.area for e in entries}):
            caption = info.get("areas", {}).get(area, "") if lang == "ru" else ""
            lines += [f"### {ns}-{area}" + (f" — {caption}" if caption else ""), ""]
            for entry in (e for e in entries if e.area == area):
                lines.append(catalog.help_page(entry.code, lang, heading=4))
    text = "\n".join(lines)
    # Ссылки на связанные коды в справочнике ведут на страницы помощи рядом с ним.
    return re.sub(r"\]\(([A-Z][A-Z0-9]{1,9}-[A-Z0-9]{2,8}-[0-9]{3})\.md\)", rf"](help/{lang}/\1.md)", text)


def _llms(catalog: Catalog, version: str) -> str:
    lines = [
        f"# HomenS.AI Error-database {version}",
        "",
        "> Единая база кодов ошибок экосистемы HomenSAI (Rent, JobPilot Pro, Core, Auto VPN, SECURITY-MODULE). "
        "Unified error-code database of the HomenSAI ecosystem.",
        "",
        "Код `NS-AREA-NNN` никогда не переиспользуется; `key` — устойчивое машинное имя; `aliases` — прежние коды "
        "продуктов. Для каждого кода: заголовок «что случилось» и шаги «что делать» на RU/UK/EN/DE. "
        "Code format NS-AREA-NNN, never reused; key is a stable machine name; aliases are former product codes; "
        "each code lists title and steps in ru/uk/en/de.",
        "",
        f"- Справочник / reference: {SITE_URL}",
        f"- Исходники / source: https://github.com/{DATABASE}",
        "",
    ]
    for ns, info in catalog.namespaces.items():
        entries = [e for e in catalog if e.namespace == ns]
        if not entries:
            continue
        lines += [f"## {ns} — {info.get('title', ns)}", ""]
        for entry in entries:
            meta = [f"level: {entry.level}", f"audience: {entry.audience}",
                    f"retryable: {'true' if entry.retryable else 'false'}"]
            if entry.aliases:
                meta.append("aliases: " + ", ".join(entry.aliases))
            if entry.http_status:
                meta.append(f"http_status: {entry.http_status}")
            if entry.deprecated:
                meta.append(f"deprecated: {entry.deprecated}" + (f" → {entry.replaced_by}" if entry.replaced_by else ""))
            lines += [f"### {entry.code} {entry.key}", " · ".join(meta)]
            for lang in LANGS:
                action = " ".join(entry.action[lang].splitlines())
                lines.append(f"- {lang}: {entry.title[lang]} — {action}")
            lines.append("")
    return "\n".join(lines)


def build(version: str | None = None) -> dict[str, bytes]:
    """Собрать файлы выпуска в память: путь в dist → байты (без SHA256SUMS)."""
    errors = validate.validate(ROOT)
    if errors:
        raise SystemExit("база не прошла tools/validate.py:\n" + "\n".join(errors[:20]))
    catalog = Catalog.load(ROOT, manifest=False, lock=False, strict=True)
    version = version or catalog.version
    if not version:
        raise SystemExit("нет версии: передайте --version или добавьте заголовок «## X.Y.Z» в CHANGELOG.md")
    namespaces = list(catalog.namespaces)
    files: dict[str, bytes] = {"errors.json": _json(_payload(catalog, version, namespaces))}
    for ns in namespaces:
        files[f"errors.{ns}.json"] = _json(_payload(catalog, version, [ns]))
    for lang in LANGS:
        files[f"errors.{lang}.md"] = _reference(catalog, version, lang).encode("utf-8")
        for entry in catalog:
            files[f"help/{lang}/{entry.code}.md"] = catalog.help_page(entry.code, lang).encode("utf-8")
        index = {"format": FORMAT, "version": version, "lang": lang,
                 "docs": [dict(catalog.search_doc(entry, lang), help=f"help/{lang}/{entry.code}.md")
                          for entry in catalog]}
        files[f"search.{lang}.json"] = _json(index)
    files["llms.txt"] = _llms(catalog, version).encode("utf-8")
    for prompt in sorted((ROOT / "prompts").glob("*/*.md")):
        files[f"prompts/{prompt.relative_to(ROOT / 'prompts').as_posix()}"] = prompt.read_bytes().replace(b"\r\n", b"\n")
    return dict(sorted(files.items()))


def sha256sums(files: dict[str, bytes]) -> bytes:
    return "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())).encode()


def write(out: Path, files: dict[str, bytes]) -> None:
    """Записать выпуск в чистую папку; чужую непустую папку (без SHA256SUMS) не удаляет."""
    if out.exists():
        if any(out.iterdir()) and not (out / "SHA256SUMS").is_file():
            raise SystemExit(f"{out}: папка не пуста и не похожа на выпуск — удалите её вручную")
        shutil.rmtree(out)
    for name, data in files.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (out / "SHA256SUMS").write_bytes(sha256sums(files))


def archive(path: Path, files: dict[str, bytes], prefix: str) -> None:
    """Воспроизводимый tar.gz: порядок по имени, время 0, владелец 0, права 0644/0755."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        all_files = dict(files, SHA256SUMS=sha256sums(files))
        dirs = sorted({str(Path(name).parent) for name in all_files} - {"."})
        dirs = sorted({str(p) for d in dirs for p in [Path(d), *Path(d).parents] if str(p) != "."})
        for name in [prefix, *(f"{prefix}/{d}" for d in dirs)]:
            info = tarfile.TarInfo(name)
            info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, 0
            tar.addfile(info)
        for name, data in sorted(all_files.items()):
            info = tarfile.TarInfo(f"{prefix}/{name}")
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            tar.addfile(info, io.BytesIO(data))
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        gz.write(buffer.getvalue())


def release_notes(version: str) -> str:
    """Раздел CHANGELOG.md этой версии — текст выпуска на GitHub."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    for match in _NOTES_RE.finditer(text):
        if match.group(1) == version:
            return match.group(2).strip() + "\n"
    return f"Выпуск {version}.\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сборка выпуска dist/ базы ошибок")
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="папка выпуска (по умолчанию dist/)")
    parser.add_argument("--version", help="версия выпуска (по умолчанию — из CHANGELOG.md)")
    parser.add_argument("--check-tag", help="тег vX.Y.Z, который должен совпасть с версией")
    parser.add_argument("--archive", type=Path, help="записать ещё и воспроизводимый tar.gz")
    parser.add_argument("--notes", type=Path, help="записать текст выпуска из CHANGELOG.md")
    args = parser.parse_args(argv)
    files = build(args.version)
    version = json.loads(files["errors.json"])["version"]
    if args.check_tag and args.check_tag != f"v{version}":
        print(f"тег {args.check_tag} не совпадает с версией базы {version} (CHANGELOG.md)", file=sys.stderr)
        return 1
    write(args.out, files)
    if args.archive:
        archive(args.archive, files, f"homensai-errors-{version}")
    if args.notes:
        args.notes.write_text(release_notes(version), encoding="utf-8", newline="\n")
    print(f"выпуск {version}: файлов {len(files) + 1} в {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
