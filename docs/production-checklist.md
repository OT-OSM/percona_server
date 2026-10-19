# Production checklist

Decisions to make with the client before the first production deploy. Each item
has a default in this repository; change the ones the client cares about and
record the answers next to the inventory.

## Topology and endpoint

| Decision | Default | Notes |
|---|---|---|
| Database nodes | 3, single-primary Group Replication | Minimum for quorum. Survives one node failure. |
| Proxy nodes | 2 | 1 is fine for labs only. |
| Stable endpoint | Keepalived VIP (`proxysql_ha_enabled`) or the client's existing load balancer | Keepalived needs VRRP (IP protocol 112) between the proxies. On cloud, prefer the cloud load balancer. |
| Read/write split | All traffic starts on the writer; read rules are opt-in (`proxysql_query_rules`) | Do not send every SELECT to secondaries unless the app tolerates slightly stale reads. |

## Data safety

| Decision | Default | Notes |
|---|---|---|
| Backup source | db3 (a secondary) | Never the writer. |
| Full backup cadence | Daily 01:00 | `backup_hour`, `backup_minute`. |
| Incrementals | Off | Turn on with `backup_incremental_enabled` for large data sets. |
| Retention | 7 days (`backup_retention_days`) | Prune keeps the newest chain no matter what. Size disk for retention plus one extra full. |
| Binlog archiving | On, shipped every 5 minutes (`backup_binlog_archive_enabled`) | Gives point-in-time recovery. Without it, RPO is the last full/incremental. |
| Off-site copies | `backup_storage: local` | Set `minio` with the client's bucket for off-host copies. This repo never installs MinIO itself. |
| RPO / RTO statement | Write it down | Example: RPO 5 minutes (binlog shipping), RTO 1 hour (restore drill proves it). |

## Security

| Decision | Default | Notes |
|---|---|---|
| Secrets | ansible-vault `vault.yml` | Never commit plaintext. Rotate before handover. |
| MySQL TLS | Off (`percona_require_secure_transport: false`) | Turn on when the client's apps support it. |
| Group Replication TLS | Off (`percona_gr_ssl: false`) | Turn on before the first bootstrap if required; changing it later needs a rolling group restart. Must be identical on all members. |
| ProxySQL admin | Localhost only, vault password | Never expose 6032. |
| OS access | `ubuntu` + SSH keys + sudo | Decide who holds the keys. |

## Sizing

| Item | Rule |
|---|---|
| RAM | 8 GB minimum per database node. The buffer pool auto-sizes to 50% of RAM. |
| Disk | datadir + 7 days of binlogs + (retention + 1) full backups + 20% headroom. Binlogs alone can surprise you on write-heavy workloads. |
| CPU | 2 vCPU is a lab floor, not a production recommendation. Size from the client's workload. |

## Monitoring

- Point Prometheus at `:9104` on every database node (scrape example in `docs/monitoring.md`).
- Install `monitoring/mysql_alerts.yml` into the existing Prometheus rule files.
- Decide who receives the alerts and test one alert end to end before handover.

## Handover tests

Run each of these in front of the client, or record the output:

1. `playbooks/preflight.yml` passes on fresh servers.
2. `playbooks/verify.yml` passes after deploy.
3. Failover drill: stop MySQL on the writer, confirm a new PRIMARY, confirm ProxySQL hostgroup 10 follows it, reconnect and write.
4. Restore drill: restore the latest backup to an isolated VM and start it read-only.
5. Kill one proxy (or move the VIP) and confirm the app keeps working.

If any of these is skipped, write down why. That note is part of the handover.
