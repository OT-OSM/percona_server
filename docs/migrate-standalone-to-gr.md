# Migrate standalone to Group Replication

Turn an existing standalone Percona 8.4 server into a 3-node Group Replication
group without losing data. The standalone becomes the seed (PRIMARY); two
fresh servers join as SECONDARY members.

## When to use this

A client started on `playbooks/standalone.yml` and now needs high
availability. Do not use this to merge two live databases; it is a
one-to-three promotion, not a data merge.

## Prerequisites

- The standalone runs Percona 8.4 (built by this repo, or meeting the checks below).
- Two fresh Ubuntu 24.04 servers with no MySQL data.
- A maintenance window. The seed's MySQL restarts once (1-3 minutes, no writes possible during it).
- `playbooks/operations/backup.yml` has been run against the standalone before, so `/usr/local/bin/percona-backup` exists there.

## What the checks enforce

`playbooks/migrate.yml` refuses to start when any of these fail, and
tells you exactly what to fix:

- GTID mode is ON and binlog format is ROW.
- Every user table is InnoDB.
- Every user table has a primary key.
- Backup tooling exists on the seed, then a full safety backup is taken automatically.

If GTID is OFF on a foreign standalone, enable it first with the stepped
procedure (OFF to OFF_PERMISSIVE to ON_PERMISSIVE to ON) and let it settle
before migrating. That step is deliberately not automated.

## Run it

```bash
# 1. Copy the migration inventory and fill in real IPs.
#    The standalone MUST be first in gr_members.
cp inventories/migrate.yml inventories/migrate-prod.yml

# 2. Fresh group UUID for the new group.
python3 -c 'import uuid; print(uuid.uuid4())'
# put it in inventories/group_vars/all/main.yml as percona_group_name

# 3. Preflight, migrate, verify.
ansible-playbook -i inventories/migrate-prod.yml playbooks/operations/preflight.yml --ask-vault-pass
ansible-playbook -i inventories/migrate-prod.yml playbooks/migrate.yml --ask-vault-pass
ansible-playbook -i inventories/migrate-prod.yml playbooks/operations/verify.yml --ask-vault-pass
```

## What happens, step by step

1. Preflight checks all three servers (OS, memory, disk, UUID, unique server ids, secrets, SSH between members).
2. The seed is checked for GR eligibility and a full backup is taken.
3. All three servers get the Group Replication configuration; the seed's MySQL restarts once.
4. The group bootstraps on the seed with its existing data. Nothing is reloaded; the data stays where it is.
5. The two fresh members join through distributed recovery and catch up from the seed's binlogs.
6. ProxySQL is configured against the group, backups move to db3 (a secondary), exporters start everywhere.

## After migration

- Switch daily operations to the `group-two-proxies.yml` inventory layout (same hosts, `backup_sources` on a secondary).
- Run the failover drill from `docs/operations.md` before calling it production.
- The pre-migration full backup stays on the seed; keep it until the first post-migration backup succeeds.

## Rollback

If the migration fails before bootstrap, the seed is still a standalone with
its original data plus a new my.cnf. Restore the pre-migration backup to a
fresh VM with `playbooks/operations/restore.yml` and repoint the application. The
automatic safety backup from step 2 is the rollback source.
