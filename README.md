[![Apache License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/OT-OSM/mysql)

[![Opstree Solutions][opstree_avatar]][opstree_homepage]<br/>[Opstree Solutions][opstree_homepage]

  [opstree_homepage]: https://opstree.github.io/
  [opstree_avatar]: https://img.cloudposse.com/150x150/https://github.com/opstree.png

# Percona Server

A production-grade Ansible role to install and configure **Percona Server 8.0** on Ubuntu with CIS best practices, optional master-slave replication, XtraBackup-based backup management, and Prometheus metrics export.

## Key Features

- [X] CIS Benchmark hardening (`validate_password`, `skip-grant-tables=OFF`, `local-infile=0`, etc.)
- [X] Standalone or Master/Slave replication topology
- [X] Percona XtraBackup with AES-256 encryption (key preserved across runs)
- [X] Prometheus `mysqld_exporter` integration (togglable)
- [X] Database and User lifecycle management
- [X] Idempotent — safe to re-run without side effects

## Requirements

- Ubuntu `focal` (20.04) or `bionic` (18.04)
- Root/sudo access on target hosts
- `community.mysql` Ansible collection (`ansible-galaxy collection install community.mysql`)

> **Security Note:** All passwords have defaults set in `defaults/main.yml` for reference only.  
> **Always override passwords using [Ansible Vault](https://docs.ansible.com/ansible/latest/vault_guide/) in `group_vars` or `host_vars`.**

---

## Role Variables

Variables are split into **`defaults/main.yml`** (user-overridable) and **`vars/main.yml`** (internal role constants).

### 🔐 Credentials — Override via Ansible Vault

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `mysql_root_password` | `N0Tweak$_@123!` | MySQL root user password |
| `mysql_replication_user.name` | `slave` | Replication user name |
| `mysql_replication_user.password` | `slaveMaster@123!` | Replication user password |
| `mysql_backup_user.name` | `backup` | XtraBackup user name |
| `mysql_backup_user.password` | `backUpMaster@123!` | XtraBackup user password |
| `mysql_exporter_db_password` | `StrongExporterPassword123!` | mysqld_exporter DB user password |

### 🔧 Feature Toggles

| Variable | Default | Description |
|----------|---------|-------------|
| `replication` | `false` | Enable master-slave replication setup |
| `backup` | `false` | Enable Percona XtraBackup server setup |
| `database_creation` | `true` | Run database creation tasks |
| `users_creation` | `true` | Run user creation tasks |
| `mysql_metrics_enabled` | `true` | Install and configure `mysqld_exporter` |
| `mysql_root_password_update` | `false` | Force update of the root password |
| `mysql_install_packages` | `true` | Set `false` to skip installation (config-only mode) |

### 🛠 MySQL Connection & General

| Variable | Default | Description |
|----------|---------|-------------|
| `version` | `"8.0"` | Percona version to install (`"8.0"`) |
| `mysql_port` | `"3306"` | MySQL listen port |
| `mysql_bind_address` | `0.0.0.0` | MySQL bind address |
| `mysql_datadir` | `/var/lib/mysql` | MySQL data directory |
| `mysql_skip_name_resolve` | `false` | Skip DNS resolution for connections |
| `mysql_sql_mode` | `STRICT_ALL_TABLES` | MySQL SQL mode |
| `mysql_config_file` | `/etc/mysql/my.cnf` | Main config file path |
| `mysql_config_include_dir` | `/etc/mysql/conf.d` | Directory for extra config fragments |

### 📊 Memory & InnoDB Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `mysql_innodb_buffer_pool_size` | `256M` | InnoDB buffer pool (tune to ~70% RAM) |
| `mysql_innodb_log_file_size` | `64M` | InnoDB log file (~25% of buffer pool) |
| `mysql_max_connections` | `151` | Maximum client connections |
| `mysql_max_allowed_packet` | `64M` | Max packet size |
| `mysql_query_cache_type` | `0` | Query cache (disabled; removed in 8.0) |
| `mysql_wait_timeout` | `28800` | Idle connection timeout (seconds) |

> See [defaults/main.yml](./defaults/main.yml) for the full list of tunable variables.

### 📦 Replication

| Variable | Default | Description |
|----------|---------|-------------|
| `mysql_server_id` | `"1"` | Unique server ID (set per-host in inventory) |
| `mysql_binlog_format` | `MIXED` | Binlog format (`ROW`, `STATEMENT`, `MIXED`) |
| `mysql_max_binlog_size` | `100M` | Max binlog file size |
| `mysql_expire_logs_days` | `10` | Binlog retention in days |

### 📈 Prometheus Exporter

| Variable | Default | Description |
|----------|---------|-------------|
| `mysql_exporter_version` | `0.15.1` | `mysqld_exporter` release version |
| `mysql_exporter_user` | `mysqld_exporter` | OS system user to run the exporter |
| `mysql_exporter_port` | `9104` | Port to expose metrics |
| `mysql_exporter_db_user` | `mysqld_exporter` | MySQL user for exporter (host: localhost) |

---

## Inventory

```ini
[master]
master_server1 mysql_server_id=1

[slave]
slave_server1 mysql_server_id=2
slave_server2 mysql_server_id=3 mysql_backup_server=true

[mysql]
master_server1
slave_server1
slave_server2

[mysql_cluster:children]
mysql
master
slave

[mysql_cluster:vars]
ansible_user=ubuntu
```

> **Notes:**
> - Leave `[master]` and `[slave]` groups **empty** for a standalone single-node setup.
> - Set `mysql_backup_server=true` on the host that should run XtraBackup.
> - `mysql_server_id` **must be unique** across all nodes.

---

## Example Playbook

```yaml
---
- hosts: mysql_cluster
  roles:
    - role: percona_server
      become: true
```

### With Vault-encrypted passwords

```yaml
# group_vars/mysql_cluster/vars.yml
replication: true
backup: true
mysql_server_id: "{{ hostvars[inventory_hostname]['mysql_server_id'] }}"

# group_vars/mysql_cluster/vault.yml  (ansible-vault encrypted)
mysql_root_password: "YourStrongRootPassword!"
mysql_replication_user:
  name: replicator
  password: "YourReplicationPassword!"
mysql_backup_user:
  name: xtrabackup
  password: "YourBackupPassword!"
mysql_exporter_db_password: "YourExporterPassword!"
```

---

## Usage

```shell
# Full role execution
ansible-playbook -i hosts site.yml

# Configuration only (skip installation)
ansible-playbook -i hosts site.yml -e "mysql_install_packages=false"

# Create/update users only
ansible-playbook -i hosts site.yml --tags "create_user"

# Create databases only
ansible-playbook -i hosts site.yml --tags "create_database"

# Deploy/update metrics exporter only
ansible-playbook -i hosts site.yml --tags "mysql_metrics"

# Disable exporter installation
ansible-playbook -i hosts site.yml -e "mysql_metrics_enabled=false"
```

---

## Backup & Restore

See **[BackupNRestore.md](./BackupNRestore.md)** for step-by-step backup and restore procedures using Percona XtraBackup with AES-256 encryption.

> **Important:** The encryption key (`/backups/mysql/encryption_key`) is generated **once** on first run and preserved on subsequent runs. Back it up securely — without it, encrypted backups cannot be restored.

---

## References

- *[Percona XtraBackup Documentation](https://docs.percona.com/percona-xtrabackup/latest/)*
- *[Setup Slave for Replication](https://www.percona.com/doc/percona-xtrabackup/2.3/howtos/setting_up_replication.html)*
- *[Configure Percona XtraBackup on Ubuntu](https://www.digitalocean.com/community/tutorials/how-to-configure-mysql-backups-with-percona-xtrabackup-on-ubuntu-16-04)*
- *[Stay Away Replication Lag](https://blog.opstree.com/2019/03/26/stay-away-replication-lag/)*
- *[MySQL Monitoring](https://blog.opstree.com/2019/07/23/mysql-monitoring/)*
- *[Encrypt MySQL Data at Rest](https://blog.opstree.com/2019/09/24/mysql-data-at-rest-encryption/)*
- *[Setting up MySQL Monitoring with Prometheus](https://blog.opstree.com/2018/12/11/setting-up-mysql-monitoring-with-prometheus/)*

---

## Author

**[Abhishek Dubey](abhishek.dubey@opstree.com)**

**[Abhishek Vishwakarma](abhishek.vishwakarma@opstree.com)**
