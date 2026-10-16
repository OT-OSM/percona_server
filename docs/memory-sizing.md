# Automatic memory sizing

The server role calculates the InnoDB buffer pool from `ansible_facts.memtotal_mb` on each playbook run. The default is **50%**, rounded down with a 128M minimum. Below 1 GiB, rounding uses 128 MiB steps; larger pools use 1 GiB steps to match default Linux 8.0 chunk/instance alignment. For example, 70% of 8 GiB produces a 5120M pool after rounding. This is a starting policy, not a performance guarantee or a total MySQL memory cap.

| Detected RAM | Default buffer pool | Default connection limit |
|---|---|---|
| 2 GiB | 1024M | 150 |
| 4 GiB | 2048M | 150 |
| 8 GiB | 4096M | 150 |
| 16 GiB | 8192M | 150 |
| Facts unavailable | 512M | 150 |

Actual VM memory facts can be slightly below the advertised size. Nondefault chunk/instance settings or an explicit pool override can cause MySQL to adjust the requested pool further. Verify `SELECT @@innodb_buffer_pool_size, @@max_connections;` after deployment.

Put overrides in `inventories/lab/host_vars/db1.yml` (or the equivalent production inventory), not in role defaults:

```yaml
# Dedicated database host, after reviewing OS/backup/concurrency headroom:
percona_buffer_pool_percent: 70

# Or pin an exact pool instead of calculating it:
# percona_innodb_buffer_pool_size: "4G"

# Shared host / container: replace host RAM with a smaller sizing budget.
# Example: a 4096 MiB budget gives a 2048M pool at the default 50%.
# percona_memory_mb: 4096

# Set from application pool size, measured concurrency and available memory:
# percona_max_connections: 100
```

An explicit pool value takes precedence over the percentage formula. Without facts the sizing input is 1024 MiB; this preserves the earlier 512M default. This fallback is not proof that the host has sufficient memory. Facts do not automatically account for cgroup limits or co-located services. Use the smaller budget or a fixed pool for those environments.

## Why only the buffer pool scales automatically

| Proposed setting | Current approach and reason |
|---|---|
| Buffer pool = 70% RAM | Default 50%; configurable up to 75% for this automatic policy. More headroom for unknown workloads and co-located processes. |
| Connections = 20% of RAM in MiB | Keep 150; the formula would allow 3,276 connections on 16 GiB regardless of CPU or query cost. |
| Sort/read/join buffers = RAM percentages | Keep engine defaults. Concurrent queries can allocate their own buffers, sometimes more than one per query. |
| Temporary tables = RAM percentage | Keep engine defaults; temporary-table allocation is workload- and 8.0-minor-dependent. |
| Log buffer = 2% RAM | Keep engine default; tune from transaction sizes and observed log waits. |
| Redo log file = 25% pool | Keep engine default; redo files are disk capacity, not a RAM reservation. Tune from redo generation/checkpoint pressure. From 8.0.30, `innodb_redo_log_capacity` supersedes the older file-size settings. |
| Thread/table caches | Keep engine defaults; tune from thread creation, table count and cache misses. |
| MyISAM key buffer = 5% RAM | Keep engine default; an InnoDB workload does not justify proportional MyISAM allocation. |

The variables from the old all-in-one role are not automatically supported by the new template. Only the memory inputs above and `percona_max_connections` are wired here; adding unused variables to inventory has no effect.

Changing RAM, the percentage or an explicit pool changes the generated configuration on the next server play and can trigger its normal restart. To retain the previous fixed behavior on an existing host, set `percona_innodb_buffer_pool_size: "512M"` before that run. Optional component playbooks do not reapply server sizing.

Before increasing limits, measure peak resident memory, swap/OOM events, active connections, query latency and backup-time headroom. RAM alone cannot label a host “production” or “high traffic.”

References: [MySQL 8.0 memory allocation](https://dev.mysql.com/doc/refman/8.0/en/memory-use.html), [8.0 dedicated-server sizing and redo-version differences](https://dev.mysql.com/doc/refman/8.0/en/innodb-dedicated-server.html), [buffer-pool instances and chunk alignment](https://dev.mysql.com/doc/refman/8.0/en/innodb-parameters.html).
