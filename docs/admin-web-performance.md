# Admin Web Performance Strategy

## React Query adoption
- **Why**: Avoid redundant API calls and serve cached data instantly when the user reopens pages.
- **Configuration**:
  - Runtime center: `staleTime = 30s`, `refetchOnWindowFocus = false`, structural key `['runtime-summary']`.
  - Logistics inspection: `staleTime = 30s`, structural key `['admin-logistics-inspection', orderId]`.
  - Finance, CRM, cases and marketplace pages keep route-local query keys that include filters, page cursors and selected IDs.
  - Auth: login changes clear local auth state and `QueryClientProvider` in `src/main.tsx` owns fresh query state for the next session.
- **Patterns**: use `useQuery`/`useMutation`, rely on `QueryClientProvider` from `src/main.tsx`, and prefer `keepPreviousData` for paginated lists.

## Code splitting and lazy loading
- `src/App.tsx` is the canonical route map and imports mounted operator pages directly so entrypoint sentinels can see accidental route overlap.
- Legacy route-level lazy pages (`DashboardPage`, `HealthPage`, `IntegrationMonitoringPage`, `BillingDashboardPage`) are retired or frozen; they must not be documented as active chunks.
- Local lazy loading is still allowed for heavy, mounted page internals such as table/filter widgets. Those fallbacks must use the shared loader/state components and stay inside the owning page.
- Result: route ownership stays reviewable, while heavier tables and filters can still defer work without reintroducing a shadow router.

## Asset preconnect
- `index.html` establishes an early `preconnect` to `/admin/assets/` to speed up asset discovery. Vite continues to emit `modulepreload` hints for hashed chunks automatically.

## Debugging chunk loading
- Use the browser DevTools network tab to verify that page-internal lazy widgets load after their owning route is opened.
- Check `modulepreload` requests to confirm that Vite is hinting dependent chunks.
- For Suspense fallbacks, ensure loaders disappear once the lazy component resolves; otherwise inspect the console for dynamic import errors.
