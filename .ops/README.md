# Local Ops Access Staging

This folder is for local-only observability access files and generated snapshots.

Tracked files here are templates and notes only.

Do not commit:
- kubeconfig files
- local access env/scripts with secrets
- generated snapshots

Expected local-only files:
- `C:\neft-processing\.ops\kubeconfig.yaml`
- `C:\neft-processing\.ops\access.ps1`
- `C:\neft-processing\.ops\snapshots\stage\...`
- `C:\neft-processing\.ops\snapshots\prod\...`

Collector script:
- `C:\neft-processing\scripts\ops\collect_reports_compat_snapshot.ps1`

Runbook:
- `C:\neft-processing\docs\ops\runbooks\reports_compat_routes_usage_readout.md`
