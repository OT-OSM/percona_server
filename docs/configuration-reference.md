# Configure only the component you use

| Component | Settings to start with | Behavior |
|---|---|---|
| Server | `percona_server_id`, `percona_bind_address`, `percona_root_password` | 8.0 only; GTID/binlogs enabled; no automatic replication |
| Existing server | `percona_adopt_existing`, `percona_bootstrap_password` | Explicit reviewed adoption and current authentication |
| Config-only | `percona_install_packages: false` | Still configures and validates |
| Memory | `percona_memory_mb`, `percona_buffer_pool_percent`, `percona_innodb_buffer_pool_size` | Automatic 50% buffer pool; [sizing and overrides](memory-sizing.md) |
| Replication | `percona_primary`, `percona_address`, `percona_replication_password`, `percona_replica_seeded` | Current writer and verified seed |
| Replication TLS | `percona_replication_tls: true`, `percona_replication_tls_ca` | CA file must exist on replicas; addresses must match server certificates |
| Server TLS | `percona_tls_ca`, `percona_tls_cert`, `percona_tls_key`, `percona_require_secure_transport` | Existing deployed certificate files |
| Service accounts | `percona_account_host`, writer's `percona_admin_password` | Create on writer, validate on selected host |
| Backup | `backup_storage`, `backup_path`, `backup_schedule_enabled` | Local staging retained; schedule off initially |
| Incrementals | `backup_incremental_enabled` | Weekly full + six incrementals when scheduling enabled |
| MinIO | `backup_minio_*`, `backup_mc_url`, `backup_mc_checksum` | Existing bucket and verified TLS; no root credentials required |
| Exporter | `exporter_listen_address`, `exporter_db_password` | Loopback by default; set private address for remote scraper |
| Proxy | `proxysql_package_checksum`, `proxysql_backends`, `proxysql_users` | Explicit server membership; schema-scoped account grants |
| Proxy reads | `proxysql_query_rules` | Empty initially; remove rules explicitly with `state: absent` |
| Observer | `orchestrator_checksum`, `orchestrator_db_password`, `orchestrator_http_password` | SQLite metadata; loopback authenticated UI |
| Recovery | `orchestrator_recovery_*`, `orchestrator_fencing_hook`, `orchestrator_routing_hook` | Off until explicitly configured and tested |

All defaults are in each role's `defaults/main.yml`. Vault example keys live in `inventories/lab/group_vars/all/vault.example.yml`; the actual `vault.yml` is ignored by Git. Never pass passwords on command lines or commit plaintext secrets.

Package policy: existing Percona 8.0 is retained. Use `percona_manage_repository: false` for an already managed authorized 8.0 mirror. Set `percona_server_package_version` to an available exact 8.0 package version for reproducibility. Match the XtraBackup 8.0 minor to the server using your repository pinning. Validate the retained ProxySQL 2.5.5 package against the chosen OS before rollout.
