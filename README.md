<!-- HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI -->
# HomenS.AI Error-database

Единая база кодов ошибок экосистемы HomenSAI: Rent, JobPilot Pro, HomenS.AI Core, Auto VPN, SECURITY-MODULE и следующие проекты. Тексты на четырёх языках: RU, UK, EN, DE. Решение владельца: Rent, DECISIONS.md 28.10-288.

## Как устроено
- **Пространства кодов.** У каждого проекта или модуля своё: `RENT-…`, `JP-…`, `CORE-…`, `VPN-…`, `SEC-…`. Общие коды — `COMMON-…`.
- **Файлы.** Один файл на область: `codes/<ПРОСТРАНСТВО>/<ОБЛАСТЬ>.json`, код вида `RENT-DR-001`.
- **Поля записи** (подробно — `ARCHITECTURE.md` §4):
  - `code`, `key`, `level` — `info` | `warn` | `error` | `alarm`;
  - `title`, `cause` и `action` на RU/UK/EN/DE: «что случилось», «почему», «что делать»;
  - `escalation` — кому передать;
  - `help`, `since`, `deprecated`.
  Схема — `schema/error-file.schema.json`.
- **Неизменность.** Код никогда не переиспользуется и не меняет смысл. Если код больше не нужен, он помечается `deprecated`, но не удаляется.
- **Выпуски.** Выходят с версиями (теги semver). Проект подключает только свои пространства через манифест и закрепляет версию в lock-файле.

## Что здесь можно публиковать
Только то, что видит пользователь: что случилось и что делать. Нельзя:
- внутренние пути, SQL, секреты, личные данные;
- подробности, которые помогают обойти защиту.

## Документы
- `ARCHITECTURE.md` — полная архитектура: формат кода, поля записи, кому передать ошибку (себе, администратору, нейросети, разработчику), версии, выпуск, API для продуктов и встраивание в помощь.
- `AGENTS.md` — правила для ИИ-агентов.
- `tools/validate.py` — проверка базы; CI запускает её при каждом изменении.

## Библиотека Python `homensai_errors`
Без внешних зависимостей, Python ≥ 3.10, исходники — `src/homensai_errors/`, подробно — `ARCHITECTURE.md` §7.2.
```python
from homensai_errors import Catalog, AppError, Errors, configure

catalog = Catalog.load("vendor/errors")      # манифест errors.manifest.json и errors.lock (SHA-256) — рядом
configure(catalog)                           # каталог для AppError; в тестах продукта — strict=True
catalog.render("RENT-DR-001", lang="uk", params={"days": 3})   # тексты и «новый код (прежний код)»
catalog.to_problem("RENT-DR-001", lang="en", status=409, params={"days": 3})   # RFC 9457
catalog.help_page("RENT-DR-001", lang="ru")  # Markdown помощи; язык не из каталога — запасной (en)
catalog.search("пароль копий", lang="ru")    # по коду, старому коду, key и словам
raise AppError(Errors.RENT_DR_001, days=3)   # самодельный код — ошибка
```
- Константы кодов: `python tools/gen_constants.py` (по умолчанию `src/homensai_errors/codes.py`; для продукта `--source --manifest --py --ts`, `--check` для CI).
- Тесты: `python -m pytest -q` (сеть не нужна).

## Выпуск `dist/`
`python tools/build_dist.py` собирает `dist/`: `errors.json`, `errors.<NS>.json`, справочник `errors.<lang>.md`, `help/<lang>/<код>.md`, `search.<lang>.json`, `llms.txt`, `prompts/`, `SHA256SUMS`. Сборка детерминирована. `dist/` в Git не хранится: при теге `vX.Y.Z` задание `release.yml` на self-hosted runner владельца собирает его и прикладывает к GitHub Release вместе с архивом `homensai-errors-X.Y.Z.tar.gz`.

## Главное правило
Продукты HomenSAI берут коды только отсюда и свои не придумывают. При сборке нужные коды копируются внутрь продукта, поэтому каждая сборка самодостаточна и в сеть за ними не ходит.

## Состояние
Архитектура 1.3, пример `COMMON-SYS-001`; пространство `RENT` — 233 кода (перенос справочника Rent, `CHANGELOG.md` 1.1.0); библиотека `homensai_errors` и сборка выпуска `dist/` (1.1.0). Наполнение — пакет ERR в реестре Rent.
