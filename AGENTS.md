<!-- HomenS.AI Error-database · © 2026 Serhii Khomenko -->
# AGENTS.md — для ИИ-агентов

- **Сначала прочитать `ARCHITECTURE.md` целиком.**
- **Найти код:** `codes/<ПРОСТРАНСТВО>/*.json`, поиск по `code`, `key` или `aliases`.
- **Добавить код:**
  1. взять следующий свободный номер в нужном пространстве;
  2. заполнить RU/UK/EN/DE;
  3. запустить `python tools/validate.py` — он проверяет и по `schema/error-file.schema.json`;
  4. не трогать существующие коды.
- **Нельзя:**
  - переиспользовать или переименовывать коды;
  - писать внутренние детали, секреты, личные данные, приёмы обхода защиты;
  - пропускать языки.
- **Подключить к проекту:** манифест `errors.manifest.json` перечисляет нужные пространства, версия закрепляется в `errors.lock`, файлы копируются в `vendor/errors/` — сборка самодостаточна (`ARCHITECTURE.md` §7).
- **Переходный период** (`ARCHITECTURE.md` §12): пока `transition.show_legacy_codes: true`, везде показывать новый код, затем старый, затем полное описание.
- **В продукте:** только `AppError("<код>", ...)` из каталога; самодельные коды запрещены и ловятся тестом (§7.4).

<!-- HSAI-AI-CONTEXT-CACHING-POLICY:BEGIN -->
## Mandatory AI preflight and token-cost optimization (owner instruction, 2026-11-12)

Before substantive work, map the **complete tracked project structure** and active state; read README, root/nested AGENTS and CLAUDE rules, architecture/status/handoff/decisions, manifests, dependencies, CI, tests, configuration and relevant sources **end-to-end**. Distinguish current files from archives/generated/vendor/sensitive content. Reuse a concise, version-aware project context map; refresh changing facts. Never blindly paste an entire repository into a model prompt.

**Audit before coding:** classify stable vs dynamic context (tools, instructions, common documents/examples, conversations, results). Reuse compact summaries, targeted reads and diffs; plan model choice, token budget, prompt caching and measurements. For direct Claude Messages API, enable top-level `cache_control: {"type":"ephemeral"}` for reusable conversation prefixes or explicit breakpoints at the **end of stable prefixes**; keep changing content after them, order `tools → system → messages`, respect 4 slots, 20-block lookback, model minimum lengths and invalidations. Default TTL 5m; use 1h only when justified by measured reuse economics. Measure `cache_creation_input_tokens`, `cache_read_input_tokens`, baseline costs/latency, and correctness; disable ineffective caching. Never cache/expose secrets unnecessarily.

**Claude Code is not the same as an API client:** use only its supported built-in context/cache behavior; these repository rules do not raise subscription limits. If a repo has no qualifying Claude API calls, mark API caching **not applicable**, and optimize context retrieval instead. Before finishing, report inspected sources, caching opportunities/implementation, real metrics vs estimates, tests and limitations. Follow existing repo safety/branch/release rules.

Canonical policy: https://github.com/HomenSAI/homensai-core/blob/main/docs/AI_CONTEXT_EFFICIENCY_POLICY.md
<!-- HSAI-AI-CONTEXT-CACHING-POLICY:END -->
