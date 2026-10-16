# Percona role: architecture and practical walkthrough

Read [Understand this Percona project](docs/UNDERSTANDING_PERCONA.md) first if the tools are new to you. Use [Improvements](docs/IMPROVEMENTS.md) as the development backlog and [Liquibase](docs/LIQUIBASE.md) for application schema management.

**Scope:** a source review of this checkout on 15 October 2026. Examples explain how to drive the existing role after the stated prerequisites are satisfied. They are not evidence of a successful deployment. The current role needs fixes before production use, especially bootstrap, backups, and failover.

## Contents

1. [Repository map](#1-repository-map)
2. [Execution and toggles](#2-execution-and-toggles)
3. [Hosts, connections, and accounts](#3-hosts-connections-and-accounts)
4. [Prepare a small lab](#4-prepare-a-small-lab)
5. [Use the components one at a time](#5-use-the-components-one-at-a-time)
6. [Backup and restore workflow](#6-backup-and-restore-workflow)
7. [Routine operation and troubleshooting](#7-routine-operation-and-troubleshooting)
8. [Develop without unnecessary complexity](#8-develop-without-unnecessary-complexity)

## 1. Repository map

This is **one Ansible role**. Files such as `proxysql.yml` are task lists inside it, not independent Galaxy roles.

| File | Responsibility / useful starting point |
|---|---|
| [defaults/main.yml](defaults/main.yml) | Public variables, feature switches, passwords, tuning, versions, schedules. Override in your deployment project. |
| [vars/main.yml](vars/main.yml) | Package constants and old variable names. Selects server version `8.0`; includes stale `ha_*` references. |
| [tasks/main.yml](tasks/main.yml) | Entry point; selects components in a fixed order. |
| [tasks/Ubuntu.yml](tasks/Ubuntu.yml) | Percona repository, packages, PyMySQL dependency. Only Ubuntu has a task file. |
| [tasks/configure.yml](tasks/configure.yml) | MySQL configuration, service, partial account hardening. |
| [templates/mysqld.cnf.j2](templates/mysqld.cnf.j2) | Server configuration, memory settings, and inventory-dependent replication settings. |
| [tasks/replication.yml](tasks/replication.yml) | Source information, replication user, channel setup and start. Does not seed existing data. |
| [tasks/database.yml](tasks/database.yml), [tasks/users.yml](tasks/users.yml) | Database/account lifecycle; skip replica-group hosts for ordinary writes. |
| [tasks/orchestrator.yml](tasks/orchestrator.yml) | Binary, local backend database/user, configuration, service, primary discovery. |
| [templates/orchestrator.conf.json.j2](templates/orchestrator.conf.json.j2) | Topology credentials, local metadata connection, recovery filters, hook. |
| [tasks/proxysql.yml](tasks/proxysql.yml) | ProxySQL package and service. |
| [tasks/proxysql_configure.yml](tasks/proxysql_configure.yml) | Backend servers, users, monitor, rules, runtime loading, disk persistence. |
| [tasks/minio.yml](tasks/minio.yml) | Installs/configures `mc` against an existing MinIO endpoint. |
| [templates/minio.service.j2](templates/minio.service.j2) | MinIO server unit template; no current task deploys it. |
| [tasks/backup_scripts.yml](tasks/backup_scripts.yml) | XtraBackup installation, script rendering, optional cron. |
| `templates/mysql-{full,incremental}-backup-{local,minio}.sh.j2` | Four backup variants; inspect the selected pair before scheduling. |
| [templates/backup.cnf.j2](templates/backup.cnf.j2) | Legacy template using `mysql_*` names; not deployed by current backup tasks. |
| [tasks/post_failover_script.yml](tasks/post_failover_script.yml) | Renders the failover hook and runs `bash -n`; syntax checking does not validate recovery logic. |
| [templates/post-failover-action.sh.j2](templates/post-failover-action.sh.j2) | Updates ProxySQL, then waits for the failed MySQL host. Contains unused rejoin functions. |
| [tasks/mysql_metrics.yml](tasks/mysql_metrics.yml) | Exporter installation/configuration; its DB account comes from user tasks. |
| [tasks/pmm.yml](tasks/pmm.yml) | Optional PMM client and API registration; currently inconsistent. |
| [handlers/main.yml](handlers/main.yml) | Service restart/reload handlers, some still using old variable names. |
| [meta/main.yml](meta/main.yml) | Galaxy metadata and claimed platform requirements, not a tested compatibility matrix. |
| [tests/test.yml](tests/test.yml) | Old smoke-playbook skeleton referencing role `percona`; no assertions. |
| [BackupNRestore.md](BackupNRestore.md) | Historical instructions referencing scripts not shipped here. Use section 6 below. |

## 2. Execution and toggles

The main task sequence is:

```text
install → configure/restart → replication → databases → users → exporter
        → Orchestrator → ProxySQL install → ProxySQL configure → mc
        → failover hook → backup scripts/cron → PMM
```

That order has consequences. Replicas need a usable starting dataset and credentials before replication starts. Orchestrator may start with recovery enabled before the hook is deployed. A play targeting the combined `percona` group also installs MySQL on the control host unless you change selection; the current Orchestrator setup actually requires that local metadata server.

| Component | Main-entry switches | Actual restrictions / prerequisites |
|---|---|---|
| Install **and** configure MySQL | `percona_install_packages: true` | One switch gates both. Setting it false does not perform config-only updates. |
| Replication | `percona_replication: true` | Needs primary/replica groups, unique IDs, primary facts, root access, initial data alignment. |
| Databases | `percona_database_creation: true` | Only does work if `percona_databases` has entries; skips replicas. |
| Ordinary users | `percona_users_creation: true` | Uses `percona_users`; skips replicas. |
| HA users | `percona_configure_replication_users: true` | Primary only; creates topology, app, and an additional replication account. |
| Exporter | `percona_metrics_enabled: true` | Defaults on; needs its DB account and an external scraper. |
| Orchestrator | Either `percona_orchestrator_install` or `percona_orchestrator_configure` true | Only orchestrator group; both installation and configuration tasks execute. Local MySQL required. |
| ProxySQL | `percona_proxysql_install`, `percona_proxysql_configure` | Both components restricted to orchestrator group by main.yml. Admin password must already work for configuration. |
| MinIO client | `percona_minio_configure: true` | Also needs `percona_ha_backup_storage: minio`; requires an existing endpoint. |
| Failover hook | `percona_deploy_failover_script: true` | Orchestrator group; do not enable until recovery defects are corrected. |
| Backups | `percona_deploy_backup_scripts: true` **or** `percona_backup_server: true` | No replica-only guard in main.yml despite comments. Scope hosts yourself. |
| Backup cron | `percona_setup_backup_cron: true` **or** `percona_backup_server: true` | `percona_backup_server: true` schedules jobs even if the cron toggle is false. |
| PMM | `percona_pmm_enabled: true` | No database-host guard in main.yml; external server and repaired registration needed. |

Turning a toggle off generally **skips tasks**; it does not stop a service, remove cron, delete users, or undo previous installation. `percona_backup` has no active task-selection effect.

### Select a component reliably

Use a dedicated play with `include_role` and `tasks_from` while learning. Role defaults, templates and handlers remain available. You bypass `tasks/main.yml`, so explicitly choose the right hosts and satisfy dependencies.

For example, after MySQL is bootstrapped, this configuration-only play avoids reinstalling packages:

```yaml
---
- name: Configure one lab database
  hosts: percona-master
  become: true
  gather_facts: true
  vars_files:
    - vault.yml
  vars:
    percona_root_password: "{{ vault_percona_root_password }}"
    percona_install_packages: false
  tasks:
    - name: Apply server configuration
      ansible.builtin.include_role:
        name: percona_server
        tasks_from: configure
```

This can restart MySQL. Run it as a planned maintenance operation on an actual database. It does not establish an unknown initial root password.

Do not rely on the old README's tag-only commands yet: `create_database` is on child tasks but not its include; `backup_scripts`, `pmm`, and `failover_script` are on includes but not propagated to children. Fix with consistent tags and `apply.tags`, or use component plays. [Ansible include behavior](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/include_tasks_module.html).

## 3. Hosts, connections, and accounts

### Suggested learning layout

| Host | First purpose | Add later |
|---|---|---|
| `db1` | Single application database | Initial primary, ID 101 |
| `db2` | Restore-test target first | Replica, ID 102; possible backup source |
| `control1` | Not needed at first | ProxySQL, Orchestrator, local MySQL metadata, ID 103 |
| External services | None required initially | MinIO and your selected monitoring server |

The current role co-locates ProxySQL and Orchestrator by group membership. Their failure can interrupt application access or automatic recovery even when both databases are healthy. Availability requirements may later justify multiple proxies/control nodes and a stable endpoint; do not build that before basic restore and replication work.

### Network paths

Ports below are defaults. Some variables describe a port without fully configuring its server listener: notably ProxySQL frontend/admin settings are not rendered by this role. Verify the listening ports rather than assuming changing a variable changes them.

| Initiator → destination | Port/protocol | Purpose |
|---|---|---|
| Ansible controller → managed hosts | SSH 22 | Provisioning with sudo/become |
| Application → ProxySQL | TCP 6033 | Normal application SQL |
| DBA on proxy host → ProxySQL | TCP 6032 on localhost | Admin SQL; different interface from application SQL |
| ProxySQL → database nodes | TCP 3306 | Queries and monitoring |
| Replica → primary | TCP 3306 | Replication stream |
| Orchestrator → database nodes | TCP 3306 | Inspect/manage topology |
| Orchestrator → its local MySQL | TCP 3306, 127.0.0.1 | Store topology/recovery metadata |
| DBA → Orchestrator | HTTP 3000 | Topology/API; current template has no authentication or HTTPS |
| Exporter → local MySQL | Local/default MySQL connection | Read metrics; current exporter config does not set a custom host/port/socket |
| Prometheus → each exporter | HTTP 9104 | Scrape metrics |
| Backup host → MinIO | HTTPS endpoint, default example port 9000 | Store/retrieve objects |
| Browser → MinIO console | Configured console port, template default 8443 | Human administration; server not provisioned here |
| PMM client → PMM server | Configured HTTPS endpoint, normally 443 | Monitoring connection; validate selected PMM deployment's requirements |
| Liquibase runner → current writer | TCP 3306 initially | Apply schema changes |

Allow each path only where needed. The database binds to `0.0.0.0` by default and the role does not configure a firewall. An HTTPS-looking endpoint or port number does not prove a service has valid TLS.

### Accounts are separate responsibilities

| Account | Current variable | Purpose / caveat |
|---|---|---|
| Local administrator | `percona_root_username`, `percona_root_password` | Ansible management; initial authentication must already work. |
| Active replication account | `percona_replication_user` | Used by replication tasks **and** rejoin function. Default name `slave`. |
| Second HA replication account | `percona_ha_replication_user` | Created by HA users tasks; not what replication.yml consumes. Default name `repl`. |
| Orchestrator topology account | `percona_ha_orchestrator_topology_user` | Remote discovery/recovery; currently reused for backup and ProxySQL monitoring. |
| Orchestrator metadata account | `percona_ha_orchestrator_backend_user` | Local backend database; different from topology access. |
| Application account | `percona_ha_app_user` | Must exist on database and ProxySQL with matching credentials. Current grant is too broad across databases. |
| Exporter account | `percona_exporter_db_user`, `percona_exporter_db_password` | Ordinary `percona_users` defaults create it, not exporter tasks. |
| Object-storage credentials | `percona_ha_minio_root_user/password` | Currently named/used as root; replace with bucket-scoped credentials. |
| ProxySQL administrator | `percona_ha_proxysql_admin_user/password` | Proxy admin authentication; not MySQL root. The role does not bootstrap/rotate it. |
| Migration account (proposed) | Defined by your app deployment | Schema-specific DDL and changelog-table access for Liquibase. |

Do not assume changing `percona_ha_replication_user.password` changes the actual replication account. Unify the two dictionaries, or explicitly set both to the same complete dictionary during transition. Ansible overrides of lists replace the list: when customizing `percona_users`, preserve the exporter entry if you still use it.

## 4. Prepare a small lab

### First resolve version and bootstrap prerequisites

The role currently selects 8.0 and has conflicting OS indications: original README says focal/jammy, metadata says noble/focal, ProxySQL URL targets Ubuntu 20, and PMM's version string contains `noble`. There is no demonstrated supported combination. Percona 8.0 is EOL; select and test a supported baseline before a fresh install. [Lifecycle](https://www.percona.com/release-lifecycle-overview/).

Before using the full role, verify on **each** MySQL host that the intended root credential works:

```bash
mysql -u root -p -e 'SELECT VERSION(), CURRENT_USER();'
```

Run this locally on the target and enter its password interactively. The current configure tasks attempt password login, then only alter root if that login already succeeds. They do not securely initialize an unknown fresh root password. Fix bootstrap using the chosen package's initial authentication method before treating a fresh installation as unattended.

To separate package installation for a disposable lab, a play may call `include_role` with `tasks_from: Ubuntu`. Then complete/verify initial authentication before invoking `configure` or the full role. Do not use password-reset or grant-bypass procedures blindly on an existing database.

### Deployment project layout

Keep environment configuration outside the role. Create the following in a separate local deployment directory; these are example filenames to create, not files already provided by this repo:

```text
percona-lab/
├── inventory.ini
├── vault.yml             # encrypted with Ansible Vault
├── single.yml
└── roles/
    └── percona_server/   # this checkout or a symlink to it
```

Install `community.mysql` on the controller and pin its tested version in your deployment project's requirements. The targets need Python/PyMySQL; the Ubuntu installation tasks install `python3-pymysql`. No `community.proxysql` dependency is used by the current shell-based ProxySQL tasks.

```bash
ansible-galaxy collection install community.mysql
ansible-vault create vault.yml
```

In the Vault editor, define `vault_percona_root_password` and later the additional component secrets. Use unique non-placeholder secrets. Keep the Vault password outside Git. A name starting with `VAULT_` or an environment-variable lookup does not itself encrypt anything.

Create `inventory.ini` using your actual private addresses:

```ini
[percona-master]
db1 ansible_host=192.0.2.11 percona_server_id=101

[percona-slave]
# Add db2 only when it is ready for the replica exercise:
# db2 ansible_host=192.0.2.12 percona_server_id=102

[percona-orchestrator]
# Add control1 only for the control-plane exercise:
# control1 ansible_host=192.0.2.13 percona_server_id=103

[percona:children]
percona-master
percona-slave
percona-orchestrator

[percona:vars]
ansible_user=ubuntu
```

These documentation IP addresses are placeholders. Here `db1` is intentionally in the primary group even for the one-node exercise so the template emits its binlog/GTID settings. Empty replica/control groups are fine. The primary group should contain exactly one initial source.

`ansible_host` selects the SSH address, but current replication, ProxySQL and discovery tasks use `ansible_default_ipv4.address`. On multi-interface machines, that can be a different network. Verify it is reachable from the database/control hosts, or fix the role to use explicit database addresses.

Create `single.yml` after meeting the root/version prerequisites:

```yaml
---
- name: Configure the first lab database
  hosts: percona-master
  become: true
  gather_facts: true
  vars_files:
    - vault.yml
  vars:
    percona_root_password: "{{ vault_percona_root_password }}"
    percona_replication: false
    percona_metrics_enabled: false
    percona_pmm_enabled: false
    percona_database_creation: false
    percona_users_creation: false
    percona_databases: []
    percona_deploy_backup_scripts: false
    percona_backup_server: false
  roles:
    - percona_server
```

Inspect selection and syntax first, then apply to the disposable host:

```bash
ansible-inventory -i inventory.ini --graph
ansible -i inventory.ini percona-master -m ansible.builtin.ping
ansible-playbook -i inventory.ini single.yml --ask-vault-pass --syntax-check
ansible-playbook -i inventory.ini single.yml --ask-vault-pass --list-hosts
ansible-playbook -i inventory.ini single.yml --ask-vault-pass
```

Add `--ask-become-pass` if your sudo configuration needs it. Check mode is not a deployment test here: shell commands, dynamic includes, and not-yet-installed clients limit its usefulness. Avoid `--diff` on secret-bearing templates until redaction is fixed.

## 5. Use the components one at a time

Each stage has a gate: stop and resolve failure before adding the next component. You may bring Liquibase in after stage A; it does not depend on HA.

### A. Database and application users

On `db1`, confirm the service and identity:

```bash
sudo systemctl status mysql --no-pager
mysql -u root -p -e 'SELECT @@hostname, @@server_id, @@read_only, @@super_read_only, @@gtid_mode;'
```

For initial database creation, call `database.yml` explicitly with `tasks_from: database` and `percona_databases` set to:

```yaml
percona_databases:
  - name: appdb
    encoding: utf8mb4
    collation: utf8mb4_unicode_ci
```

**Current coupling:** feeding that same list to `configure.yml` also generates `binlog_do_db=appdb`. This can exclude other schemas and administrative changes from replication. For this lab, keep `percona_databases: []` in configuration plays and supply the database list only to the database-creation task include. Remove that coupling in code before maintaining a larger deployment.

Then call `tasks_from: users` on `db1` with `percona_users_creation: true` and a schema-scoped account list:

```yaml
percona_users:
  - name: appuser
    host: "192.0.2.20"  # replace with actual application/proxy source address
    password: "{{ vault_app_password }}"
    priv: "appdb.*:SELECT,INSERT,UPDATE,DELETE"
```

Keep infrastructure secrets in Vault and mask user tasks before real use; current `users.yml` has `no_log: false`. Use a separate DDL account for migrations. **Gate:** connect from the intended application host, write/read a test row, and verify the app account cannot change unrelated schemas.

### B. Full backup and restore

Start with local full backups; use section 6 for the recovery process. First correct the script/credential problems in [P0-3 and P0-4](docs/IMPROVEMENTS.md#p0-fix-before-relying-on-the-stack).

On the chosen backup source, select `tasks_from: backup_scripts` with:

```yaml
percona_deploy_backup_scripts: true
percona_ha_backup_storage: local
percona_ha_local_backup_path: /var/backup/mysql
percona_setup_backup_cron: false
percona_backup_server: false
```

The current scripts use `percona_ha_orchestrator_topology_user`, even without Orchestrator installed. Until credentials are refactored, that account must exist locally and have the selected XtraBackup version's required privileges. `percona_backup_user` is currently unused by these scripts. Merely enabling the backup toggle does not create a backup account.

After repairing and inspecting the rendered script, run a manual full backup:

```bash
sudo /usr/local/bin/mysql-full-backup.sh
```

**Gate:** restore to an isolated host and verify application data. A successful backup exit code alone is insufficient. Only then schedule jobs. One full backup per day may be simpler than full-plus-incremental chains if database size and backup duration allow it.

### C. Metrics

Create the exporter DB user on the primary through `users.yml` (or deliberately provision it locally before replication). Set the full exporter account entry in `percona_users`, with its Vault-backed password. Enable `percona_metrics_enabled` or call `tasks_from: mysql_metrics` on each database node.

```bash
sudo systemctl status mysqld_exporter --no-pager
curl --fail http://127.0.0.1:9104/metrics
```

**Gate:** `mysql_up` is `1`, and the external scraper receives fresh metrics. A running exporter process with `mysql_up 0` means database access is broken. Add a Prometheus scrape target for each exporter; the role does not do this. Monitor disk usage, backup age, replication failures, connections, and query latency.

Use PMM later if you need its database investigation features. Do not enable the present PMM tasks until package/agent/API consistency is corrected; adding an inventory record is not proof of working telemetry.

### D. One replica

Add `db2` to the replica group and provision a unique server ID and root access. Configure its read-only settings. For a populated primary, first take a compatible physical backup, restore it to the replica, preserve the correct GTID history, and ensure a unique server UUID. The role does not perform that seed. Even a “new” primary may already contain account changes; verify the starting histories rather than assuming two empty-looking instances match.

Run replication setup on **both** primary and replica in one play using the normal linear strategy. Gather facts for both in that run. Set `percona_replication: true`, `percona_gtid_mode: true`, and one consistent `percona_replication_user` dictionary. Avoid limiting to a replica in a fresh process: the source facts may be absent. Establish validated TLS for replication; the current task does not configure it.

```yaml
---
- name: Connect an already seeded replica
  hosts: percona-master:percona-slave
  become: true
  gather_facts: true
  vars_files:
    - vault.yml
  vars:
    percona_root_password: "{{ vault_percona_root_password }}"
    percona_replication: true
    percona_gtid_mode: true
    percona_replication_user:
      name: repl
      password: "{{ vault_replication_password }}"
      priv: "*.*:REPLICATION SLAVE,REPLICATION CLIENT"
  tasks:
    - name: Configure the replication channel
      ansible.builtin.include_role:
        name: percona_server
        tasks_from: replication
```

Inspect the replica directly:

```sql
SHOW REPLICA STATUS\G
SELECT @@server_id, @@server_uuid, @@read_only, @@super_read_only;
SELECT @@global.gtid_executed, @@global.gtid_purged;
```

**Gate:** receiver and applier threads run, last error fields are empty, auto-position is enabled, the expected source is shown, and a test write on `db1` appears on `db2`. Inspect lag over time. Field names may use source/replica or legacy master/slave terminology depending on the exact server/module version. The role currently prints status rather than asserting health, and may skip restarting an already configured but stopped replica.

### E. ProxySQL, initially writer-only

Add `control1`; gather facts for the complete `percona` group in a first play, then operate on `percona-orchestrator` in a second play. Provision a MySQL command-line client there. Use `tasks_from: proxysql` with `percona_proxysql_install: true`. Bootstrap the proxy's admin credentials deliberately: setting `percona_ha_proxysql_admin_password` only changes the password used by task commands, not the server password.

Create matching application credentials on database and proxy. If using the role's HA account path, invoke `users.yml` with `percona_configure_replication_users: true` on the primary; note that it also creates other HA users, grants app access to `*.*`, and forces `mysql_native_password`. Prefer fixing those behaviors before adopting that path for a real application.

Then invoke `tasks_from: proxysql_configure` with `percona_proxysql_configure: true`, a complete `percona_ha_app_user` dictionary, valid monitor credentials, and:

```yaml
percona_ha_proxysql_query_rules: []
```

Set the app user's `default_hostgroup` to the writer hostgroup (default `10`). With no matching routing rules, traffic goes there. This task clears **all** existing query rules, so use a fresh lab proxy or first fix management of only role-owned rules. [ProxySQL configuration semantics](https://proxysql.com/documentation/main-runtime/mysql-tables/).

```bash
# Application interface, from the application host:
mysql -h control1 -P 6033 -u appuser -p appdb
# Administration interface, locally on control1:
mysql -h 127.0.0.1 -P 6032 -u admin -p
```

`control1` must resolve from that client, or use its actual private address. On the admin connection inspect:

```sql
SELECT hostgroup_id, hostname, port, status FROM runtime_mysql_servers;
SELECT hostgroup, srv_host, status, ConnUsed, ConnFree
FROM stats_mysql_connection_pool;
SELECT hostname, port, connect_error FROM monitor.mysql_server_connect_log
ORDER BY time_start_us DESC LIMIT 10;
```

**Gate:** application reads and writes reach the writer through 6033, backend monitor errors are absent, and configuration survives a controlled proxy restart. Later test read-after-write, transactions, prepared statements, locking reads and replica lag before enabling reader rules. `transaction_persistent=1` keeps a started transaction in its hostgroup; it is not a guarantee that every session began on the writer. [User configuration](https://proxysql.com/documentation/users-configuration/).

### F. Orchestrator in observation mode

Provision and authenticate the local metadata MySQL on `control1`. Create the topology account on the database nodes, verify remote connectivity, and review the archived upstream/version choice. Keep recovery disabled and remove the hook while observing. With the present variables, use all of:

```yaml
percona_orchestrator_install: true
percona_orchestrator_configure: true
percona_ha_orchestrator_recovery_enabled: false
percona_ha_orchestrator_recover_master_filters: []
percona_ha_orchestrator_recover_intermediate_master_filters: []
percona_deploy_failover_script: false
```

The template still emits a post-failover hook even when deployment is disabled; change it to render an empty list in observation mode. Validate how the selected maintained build interprets all recovery settings, and isolate the API so a user cannot trigger recovery unexpectedly. Invoke `tasks_from: orchestrator` on the control host after gathering database facts.

```bash
sudo systemctl status orchestrator --no-pager
sudo journalctl -u orchestrator -n 100 --no-pager
```

Use its private UI/API to check that both database nodes appear with the correct relationship. A ready TCP port is not proof discovery succeeded; current discovery failure is suppressed.

**Gate before automatic recovery:** complete fencing, promotion, routing, application reconnect, and old-primary recovery drills in a disposable environment. Measure data loss and outage. The README's approximate 30-second recovery claim is not a measured guarantee. Never reapply an old inventory after failover until reconciling node roles: the template would make the promoted replica read-only again.

### G. Off-host storage and scheduling

Use an existing MinIO service and bucket-scoped credentials; the role does not install its server. Correct TLS validation, stream status handling and retention first. On the backup host, run `tasks_from: minio` with `percona_minio_configure: true`, then render backup scripts with `percona_ha_backup_storage: minio`.

**Gate:** a backup uploaded to the actual bucket can be downloaded and restored, and a simulated failed upload leaves the chain's committed LSN unchanged. The default schedules are Sunday full and Monday–Saturday incremental at 01:00 **in the backup host's timezone**, not necessarily your laptop's timezone. Enable cron only after that gate.

## 6. Backup and restore workflow

### Current format differences

| Output | What the current template actually writes |
|---|---|
| Local `*.xbstream.gz` | XtraBackup-compressed files inside xbstream, then an outer gzip layer. |
| MinIO `*.xbstream.gz` | XtraBackup-compressed files inside xbstream, **without** outer gzip despite the suffix. |

Correct the naming/format before creating a standard restore tool. Compression codec support depends on the installed XtraBackup version. [Percona restore documentation](https://docs.percona.com/percona-xtrabackup/8.0/restore-a-backup.html).

### Recovery procedure to implement and rehearse

1. Select one completed full backup and every required subsequent incremental up to the recovery point. Retrieve checksums, version metadata, GTID/binlog coordinates and a chain manifest; the current scripts do not reliably produce all of these.
2. Work on copies in an isolated restore directory with sufficient disk space. Keep originals unchanged.
3. Remove the outer gzip layer **only if present**, then extract xbstream. Decompress the extracted XtraBackup-compressed files using the matching tool/codec. Do this separately for the full and each incremental.
4. Validate each incremental's `from_lsn` against the preceding backup's `to_lsn` from `xtrabackup_checkpoints`. Missing or mismatched links mean stop.
5. Prepare the chain in order. For a full-only restore use ordinary `--prepare`. For a chain, defer rollback until the last incremental.
6. On the isolated target, stop MySQL, preserve any existing data separately, and use a confirmed empty target datadir. Copy back the prepared backup, set MySQL ownership and validate path/security-policy permissions.
7. Start isolated from application traffic. Verify startup, schema, expected rows, and application checks. For a new replica, ensure a unique server ID/UUID and correct replication history before attaching it.
8. Record recovery duration and recoverable data timestamp. Add it to service acceptance criteria.

After extraction and decompression, a chain with two incrementals is prepared as follows; these paths represent **working copies**:

```bash
xtrabackup --prepare --apply-log-only --target-dir=/restore/base
xtrabackup --prepare --apply-log-only --target-dir=/restore/base --incremental-dir=/restore/inc1
xtrabackup --prepare --target-dir=/restore/base --incremental-dir=/restore/inc2
```

The result is in `/restore/base`. Do not apply the same incremental twice. A prematurely finalized base cannot accept later incrementals in the normal chain workflow. [Preparing incremental backups](https://docs.percona.com/percona-xtrabackup/8.0/prepare-incremental-backup.html).

Retention must delete **whole expired chains**, not arbitrary older files. Keeping 30 days of full backups but seven days of incrementals does not provide every recovery point over 30 days. For PITR, additionally archive binlogs off-host and restore them from validated backup coordinates; seven-day server-side binlog retention alone is not disaster protection. [PITR procedure](https://docs.percona.com/percona-xtrabackup/8.0/point-in-time-recovery.html).

## 7. Routine operation and troubleshooting

| Symptom | Check first | Relevant file |
|---|---|---|
| Initial run gets access denied | Does local root password authentication already work? Correct host/socket and selected auth plugin? | `tasks/configure.yml` |
| Undefined primary IP/fact | Gather primary facts in the same run; primary group populated; no isolated replica-only limit. | `tasks/replication.yml` |
| Replica looks configured but does not advance | Receiver/applier threads, last errors, correct source, GTIDs, binlog availability. | `tasks/replication.yml` |
| Data/users missing on replica | Seed correctness and generated `binlog_do_db`/`binlog_ignore_db` filters. | `templates/mysqld.cnf.j2` |
| App login to proxy fails | Correct port 6033; user/password in both ProxySQL and MySQL; runtime loaded; source-host grant/auth compatibility. | `tasks/proxysql_configure.yml` |
| Proxy admin setup fails immediately | Actual admin credentials; role has no admin bootstrap task. | `tasks/proxysql_configure.yml` |
| Read returns old data | Query routed to replica; lag and read-after-write expectations. | Query rules in `defaults/main.yml` |
| Exporter runs but has no DB metrics | `mysql_up`, account existence, local socket/port, grants and credential file. | `tasks/users.yml`, exporter templates |
| MinIO backup reports failure after upload | Sequential `PIPESTATUS` reads erase the second status; inspect actual object and logs. | MinIO backup templates |
| Scheduled backups run despite cron=false | `percona_backup_server` also enables cron; disabling flags does not remove existing jobs. | `tasks/backup_scripts.yml` |
| Orchestrator is up but topology empty | Topology account, source IP facts, private connectivity, suppressed discovery failure. | `tasks/orchestrator.yml` |
| Old primary never rejoins | The current background hook waits for reachability; it never calls its rejoin functions. | `templates/post-failover-action.sh.j2` |
| PMM record exists, no metrics | Package generation, real agent IDs, registration errors, DB credentials, service health. | `tasks/pmm.yml` |

Before maintenance, capture current writer, replication health, backup freshness and application error rate. Apply configuration to one host at a time with deliberate traffic handling. Afterward check the same measurements. Do not rerun the complete HA role as a generic incident-recovery command.

## 8. Develop without unnecessary complexity

Keep one role initially. First make its components independently selectable, fix authentication and secret handling, and prove backup restoration. Then harden replication and writer-only proxy access. Automate promotion only after manual recovery is reliable.

Start each change with one concrete behavior and one useful acceptance check: “a failed upload cannot advance the LSN,” “a second run does not restart an unchanged server,” or “an unavailable replica cannot receive application reads.” The prioritized tasks and checks are in [Improvements](docs/IMPROVEMENTS.md).

Leave app tables and indexes to [Liquibase](docs/LIQUIBASE.md); leave database installation, accounts, and configuration to Ansible. This boundary gives you a small, understandable system that can grow with measured needs.
