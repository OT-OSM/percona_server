# Standalone verification runbook — Percona 8.0

Run after `playbooks/standalone.yml` completes successfully. Compare results with your inventory overrides; expected values below describe the default writable standalone setup. Commands are read-only except the explicitly optional write test and Ansible rerun.

## 1. Linux terminal — service and storage

```bash
sudo systemctl is-active mysql
sudo systemctl is-enabled mysql
sudo systemctl status mysql --no-pager
sudo ss -lntp '( sport = :3306 )'
df -h /var/lib/mysql
df -i /var/lib/mysql
free -h
sudo stat -c '%U:%G %a %n' /var/lib/mysql
```

Expected: `active`, `enabled`, MySQL listening on the configured IP/port, available disk space/inodes and a mysql-owned datadir. Replace port 3306 if overridden. `127.0.0.1:3306` is local-only; a private IP binds that interface; `0.0.0.0:3306` listens on all IPv4 interfaces but does not grant login access. A listener check does not test remote firewall access.

## 2. Linux terminal — log in locally

```bash
mysql --protocol=SOCKET --socket=/var/run/mysqld/mysqld.sock -u root -p
```

Enter the MySQL root password at the prompt, not the Vault unlock password. Substitute the socket if overridden. Run subsequent SQL inside this client; do not paste the `mysql>` prompt itself.

## 3. MySQL — identity and effective configuration

```sql
SELECT VERSION() AS version, @@version_comment AS vendor,
       @@hostname AS hostname, @@server_id AS server_id,
       @@server_uuid AS server_uuid;

SHOW GLOBAL VARIABLES WHERE Variable_name IN
  ('datadir', 'socket', 'port', 'bind_address', 'read_only', 'super_read_only');

SELECT USER() AS connection_identity, CURRENT_USER() AS authenticated_account;
```

Expected: Percona Server 8.0.x, server ID matching inventory (sample db1: 101), a nonempty UUID, `/var/lib/mysql/`, your configured address/port/socket, and both read-only flags OFF. Local root login should authenticate as `root@localhost` with the default administrator name.

## 4. MySQL — connection limits versus current usage

```sql
SHOW GLOBAL VARIABLES LIKE '%connection%';
SHOW GLOBAL VARIABLES WHERE Variable_name IN ('max_connections', 'max_user_connections');
SHOW GLOBAL STATUS WHERE Variable_name IN
  ('Threads_connected', 'Threads_running', 'Max_used_connections',
   'Connections', 'Aborted_connects', 'Connection_errors_max_connections', 'Uptime');
SHOW FULL PROCESSLIST;
```

| Result | Interpretation |
|---|---|
| max_connections | Configured classic-protocol limit; default 150, not the current connection count |
| max_user_connections = 0 | No global per-account limit from this setting; account-specific limits and the server-wide limit still apply |
| mysqlx_max_connections | Separate X Protocol setting, not the classic port-3306 limit |
| Threads_connected | Connections currently open, including your verification session |
| Threads_running | Threads that are not sleeping; varies with workload |
| Max_used_connections | Peak simultaneous connections since startup or relevant counter reset; compare with the configured limit |
| Connections | Cumulative connection attempts, not currently connected clients |
| Aborted_connects | Failed connection attempts; an earlier incorrect password can increase it |
| Connection_errors_max_connections | Refusals because the connection limit was reached; investigate increases |
| Uptime | Server uptime in seconds; an unexpected reset suggests a restart |

`SHOW GLOBAL VARIABLES` displays settings; `SHOW GLOBAL STATUS` displays runtime measurements. The syntax is `SHOW ... VARIABLES`, not `SELECT variables LIKE ...`. Large connection-memory limits in the broad output are not evidence that that much RAM has been allocated. Process lists can contain application SQL; redact before sharing.

## 5. MySQL — memory and durability

```sql
SELECT @@global.innodb_buffer_pool_size AS buffer_pool_bytes,
       ROUND(@@global.innodb_buffer_pool_size / 1024 / 1024, 0) AS buffer_pool_MiB,
       @@global.max_connections AS max_connections;

SHOW GLOBAL VARIABLES WHERE Variable_name IN
  ('innodb_buffer_pool_instances', 'innodb_buffer_pool_chunk_size',
   'innodb_log_buffer_size', 'tmp_table_size', 'max_heap_table_size',
   'sort_buffer_size', 'read_buffer_size', 'read_rnd_buffer_size',
   'join_buffer_size', 'thread_cache_size', 'table_open_cache', 'key_buffer_size',
   'innodb_flush_log_at_trx_commit', 'sync_binlog');

SHOW GLOBAL STATUS WHERE Variable_name IN
  ('Innodb_buffer_pool_reads', 'Innodb_buffer_pool_read_requests',
   'Innodb_buffer_pool_pages_free', 'Innodb_log_waits');
```

Expected: buffer pool matches your explicit override or the rounded RAM calculation in [memory sizing](memory-sizing.md); `innodb_flush_log_at_trx_commit=1` and `sync_binlog=1`. Other buffers/caches use engine defaults unless separately configured. Counter increases should be evaluated over representative load; a new empty server cannot establish adequate sizing, and buffer-pool size is not total MySQL memory usage.

## 6. MySQL — ready for replication, but not yet a replica

```sql
SHOW GLOBAL VARIABLES WHERE Variable_name IN
  ('gtid_mode', 'enforce_gtid_consistency', 'log_bin', 'binlog_format',
   'log_replica_updates', 'binlog_expire_logs_seconds');
SHOW BINARY LOGS;
SHOW REPLICA STATUS\G
```

Expected: GTID ON, consistency ON, binary logging ON, ROW format, replica updates ON and retention matching inventory (default 604800 seconds / 7 days). Binary logs should exist. **`SHOW REPLICA STATUS` returning an empty set is correct for this standalone server**; enabling GTID/binlogs does not attach a replica. These checks do not verify backups or guarantee recoverability.

## 7. MySQL — schemas, accounts and access

```sql
SHOW DATABASES;
SELECT User, Host, plugin, account_locked FROM mysql.user ORDER BY User, Host;
SELECT User, Host FROM mysql.user WHERE User = '' OR (User = 'root' AND Host <> 'localhost');
SHOW GRANTS FOR CURRENT_USER;
SHOW GLOBAL VARIABLES WHERE Variable_name IN
  ('skip_name_resolve', 'local_infile', 'require_secure_transport');
```

Expected: any configured databases exist; empty `percona_databases` creates no application schema. Internal MySQL accounts are normal. With the default root name and no explicit remote-root override in `percona_users`, the anonymous/remote-root query should return no rows. `skip_name_resolve=ON` and `local_infile=OFF`; `require_secure_transport` follows inventory and is OFF by default, so passing baseline checks is not proof that network encryption is enforced.

If you created the example application account, replace its name/client IP as needed:

```sql
SHOW GRANTS FOR 'appuser'@'192.168.1.20';
```

Expected: the intended schema/table privileges and no unexpected global privileges; `USAGE ON *.*` alone does not grant global data access. If the account was not configured, an account-not-found error is expected.

## 8. Optional — test access from the actual application machine

Run in that machine's terminal, using the real database IP and configured account/schema:

```bash
mysql --protocol=TCP -h 192.168.1.10 -P 3306 -u appuser -p appdb
```

Then inside MySQL:

```sql
SELECT CURRENT_USER(), DATABASE(), @@hostname, @@read_only;
SHOW SESSION STATUS LIKE 'Ssl_cipher';
```

Expected: the intended account/schema/server and read_only=0. If TLS is required, use `--ssl-mode=VERIFY_IDENTITY --ssl-ca=/path/to/ca.pem` and a server hostname/IP covered by the certificate; expect a nonempty cipher. Root remote login is not an acceptance requirement. Connection refusal/timeout points toward the listener/network; access denied points toward account matching, credentials or authentication requirements.

## 9. Optional — isolated write/read test

This section creates data and is not a read-only check. Run locally as root using the reserved test name below; if the schema already exists, stop and choose another name rather than touching its contents. Execute each statement only after the previous one succeeds.

```sql
CREATE DATABASE percona_standalone_verify;
CREATE TABLE percona_standalone_verify.probe (id INT PRIMARY KEY, message VARCHAR(80)) ENGINE=InnoDB;
INSERT INTO percona_standalone_verify.probe VALUES (1, 'standalone write/read OK');
SELECT * FROM percona_standalone_verify.probe;
```

Expected: exactly the inserted row. After checking, remove only the test schema you just created:

```sql
DROP DATABASE percona_standalone_verify;
```

## 10. Logs and repeat-run check

Inside MySQL:

```sql
SHOW GLOBAL VARIABLES WHERE Variable_name IN
  ('log_error', 'slow_query_log', 'slow_query_log_file', 'long_query_time');
SHOW ENGINE INNODB STATUS\G
```

Expected: slow logging ON, threshold matching inventory (default 2 seconds) and configured log paths. Review InnoDB output for current problems; a historical deadlock entry alone does not mean startup failed.

Exit the MySQL client with `exit`, then run in the Linux terminal:

```bash
sudo journalctl -u mysql --since '30 minutes ago' --no-pager
sudo tail -n 100 /var/log/mysql/error.log
sudo systemctl show mysql -p MainPID -p ActiveEnterTimestamp
```

Investigate startup failures, crash recovery loops, permission failures and unexpected shutdowns; redact logs before sharing. Use the queried log path if customized.

For a deliberate idempotency check, record the service PID/start timestamp, then rerun from the repository root with unchanged inventory (this is a real configuration run):

```bash
ansible-playbook -i inventories/lab/hosts.yml playbooks/standalone.yml --ask-vault-pass --ask-become-pass
sudo systemctl show mysql -p MainPID -p ActiveEnterTimestamp
```

Expected: failed=0, unreachable=0, no unexpected database/account/config changes and no database restart when nothing relevant changed; package metadata refresh can still report changes. Omit the become prompt for passwordless sudo. Inspect unexpected changes rather than repeating runs blindly.

Record the play recap, server version/identity, effective settings, connectivity result and any unresolved errors. Restart/reboot persistence tests need a planned interruption; basic health checks do not replace [live production acceptance](validation.md).

References: [MySQL 8.0 status variables](https://dev.mysql.com/doc/refman/8.0/en/server-status-variables.html), [SHOW REPLICA STATUS](https://docs.oracle.com/cd/E17952_01/mysql-8.0-en/show-replica-status.html).
