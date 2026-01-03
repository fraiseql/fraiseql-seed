# Trinity PostgreSQL Extension - Installation Guide

The Trinity extension provides UUID→INTEGER primary key transformation capabilities for PrintOptim Forge → FraiseQL data pipelines.

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Verification](#verification)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Cloud Deployment](#cloud-deployment)

## Requirements

### PostgreSQL Version
- **Minimum:** PostgreSQL 12.0
- **Recommended:** PostgreSQL 13.0+
- **Tested:** PostgreSQL 12.0 - 18.x

### System Requirements
- **Memory:** 512MB minimum, 2GB recommended
- **Disk:** 100MB for extension files
- **Privileges:** Database superuser for installation

### Dependencies
- PostgreSQL development headers (for compilation)
- Standard PostgreSQL extensions (automatically handled)

## Installation

### Method 1: Automatic (Recommended)

If using FraiseQL-Seed, the extension is installed automatically:

```bash
# FraiseQL-Seed handles installation
pip install fraiseql-seed
fraiseql-seed init --database-url="postgresql://user:pass@localhost/db"
```

### Method 2: Manual Installation

1. **Copy extension files:**
   ```bash
   # Copy to PostgreSQL extension directory
   sudo cp extensions/trinity/trinity--1.0.sql /usr/share/postgresql/extension/
   sudo cp extensions/trinity/trinity.control /usr/share/postgresql/extension/
   ```

2. **Install in database:**
   ```sql
   -- Connect to your database
   psql -d your_database

   -- Install the extension
   CREATE EXTENSION trinity;
   ```

### Method 3: Docker Installation

```dockerfile
# Add to your Dockerfile
COPY extensions/trinity/ /usr/share/postgresql/extension/
RUN chmod 644 /usr/share/postgresql/extension/trinity*
```

## Verification

After installation, verify the extension is working:

```sql
-- Check extension is installed
SELECT * FROM pg_extension WHERE extname = 'trinity';

-- Test basic functionality
SELECT trinity.allocate_pk('test', '550e8400-e29b-41d4-a716-446655440000'::UUID, 'tenant-123'::UUID);

-- Should return: 1

-- Test identifier generation
SELECT trinity.generate_identifier('Hewlett Packard Inc.');

-- Should return: hewlett-packard-inc
```

## Configuration

### Tenant ID Setting

For multi-tenant applications, set the tenant ID:

```sql
-- Set tenant ID for current session
SET trinity.tenant_id = 'your-tenant-uuid'::UUID;

-- Or set globally (requires superuser)
ALTER SYSTEM SET trinity.tenant_id = 'your-tenant-uuid';
```

### Performance Tuning

```sql
-- Increase work memory for large transformations
SET work_mem = '256MB';

-- Increase maintenance work memory for index creation
SET maintenance_work_mem = '512MB';
```

### Connection Settings

```sql
-- For high-throughput scenarios
SET statement_timeout = '300s';  -- 5 minutes
SET idle_in_transaction_session_timeout = '60s';
```

## Troubleshooting

### Extension Not Found

**Error:** `ERROR: extension "trinity" does not exist`

**Solutions:**
1. Check PostgreSQL version: `SELECT version();`
2. Verify files are in correct location: `ls /usr/share/postgresql/extension/trinity*`
3. Check permissions: `ls -la /usr/share/postgresql/extension/`
4. Restart PostgreSQL if files were added after startup

### Permission Denied

**Error:** `ERROR: permission denied for schema trinity`

**Solutions:**
1. Install as superuser or database owner
2. Grant necessary permissions:
   ```sql
   GRANT USAGE ON SCHEMA trinity TO your_user;
   GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA trinity TO your_user;
   ```

### Function Not Found

**Error:** `ERROR: function trinity.allocate_pk(uuid, uuid) does not exist`

**Solutions:**
1. Verify extension is installed: `SELECT * FROM pg_extension;`
2. Check search path: `SHOW search_path;`
3. Try with schema prefix: `SELECT trinity.allocate_pk(...);`

### Performance Issues

**Slow allocations:**
- Check indexes: `SELECT * FROM pg_indexes WHERE schemaname = 'trinity';`
- Analyze tables: `ANALYZE trinity.uuid_allocation_log;`
- Increase work_mem

**Memory issues:**
- Monitor memory usage: `SELECT * FROM pg_stat_activity;`
- Adjust work_mem and maintenance_work_mem
- Consider batch processing for large datasets

## Cloud Deployment

### AWS RDS

```bash
# Custom parameter group settings
rds-modify-db-parameter-group \
  --db-parameter-group-name your-param-group \
  --parameters "ParameterName=work_mem,ParameterValue=256MB,ApplyMethod=immediate"
```

**RDS-specific notes:**
- Extension must be installed by DBA
- Custom parameter groups required for memory settings
- Monitor CloudWatch metrics for performance

### Azure Database

```sql
-- Azure requires explicit permissions
GRANT CREATE EXTENSION TO your_user;
CREATE EXTENSION trinity;
```

**Azure-specific notes:**
- Extension installation may require Azure support
- Monitor DTU usage for performance
- Consider Hyperscale tier for high-throughput scenarios

### Heroku Postgres

```bash
# Heroku requires addon provisioning
heroku addons:create heroku-postgresql:standard-0

# Install extension via heroku psql
heroku psql -c "CREATE EXTENSION trinity;"
```

**Heroku-specific notes:**
- Extension available on Standard and Premium plans
- Monitor connection limits
- Use connection pooling (PgBouncer) for high traffic

### Google Cloud SQL

```sql
-- Cloud SQL requires flag enable_pg_trinity
-- Contact Google Cloud support to enable custom extensions
CREATE EXTENSION trinity;
```

**Cloud SQL-specific notes:**
- Custom extensions require support ticket
- Monitor CPU and memory usage closely
- Consider read replicas for reporting workloads

## Upgrade Path

### From 1.0 to 1.1 (Future)

```sql
-- Backup your data
pg_dump your_database > backup.sql

-- Upgrade extension
ALTER EXTENSION trinity UPDATE TO '1.1';

-- Verify functionality
SELECT trinity.diagnose_allocation('test_table', 'test-uuid'::UUID);
```

## Monitoring

### Key Metrics to Monitor

```sql
-- Allocation statistics
SELECT * FROM trinity.allocation_stats();

-- FK integrity checks
SELECT trinity.check_fk_integrity('your_table');

-- Performance monitoring
SELECT * FROM pg_stat_user_functions
WHERE schemaname = 'trinity';
```

### Log Analysis

```sql
-- Check for errors in logs
SELECT * FROM pg_log
WHERE message LIKE '%trinity%'
ORDER BY log_time DESC;
```

## Support

For issues and questions:

1. Check this documentation
2. Review troubleshooting section
3. Check GitHub issues
4. Contact the development team

---

**Version:** 1.0
**Last Updated:** 2026-01-03
**Compatibility:** PostgreSQL 12.0+