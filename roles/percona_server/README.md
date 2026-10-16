# percona_server

Install and configure Percona 8.4.

```mermaid
flowchart LR
  A[Packages] --> B[Local login] --> C[mysqld.cnf] --> D[Databases / users]
```

Owns MySQL configuration. Default data and binlog directory: `/var/lib/mysql`. Group settings are enabled by membership in `gr_members`. Application definitions are applied once after the group forms.

```yaml
percona_max_connections: 150
percona_innodb_buffer_pool_size: 2G
```

```bash
ansible-playbook -i inventories/lab/hosts.yml playbooks/standalone.yml --ask-vault-pass
```

[Defaults](defaults/main.yml) · [Tasks](tasks/main.yml) · [Project setup](../../README.md)
