# Client Portal v1.2 — Operability & Self‑Service (Daily‑use Product)

## 0) Главная цель v1.2

Сделать портал не просто «работает», а удобен и полезен каждый день для владельца/админа/бухгалтера/флит‑менеджера и безопасен для водителя:

- владелец видит статус компании/подписки/лимитов и «что горит»;
- массовые операции по картам/пользователям;
- удобные отчёты/выгрузки (минимум);
- журнал действий (audit viewer) с фильтрами;
- поддержка (тикеты/обращения) хотя бы MVP;
- качественная навигация, поиск, фильтры, пагинация;
- «операционный дашборд» без необходимости лезть в админку.

## 1) DoD v1.2 (что значит «готово»)

- **Dashboard** = центр управления: видны ключевые метрики, статусы, лимиты, последние события.
- **Bulk actions:** массово блокировать/разблокировать карты, назначать лимиты шаблоном, отзывать доступы.
- **Search/filters/pagination** в users/cards/docs.
- **Audit viewer:** журнал действий + фильтры + экспорт.
- **Exports:** выгрузка cards/users/transactions/docs в CSV/XLSX (минимум CSV).
- **Support MVP:** создать обращение, список обращений, статус.
- **UX:** ни одна операция не требует «догадаться»; всё с подтверждениями/empty states.

(Тесты можно продолжать держать в конце релиза, но функционал должен быть «product‑grade».)

## 2) EPIC 1 — Dashboard v2 (P0)

### 2.1 «Операционный дашборд» по ролям

Показывать:

- Org status (ACTIVE/SUSPENDED/ONBOARDING) + CTA;
- Subscription plan + modules enabled + лимиты (cards/users);
- Cards: total/active/blocked;
- Users: total/active/invited/disabled;
- Documents: последние 5 (инвойсы/акты);
- Activity: последние 10 audit events (если роль OWNER/ADMIN).

**DoD:**

- разный вид для OWNER/ADMIN/ACCOUNTANT/DRIVER;
- кликабельные переходы в соответствующие разделы;
- не грузит 10 endpoints: всё через `/client/me` + 1–2 доп. ручки максимум.

## 3) EPIC 2 — Cards: Bulk operations + Templates (P0)

### 3.1 Массовые операции (OWNER/ADMIN/FLEET)

- мультивыбор карт в таблице;
- bulk block/unblock;
- bulk assign access (выдать водителю доступ на N карт);
- bulk revoke access;
- bulk apply limits template.

### 3.2 Шаблоны лимитов (org policies)

- создать «шаблон лимитов» (AMOUNT/LITERS/COUNT + window);
- применить к карте/группе карт;
- override per card.

**DoD:**

- подтверждение действий;
- прогресс/результаты (частичный успех);
- audit события пишутся на bulk операции (можно агрегировано).

## 4) EPIC 3 — Users: Onboarding invites v2 + Access management (P0)

### 4.1 Улучшение приглашений

- повторно отправить invite;
- отменить invite;
- resend link/otp (dev/stage);
- состояние «не принял приглашение».

### 4.2 Управление доступами водителя из профиля водителя

- страница водителя: какие карты, какие права;
- кнопки: добавить/убрать доступ.

**DoD:**

- OWNER/ADMIN управляют, DRIVER видит только своё.

## 5) EPIC 4 — Docs: удобство + поиск + экспорт (P1)

- фильтр по типу/дате/статусу;
- предпросмотр PDF (встроенный viewer) перед скачиванием;
- экспорт реестра документов (CSV).

**DoD:**

- быстрый поиск по номеру/дате;
- download остаётся secure.

## 6) EPIC 5 — Audit Viewer (P0, must‑have)

### 6.1 Страница «Журнал действий»

- фильтры: дата, actor, action, entity (card/user/contract);
- поиск по request_id;
- экспорт CSV.

### 6.2 Права

- OWNER видит всё по org;
- ADMIN видит всё по org;
- ACCOUNTANT видит финансово‑документные события (опционально);
- DRIVER не видит.

**DoD:**

- показывает минимум 4 ключевых события (contract_sign, role_change, limit_change, card_block);
- события связаны ссылками (к карте/пользователю).

## 7) EPIC 6 — Reports/Exports MVP (P1)

Минимум 3 выгрузки:

- Cards registry (CSV);
- Users registry (CSV);
- Transactions for selected cards/date range (CSV).

**DoD:**

- доступность по ролям (accountant/fleet);
- большие выгрузки не кладут UI (asynchronous не обязательно, можно ограничение объёма + уведомление).

## 8) EPIC 7 — Support MVP (P1)

Если support‑service ещё не готов — делаем stub, но рабочий:

- создать обращение (topic + text + attachments optional);
- список обращений;
- статус: OPEN/IN_PROGRESS/CLOSED;
- комментарии (опционально).

**DoD:**

- доступно всем ролям, но DRIVER видит только свои обращения;
- нет 404 — если сервис не готов, coming soon.

## 9) EPIC 8 — Navigation/UX/Quality (P0)

- глобальный поиск (по картам/пользователям) хотя бы внутри разделов;
- единые таблицы: сортировка, пагинация;
- сохранение фильтров в query params;
- улучшение «скорость + предсказуемость»: skeleton loaders, empty states.

**DoD:**

- в users/cards/docs есть пагинация и поиск;
- нет «таблиц без управления».

## 10) Что НЕ делаем в v1.2 (чтобы не развалить)

- полноценный marketplace orders lifecycle;
- fleet vehicles/routes полноценные (только оболочки/экраны);
- оплату/эквайринг/биллинг‑сложность;
- EDO/интеграции как продукт (только gating/stub).

v1.2 = операционность портала, не «новые большие модули».

## 11) План v1.2 по порядку (самый эффективный)

1. Dashboard v2
2. Audit viewer
3. Bulk cards + limit templates
4. Users invites v2 + access management
5. Docs preview + filters
6. Exports
7. Support MVP / stub
8. UX polish
