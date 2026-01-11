# BI ClickHouse sync

Runtime sync is executed via the core admin endpoints:

- `POST /admin/bi/sync/init` for the initial bootstrap
- `POST /admin/bi/sync/run` for incremental updates

Watermarks are stored in `bi.bi_watermarks` and sync runs in `bi.bi_sync_runs`.
