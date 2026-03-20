# Trinity PostgreSQL Extension - Troubleshooting Guide

Common issues and solutions for the Trinity extension.

## Installation Issues

### Extension Not Found

**Symptoms:**
```
ERROR: extension "trinity" does not exist
```

**Solutions:**

1. **Check PostgreSQL version:**
   ```sql
   SELECT version();
   ```
   *Must be PostgreSQL 12.0+*

2. **Verify extension files:**
   ```bash
   ls -la /usr/share/postgresql/extension/trinity*
   ```

3. **Check file permissions:**
   ```bash
   sudo chmod 644 /usr/share/postgresql/extension/trinity*
   ```

4. **Restart PostgreSQL:**
   ```bash
   sudo systemctl restart postgresql
   ```

### Permission Denied

**Symptoms:**
```
ERROR: permission denied for schema trinity
```

**Solutions:**

1. **Install as superuser:**
   ```bash
   sudo -u postgres psql -d your_db -c "CREATE EXTENSION trinity;"
   ```

2. **Grant permissions:**
   ```sql
   GRANT USAGE ON SCHEMA trinity TO your_user;
   GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA trinity TO your_user;
   GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA trinity TO your_user;
   ```

## Runtime Issues

### Function Not Found

**Symptoms:**
```
ERROR: function trinity.allocate_pk(uuid, uuid) does not exist
```

**Solutions:**

1. **Check search path:**
   ```sql
   SHOW search_path;
   SET search_path TO public,trinity;
   ```

2. **Verify extension installation:**
   ```sql
   SELECT * FROM pg_extension WHERE extname = 'trinity';
   ```

3. **Try schema-qualified name:**
   ```sql
   SELECT trinity.allocate_pk('table', 'uuid'::UUID);
   ```

### Performance Issues

**Symptoms:**
- Slow PK allocation (>10ms)
- High memory usage
- Connection timeouts

**Solutions:**

1. **Check indexes:**
   ```sql
   SELECT * FROM pg_indexes WHERE schemaname = 'trinity';
   ```

2. **Analyze tables:**
   ```sql
   ANALYZE trinity.uuid_allocation_log;
   ANALYZE trinity.table_dependency_log;
   ```

3. **Increase memory settings:**
   ```sql
   SET work_mem = '256MB';
   SET maintenance_work_mem = '512MB';
   ```

4. **Monitor active queries:**
   ```sql
   SELECT * FROM pg_stat_activity WHERE state = 'active';
   ```

## Data Issues

### Foreign Key Violations

**Symptoms:**
```
ERROR: Missing foreign key: no allocation found for manufacturer UUID ...
```

**Solutions:**

1. **Allocate target records first:**
   ```sql
   -- Allocate manufacturer first
   SELECT trinity.allocate_pk('manufacturer', 'manufacturer-uuid'::UUID);

   -- Then resolve FK
   SELECT trinity.resolve_fk('model', 'manufacturer', 'manufacturer-uuid'::UUID);
   ```

2. **Check allocation exists:**
   ```sql
   SELECT trinity.diagnose_allocation('manufacturer', 'manufacturer-uuid'::UUID);
   ```

### Circular Dependencies

**Symptoms:**
```
ERROR: Circular dependency detected: model → manufacturer would create cycle
```

**Solutions:**

1. **Check dependency graph:**
   ```sql
   SELECT * FROM trinity.detect_circular_dependencies();
   ```

2. **Review FK relationships:**
   ```sql
   SELECT * FROM trinity.table_dependency_log ORDER BY source_table;
   ```

3. **Remove problematic relationships:**
   ```sql
   DELETE FROM trinity.table_dependency_log
   WHERE source_table = 'problematic_table';
   ```

### Duplicate Key Violations

**Symptoms:**
```
ERROR: duplicate key value violates unique constraint
```

**Solutions:**

1. **Check for existing allocation:**
   ```sql
   SELECT * FROM trinity.get_uuid_to_pk_mappings('table_name')
   WHERE uuid_value = 'problem-uuid'::UUID;
   ```

2. **Use idempotent operations:**
   ```sql
   -- allocate_pk is idempotent - safe to retry
   SELECT trinity.allocate_pk('table', 'uuid'::UUID);
   ```

## Multi-Tenant Issues

### Tenant Isolation Problems

**Symptoms:**
- Data leaking between tenants
- Incorrect PK values for tenant

**Solutions:**

1. **Verify tenant setting:**
   ```sql
   SHOW trinity.tenant_id;
   SET trinity.tenant_id = 'correct-tenant-uuid'::UUID;
   ```

2. **Check tenant-specific allocations:**
   ```sql
   SELECT * FROM trinity.allocation_stats('your-tenant'::UUID);
   ```

3. **Validate tenant isolation:**
   ```sql
   -- Should return different PKs
   SET trinity.tenant_id = 'tenant-a'::UUID;
   SELECT trinity.allocate_pk('test', 'shared-uuid'::UUID);

   SET trinity.tenant_id = 'tenant-b'::UUID;
   SELECT trinity.allocate_pk('test', 'shared-uuid'::UUID);
   ```

## CSV Processing Issues

### Malformed CSV

**Symptoms:**
```
ERROR: CSV must have at least header and one data row
```

**Solutions:**

1. **Check CSV format:**
   ```sql
   -- Valid format:
   -- id,name
   -- uuid1,value1
   -- uuid2,value2
   ```

2. **Validate UUIDs:**
   ```sql
   SELECT trinity._validate_uuid('your-uuid-string');
   ```

3. **Check line endings:**
   - Ensure consistent line endings (LF, not CRLF)
   - Remove trailing empty lines

### Memory Issues with Large CSV

**Symptoms:**
- Out of memory errors
- Slow processing

**Solutions:**

1. **Process in batches:**
   ```sql
   -- Split large CSV into chunks
   -- Process each chunk separately
   ```

2. **Increase memory:**
   ```sql
   SET work_mem = '1GB';
   ```

3. **Monitor progress:**
   ```sql
   SELECT COUNT(*) FROM trinity.uuid_allocation_log;
   ```

## Monitoring and Diagnostics

### Health Checks

```sql
-- Extension status
SELECT * FROM pg_extension WHERE extname = 'trinity';

-- Table sizes
SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del
FROM pg_stat_user_tables
WHERE schemaname = 'trinity';

-- Function usage
SELECT schemaname, funcname, calls, total_time/calls as avg_time
FROM pg_stat_user_functions
WHERE schemaname = 'trinity';
```

### Diagnostic Queries

```sql
-- Allocation overview
SELECT table_name, COUNT(*) as allocations,
       MIN(pk_value) as min_pk, MAX(pk_value) as max_pk
FROM trinity.uuid_allocation_log
GROUP BY table_name;

-- FK integrity check
SELECT trinity.check_fk_integrity('your_table');

-- Performance analysis
SELECT * FROM trinity.allocation_stats();
```

## Cloud-Specific Issues

### AWS RDS

**Connection limits:**
- Monitor connection count: `SELECT COUNT(*) FROM pg_stat_activity;`
- Use connection pooling

**Parameter groups:**
- Set `work_mem` and `maintenance_work_mem` appropriately
- Monitor CloudWatch metrics

### Azure Database

**Resource limits:**
- Monitor DTU usage
- Scale up if needed

**Extension permissions:**
- May require Azure support for custom extensions

### Heroku Postgres

**Connection limits:**
- Monitor connection count vs plan limits
- Use PgBouncer for connection pooling

**Maintenance:**
- Monitor database size and performance
- Scale up plan if needed

## Getting Help

### Debug Information

When reporting issues, include:

```sql
-- System information
SELECT version();
SELECT * FROM pg_extension WHERE extname = 'trinity';

-- Extension status
SELECT COUNT(*) FROM trinity.uuid_allocation_log;
SELECT COUNT(*) FROM trinity.table_dependency_log;

-- Recent errors
SELECT * FROM pg_log
WHERE message LIKE '%trinity%'
ORDER BY log_time DESC LIMIT 10;
```

### Support Channels

1. Check this troubleshooting guide
2. Review GitHub issues
3. Check recent commits for fixes
4. Contact the development team

---

**Version:** 1.0
**Last Updated:** 2026-01-03
