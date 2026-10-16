# Practical improvement plan

This is a source-review backlog, not a claim that fixes have been implemented. Reviewed on **15 October 2026**. Links identify the current code; acceptance checks describe how to prove a future change. Start with correctness and recovery, then optimize measured bottlenecks.

Return to the [concepts guide](UNDERSTANDING_PERCONA.md) or [technical walkthrough](../README_IN_DEPTH.md).

## P0: Fix before relying on the stack

### P0-1. Establish a supported, reproducible baseline

**Evidence:** [vars/main.yml](../vars/main.yml) selects server 8.0; [backup tasks](../tasks/backup_scripts.yml) install `percona-xtrabackup-80`. [Defaults](../defaults/main.yml) select Orchestrator 3.2.6 from `openark`, a fixed ProxySQL 2.5.5 Ubuntu 20 package, and a PMM version string from a different generation than its package name. OS claims differ between README and metadata.

**Action:** pick one tested Ubuntu/server/tool combination first. Evaluate Percona Server 8.4 with compatible XtraBackup, proxy, authentication and orchestration versions. Pin package/binary versions and checksums, and declare supported OS/architecture combinations. Derive download URLs from those selections. Existence of a binary must not prevent a requested upgrade forever.

**Why now:** Percona Server/XtraBackup 8.0 reached EOL on 1 April 2026; PMM 2 reached EOL on 31 October 2025. The `openark/orchestrator` repository is archived. These are maintenance constraints, not reasons to change every tool simultaneously. [Percona lifecycle](https://www.percona.com/release-lifecycle-overview/), [Orchestrator upstream](https://github.com/openark/orchestrator).

**Done when:** clean installation and upgrade work on the declared matrix, and the installed versions match expectations. Do not assume changing `version` to `8.4` is sufficient: this code forces `mysql_native_password`, disabled by default in 8.4, and uses version-sensitive replication commands/configuration. [Upgrade checklist](https://docs.percona.com/percona-server/8.4/upgrade-checklist-8.4.html).

### P0-2. Make initial authentication and secret handling correct

**Evidence:** [configure.yml](../tasks/configure.yml) alters root only after the desired password already authenticates, so it lacks a fresh-install bootstrap path. Root alteration and general user tasks use `no_log: false`. Backup and failover scripts embed passwords and are deployed mode `0755`; Orchestrator logs are `0666`. ProxySQL commands carry the admin password, including tasks without redaction.

**Action:** distinguish initial bootstrap, normal authentication, and explicit rotation. Use the package's supported initial local authentication method, then verify desired credentials. Fail clearly when neither authorized path works. Store secrets in Vault; render separate root-readable client files with mode `0600`; suppress sensitive task output/diffs. Use restrictive script/log permissions and serialize values correctly for SQL, JSON, shell and client files. Masking Ansible output does not fix credentials embedded in readable scripts or command arguments.

**Done when:** first install and second run both work, rotation works using an old credential to establish the new one, and credentials are absent from normal logs and world-readable files. Test passwords containing quotes and shell-special characters in a disposable environment.

### P0-3. Correct backup success detection and chain metadata

**Evidence:** both [full](../templates/mysql-full-backup-minio.sh.j2) and [incremental](../templates/mysql-incremental-backup-minio.sh.j2) MinIO scripts read `PIPESTATUS[0]`, assign it, then read `PIPESTATUS[1]`. The first assignment itself replaces the array. The upload status becomes unset and the current fallback reports failure even for a successful pipeline. This behavior was reproduced locally with a harmless two-command pipeline.

Local scripts parse `last_lsn` from log text; MinIO scripts parse `The latest check point`. Neither is a robust committed chain manifest. Local incremental mode falls back to LSN `0` when no metadata file exists. Scripts have no shared full/incremental lock, and fixed `/tmp` log names can collide. They reuse the topology account rather than a dedicated backup account.

**Action:** capture the entire array immediately after the pipeline:

```bash
# In the current MinIO script style (pipefail, without errexit):
pipeline_status=("${PIPESTATUS[@]}")
backup_exit=${pipeline_status[0]}
upload_exit=${pipeline_status[1]}
```

Then reject either nonzero status before committing metadata. If adding `set -e`, explicitly handle a failing pipeline so the shell does not exit before status collection. Use `flock` for both full and incremental jobs, private per-run temporary directories, and cleanup traps. Preserve `xtrabackup_checkpoints` using a supported metadata-output mechanism such as the selected version's `--extra-lsndir`. Track base ID, previous backup ID, `from_lsn`, `to_lsn`, versions, timestamps and checksums. Atomically commit metadata only after the artifact and manifest are durable. Reject missing, empty or invalid base metadata.

Standardize one compression format. Local scripts add gzip over XtraBackup compression; MinIO scripts do not, despite the `.gz` suffix. Use a dedicated least-privilege backup account and verify local grants.

**Done when:** a full plus two incrementals restores correctly; failed backup/upload does not advance metadata; overlapping jobs cannot run; retry leaves no “complete” partial artifact. Begin with full-only backups if that meets recovery and resource needs.

### P0-4. Preserve recoverable chains and implement a restore drill

**Evidence:** the incremental MinIO script runs recursive age-based deletion against the **entire bucket**, including full backups and other prefixes. Local mode independently expires full and incremental files. [BackupNRestore.md](../BackupNRestore.md) references absent scripts, and no restore playbook exists in this checkout.

**Action:** select expired backup chains from manifests; delete a base and its dependent incrementals together only after newer recovery coverage is verified. Restrict deletion to the backup namespace and separate cleanup privileges if practical. Add one explicit isolated restore workflow before adding automatic resync. Add off-host binlog archiving only if the required RPO is smaller than backup intervals.

**Done when:** retention never deletes a live chain member, restore tests verify data/application behavior, and measured recovery time meets the chosen target. A three-day object listing or a green cron job is not evidence of recoverability.

### P0-5. Make replication bootstrap and reapplication safe

**Evidence:** [replication.yml](../tasks/replication.yml) configures channels but never seeds data. It uses `percona_replication_user`, while HA users create `percona_ha_replication_user`. Validation only prints status. [mysqld.cnf.j2](../templates/mysqld.cnf.j2) couples database creation with source binlog filters and role assignment with static inventory. Replicas lack the primary branch's explicit binlog retention settings; do not infer binary logging is absent, since server defaults may enable it, but verify promotion requirements explicitly.

**Action:** use one replication account definition; separate database lifecycle from optional replication filters, defaulting to unfiltered replication. Add explicit seed prerequisites, unique ID/UUID assertions, source-address variables, and replication health assertions. Configure TLS and verify authentication compatibility. Ensure every promotion candidate logs replicated transactions and retains enough history. Detect stopped/broken channels without blindly resetting healthy channels. Stop if inventory conflicts with actual topology after failover.

**Done when:** a populated source seeds a correct replica; schema/account changes propagate; lag/errors are detected; reruns neither reset healthy replication nor revert a promoted writer's role. Retention should exceed the tolerated replica outage and recovery window, not rely on a comment that seven days “prevents error 1236.”

### P0-6. Keep automatic failover disabled until recovery is complete

**Evidence:** [the hook](../templates/post-failover-action.sh.j2) sets the failed server `ONLINE` in the reader group before recovery. `force_read_only()` and `simple_rejoin()` are defined but never invoked. The background flow only waits for connectivity; there is no actual GTID comparison or Semaphore restore API call. The parent exits while work runs in the background, removing its lock early; the lock's check-then-touch is also non-atomic. [Orchestrator configuration](../templates/orchestrator.conf.json.j2) always installs a hook reference, even when the script is not deployed.

**Action:** observation first. Design one recovery owner, enforce fencing, quarantine the old primary, validate the promotion candidate's history, then route to the verified writer. Never make the failed host available to readers until its data and replication are validated. Rejoin only after checking missing/purged/errant GTIDs; rebuild from a trusted backup when necessary. Make hooks conditional, bounded, properly locked and observable. Start with operator-driven old-primary rebuild instead of background automatic resync.

**Done when:** a network partition cannot leave two accessible writers; the application reconnects correctly; stale hosts receive no traffic; repeated hook execution is safe; recovery failures produce a visible failed state. Test control-host/proxy failure as well as database failure. There is no established 30-second RTO in this repo.

## P1: Make operation predictable

| Area | Evidence | Smallest useful change | Acceptance check |
|---|---|---|---|
| Component selection | `percona_install_packages` gates install and configure; Orchestrator's install/configure flags share an undivided task list. | Separate install/configure paths with explicit defaults; add early dependency assertions. | Config-only updates work without package changes; invalid combinations fail before mutation. |
| Extra restarts | Configure flushes a restart handler and then explicitly restarts again when the same template changes. | Use one restart path; validate config first. Use rolling maintenance at playbook level. | One restart for a real change, none on an unchanged run. |
| Idempotence | Root ALTER always reports changed; ProxySQL rewrites/clears state while reporting unchanged. | Compare desired state before mutation and report changes honestly. | Second run leaves services and proxy configuration unchanged. |
| ProxySQL admin | No initial admin credential or listener configuration despite corresponding defaults. | Manage initial admin authentication, rotation, and explicit frontend/admin binds. | Fresh setup works; desired admin credentials persist across restart. |
| Query routing | General `^SELECT` goes to readers; defaults hardcode hostgroups 10/20. | Begin writer-only, then add application-tested read rules; derive IDs or validate them. | Transactions, locking reads, read-after-write, prepared statements and lag scenarios behave correctly. |
| ProxySQL ownership | Task deletes all query rules and reuses the powerful topology user for monitoring. | Manage only owned rules; use a restricted monitoring account. | Unrelated rules survive; monitoring cannot perform recovery/admin actions. |
| Account privilege | App account is granted `*.*`; `mysql_native_password` is forced. | Scope app access to its schema and use an authentication method supported by the tested stack. | App cannot modify other schemas; connections work without legacy plugin dependence. |
| TLS and access | MinIO uses `--insecure`; PMM disables certificate validation; Orchestrator is unauthenticated HTTP. | Trusted certificates and verified TLS; private binds/firewall policies; authenticated administration. | Invalid certs are rejected, valid connections work, and admin services are unreachable from app/public networks. |
| Exporter | Tasks don't create its user, don't restart on credential changes, and omit DB host/port/socket configuration. | Explicit account dependency; complete connection settings; restart handler on config/binary changes. | Scrapes work after rotation and on custom port/socket; failed scrapes alert. |
| PMM | `pmm2-client` paired with `3.5.0-7.noble`, hardcoded `pmm-server` agent ID, errors suppressed. | Choose supported PMM generation; use its documented registration workflow and actual IDs; fail on registration errors. | Node has fresh metrics after initial registration and rerun, not just an API record. |
| Disabling features | False switches skip tasks but leave services/cron running. | Document skip semantics; add explicit desired `present/absent` or enabled states only where needed. | Disabling a scheduled job actually removes it when that behavior is requested. |
| Tags and variables | Dynamic tag inheritance incomplete; legacy `mysql_*`, `ha_*`, unprefixed `version` remain. | Normalize public names, handler names and tags; deprecate aliases with a small transition plan. | Each supported tag executes intended children; removed aliases produce clear errors. |
| Error visibility | Discovery and PMM failures are suppressed. | Retry transient failures, then fail with a useful redacted diagnostic. | An unreachable dependency cannot produce a green deployment. |
| Services and downloads | ProxySQL package unit edited directly; unverified downloads and latest `mc`. | systemd drop-in; pinned downloads with checksums; version-aware upgrades. | Package upgrade preserves local settings; corrupt downloads fail verification. |

## P2: Tune only after measuring

The automatic RAM formulas in [defaults/main.yml](../defaults/main.yml) are starting assumptions, not workload-aware optimization. On a 16 GiB host they allow about **3,276 connections**, a **70% buffer pool**, and sort/read/join buffers of up to **16/8/8 MiB**. These buffers are allocated as needed, not all at connection startup, and some may be allocated multiple times per query. High concurrent work can still exhaust memory. A shared control/monitoring host needs a different budget from a dedicated database.

| Measure | First adjustment | Avoid |
|---|---|---|
| Peak active connections, OOM/swap, application pool sizes | Cap connections based on measured concurrency and a memory budget; set small session buffers and increase only for demonstrated need. | Scaling maximum connections directly from RAM in MB. |
| Query latency, rows examined, slow log | Fix queries and indexes; review execution plans on representative data. | Adding replicas to hide inefficient queries. |
| Buffer-pool misses and disk latency | Adjust buffer pool with headroom for OS, connections, backups and colocated services. | Assuming 70% fits every machine. |
| Redo/checkpoint pressure and disk capacity | Tune redo capacity using the chosen server version's supported settings. | Carrying an old redo variable into an upgrade without compatibility review. |
| Replica apply delay and source write volume | Investigate slow apply, long transactions, CPU/I/O and suitable apply concurrency. | Treating lag as a reason to relax correctness or purge history sooner. |
| Backup duration, CPU and I/O impact | Benchmark compression and parallelism; schedule off peak; use a healthy replica if appropriate. | Double compression without a measured benefit. |
| Storage growth and recovery targets | Size binlog/backup retention and disk alerts from required recovery coverage. | Increasing retention without disk planning. |
| Durability | Verify `innodb_flush_log_at_trx_commit` and `sync_binlog` against the recovery requirements. | Relaxing durable commit behavior merely to improve benchmark results. |

## A manageable implementation order

1. **Usable single node:** supported versions, bootstrap, secrets, split install/configure, one restart path. Verify clean install and no-change rerun.
2. **Recoverable data:** full-only backup, reliable status/metadata, off-host copy if needed, isolated restore exercise. Add incrementals only if justified.
3. **Visible replication:** seed and health checks, filters removed, metrics and alerts, deliberate recovery procedure.
4. **Stable app endpoint:** working ProxySQL bootstrap, writer-only traffic, then optional validated read routing.
5. **Schema discipline:** add the small [Liquibase workflow](LIQUIBASE.md). It can begin after milestone 1 and does not require HA.
6. **Controlled HA:** choose maintained orchestration, prove fencing/promotion/rejoin, then decide whether proxy/control redundancy is necessary.

Keep tests small but meaningful: YAML/Ansible syntax, rendered configuration parsing, shell syntax and failure-path checks, one disposable VM deployment/rerun, and one restore/replication exercise. Containers alone do not establish that systemd, package installation and host permissions work correctly. Do not begin by splitting this into many roles, adding Kubernetes, or creating a generic database platform.
