# percona_backup

Back up a selected node with XtraBackup 8.4.

```mermaid
flowchart LR
  D[Database] --> B[Full / incremental] --> L[Local staging] --> M[Optional MinIO]
```

The existing backup engine keeps chain metadata and prepares working copies. Default scheduling is daily full backups in the lab inventory. Restore is a separate explicit playbook, never part of normal setup. No retention deletion or PITR automation yet.

```yaml
backup_schedule_enabled: true
backup_storage: local
backup_path: /var/backup/mysql
```

```bash
ansible-playbook -i inventories/lab/ha.yml playbooks/backup.yml --ask-vault-pass
```

[Defaults](defaults/main.yml) · [Tasks](tasks/main.yml) · [Project setup](../../README.md)
