# proxysql

Route application traffic to the group writer.

```mermaid
flowchart LR
  A[Application :6033] --> P[ProxySQL] --> W[Current writer]
```

Uses native Group Replication monitoring and caching_sha2_password accounts. All traffic starts on the writer; read rules are optional. Both proxies receive the same inventory settings. Admin listens on localhost:6032.

DNS names are supported for inventory hosts. Each proxy automatically detects
its IPv4 source address toward the current writer and uses it for both monitor
and application account grants. Detection runs on the proxy, not the controller.
It selects a route without sending database credentials or a network probe packet.

For NAT, IPv6-only networks, or routes that use different source addresses for
different database members, set `proxysql_source_address` per proxy to an account
host value that matches the source MySQL actually sees. A hostname is unsuitable
with the server's `skip-name-resolve` setting. Rerun the proxy playbook after an IP
change; old account host entries are not automatically deleted.

```yaml
proxysql_listen_address: '0.0.0.0'
proxysql_query_rules: []
```

```bash
ansible-playbook -i inventories/group-two-proxies.yml playbooks/operations/proxysql.yml --ask-vault-pass
```

[Defaults](defaults/main.yml) · [Tasks](tasks/main.yml) · [Project setup](../../README.md)
