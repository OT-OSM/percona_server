# Migrate the old layout deliberately

The original role is preserved in `archive/legacy/`; active playbooks load only `roles/`. Do not replay old all-in-one inventories against the new roles without reviewing inputs.

| Old input / behavior | New location / behavior |
|---|---|
| `percona-master` / `percona-slave` | `primary` / `replicas`, both under `database` |
| Per-host implicit network facts | Explicit `percona_address` |
| `percona_replication: true` | Explicit replication playbook |
| Two replication-user dictionaries | One `percona_replication_user` string + `percona_replication_password` |
| Default exporter included in server role | Explicit monitoring playbook and exporter-owned account |
| HA app-user dictionary | `proxysql_users` list with schema-scoped privileges |
| `percona_ha_backup_storage` | `backup_storage` |
| `percona_backup_server` implicitly enables cron | `backup_schedule_enabled` only |
| Four streaming backup scripts | One staged backup/prepare program with manifests |
| MinIO server template | Historical only; use an existing storage service |
| Orchestrator local MySQL backend | Local SQLite for one observer |
| Automatic rejoin / PMM | Archived; not part of active playbooks |

For an existing database:

1. Capture effective MySQL settings, current topology and a verified backup. Compare with the smaller new template; carry forward required tuning/TLS settings before applying it.
2. Use the actual writer/replica identities and addresses. A changed UUID/server ID or accidental writer-to-reader switch is not a routine configuration update.
3. Supply current root authentication through `percona_bootstrap_password` if different from the desired Vault credential. No password bypass is attempted.
4. Set `percona_adopt_existing: true` only after review. If enabling GTID on an existing non-GTID server, plan maintenance and explicitly set `percona_allow_gtid_enable: true` after compatibility checks.
5. Inspect the change in staging, then apply during a suitable maintenance window. Remove one-time flags afterward.

The new server-state marker detects later read-only/identity drift. Following a genuine promotion, review both runtime and persisted configuration and reconcile the marker deliberately; do not delete it as a routine workaround.

Old scheduled backup jobs are removed by the new backup role. Old backup formats are **not** consumed by the new restore program: preserve them with their recovery procedure and begin a new full chain. No data files are converted or deleted during restructure.
