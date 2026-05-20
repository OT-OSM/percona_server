[![Apache License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/OT-OSM/percona_server)

[![Opstree Solutions][opstree_avatar]][opstree_homepage]<br/>[Opstree Solutions][opstree_homepage]

  [opstree_homepage]: https://opstree.github.io/
  [opstree_avatar]: https://img.cloudposse.com/150x150/https://github.com/opstree.png

# Percona Server HA

A production-grade Ansible role to install, configure, and manage **Percona Server 8.0** on Ubuntu with full High Availability support including Master-Slave replication, automated failover via Orchestrator, query routing via ProxySQL, XtraBackup-based backup to MinIO or local disk, and Prometheus metrics via mysqld_exporter and PMM.

## Key Features

- [x] Percona Server 8.0 installation on Ubuntu 20.04 / 22.04
- [x] Master-Slave replication with GTID mode
- [x] Automated failover via Orchestrator (~30s RTO)
- [x] Query routing via ProxySQL (writes → master, reads → slave)
- [x] XtraBackup — weekly full + daily incremental backup
- [x] Backup storage toggle — MinIO (object storage) or local disk
- [x] MinIO client (mc) installation and configuration
- [x] mysqld_exporter for Prometheus metrics (togglable)
- [x] PMM (Percona Monitoring and Management) integration (togglable)
- [x] Post-failover automation script for slave resync via Semaphore
- [x] Database and User lifecycle management
- [x] Auto-calculated memory settings based on system RAM
- [x] Idempotent — safe to re-run without side effects
- [x] All variables prefixed with `percona_` — no conflicts with other roles

---

## Requirements

- Ubuntu `focal` (20.04) or `jammy` (22.04)
- Root/sudo access on target hosts
- `community.mysql` Ansible collection:

```bash
ansible-galaxy collection install community.mysql
```

> **Security Note:** All passwords have placeholder defaults in `defaults/main.yml`.
> **Always override passwords using Ansible Vault or Semaphore environment variables.**

---

## Architecture

```
                    ┌─────────────────────────────┐
                    │   Orchestrator + ProxySQL    │
                    │       192.168.8.12           │
                    │  Orchestrator  :3000         │
                    │  ProxySQL      :6033 / 6032  │
                    └────────────┬────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
          ┌─────────▼──────────┐   ┌─────────▼──────────┐
          │   Percona Master   │   │   Percona Slave     │
          │   192.168.8.77     │◄──│   192.168.8.61      │
          │   Port: 3306       │   │   Port: 3306        │
          │   HG: 10 (writes)  │   │   HG: 20 (reads)    │
          │                    │   │   Runs XtraBackup   │
          └────────────────────┘   └─────────────────────┘
                                            │
                                   ┌────────▼────────┐
                                   │   MinIO Storage  │
                                   │   :9000          │
                                   │  percona-backup/ │
                                   └─────────────────┘
```

---

## Inventory Groups

```ini
[percona-master]
master_server percona_server_id=1

[percona-slave]
slave_server percona_server_id=2

[percona-orchestrator]
orchestrator_server
```

> Override group names via vars if needed:
> ```yaml
> percona_master_group:       "percona-master"
> percona_slave_group:        "percona-slave"
> percona_orchestrator_group: "percona-orchestrator"
> ```

---

## Role Variables

### Feature Toggles — Percona Server

| Variable | Default | Description |
|---|---|---|
| `percona_install_packages` | `true` | Install Percona Server packages |
| `percona_replication` | `false` | Enable master-slave replication |
| `percona_database_creation` | `true` | Run database creation tasks |
| `percona_users_creation` | `true` | Run user creation tasks |
| `percona_metrics_enabled` | `true` | Install and configure mysqld_exporter |
| `percona_root_password_update` | `false` | Force update of root password |

### Feature Toggles — HA Components

| Variable | Default | Description |
|---|---|---|
| `percona_orchestrator_install` | `false` | Install Orchestrator |
| `percona_orchestrator_configure` | `false` | Configure Orchestrator |
| `percona_proxysql_install` | `false` | Install ProxySQL |
| `percona_proxysql_configure` | `false` | Configure ProxySQL |
| `percona_minio_configure` | `false` | Install and configure mc client |
| `percona_configure_replication_users` | `false` | Create HA replication users |
| `percona_deploy_failover_script` | `false` | Deploy post-failover script |
| `percona_deploy_backup_scripts` | `false` | Deploy backup scripts and cron |
| `percona_setup_backup_cron` | `false` | Enable backup cron jobs |
| `percona_backup_server` | `false` | Mark node as backup server |
| `percona_pmm_enabled` | `false` | Enable PMM monitoring |

### MySQL — Connection & General

| Variable | Default | Description |
|---|---|---|
| `percona_port` | `3306` | MySQL listen port |
| `percona_bind_address` | `0.0.0.0` | MySQL bind address |
| `percona_datadir` | `/var/lib/mysql` | MySQL data directory |
| `percona_socket` | `/var/run/mysqld/mysqld.sock` | MySQL socket path |
| `percona_config_file` | `/etc/mysql/mysql.conf.d/mysqld.cnf` | Main config file |
| `percona_daemon` | `mysql` | MySQL service name |
| `percona_server_id` | `1` | Unique server ID — set per play |

### MySQL — Credentials

| Variable | Default | Description |
|---|---|---|
| `percona_root_username` | `root` | MySQL root username |
| `percona_root_password` | `changeme` | MySQL root password — override via Vault |

### MySQL — Replication & Binlog

| Variable | Default | Description |
|---|---|---|
| `percona_gtid_mode` | `true` | Enable GTID mode |
| `percona_binlog_format` | `ROW` | Binlog format |
| `percona_max_binlog_size` | `100M` | Max binlog file size |
| `percona_binlog_expire_logs_seconds` | `604800` | Binlog retention — 7 days |

### MySQL — Auto-Calculated Memory Settings

Memory settings are auto-calculated based on `ansible_memtotal_mb`. Override in `vars/vars.yml` if needed.

| Variable | Calculation | Description |
|---|---|---|
| `percona_innodb_buffer_pool_size` | 70% of RAM (min 128M) | InnoDB buffer pool |
| `percona_innodb_log_file_size` | 25% of buffer pool (min 64M) | InnoDB log file |
| `percona_max_connections` | 20% of RAM in MB (min 50) | Max connections |
| `percona_tmp_table_size` | 5% of RAM (min 16M, max 256M) | Temp table size |
| `percona_sort_buffer_size` | 1% of RAM (min 1M, max 16M) | Sort buffer |

### mysqld_exporter — Prometheus Metrics

| Variable | Default | Description |
|---|---|---|
| `percona_exporter_version` | `0.15.1` | mysqld_exporter version |
| `percona_exporter_user` | `mysqld_exporter` | OS system user |
| `percona_exporter_port` | `9104` | Metrics port |
| `percona_exporter_db_user` | `mysqld_exporter` | MySQL user for exporter |
| `percona_exporter_db_password` | `changeme` | Override via Vault |

### HA — Orchestrator Settings

| Variable | Default | Description |
|---|---|---|
| `percona_ha_orchestrator_version` | `3.2.6` | Orchestrator version |
| `percona_ha_orchestrator_port` | `3000` | Orchestrator HTTP port |
| `percona_ha_orchestrator_install_path` | `/usr/local/orchestrator` | Install path |
| `percona_ha_orchestrator_config_file` | `/etc/orchestrator.conf.json` | Config file |

### HA — ProxySQL Settings

| Variable | Default | Description |
|---|---|---|
| `percona_ha_proxysql_version` | `2.5.5` | ProxySQL version |
| `percona_ha_proxysql_port` | `6033` | ProxySQL application port |
| `percona_ha_proxysql_admin_port` | `6032` | ProxySQL admin port |
| `percona_ha_proxysql_writer_hostgroup` | `10` | Writer hostgroup ID |
| `percona_ha_proxysql_reader_hostgroup` | `20` | Reader hostgroup ID |
| `percona_ha_proxysql_admin_user` | `admin` | ProxySQL admin user |
| `percona_ha_proxysql_admin_password` | `changeme` | Override via Vault |

### HA — Backup Settings

| Variable | Default | Description |
|---|---|---|
| `percona_ha_backup_storage` | `minio` | Storage type — `minio` or `local` |
| `percona_ha_backup_log_file` | `/var/log/mysql-backup.log` | Backup log file |
| `percona_ha_backup_lsn_file` | `/var/lib/mysql-backup/last_lsn` | LSN tracking file |
| `percona_ha_backup_scripts_path` | `/usr/local/bin` | Backup scripts location |
| `percona_ha_backup_full_retention_days` | `30` | Full backup retention |
| `percona_ha_backup_inc_retention_days` | `7` | Incremental backup retention |
| `percona_ha_local_backup_path` | `/var/backup/mysql` | Local backup path (local storage only) |

### HA — Backup Cron Schedule

| Variable | Default | Description |
|---|---|---|
| `percona_ha_backup_full_cron_minute` | `0` | Full backup cron minute |
| `percona_ha_backup_full_cron_hour` | `1` | Full backup cron hour |
| `percona_ha_backup_full_cron_weekday` | `0` | Full backup weekday (0=Sunday) |
| `percona_ha_backup_inc_cron_minute` | `0` | Incremental backup cron minute |
| `percona_ha_backup_inc_cron_hour` | `1` | Incremental backup cron hour |
| `percona_ha_backup_inc_cron_weekday` | `1-6` | Incremental days (Mon-Sat) |

### HA — MinIO Settings

| Variable | Default | Description |
|---|---|---|
| `percona_ha_mc_install_path` | `/usr/local/bin/mc` | mc binary path |
| `percona_ha_minio_alias` | `companyminio` | mc alias name |
| `percona_ha_minio_endpoint` | `https://minio.example.com:9000` | MinIO endpoint |
| `percona_ha_minio_root_user` | `minioadmin` | MinIO access key |
| `percona_ha_minio_root_password` | `changeme` | Override via Vault |
| `percona_ha_minio_bucket` | `percona-backup` | Backup bucket name |
| `percona_ha_minio_resync_folder` | `failover-resync` | Failover resync folder |

### HA — PMM Settings

| Variable | Default | Description |
|---|---|---|
| `percona_ha_pmm_server_url` | `https://pmm.example.com` | PMM server URL |
| `percona_ha_pmm_username` | `admin` | PMM username |
| `percona_ha_pmm_password` | `changeme` | Override via Vault |
| `percona_ha_pmm_client_version` | `3.5.0-7.noble` | PMM client version |

---

## Backup Storage Toggle

The role supports two backup storage backends controlled by `percona_ha_backup_storage`:

```yaml
# MinIO — streams backup directly to object storage (default)
percona_ha_backup_storage: "minio"

# Local disk — stores backup on local filesystem
percona_ha_backup_storage: "local"
percona_ha_local_backup_path: "/var/backup/mysql"
```

### MinIO Backup Structure

```
percona-backup/
├── 2026-05-17-sunday/
│   └── full_20260517_010001.xbstream.gz
├── 2026-05-18-monday/
│   └── inc_monday_20260518_010001.xbstream.gz
├── 2026-05-19-tuesday/
│   └── inc_tuesday_20260519_010001.xbstream.gz
└── failover-resync/
```

---

## Example Playbook

```yaml
# =============================================================================
# MySQL HA — Percona Server + Orchestrator / ProxySQL / MinIO
# =============================================================================

# ─────────────────────────────────────────────
# MySQL Master Node
# ─────────────────────────────────────────────
- name: Configure MySQL Master
  hosts: "{{ percona_master_group | default('percona-master') }}"
  become: true
  vars_files:
    - vars/vars.yml
  vars:
    percona_server_id:                   "1"
    percona_replication:                 true
    percona_gtid_mode:                   true
    percona_configure_replication_users: true
    percona_orchestrator_install:        false
    percona_proxysql_install:            false
    percona_minio_configure:             true
    percona_deploy_backup_scripts:       true
    percona_setup_backup_cron:           false
    percona_pmm_enabled:                 false
  roles:
    - mysql

# ─────────────────────────────────────────────
# MySQL Slave Node
# ─────────────────────────────────────────────
- name: Configure MySQL Slave
  hosts: "{{ percona_slave_group | default('percona-slave') }}"
  become: true
  vars_files:
    - vars/vars.yml
  vars:
    percona_server_id:                   "2"
    percona_replication:                 true
    percona_gtid_mode:                   true
    percona_configure_replication_users: false
    percona_orchestrator_install:        false
    percona_proxysql_install:            false
    percona_minio_configure:             true
    percona_deploy_backup_scripts:       true
    percona_setup_backup_cron:           true
    percona_pmm_enabled:                 false
  roles:
    - mysql

# ─────────────────────────────────────────────
# Orchestrator + ProxySQL Host
# ─────────────────────────────────────────────
- name: Configure Orchestrator + ProxySQL
  hosts: "{{ percona_orchestrator_group | default('percona-orchestrator') }}"
  become: true
  vars_files:
    - vars/vars.yml
  vars:
    percona_configure_replication_users: false
    percona_orchestrator_install:        true
    percona_orchestrator_configure:      true
    percona_proxysql_install:            true
    percona_proxysql_configure:          true
    percona_minio_configure:             false
    percona_deploy_failover_script:      true
    percona_deploy_backup_scripts:       false
    percona_install_packages:            false
    percona_pmm_enabled:                 false
  roles:
    - mysql
```

---

## Usage

```bash
# Full HA setup
ansible-playbook -i inventory playbooks/dev/percona-server/playbook.yml

# Configuration only — skip package installation
ansible-playbook -i inventory playbooks/dev/percona-server/playbook.yml \
  -e "percona_install_packages=false"

# Create/update users only
ansible-playbook -i inventory playbooks/dev/percona-server/playbook.yml \
  --tags "create_user"

# Deploy backup scripts only
ansible-playbook -i inventory playbooks/dev/percona-server/playbook.yml \
  --tags "backup_scripts"

# Deploy metrics exporter only
ansible-playbook -i inventory playbooks/dev/percona-server/playbook.yml \
  --tags "mysql_metrics"

# Run restore playbook
ansible-playbook -i inventory playbooks/dev/percona-server/restore-playbook.yml \
  -e "restore_source_host=192.168.8.61 restore_target_host=192.168.8.77"
```

---

## Secrets Management

All sensitive values are loaded from Semaphore environment variables:

| Semaphore Variable | Role Variable | Description |
|---|---|---|
| `VAULT_MYSQL_ROOT_PASSWORD` | `percona_root_password` | MySQL root password |
| `VAULT_REPL_PASSWORD` | `percona_ha_replication_user.password` | Replication user password |
| `VAULT_ORC_PASSWORD` | `percona_ha_orchestrator_topology_user.password` | Orchestrator topology password |
| `VAULT_ORC_SRV_PASSWORD` | `percona_ha_orchestrator_backend_user.password` | Orchestrator backend DB password |
| `VAULT_APP_PASSWORD` | `percona_ha_app_user.password` | Application user password |
| `VAULT_PROXYSQL_PASSWORD` | `percona_ha_proxysql_admin_password` | ProxySQL admin password |
| `VAULT_MINIO_PASSWORD` | `percona_ha_minio_root_password` | MinIO root password |
| `VAULT_PMM_PASSWORD` | `percona_ha_pmm_password` | PMM admin password |

---

## ProxySQL Query Rules

10 production query rules are pre-configured:

| Rule | Pattern | Hostgroup | Description |
|---|---|---|---|
| 1 | `^SELECT.*FOR UPDATE` | 10 (master) | Locking reads to master |
| 2 | `^SELECT.*LOCK IN SHARE MODE` | 10 (master) | Lock share mode to master |
| 3 | `^SELECT.*INTO` | 10 (master) | SELECT INTO to master |
| 4 | `^SELECT` | 20 (slave) | Regular reads to replicas |
| 5 | `^SHOW` | 10 (master) | SHOW commands to master |
| 6 | `^SET` | 10 (master) | SET commands to master |
| 7 | `^BEGIN` | 10 (master) | Transactions to master |
| 8 | `^COMMIT` | 10 (master) | Commit to master |
| 9 | `^ROLLBACK` | 10 (master) | Rollback to master |
| 10 | `^CALL` | 10 (master) | Stored procedures to master |

---

## HA Components

| Component | Version | Port | Purpose |
|---|---|---|---|
| Percona Server | 8.0 | 3306 | MySQL database |
| Orchestrator | 3.2.6 | 3000 | Topology manager + auto failover |
| ProxySQL | 2.5.5 | 6033/6032 | Query router + connection pooling |
| MinIO Client (mc) | latest | — | Backup upload to object storage |
| mysqld_exporter | 0.15.1 | 9104 | Prometheus metrics |
| PMM Client | 3.5.0 | — | Percona monitoring platform |

---

## References

- [Percona Server Documentation](https://docs.percona.com/percona-server/8.0/)
- [Percona XtraBackup Documentation](https://docs.percona.com/percona-xtrabackup/latest/)
- [Orchestrator Documentation](https://github.com/openark/orchestrator/tree/master/docs)
- [ProxySQL Documentation](https://proxysql.com/documentation/)
- [MinIO Client Documentation](https://min.io/docs/minio/linux/reference/minio-mc.html)
- [PMM Documentation](https://docs.percona.com/percona-monitoring-and-management/)
- [Stay Away Replication Lag](https://blog.opstree.com/2019/03/26/stay-away-replication-lag/)
- [MySQL Monitoring](https://blog.opstree.com/2019/07/23/mysql-monitoring/)

---

## Author

**[Abhishek Dubey](abhishek.dubey@opstree.com)**

**[Abhishek Vishwakarma](abhishek.vishwakarma@opstree.com)**
