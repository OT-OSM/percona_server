[![Apache License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/OT-OSM/mysql)

[![Opstree Solutions][opstree_avatar]][opstree_homepage]<br/>[Opstree Solutions][opstree_homepage]

  [opstree_homepage]: https://opstree.github.io/
  [opstree_avatar]: https://img.cloudposse.com/150x150/https://github.com/opstree.png

# OSM: Percona

A high end ansible role to setup Percona server version 5.7 or greater with best practices in terms of security and performance tunning.

## Key Features

- [X] Best Practices(Performance Tunning)
- [X] Backup Server Management
- [X] Database and User Management

## Requirements

No special requirement, only root access of the server is required.

## Role Variables

We have categorized variables into two part i.e. **[Manadatory]()** and **[Optional]()**

#### Mandatory Variables

|**Variable**|**Default Value**|**Possible Values**|**Description**|
|------------|-----------------|-------------------|---------------|
|mysql_root_username| `root` | *Root Username* | Name of the admin user of MySQL |
|mysql_root_password| `N0Tweak$_@123!` | *Any Strong Password* | A strong password for MySQL root user |
|mysql_replication_user.name | `slave` | *Any Username* | Name of the slave user |
|mysql_replication_user.password | `slaveMaster@123!` | *Any Strong Password* | A strong password for MySQL Slave |
|mysql_backup_user.name | `backup` | *Any Username* | Name of the Percona xtrabackup user |
|mysql_backup_user.password | `backUpMaster@123!` | *Any Strong Password* | A strong password for Percona xtrabackup user |
|mysql_install_packages | `true` | true or false | Whether you want to install MySQL packages. Set the value false if you need only configuration part |
|replication | `true` | true or false | If you don't want to setup slave, set the value false |
|backup | `true` | true or false | If you don't want to setup backup server, set the value false |
|users_creation | `true` | true or false | Whether you want to include tasks for user creation or not |
|database_creation | `true` | true or false | Whether you want to include tasks for database creation or not |

#### Optional Variables

|**Variable**|**Default Value**|**Possible Values**|**Description**|
|------------|-----------------|-------------------|---------------|
|mysql_config_file| `/etc/mysql/percona-server.conf.d/mysqld.cnf` | *Any Linux Path* | Configuration file location of MySQL |
|mysql_slow_query_log_file | `/var/log/mysql/mysql-slow.log` | *Any Linux Path* | Log file location of MySQL slow query |
|mysql_log_error | `/var/log/mysql/mysql.err` | *Any Linux Path* | Log file location of MySQL errors |
|mysql_max_binlog_size | `100M` | *Size in MB* | Maximum size of bin log files in MySQL |
|mysql_binlog_format | `MIXED` | ROW or COLOUMN or MIXED | Binlog format of MySQL |
|version | 5.7 | *MySQL Version greater than 5.7* | Which version of MySQL you want to install on Debian System |

The rest of the things are in [defaults](./defaults/main.yml)

## Inventory

An example inventory could be like this:-

```ini
[master]
master_server1

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
**`Note:`**
- ***Leave blank `master` and `slave` if you want to setup standalone server.***

- ***Define `mysql_backup_server` if you want server work as backup server***


## Example Playbook

Here is an example of playbook to execute this role:-

```yaml
---
- hosts: mysql_cluster
  roles:
    - role: percona_server
      become: yes
```

## Usage

There are multiple ways of executing the playbook according to your environment

- To run complete role

```shell
ansible-playbook -i hosts site.yml
```

- To create users

```shell
ansible-playbook -i hosts site.yml --tags "create_user"
```

- To create databases

```shell
ansible-playbook -i hosts site.yml --tags "create_database"
```
- [To perform backup and restore with Backup Server](./BackupNRestore.md)

## References

- *[Steps for Backup and Restore operations with Backup Server](./BackupNRestore.md)*

- *[Setup Slave for Replication](https://www.percona.com/doc/percona-xtrabackup/2.3/howtos/setting_up_replication.html)* 

- *[Configure Percona xtrabackup ubuntu](https://www.digitalocean.com/community/tutorials/how-to-configure-mysql-backups-with-percona-xtrabackup-on-ubuntu-16-04)*


Here we do have some of our OpsTree blog's regarding MySQL.

- *[Stay Away Replication Lag](https://blog.opstree.com/2019/03/26/stay-away-replication-lag/)*

- *[Mysql Monitoring](https://blog.opstree.com/2019/07/23/mysql-monitoring/)*

- *[Encrypt Mysql data at rest](https://blog.opstree.com/2019/09/24/mysql-data-at-rest-encryption/)*

- *[Setting up Mysql Monitoring with Prometheus](https://blog.opstree.com/2018/12/11/setting-up-mysql-monitoring-with-prometheus/)*

## Author

**[Abhishek Dubey](abhishek.dubey@opstree.com)**

**[Abhishek Vishwakarma](abhishek.vishwakarma@opstree.com)**
