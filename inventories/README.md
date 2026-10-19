# Pick one inventory

An inventory is just your server list. These four files are **alternative setups**, not four groups you must deploy together.

| What you want | Edit this file | Servers |
|---|---|---|
| Standalone + backups + monitoring | `standalone.yml` | 1 database |
| Group Replication + two proxies | `group-two-proxies.yml` | 3 databases + 2 ProxySQL |
| Migrate your existing standalone | `migrate.yml` | Existing db1 + 2 fresh databases + 2 ProxySQL |
| Group Replication + one proxy | `group-one-proxy.yml` | 3 databases + 1 ProxySQL |

Replace `ansible_host` with your VM IPs. `db1`, `db2`, `db3`, `proxy1` and `proxy2` are labels for those VMs. Keep database IDs unique.

The same database appears under `database`, `backup_sources` or `monitoring_targets` because those groups select its jobs. It does **not** create another VM.

## Shared settings

- `group_vars/all/main.yml`: SSH user, database settings, database names and backup settings.
- `group_vars/all/vault.yml`: your encrypted passwords; never distributed in the collection.
- `group_vars/all/vault.example.yml`: password key names to fill.
- `group_vars/proxies.yml`: application accounts and optional two-proxy VIP.

These settings apply to whichever inventory you choose. For a different client, copy this directory into a separate client directory and use separate passwords/settings.

Always pass **one file**, for example `-i inventories/standalone.yml`. Do not pass `-i inventories/`, because that combines alternative inventories.

[Four deployment commands](../docs/deployment-runbook.md)
