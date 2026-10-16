# Components in one view

| Component | Purpose |
|---|---|
| Percona Server 8.0 | Stores data and runs MySQL queries |
| Replication | Copies primary transactions to a seeded replica; not a backup |
| XtraBackup | Physical full/incremental copies for tested recovery |
| MinIO | Optional external object store for backup artifacts |
| mysqld_exporter | Database measurements for Prometheus |
| ProxySQL | Application connection pooling and deliberate routing |
| Orchestrator | Topology observation and explicitly tested recovery coordination |
| Liquibase | Application schema history, outside infrastructure deployment |

Primary → replica is asynchronous: recent acknowledged writes can be lost during promotion. GTIDs identify transactions; LSNs describe physical backup continuity. A successful backup job is not a restore test.

For the longer glossary, see the [historical learning document](../archive/legacy/docs/UNDERSTANDING_PERCONA.md); statements about old implementation defects refer to that archived snapshot.
