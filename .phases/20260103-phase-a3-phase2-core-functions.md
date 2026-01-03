# Phase A.3.2: Core Functions Implementation

**Status:** Planning
**Created:** 2026-01-03
**Target Completion:** 1 week
**Estimated Work:** 40-50 hours

---

## Executive Summary

Phase A.3.2 implements the **5 core public functions** of the Trinity PostgreSQL extension, enabling the complete UUID→INTEGER PK transformation pipeline. This phase builds on the Phase 1 foundation (tables, helper functions, 20 passing tests) to deliver the production-ready API that PrintOptim Forge and FraiseQL will call.

**Key Deliverables:**
- 5 core functions: allocate_pk(), generate_identifier(), resolve_fk(), transform_csv(), get_uuid_to_pk_mappings()
- 100+ comprehensive tests
- Performance benchmarks (1M+ rows)
- Production-grade error handling
- Integration code for SpecQL and FraiseQL-Seed

**Success Criteria:**
- All 5 functions working correctly
- 100+ tests passing
- Performance targets met (<2s for 1M rows)
- Error messages clear and actionable
- Multi-tenant safety verified

---

## Implementation Plan

### 2.1 allocate_pk() Function

**Function Signature:**
```sql
CREATE FUNCTION trinity.allocate_pk(
    p_table_name TEXT,
    p_uuid_value UUID,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS BIGINT
LANGUAGE plpgsql
STABLE STRICT
AS $$
```

**Implementation Requirements:**
- Validate inputs (table name, UUID, tenant)
- Check if UUID already allocated (idempotent)
- If exists, return existing pk_value
- If not, allocate new: MAX(pk_value) + 1
- INSERT into uuid_allocation_log with proper error handling
- Handle race conditions gracefully

**Performance Target:** <2-5ms per call (1M calls = ~500ms total)

**Tests Required:** 20+ tests
- First allocation → pk=1
- Sequential allocations → 1, 2, 3, ...
- Same UUID twice → same PK (idempotent)
- Null inputs → exception
- Invalid UUID → exception
- Race conditions → correct handling
- Tenant isolation

### 2.2 generate_identifier() Function

**Function Signature:**
```sql
CREATE FUNCTION trinity.generate_identifier(
    p_name TEXT,
    p_instance INT DEFAULT NULL,
    p_separator TEXT DEFAULT '-'
) RETURNS TEXT
LANGUAGE plpgsql
STABLE STRICT
AS $$
```

**Slug Generation Rules:**
- Input: "Hewlett Packard Inc." → Output: "hewlett-packard-inc"
- Lowercase, trim spaces
- Replace spaces/special chars with separator
- Remove invalid characters
- Append instance suffix: "acme-corp" + instance=2 → "acme-corp-2"
- Handle Unicode properly

**Performance Target:** <0.1ms per call

**Tests Required:** 20+ tests
- Common names → correct slugs
- Special characters → handled
- Multiple spaces → collapsed
- Instance suffixes
- Unicode handling
- Custom separators

### 2.3 resolve_fk() Function

**Function Signature:**
```sql
CREATE FUNCTION trinity.resolve_fk(
    p_source_table TEXT,
    p_target_table TEXT,
    p_uuid_fk UUID,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS BIGINT
LANGUAGE plpgsql
STABLE STRICT
AS $$
```

**Implementation Requirements:**
- Handle NULL FK → return NULL (not error)
- Lookup UUID in allocation log
- If found, return pk_value
- If not found, raise MissingForeignKeyError with context
- Register FK relationship in table_dependency_log
- Check for circular dependencies

**Performance Target:** <1ms per lookup

**Tests Required:** 15+ tests
- Valid FK lookup → correct PK
- Null FK → NULL
- Missing FK → exception with context
- Tenant isolation
- Dependency registration
- Circular dependency detection

### 2.4 transform_csv() Function

**Function Signature:**
```sql
CREATE FUNCTION trinity.transform_csv(
    p_table_name TEXT,
    p_csv_content TEXT,
    p_pk_column TEXT,
    p_id_column TEXT DEFAULT 'id',
    p_name_column TEXT DEFAULT NULL,
    p_fk_mappings JSONB DEFAULT NULL,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS TABLE (
    pk_value BIGINT,
    id UUID,
    identifier TEXT,
    extra_columns JSONB
)
LANGUAGE plpgsql
VOLATILE STRICT
AS $$
```

**Implementation Requirements:**
- Parse CSV header and rows
- For each row: allocate PK, generate identifier (if name provided), resolve FKs
- Return transformed data as TABLE
- Handle malformed CSV gracefully
- Batch operations for performance

**Performance Target:** <2s for 1M rows

**Tests Required:** 30+ tests
- Single row transformation
- Multiple rows with FKs
- Identifier generation
- Malformed CSV → exceptions
- Performance benchmarks

### 2.5 get_uuid_to_pk_mappings() Function

**Function Signature:**
```sql
CREATE FUNCTION trinity.get_uuid_to_pk_mappings(
    p_table_name TEXT,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS TABLE (
    uuid_value UUID,
    pk_value BIGINT,
    allocated_at TIMESTAMP
)
LANGUAGE plpgsql
STABLE STRICT
AS $$
```

**Implementation:** Simple SELECT from uuid_allocation_log with ordering.

**Tests Required:** Basic verification tests

---

## Testing Strategy

### Test Suite Structure
- `test_phase2_core_functions.sql` - Main test file (100+ tests)
- Integration tests with real data pipelines
- Performance benchmarks with large datasets
- Multi-tenant isolation verification

### Test Categories
1. **Unit Tests** (60+ tests)
   - Each function individually
   - Edge cases and error conditions
   - Performance validation

2. **Integration Tests** (30+ tests)
   - manufacturers → models pipeline
   - Multi-table transformations
   - Concurrent operations

3. **Performance Tests** (10+ tests)
   - 1K, 10K, 100K, 1M row benchmarks
   - Memory usage monitoring
   - Index performance verification

### Acceptance Criteria
- [ ] 100+ tests pass
- [ ] All performance targets met
- [ ] Error messages clear and actionable
- [ ] Multi-tenant safety verified
- [ ] Code review sign-off

---

## Error Handling Strategy

### Custom Error Codes
```sql
TRINITY_INVALID_UUID           = 'T0001'
TRINITY_INVALID_TABLE          = 'T0002'
TRINITY_MISSING_FOREIGN_KEY    = 'T0003'
TRINITY_CIRCULAR_DEPENDENCY    = 'T0004'
TRINITY_DUPLICATE_IDENTIFIER   = 'T0005'
TRINITY_CONSTRAINT_VIOLATION   = 'T0006'
```

### Error Message Standards
- Include input values in error messages
- Provide hints for resolution
- Use PostgreSQL error codes where possible
- Log context for debugging

---

## Performance Targets

| Operation | Target | Test Size |
|-----------|--------|-----------|
| allocate_pk() | <2-5ms | 1M calls |
| resolve_fk() | <1ms | 1M lookups |
| generate_identifier() | <0.1ms | 1M calls |
| transform_csv() | <2s | 1M rows |
| Total pipeline | <5s | 1M rows |

---

## Integration Requirements

### SpecQL Integration
- Generate helper functions: `schema.table_pk(text) → INTEGER`
- Auto-generate from extension output
- Update SpecQL generators to use extension

### FraiseQL-Seed Integration
- Auto-install extension on setup
- Add extension checks to seed scripts
- Update documentation

---

## Risk Mitigation

### Risk: Race Conditions in PK Allocation
**Mitigation:** Use ON CONFLICT DO NOTHING with retry logic
**Testing:** Concurrent allocation tests with multiple connections

### Risk: Performance Degradation
**Mitigation:** Index strategy, batch operations, query optimization
**Testing:** Performance benchmarks with realistic data sizes

### Risk: Complex CSV Parsing Errors
**Mitigation:** Comprehensive input validation, clear error messages
**Testing:** Malformed CSV test cases

---

## Timeline

**Day 1-2:** Implement allocate_pk() and generate_identifier()
**Day 3:** Implement resolve_fk()
**Day 4:** Implement transform_csv()
**Day 5:** Implement get_uuid_to_pk_mappings() and basic tests
**Day 6:** Comprehensive testing and performance benchmarks
**Day 7:** Error handling polish and integration code

---

## Files to Create/Modify

- `extensions/trinity/trinity--1.0.sql` - Add Phase 2 functions
- `extensions/trinity/test_phase2_core_functions.sql` - Test suite
- `extensions/trinity/test_phase2_performance.sql` - Benchmarks
- `specql/generators/trinity_helper_generator.py` - Integration
- `fraiseql_seed/install_extensions.sql` - Auto-installation

---

## DO NOT List

1. **DO NOT** modify existing Phase 1 functions
2. **DO NOT** change table schemas without migration
3. **DO NOT** skip tenant_id validation
4. **DO NOT** use dynamic SQL without quote_ident()
5. **DO NOT** commit without full test suite passing
6. **DO NOT** bypass circular dependency checks

---

## Next Steps

1. Start implementation with allocate_pk()
2. Implement functions in dependency order
3. Create comprehensive tests for each function
4. Run performance benchmarks
5. Add integration code
6. Final verification and commit

**Created:** 2026-01-03
**Approval Required:** Code review after implementation