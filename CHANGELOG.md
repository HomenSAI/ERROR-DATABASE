<!-- HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI -->
# CHANGELOG

## 1.2.0 — не выпущено
Минорная версия, обратно совместимая: буквенные коды, `key` и `aliases` не менялись; в записях и в `namespaces.json` добавлены новые поля.
- **Цифровой код `PPP-AAA-NNN`** у каждой ошибки (253 кода) для удобного поиска: `RENT-FX-003` → `003-012-003` (`ARCHITECTURE.md` §3.1). PPP — номер пространства (`COMMON` 001, `CORE` 002, `RENT` 003, `JP` 004, `VPN` 005, `SEC` 006), AAA — номер области (в порядке перечисления в `namespaces.json`; у `RENT`: `DR` 001 … `FX` 012 … `LOG` 023), NNN — номер из буквенного кода. Номера не меняются и не переиспользуются.
- `namespaces.json`: у пространств поле `number`, рядом с `areas` — `area_numbers` (`areas` не менялось). У записей в `codes/*/*.json` — поле `number` после `code`; схема `schema/error-file.schema.json`: `number` обязательно, шаблон `^[0-9]{3}-[0-9]{3}-[0-9]{3}$`.
- `tools/validate.py`: `number` совпадает с вычисленным из `namespaces.json` и уникален; у каждого пространства и области есть номер из трёх цифр, номера уникальны на своём уровне.
- Библиотека: `Entry.number` (в выпусках до 1.2.0 пуст); `Catalog.get`/`find`/`in` находят запись по цифровому коду — `003-012-003`, `003012003`, `003 012 003`; `search` — по цифровому коду и его началу (`003-012`); `search_doc`, `Rendered.number`, `to_problem` (расширение `number`), `help_page` («Цифровой код: …») и первая строка `render` (`RENT-FX-003 · 003-012-003`) показывают цифровой код рядом с буквенным. Подписи — на 4 языках.
- Выпуск: `number` в `errors*.json`, `search.<lang>.json`, `llms.txt` (и описание формата), справочниках и страницах помощи; в `namespaces` выпуска — `number` и `area_numbers`.
- Сайт: цифровой код на странице ошибки («Цифровой код», «Цифровий код», «Numeric code», «Numerischer Code»), в списках и результатах поиска; строка поиска дополнена «… или цифровому коду»; `tools/site/site.js` ищет по цифровому коду с дефисами, пробелами и без (совпадение с `Catalog.search` проверяет `tests/test_site.py`).
- Архитектура 1.5: §3.1 «Цифровой код», §6.2, §8.
- Тесты `tests/test_numbers.py`; в `tests/test_texts.py` ожидаемые первая строка `render` и ответ `to_problem` дополнены цифровым кодом.
- Документ `docs/CONNECT-PRODUCT.md` «Как подключить продукт к базе ошибок»: правило владельца 15.11.2026 (коды только из базы), буквенный и цифровой код, добавление кода, подключение через `errors.lock`, что показывает интерфейс, тесты продукта; ссылки в `AGENTS.md` и `README.md`.

## 1.1.0 — не выпущено
- **RENT: перенесён справочник кодов HomenS.AI Rent** (решение 288, пункт реестра ERR.import-rent): 232 кода, прежний код Rent — в `aliases` (переходный период §12).
  Области: ACL 2, AUTH 40, BILL 5, BOT 6, DB 16, DR 54, EXP 3, FILE 6, FORM 29, FX 2, IMP 2, INT 10, LOG 2, PAY 7, PDF 2, PIN 9, RECOV 8, SCHED 1, SECW 7, SET 14, TRAIN 2, WEB 6. Новые области записаны в `namespaces.json`.
- **RENT: досверка с Rent 14.11.2026** (пункт реестра ERR.rent-consume): добавлены 6 кодов, появившихся в Rent после переноса — `RENT-FX-003` (одна валюта учёта, решение 263), `RENT-PAY-008` (подключение monobank не найдено), `RENT-DR-055`…`058` (папка копий — ссылка; папка стала ссылкой; копия больше предела чтения; служебные файлы ОС в цепочке). Теперь каждый код справочника Rent (238) есть в базе.
- Тексты RU/UK — из справочника Rent; «почему» для 207 кодов, где его не было, и переводы EN/DE подготовлены моделью (NanoGPT, DeepSeek V4.1 flash), проверены `tools/validate.py` и ревью (GLM-5.3).
- Технические подробности справочника Rent (класс исключения, текст SQLite) не переносятся (§9).
- **Библиотека Python `homensai_errors`** (`src/homensai_errors/`, пункт реестра ERR.library, §7.2): `Catalog.load` (исходники или выпуск, манифест `errors.manifest.json`, сверка SHA-256 по `errors.lock`), поиск по `code`/`key`/`aliases`, `render` с прежними кодами (§12), `to_problem` (RFC 9457), `help_page` с запасным языком, `search`; `AppError` — только коды из каталога; константы `Errors`/`CODES` (`tools/gen_constants.py`, Python и TypeScript). Тесты `tests/` (pytest, без сети).
- **Сборка выпуска** `tools/build_dist.py` (пункт реестра ERR.dist-build, §6.2): `errors.json`, `errors.<NS>.json`, `errors.<lang>.md`, `help/<lang>/<код>.md`, `search.<lang>.json`, `llms.txt`, `prompts/`, `SHA256SUMS`; детерминированно. `dist/` — в `.gitignore`; задание `release.yml` при теге `v*` на self-hosted runner владельца загружает выпуск в GitHub Release.
- **Сайт-справочник на GitHub Pages** (пункт реестра ERR.pages, решения 288 и 321, §6.4): `tools/build_site.py` → `site/` (в `.gitignore`) из того же каталога — главная на 4 языках, страница каждого кода `/errors/<код>` (английский, адрес `type` RFC 9457) и `/<lang>/errors/<код>`, списки по пространствам, поиск на клиенте по `search.<lang>.json` (тот же алгоритм, что `Catalog.search`), светлая и тёмная тема, контраст WCAG AA, без трекеров, CDN и внешних шрифтов; все файлы `dist/` на сайте. Детерминированно; тест `tests/test_site.py`. Публикация — `.github/workflows/pages.yml` (self-hosted runner, `deploy-pages`); владельцу один раз включить Settings → Pages → Source: GitHub Actions.
- Архитектура 1.4: сайт-справочник (§6.4).
- Архитектура 1.3: `type` ответа RFC 9457 — адрес кода на сайте-справочнике (GitHub Pages, решение 321), формат `errors.lock`, режимы `strict`, состав выпуска.
- Кодов не добавлено и не изменено.

## 1.0.0
- Архитектура 1.0–1.2, схема, проверка, примеры `COMMON-SYS-001` и `RENT-DR-001`.
