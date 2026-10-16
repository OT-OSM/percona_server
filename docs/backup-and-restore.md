# Backup and restore

```mermaid
flowchart LR
  F[Full] --> I1[Incremental 1] --> I2[Incremental 2]
  I2 --> V[Validate manifests / LSN / checksums]
  V --> P[Prepare independent working copies]
  P --> T[Stop isolated target / preserve old data]
  T --> R[Copy back / new UUID / verify]
```

## First backup

Set the backup Vault credential, select `backup_sources`, and run `playbooks/backup.yml`. Then on the source:

```bash
sudo /usr/local/bin/percona-backup backup full
sudo /usr/local/bin/percona-backup backup incremental
```

Incrementals require a completed previous backup from the same server UUID. Files are uncompressed XtraBackup directories, so there is no misleading `.gz` extension or codec mismatch. Budget space for local chains, restore copies, and the preserved old datadir.

Each completed directory has `data/`, `manifest.json`, `_SUCCESS.json`, and `backup.log`. `state.json` advances atomically only after success. A failed backup/upload leaves state unchanged; incomplete directories are never eligible for restore. Full and incremental runs share a lock.

## MinIO

Configure an existing bucket, scoped credentials, trusted HTTPS endpoint and a pinned `mc` URL/checksum. The role does not install a MinIO server. Artifacts are under `<bucket>/<inventory-host>/<backup-id>/`. Download the entire chain into `backup_path` before restore. Only backups with a valid final success marker qualify. Local staging remains after upload.

**Retention is intentionally manual:** the old bucket-wide age deletion was unsafe and has been removed. Keep each full plus every dependent incremental together. Monitor disk/object capacity; do not delete the currently referenced chain. Automated chain-aware retention and off-host binlog PITR are separate follow-ups.

## Isolated restore

Provision an isolated target with the server role and copy/download the selected chain there. The restore play installs its own tooling without needing a backup account on the unseeded target. Put it in `restore_targets`, then run:

```bash
ansible-playbook playbooks/restore.yml --ask-vault-pass --limit restore1 \
  -e backup_restore_target=restore1 \
  -e backup_restore_id=REPLACE_WITH_BACKUP_ID \
  -e backup_restore_workdir=/var/tmp/percona-restore-001
```

The play rejects the declared primary and existing replication channels. It verifies/prepares copies first, then stops MySQL, moves its old datadir aside, copies back, creates a new UUID, starts read-only with automatic replication suppressed, clears any copied channel metadata on this isolated copy, records missing backup GTIDs without resetting history, and checks connectivity. Keep source credentials available: physical restore includes the source's MySQL account tables.

If copy-back/start fails, the original data remains at `/var/lib/mysql.before-<timestamp>`. Investigate before retrying; no automatic destructive rollback is attempted. Verify application rows and schema separately. Syntax and fixture tests do not establish that a live backup is restorable.

[Percona 8.0 GTID replica recovery reference](https://docs.percona.com/percona-xtrabackup/8.0/create-gtid-replica.html). The new workflow adds only missing backup GTIDs; it does not reset existing executed history.

General restore targets remain read-only behind `/etc/mysql/mysql.conf.d/zz-percona-restore.cnf`. Keep them isolated while verifying data. A production cutover requires deliberate topology/configuration reconciliation; the restore play never makes the target an application writer. The replica attachment play removes this startup guard only after successful replication validation and a read-only baseline check.
