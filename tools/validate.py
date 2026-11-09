#!/usr/bin/env python3
# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/
"""Проверка базы ошибок без внешних зависимостей (ARCHITECTURE.md §8).

Проверяет: формат файлов и обязательные поля, пространства и области из namespaces.json, уникальность code/key/aliases,
все 4 языка, одинаковые подстановки {..} во всех языках и объявленные params, номера без пропусков, ссылки related и
replaced_by, белый список данных для ИИ и разработчика. Выход 0 — всё в порядке, 1 — есть ошибки (список в stderr).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("ru", "uk", "en", "de")
REQUIRED = ("code", "key", "level", "audience", "title", "cause", "action", "escalation", "retryable", "help", "since")
ALLOWED = set(REQUIRED) | {"aliases", "params", "http_status", "related", "deprecated", "replaced_by", "tags", "fixed_in", "examples"}
LEVELS = {"info", "warn", "error", "alarm"}
AUDIENCES = {"user", "admin", "developer"}
STEPS = {"self", "admin", "ai", "developer"}
DATA = {"code", "params", "app_version", "os", "log_excerpt_redacted"}
CODE_RE = re.compile(r"^([A-Z][A-Z0-9]{1,9})-([A-Z0-9]{2,8})-([0-9]{3})$")
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,80}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    namespaces = json.loads((root / "namespaces.json").read_text(encoding="utf-8"))
    seen_codes: dict[str, str] = {}
    seen_names: dict[str, str] = {}
    numbers: dict[tuple[str, str], list[int]] = {}
    refs: list[tuple[str, str]] = []
    for path in sorted((root / "codes").glob("*/*.json")):
        rel = path.relative_to(root).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"{rel}: не JSON ({exc})")
            continue
        ns, area = data.get("namespace"), data.get("area")
        if ns not in namespaces:
            errors.append(f"{rel}: пространство {ns!r} не объявлено в namespaces.json")
            continue
        if area not in namespaces[ns].get("areas", {}):
            errors.append(f"{rel}: область {area!r} не объявлена в namespaces.json для {ns}")
        if path.parent.name != ns or path.stem != area:
            errors.append(f"{rel}: файл должен называться codes/{ns}/{area}.json")
        for entry in data.get("codes", []):
            errors += _entry(rel, ns, area, entry, seen_codes, seen_names, numbers, refs)
    for (ns, area), nums in numbers.items():
        if sorted(nums) != list(range(1, len(nums) + 1)):
            errors.append(f"{ns}-{area}: номера должны идти с 001 без пропусков, сейчас {sorted(nums)}")
    for where, target in refs:
        if target not in seen_codes:
            errors.append(f"{where}: ссылка на несуществующий код {target}")
    return errors


def _entry(rel, ns, area, entry, seen_codes, seen_names, numbers, refs) -> list[str]:
    errors: list[str] = []
    code = entry.get("code", "?")
    where = f"{rel}:{code}"
    for field in REQUIRED:
        if field not in entry:
            errors.append(f"{where}: нет поля {field}")
    for field in entry:
        if field not in ALLOWED:
            errors.append(f"{where}: неизвестное поле {field}")
    match = CODE_RE.match(code)
    if not match or match.group(1) != ns or match.group(2) != area:
        errors.append(f"{where}: код должен иметь вид {ns}-{area}-NNN")
    else:
        numbers.setdefault((ns, area), []).append(int(match.group(3)))
    if code in seen_codes:
        errors.append(f"{where}: код уже есть в {seen_codes[code]}")
    seen_codes[code] = rel
    key = entry.get("key", "")
    if not KEY_RE.match(key):
        errors.append(f"{where}: key должен быть UPPER_SNAKE_CASE")
    for name in [key, *entry.get("aliases", [])]:
        if name in seen_names and seen_names[name] != code:
            errors.append(f"{where}: имя {name} уже занято кодом {seen_names[name]}")
        seen_names[name] = code
    if entry.get("level") not in LEVELS:
        errors.append(f"{where}: level — один из {sorted(LEVELS)}")
    if entry.get("audience") not in AUDIENCES:
        errors.append(f"{where}: audience — один из {sorted(AUDIENCES)}")
    if not isinstance(entry.get("retryable"), bool):
        errors.append(f"{where}: retryable — true или false")
    declared = set(entry.get("params", {}))
    for field in ("title", "cause", "action"):
        texts = entry.get(field)
        if not isinstance(texts, dict) or set(texts) != set(LANGS):
            errors.append(f"{where}: {field} должен быть ровно на языках {', '.join(LANGS)}")
            continue
        sets = {lang: set(PLACEHOLDER_RE.findall(text or "")) for lang, text in texts.items()}
        if any(not texts[lang].strip() for lang in LANGS):
            errors.append(f"{where}: {field} — пустой текст")
        if len({frozenset(s) for s in sets.values()}) > 1:
            errors.append(f"{where}: {field} — разные подстановки в языках {sets}")
        for name in set().union(*sets.values()) - declared:
            errors.append(f"{where}: {field} — подстановка {{{name}}} не объявлена в params")
    steps = entry.get("escalation") or []
    if not steps or steps[0].get("to") != "self":
        errors.append(f"{where}: escalation начинается со ступени self")
    for step in steps:
        if step.get("to") not in STEPS:
            errors.append(f"{where}: escalation.to — один из {sorted(STEPS)}")
        bad = set(step.get("data", [])) - DATA
        if bad:
            errors.append(f"{where}: escalation.data вне белого списка: {sorted(bad)}")
    for field in ("since", "deprecated"):
        if field in entry and not VERSION_RE.match(str(entry[field])):
            errors.append(f"{where}: {field} — версия X.Y.Z")
    for product, version in (entry.get("fixed_in") or {}).items():
        if not VERSION_RE.match(str(version)):
            errors.append(f"{where}: fixed_in.{product} — версия X.Y.Z")
    if "examples" in entry and entry.get("audience") != "developer":
        errors.append(f"{where}: examples — только для audience developer")
    for target in [*entry.get("related", []), *([entry["replaced_by"]] if "replaced_by" in entry else [])]:
        refs.append((where, target))
    return errors


def main() -> int:
    errors = validate()
    for line in errors:
        print(line, file=sys.stderr)
    count = sum(len(json.loads(p.read_text(encoding="utf-8")).get("codes", [])) for p in (ROOT / "codes").glob("*/*.json"))
    print(f"кодов: {count}, ошибок проверки: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
