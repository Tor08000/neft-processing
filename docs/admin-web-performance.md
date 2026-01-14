# Admin Web Performance Strategy

## React Query adoption
- **Why**: Avoid redundant API calls and serve cached data instantly when the user reopens pages.
- **Configuration**:
  - Operations list: `staleTime = 30s`, `refetchOnMount = false`, structural keys `['operations', filters]`.
  - Dashboard: `staleTime = 5s`, `refetchOnWindowFocus = false`, key `['dashboard']`.
  - Auth: login mutation invalidates cached queries (e.g. `['me']`, `['operations']`) after token refresh.
- **Patterns**: use `useQuery`/`useMutation`, rely on `QueryClientProvider` from `src/main.tsx`, and prefer `keepPreviousData` for paginated lists.

## Code splitting and lazy loading
- Pages (`DashboardPage`, `OperationsListPage`, `BillingSummaryPage`, `ClearingBatchesPage`, `HealthPage`, `LoginPage`) and layout are imported via `React.lazy` with `<Suspense>` fallbacks.
- Heavier widgets (tables and filters) are also loaded lazily inside pages to keep the initial bundle light.
- Result: the initial JS payload shrinks, and secondary pages load their chunks on demand.

## Asset preconnect
- `index.html` establishes an early `preconnect` to `/admin/assets/` to speed up asset discovery. Vite continues to emit `modulepreload` hints for hashed chunks automatically.

## Debugging chunk loading
- Use the browser DevTools network tab to verify that route-level chunks are fetched only when navigating to the corresponding page.
- Check `modulepreload` requests to confirm that Vite is hinting dependent chunks.
- For Suspense fallbacks, ensure loaders disappear once the lazy component resolves; otherwise inspect the console for dynamic import errors.
