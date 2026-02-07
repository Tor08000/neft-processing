# Partner Portal Demo/Prod Rules

## Что такое demo режим

Demo режим — это режим партнёрского портала без обращений к API, предназначенный для демонстрации пользовательского интерфейса и основного пользовательского сценария на демо-данных.

## Базовые правила

### Demo

- **No API:** нельзя делать запросы в backend (`fetch`, `request`, `apiClient`, `useEffect` с вызовом API).
- **No forbidden / errors:** в demo не показываем ошибки 403/404 или сырые ошибки (`[object Object]`, `forbidden`).
- **Fallback:** если данных нет или раздел недоступен, показываем `DemoEmptyState` с понятным текстом.

### Prod

- Использует API как раньше.
- Ошибки отображаются через `PartnerErrorState`.
- Пустые состояния отображаются через `EmptyState`.
- **Запрещены демо fallback-логики** (например, `если 403 → demo`).

## Структура файлов

Для каждой страницы используется фиксированный паттерн:

- `XxxPage.tsx` — router wrapper.
- `XxxPageDemo.tsx` — demo UI без API.
- `XxxPageProd.tsx` — prod UI с API и состояниями.

## Источник демо данных

Единый источник демо-данных: `frontends/partner-portal/src/demo/partnerDemoData.ts`.

## Как тестировать

- Demo partner (`partner@neft.local` или `@demo.test`) должен открывать `*Demo` страницы.
- Non-demo partner должен открывать `*Prod` страницы с API запросами.
- В demo режиме в Network tab не должно быть API запросов (кроме статики).
