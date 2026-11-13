<!-- HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI -->
# CHANGELOG

## 1.1.0 — не выпущено
- **RENT: перенесён справочник кодов HomenS.AI Rent** (решение 288, пункт реестра ERR.import-rent): 232 кода, прежний код Rent — в `aliases` (переходный период §12).
  Области: ACL 2, AUTH 40, BILL 5, BOT 6, DB 16, DR 54, EXP 3, FILE 6, FORM 29, FX 2, IMP 2, INT 10, LOG 2, PAY 7, PDF 2, PIN 9, RECOV 8, SCHED 1, SECW 7, SET 14, TRAIN 2, WEB 6. Новые области записаны в `namespaces.json`.
- Тексты RU/UK — из справочника Rent; «почему» для 207 кодов, где его не было, и переводы EN/DE подготовлены моделью (NanoGPT, DeepSeek V4.1 flash), проверены `tools/validate.py` и ревью (GLM-5.3).
- Технические подробности справочника Rent (класс исключения, текст SQLite) не переносятся (§9).
- **Библиотека Python `homensai_errors`** (`src/homensai_errors/`, пункт реестра ERR.library, §7.2): `Catalog.load` (исходники или выпуск, манифест `errors.manifest.json`, сверка SHA-256 по `errors.lock`), поиск по `code`/`key`/`aliases`, `render` с прежними кодами (§12), `to_problem` (RFC 9457), `help_page` с запасным языком, `search`; `AppError` — только коды из каталога; константы `Errors`/`CODES` (`tools/gen_constants.py`, Python и TypeScript). Тесты `tests/` (pytest, без сети).
- **Сборка выпуска** `tools/build_dist.py` (пункт реестра ERR.dist-build, §6.2): `errors.json`, `errors.<NS>.json`, `errors.<lang>.md`, `help/<lang>/<код>.md`, `search.<lang>.json`, `llms.txt`, `prompts/`, `SHA256SUMS`; детерминированно. `dist/` — в `.gitignore`; задание `release.yml` при теге `v*` на self-hosted runner владельца загружает выпуск в GitHub Release.
- Архитектура 1.3: `type` ответа RFC 9457 — адрес кода на сайте-справочнике (GitHub Pages, решение 321), формат `errors.lock`, режимы `strict`, состав выпуска.
- Кодов не добавлено и не изменено.

## 1.0.0
- Архитектура 1.0–1.2, схема, проверка, примеры `COMMON-SYS-001` и `RENT-DR-001`.
