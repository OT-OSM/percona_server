# EOD — Percona 8.0 modular restructuring

## Completed work

- Restructured the repository into six focused roles: server, replication, backup, exporter, ProxySQL and Orchestrator.
- Added ten explicit playbooks, a standalone-first quickstart, a numbered live lab checklist, one expandable lab inventory, host/group variable examples, and an encrypted-secret setup path.
- Added `preflight.yml` and `validation.yml` to every role, with concise component-mapping diagrams in each role README.
- Separated server configuration ownership from optional services and separated destructive restore/seed operations from normal setup.
- Preserved Percona **8.0**. Added package-candidate/running-version checks to reject implicit major-version changes.
- Added RAM-aware buffer-pool defaults (50%), a configurable sizing budget/percentage and explicit overrides. Kept connection/query-buffer scaling workload-driven; documented restart impact and shared-host limits.
- Archived the original role and earlier review documents; added configuration, migration, operation and validation guides.

## Bugs addressed in the active implementation

| Previous problem | Change |
|---|---|
| Standalone implicitly involved optional components | Server play invokes only the server role; add-ons have explicit entry points |
| Setting install=false also skipped configuration | Package installation and configuration are independent |
| Root setup required the desired password to work already | Try desired credentials, then authorized initial/current credentials; no grant bypass |
| Passwords in readable scripts/command arguments and task output | Private credential files, module authentication and secret redaction |
| MySQL could restart twice for one config update | One notified restart after configuration validation |
| RAM-derived connection/session limits could be excessive | Conservative explicit starting values with documented tuning |
| Database creation implicitly introduced binlog filters | Schema lifecycle is independent of replication filtering |
| Replication used competing credential dictionaries | One replication account definition; credential changes update the existing channel without resetting history |
| Replica setup depended on source network facts | Explicit inventory database addresses |
| Replica status was printed without a health gate | Validate identities, GTIDs, source, both threads and error fields |
| Stale inventory could revert a promoted server | Managed-state/live-role mismatch stops configuration |
| Exporter setup assumed another role created its user | Exporter owns its restricted account and validates mysql_up=1 |
| Exporter credential/binary changes did not restart it | Dedicated change-driven restart handler |
| Backup scripts reused the topology account | Dedicated backup account and private connection file |
| Streaming pipeline lost upload exit status | Replaced with checked subprocesses and explicit publication success boundary |
| LSN extracted from log text / missing base became zero | Structured checkpoints, chain manifests, base requirement and atomic state updates |
| Full/incremental jobs could overlap | One shared process lock |
| `.gz` extension did not describe MinIO content | One documented uncompressed XtraBackup directory format |
| Retention could delete required full/chain members | Removed unsafe automatic deletion; retention is explicitly manual pending chain-aware cleanup |
| Backup-role selection silently enabled cron | Explicit schedule state; disabling removes managed jobs and old job names |
| Replica backups could carry old channel metadata into a restore | Force read-only/skip-start isolation, clear only copied stopped-channel metadata, preserve GTIDs; lift the startup guard only after validated attachment |
| No usable restore implementation | Explicit checksum/chain verification, working-copy preparation, preserved target datadir and isolated copy-back |
| Proxy admin password was assumed to exist | Initial configuration and deliberate existing-credential rotation path |
| Proxy tasks deleted all query rules | Manage explicit entries with collection modules; preserve unrelated rules |
| General SELECT routing assumed stale reads were acceptable | Default writer-only routing; optional read rules require explicit configuration |
| Proxy monitoring reused a powerful topology account | Dedicated monitoring account and schema-scoped app grants |
| Orchestrator assumed another role installed its backend MySQL | Explicit single-observer SQLite metadata backend |
| Discovery failures were suppressed | Retry then fail on API/discovery errors |
| Failover hook could place a failed host online; rejoin functions were unused | Retired unsafe hook; observation by default; recovery requires supplied tested fencing/routing hooks |
| TLS checks were disabled for object storage | Trusted HTTPS and verified downloads; no --insecure path |

## Validation and honest limits

Local validation covers 81 YAML files, all 10 playbook entry points, 26 installed module parameter schemas, 10 rendered template variants, 10 actual Ansible guard fixtures and 15 backup failure-path tests. Memory sizing adds ten rendered configurations and four invalid-input guards. Active documentation links are also checked. See [validation.md](validation.md) and run `python3 tests/check.py` for reproducible evidence.

No live infrastructure deployment was performed. Still required: clean 8.0 VM install/rerun, real restore/replication/proxy acceptance, and failover/partition drills with environment-specific hooks. PMM, automated retention, PITR/binlog archiving and generic automatic rejoin remain outside the active implementation. The retained ProxySQL/Orchestrator binary versions still require OS/security/maintenance review. These are not reported as completed fixes.

## Short version for a daily report

> Restructured the Percona 8.0 automation into six modular roles with standalone-first playbooks and an expandable inventory. Added per-role preflight/validation checks and visual component guides. Addressed configuration coupling, bootstrap/secret handling, duplicate restarts, replication checks, exporter lifecycle, backup metadata/locking/upload handling, proxy configuration and unsafe failover defaults. Added local regression checks and documented remaining live infrastructure acceptance. No 8.0 → 8.4 migration was performed.
