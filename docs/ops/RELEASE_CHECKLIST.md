# Release Checklist

> Используется перед тегированием релиза. Любой пункт FAIL = блокирующий.

## Pre-release

- [ ] Migrations applied on staging (`scripts\check_migrations.cmd`).
- [ ] Backups taken (Postgres/MinIO/ClickHouse if enabled).
- [ ] Backup restore verification PASS (`scripts\backup\verify_backup.cmd`).
- [ ] Smoke suite PASS (`scripts\smoke_*.cmd`, `scripts\test_processing_core_docker.cmd`).
- [ ] Dashboards green (SLO overview, billing, EDO) from `docs/ops/dashboards/*.json`.
- [ ] Rollback plan documented and ready.

## Release

- [ ] Tag created (`vYYYY.MM.PATCH` or `-rcX`).
- [ ] Release notes generated (`scripts\release\generate_release_notes.cmd vYYYY.MM.PATCH`).
- [ ] CI gates PASS (static → migrations → contracts → core → smoke → UI).
- [ ] Deployment executed with reproducible artifacts.

## Post-release

- [ ] Monitoring confirms SLOs within targets (`docs/ops/SLO.md`).
- [ ] On-call notified and alerting verified.
