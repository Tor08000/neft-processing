# STABLE Sprint — Freeze & Stabilize

## Что сделано
- Нормализован словарь терминов и обновлены документы (glossary + legal/compliance/ux).
- Добавлен stable suite runner для минимального набора invariants/smoke тестов.
- Усилены smoke/invariant тесты для documents и decision engine.
- Уточнены Alembic protected revisions и stability notes.
- UI: статусы документов приведены к единообразному отображению.

## Что сознательно не делали
- Не добавляли новые endpoints/роуты.
- Не меняли бизнес-логику или state-machine переходы.
- Не добавляли новые модели/таблицы/миграции.

## Следующий фокус
- Прогон stable suite в CI как обязательный gating.
- Детализация known limitations и устранение инфраструктурных несоответствий.
