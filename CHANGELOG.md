<!-- HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI -->
# CHANGELOG

## 1.1.0 — не выпущено
- **RENT: перенесён справочник кодов HomenS.AI Rent** (решение 288, пункт реестра ERR.import-rent): 232 кода, прежний код Rent — в `aliases` (переходный период §12).
  Области: ACL 2, AUTH 40, BILL 5, BOT 6, DB 16, DR 54, EXP 3, FILE 6, FORM 29, FX 2, IMP 2, INT 10, LOG 2, PAY 7, PDF 2, PIN 9, RECOV 8, SCHED 1, SECW 7, SET 14, TRAIN 2, WEB 6. Новые области записаны в `namespaces.json`.
- Тексты RU/UK — из справочника Rent; «почему» для 207 кодов, где его не было, и переводы EN/DE подготовлены моделью (NanoGPT, DeepSeek V4.1 flash), проверены `tools/validate.py` и ревью (GLM-5.3).
- Технические подробности справочника Rent (класс исключения, текст SQLite) не переносятся (§9).

## 1.0.0
- Архитектура 1.0–1.2, схема, проверка, примеры `COMMON-SYS-001` и `RENT-DR-001`.
