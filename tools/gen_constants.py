#!/usr/bin/env python3
# HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI
"""Генерация констант кодов ошибок для Python и TypeScript (ARCHITECTURE.md §11.2).

Без аргументов — пересобрать `src/homensai_errors/codes.py` по всей базе (после добавления кода).
Для продукта: `--source vendor/errors --manifest errors.manifest.json --py app/errors_codes.py --ts web/codes.ts`.
`--check` — ничего не писать, выход 1, если файлы устарели (для CI). Выход 0 — всё в порядке.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from homensai_errors.catalog import Catalog  # noqa: E402
from homensai_errors.constants import python_module, typescript_module  # noqa: E402

DEFAULT_PY = ROOT / "src" / "homensai_errors" / "codes.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=ROOT, help="исходники базы или папка выпуска (vendor/errors)")
    parser.add_argument("--manifest", type=Path, help="errors.manifest.json продукта (пространства)")
    parser.add_argument("--py", type=Path, help="куда записать Python-модуль")
    parser.add_argument("--ts", type=Path, help="куда записать TypeScript-модуль")
    parser.add_argument("--check", action="store_true", help="только сверить, выход 1 при расхождении")
    args = parser.parse_args(argv)
    py = args.py or (DEFAULT_PY if args.ts is None else None)
    catalog = Catalog.load(args.source, manifest=args.manifest if args.manifest else False, lock=False, strict=True)
    outputs = [(path, render(catalog)) for path, render in ((py, python_module), (args.ts, typescript_module)) if path]
    stale = 0
    for path, text in outputs:
        data = text.encode("utf-8")
        current = path.read_bytes() if path.is_file() else None
        if current == data:
            continue
        if args.check:
            print(f"{path}: устарел — запустите python tools/gen_constants.py", file=sys.stderr)
            stale += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"записан {path}")
    print(f"кодов: {len(catalog)}, файлов: {len(outputs)}, устаревших: {stale}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
