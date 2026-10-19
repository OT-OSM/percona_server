# proxysql

Route application traffic to the group writer.

```mermaid
flowchart LR
  A[Application :6033] --> P[ProxySQL] --> W[Current writer]
```

Uses native Group Replication monitoring and caching_sha2_password accounts. All traffic starts on the writer; read rules are optional. Both proxies receive the same inventory settings. Admin listens on localhost:6032.

```yaml
proxysql_listen_address: '0.0.0.0'
proxysql_query_rules: []
```

```bash
ansible-playbook -i inventories/group-two-proxies.yml playbooks/operations/proxysql.yml --ask-vault-pass
```

[Defaults](defaults/main.yml) · [Tasks](tasks/main.yml) · [Project setup](../../README.md)
