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
> **Always override passwords via Semaphore environment variables or Ansible Vault.**

---

## Role Variables

### 🔧 Feature Toggles — Percona Server

| Variable | Default | Description |
|---|---|---|
| `percona_install_packages` | `true` | Install Percona Server packages |
| `percona_replication` | `false` | Enable master-slave replication |
| `percona_database_creation` | `true` | Run database creation tasks |
| `percona_users_creation` | `true` | Run user creation tasks |
| `percona_metrics_enabled` | `true` | Install and configure mysqld_exporter |
| `percona_root_password_update` | `false` | Force update of root password |

### 🔧 Feature Toggles — HA Components

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

### 🔐 Credentials — Override via Vault

| Variable | Default | Description |
|---|---|---|
| `percona_root_username` | `root` | MySQL root username |
| `percona_root_password` | `changeme` | MySQL root password |
| `percona_ha_replication_user.password` | `changeme` | Replication user password |
| `percona_ha_orchestrator_topology_user.password` | `changeme` | Orchestrator topology password |
| `percona_ha_proxysql_admin_password` | `changeme` | ProxySQL admin password |
| `percona_ha_minio_root_password` | `changeme` | MinIO root password |
| `percona_exporter_db_password` | `changeme` | mysqld_exporter DB password |
| `percona_ha_pmm_password` | `changeme` | PMM admin password |

### 🛠 MySQL Connection & General

| Variable | Default | Description |
|---|---|---|
| `percona_port` | `3306` | MySQL listen port |
| `percona_bind_address` | `0.0.0.0` | MySQL bind address |
| `percona_datadir` | `/var/lib/mysql` | MySQL data directory |
| `percona_config_file` | `/etc/mysql/mysql.conf.d/mysqld.cnf` | Main config file |
| `percona_daemon` | `mysql` | MySQL service name |
| `percona_server_id` | `1` | Unique server ID — set per play |

### 📊 Memory & InnoDB Tuning

Memory settings are auto-calculated based on `ansible_memtotal_mb`. Override in `vars/vars.yml` if needed.

| Variable | Calculation | Description |
|---|---|---|
| `percona_innodb_buffer_pool_size` | 70% of RAM (min 128M) | InnoDB buffer pool |
| `percona_innodb_log_file_size` | 25% of buffer pool (min 64M) | InnoDB log file |
| `percona_max_connections` | 20% of RAM in MB (min 50) | Max connections |
| `percona_max_allowed_packet` | `64M` | Max packet size |
| `percona_wait_timeout` | `28800` | Idle connection timeout (seconds) |

### 📦 Replication

| Variable | Default | Description |
|---|---|---|
| `percona_server_id` | `1` | Unique server ID — set per play |
| `percona_gtid_mode` | `true` | Enable GTID mode |
| `percona_binlog_format` | `ROW` | Binlog format |
| `percona_max_binlog_size` | `100M` | Max binlog file size |
| `percona_binlog_expire_logs_seconds` | `604800` | Binlog retention — 7 days |

### 📈 Prometheus Exporter

| Variable | Default | Description |
|---|---|---|
| `percona_exporter_version` | `0.15.1` | mysqld_exporter version |
| `percona_exporter_user` | `mysqld_exporter` | OS system user |
| `percona_exporter_port` | `9104` | Metrics port |
| `percona_exporter_db_user` | `mysqld_exporter` | MySQL user for exporter |

### 💾 Backup Settings

| Variable | Default | Description |
|---|---|---|
| `percona_ha_backup_storage` | `minio` | Storage type — `minio` or `local` |
| `percona_ha_backup_log_file` | `/var/log/mysql-backup.log` | Backup log file |
| `percona_ha_backup_lsn_file` | `/var/lib/mysql-backup/last_lsn` | LSN tracking file |
| `percona_ha_backup_full_retention_days` | `30` | Full backup retention days |
| `percona_ha_backup_inc_retention_days` | `7` | Incremental backup retention days |
| `percona_ha_local_backup_path` | `/var/backup/mysql` | Local backup path (local only) |
| `percona_ha_backup_full_cron_weekday` | `0` | Full backup weekday (0=Sunday) |
| `percona_ha_backup_inc_cron_weekday` | `1-6` | Incremental days (Mon-Sat) |

---

## Inventory

```ini
# =============================================================================
# Percona MySQL HA — Inventory
# =============================================================================
# Notes:
#   - percona_server_id must be unique across all nodes
#   - Set percona_backup_server=true on slave that runs XtraBackup
#   - Leave percona-master and percona-slave empty for standalone setup
# =============================================================================

[percona-master]
master_server percona_server_id=1

[percona-slave]
slave_server1 percona_server_id=2
slave_server2 percona_server_id=3 percona_backup_server=true

[percona-orchestrator]
orchestrator_server

[percona:children]
percona-master
percona-slave
percona-orchestrator

[percona:vars]
ansible_user=ubuntu
```

> **Notes:**
> - Leave `[percona-master]` and `[percona-slave]` groups empty for a standalone single-node setup.
> - Set `percona_backup_server=true` on the slave that should run XtraBackup.
> - `percona_server_id` **must be unique** across all nodes.

---

## Example Playbook

```yaml
---
# =============================================================================
# MySQL HA — Percona Server + Orchestrator / ProxySQL / MinIO
# =============================================================================

# ─────────────────────────────────────────────
# MySQL Master Node
# ─────────────────────────────────────────────
- name: Configure MySQL Master
  hosts: percona-master
  become: true
  vars_files:
    - vars/vars.yml
  vars:
    percona_server_id:                   "1"
    percona_replication:                 true
    percona_gtid_mode:                   true
    percona_configure_replication_users: true
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
  hosts: percona-slave
  become: true
  vars_files:
    - vars/vars.yml
  vars:
    percona_server_id:                   "2"
    percona_replication:                 true
    percona_gtid_mode:                   true
    percona_configure_replication_users: false
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
  hosts: percona-orchestrator
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
    percona_setup_backup_cron:           false
    percona_replication:                 false
    percona_database_creation:           false
    percona_users_creation:              false
    percona_metrics_enabled:             false
    percona_install_packages:            false
    percona_pmm_enabled:                 false
  roles:
    - mysql
```

### With Vault-encrypted passwords

```yaml
# playbooks/dev/percona-server/vars/vars.yml
percona_root_username: "root"
percona_gtid_mode:     true

# Secrets — loaded from Semaphore environment variables
percona_root_password: "{{ lookup('env', 'VAULT_MYSQL_ROOT_PASSWORD') }}"

percona_ha_replication_user:
  name:     "repl"
  password: "{{ lookup('env', 'VAULT_REPL_PASSWORD') }}"
  priv:     "*.*:REPLICATION SLAVE"

percona_ha_orchestrator_topology_user:
  name:     "orchestrator"
  password: "{{ lookup('env', 'VAULT_ORC_PASSWORD') }}"

percona_ha_proxysql_admin_password: "{{ lookup('env', 'VAULT_PROXYSQL_PASSWORD') }}"
percona_ha_minio_root_password:     "{{ lookup('env', 'VAULT_MINIO_PASSWORD') }}"
percona_exporter_db_password:       "{{ lookup('env', 'VAULT_EXPORTER_PASSWORD') }}"
```

---

## Backup Storage Toggle

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

## Usage

```bash
# Full HA setup
percona-server/playbook.yml

# Configuration only — skip package installation
percona-server/playbook.yml \
  -e "percona_install_packages=false"

# Create/update users only
percona-server/playbook.yml \
  --tags "create_user"

# Create databases only
percona-server/playbook.yml \
  --tags "create_database"

# Deploy backup scripts only
percona-server/playbook.yml \
  --tags "backup_scripts"

# Deploy metrics exporter only
percona-server/playbook.yml \
  --tags "mysql_metrics"

# Disable metrics exporter
percona-server/playbook.yml \
  -e "percona_metrics_enabled=false"

# Run restore playbook
ansible-playbook -i inventory playbooks/dev/percona-server/restore-playbook.yml \
  -e "restore_source_host=192.168.8.61 restore_target_host=192.168.8.77"
```

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

**[Rajnish Sharma](rajnish.sharma@mygurukulam.co)**
