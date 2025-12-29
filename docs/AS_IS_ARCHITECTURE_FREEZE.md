# NEFT Platform — AS-IS Architecture Freeze
## End of Core Development Stage

## 1. Executive Summary
Ядро платформы NEFT доведено до 250–300% готовности и зафиксировано как управляемый процессинговый центр, а не MVP или прототип. Архитектура намеренно ориентирована на объяснимость, управляемость и детерминизм, исключая «чёрные ящики» как принцип проектирования. Этот этап разработки официально завершён и признан архитектурно закрытым.

Core platform architecture is completed and frozen. Further work must proceed only through versioned extensions.

## 2. Архитектурный охват (AS-IS Scope)
Зафиксированное ядро включает следующие контуры:

* Financial Core (Ledger + Money Flow)
* Fuel Processing
* Logistics & Navigator
* CRM Control Plane
* Explain Layer
* Ops Workflow
* Fleet Intelligence & Control
* Decision / Assistant Stack
* Administrative UI (управленческий)

Это именно ядро платформы; периферийные продукты и внешние интеграции не входят в зафиксированный контур.

## 3. Зафиксированные архитектурные эталоны

### 3.1 Financial Core — Reference Implementation
Двойная запись, инварианты и детерминированность финансовых состояний обеспечивают воспроизводимость и объяснимость операций. Поддерживаются replay и explain как встроенные свойства финансовой модели. Enterprise-grade financial integrity закреплена как обязательный стандарт.

Financial Core is the immutable source of financial truth.

### 3.2 Fuel Processing — Hardened Spend Control
Полный контур authorize / settle / reverse реализован как единая транзакционная модель. Limits v2 работают в контекстных режимах, причины отказов канонизированы, explain-first дизайн встроен по умолчанию. Контур интегрирован с Money Flow.

### 3.3 Logistics & Navigator — Context Engine
Маршрутизация, ETA и отклонения фиксируются как контекстные события. Связка «маршрут ↔ топливо» встроена в доменную модель. Навигация организована через адаптеры и провайдер-агностичный слой.

### 3.4 CRM Control Plane — Policy Authority (Frozen)
Контрольная плоскость политики фиксирована как версионированная. Контракты и подписки v2 управляют использованием, пророццией и пакетами. Feature flags и риск/лимит-профили являются ядром управления. Политика freeze прописана явно.

CRM is a control plane, not a UI layer.

### 3.5 Explain Layer — Product-Level Capability
Единая explain-система определяет первичную причину и управляет реакциями. Поддержаны действия, SLA и эскалации, включая Ops inbox. Это продуктовая возможность, а не вспомогательная телеметрия.

Explainability is a first-class product feature.

### 3.6 Ops Workflow — Operational Governance
Операционная модель включает эскалации, SLA-трекинг и KPI по первичным причинам. Контур обеспечивает аудируемость действий и воспроизводимость операционных решений.

### 3.7 Fleet Intelligence & Control — Closed Loop System
Система фиксирует scores, тренды и инсайты, формирует предлагаемые действия и отслеживает эффект. Поддержаны decay, cooldown и confidence, а также обучение на результатах действий без ML.

### 3.8 Decision Stack / Assistant
Слой решения включает benchmarks, projections и What-If sandbox, а также Decision Memory. Контур предназначен для принятия решений CFO и Head of Ops.

Designed for CFO / Head of Ops decision-making.

## 4. Explicitly Deferred Capabilities (Intentional Non-Scope)
Следующие возможности сознательно исключены из ядра и остаются вне объёма:

* e-Signature providers
* EDI / Диадок / СБИС
* ERP integrations (1C, SAP)
* ML-heavy risk models (v5 in shadow)
* Mobile applications / UI polish

Deferred by design, architecture-ready.

## 5. Architecture Freeze Declaration
Архитектура ядра считается замороженной. Любые изменения возможны только через версионирование и создание новых контуров без модификации эталонных блоков. Money Flow, Ledger и Explain признаются immutable reference layers.

Core architecture is frozen. Any future development must extend, not modify, the existing core.

## 6. Forward Boundary
Дальнейшие работы относятся не к развитию ядра, а к выделению сервисов, интеграциям, продуктовым поверхностям и масштабированию.
