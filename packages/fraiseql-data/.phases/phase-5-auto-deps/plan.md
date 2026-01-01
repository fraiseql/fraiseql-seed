# Phase 5: Auto-Dependency Resolution

## Objective

Enable automatic generation of all FK dependencies when adding a table to the seed plan, eliminating the need to manually specify the entire dependency hierarchy.

## Context

Currently, users must manually add all dependencies:
```python
builder.add("tb_organization", count=1)
builder.add("tb_location", count=1)
builder.add("tb_machine", count=1)
builder.add("tb_allocation", count=10).execute()
```

With auto-deps, this becomes:
```python
builder.add("tb_allocation", count=10, auto_deps=True).execute()
# Automatically generates: organization → location → machine → allocation
```

## Design Principles

1. **Just Works**: Default behavior should be simple and predictable
2. **Isolation First**: No reuse of existing data by default (test isolation)
3. **Progressive Enhancement**: Simple cases are simple, complex cases are possible
4. **Explicit is Better**: Auto-deps is opt-in, not default behavior
5. **Deduplication**: Same dependency appearing multiple times = single instance

## API Design

### Basic Usage (Minimal Strategy)

```python
# Generate 1 of each dependency (minimal, predictable)
builder.add("tb_allocation", count=10, auto_deps=True).execute()
# Creates: 1 org, 1 location, 1 machine, 10 allocations
```

### Advanced Configuration

```python
# Explicit counts for specific dependencies
builder.add("tb_allocation", count=100, auto_deps={
    "tb_organization": 2,      # 2 organizations
    "tb_location": 5,          # 5 locations
    "tb_machine": 20,          # 20 machines
    # Other dependencies default to count=1
}).execute()

# With overrides for auto-generated dependencies
builder.add("tb_allocation", count=100, auto_deps={
    "tb_organization": {
        "count": 2,
        "overrides": {"name": lambda i: f"Org-{i}"}
    },
    "tb_machine": 20,
}).execute()

# Reuse existing data (opt-in for specific use cases)
builder.add("tb_allocation", count=10, auto_deps=True, reuse_existing=True).execute()
# If organizations already exist in DB, reuse them instead of creating new ones
```

### Realistic Mode (Future Enhancement - Not Phase 5)

```python
# Phase 6+ feature: ratio-based generation
builder.add("tb_allocation", count=100, auto_deps="realistic").execute()
# Calculates realistic ratios: 2 orgs, 10 locations, 30 machines, 100 allocations
```

## Core Behaviors

### Multi-Path Dependency Deduplication

When a target table has multiple dependency paths to the same table, dependencies are **deduplicated** - only one instance is created.

**Example:**
```python
# Schema:
# tb_allocation → tb_machine → tb_organization
# tb_allocation → tb_contract → tb_organization
# (Two paths to tb_organization)

builder.add("tb_allocation", count=10, auto_deps=True).execute()

# Creates:
# - 1 tb_organization (deduplicated)
# - 1 tb_machine (FK → organization)
# - 1 tb_contract (FK → organization)
# - 10 tb_allocation (FK → machine, FK → contract)
```

**Implementation:**
- Build dependency tree as a DAG (directed acyclic graph)
- Each unique table appears once in the dependency set
- Topological sort ensures correct insertion order

### Reuse Existing Data Strategy

When `reuse_existing=True`:

**Selection Strategy:**
1. Query database for existing rows: `SELECT * FROM table ORDER BY pk LIMIT N`
2. Take first N rows ordered by primary key
3. If DB has fewer than N rows needed:
   - Reuse all existing rows
   - Generate additional rows to meet count
   - Example: Need 5, have 2 → reuse 2, generate 3 new

**Example:**
```python
# Database has 100 organizations (pk_organization: 1-100)

builder.add("tb_allocation", count=10, auto_deps={
    "tb_organization": 3
}, reuse_existing=True).execute()

# Reuses organizations with pk_organization IN (1, 2, 3)
# Does NOT generate new organizations
```

**Partial Reuse Example:**
```python
# Database has 1 organization

builder.add("tb_allocation", count=10, auto_deps={
    "tb_organization": 3
}, reuse_existing=True).execute()

# Reuses existing organization (pk=1)
# Generates 2 additional organizations (pk=2, 3)
# Total: 3 organizations (1 reused + 2 new)
```

### Already in Plan Behavior

If a dependency is already manually added to the plan, the **manual specification takes precedence**.

**Priority Order:**
1. Manual `.add()` call (highest priority)
2. Auto-deps dict config (explicit count)
3. Auto-deps default (count=1, lowest priority)

**Example 1: Manual Wins Over Auto-Deps**
```python
builder.add("tb_organization", count=5)  # Manual: 5 orgs

builder.add("tb_allocation", count=10, auto_deps={
    "tb_organization": 3  # Auto-deps: 3 orgs (IGNORED)
}).execute()

# Result: 5 organizations (manual count used)
# Warning logged: "tb_organization already in plan with count=5, ignoring auto_deps count=3"
```

**Example 2: Auto-Deps Deduplication**
```python
builder.add("tb_allocation", count=10, auto_deps=True)
builder.add("tb_order", count=20, auto_deps=True)
# Both auto-generate tb_organization

# Result: 1 organization (deduplicated)
# Both allocations and orders reference same organization
```

**Example 3: Manual + Auto-Deps**
```python
builder.add("tb_organization", count=2)  # Manual

with builder.batch() as batch:
    batch.add("tb_allocation", count=10, auto_deps=True)
    batch.add("tb_order", count=20, auto_deps=True)

# Result: 2 organizations (manual count used)
# Allocations and orders distributed across 2 organizations
```

### Self-Referencing Tables in Dependency Chain

When auto-deps encounters a self-referencing table, it generates **exactly 1 row** (root row with NULL parent).

**Example:**
```python
# Dependency chain:
# tb_allocation → tb_product → tb_category (self-ref) → tb_organization

builder.add("tb_allocation", count=10, auto_deps=True).execute()

# Creates:
# - 1 tb_organization
# - 1 tb_category (root, parent_category=NULL)
# - 1 tb_product (FK → category)
# - 10 tb_allocation (FK → product)
```

**Limitation:** Auto-generated self-ref tables are always shallow (1 row, no hierarchy).

**Workaround:** Manually add self-ref table with hierarchy:
```python
builder.add("tb_organization", count=1)
builder.add("tb_category", count=10)  # Manual: creates hierarchy
builder.add("tb_product", count=5, auto_deps=True)  # Auto: reuses categories
```

### Distribution Strategy for Child Rows

Child rows are distributed across parent rows using **random selection** (existing system behavior).

**Example:**
```python
builder.add("tb_allocation", count=100, auto_deps={
    "tb_machine": 20
}).execute()

# 100 allocations distributed randomly across 20 machines
# Each machine gets ~5 allocations (may vary due to randomness)
# Example distribution: [6, 4, 5, 7, 3, 5, ...]
```

**Note:** Even distribution is a future enhancement (Phase 6+).

### Batch Operations + Auto-Deps

Dependencies are **deduplicated within batch context**.

**Example:**
```python
with builder.batch() as batch:
    batch.add("tb_allocation", count=10, auto_deps=True)
    batch.add("tb_order", count=20, auto_deps=True)
# Both auto-generate tb_organization

# Result: 1 organization (deduplicated)
# Both allocations and orders reference the same organization
```

**Implementation:**
- Collect all auto-deps from batch operations
- Deduplicate dependency set
- Add dependencies before batch execution

## Implementation Plan

### Feature 1: Basic Auto-Deps (Minimal Strategy)

**Behavior:**
- `auto_deps=True` generates exactly 1 of each dependency
- Recursively walks FK tree to find all transitive dependencies
- Deduplicates dependencies (multi-path → single instance)
- Adds dependencies in topological order (root → leaf)
- Does NOT reuse existing database data (creates new data each time)

**Files to Modify:**
- `src/fraiseql_data/builder.py`:
  - Modify `add()` to accept `auto_deps` and `reuse_existing` parameters
  - Add `_build_dependency_tree()` method
  - Add `_add_auto_dependencies()` method
  - Add `_deduplicate_dependencies()` method

**Files to Create:**
- `tests/test_auto_deps_basic.py`

**Example:**
```python
# Schema:
# tb_organization (no FKs)
# tb_location (FK: organization)
# tb_machine (FK: location)
# tb_allocation (FK: machine)

builder.add("tb_allocation", count=10, auto_deps=True).execute()

# Internally does:
# 1. Introspect tb_allocation → depends on tb_machine
# 2. Introspect tb_machine → depends on tb_location
# 3. Introspect tb_location → depends on tb_organization
# 4. Introspect tb_organization → no dependencies (root)
# 5. Deduplicate dependency set (no duplicates in this case)
# 6. Add in order: organization(1) → location(1) → machine(1) → allocation(10)
```

### Feature 2: Explicit Dependency Counts

**Behavior:**
- `auto_deps={"table_name": count}` allows specifying counts for specific tables
- Tables not specified default to count=1
- Warns (does not error) if auto-dep count > target count

**Files to Modify:**
- `src/fraiseql_data/builder.py`: Update `_add_auto_dependencies()` to handle dict config

**Example:**
```python
builder.add("tb_allocation", count=100, auto_deps={
    "tb_organization": 2,   # 2 organizations
    "tb_machine": 20,       # 20 machines
    # tb_location defaults to count=1
}).execute()

# Creates: 2 orgs, 1 location, 20 machines, 100 allocations
# Machines distributed across 2 orgs (random)
# Allocations distributed across 20 machines (random)
```

**Warning Example:**
```python
builder.add("tb_allocation", count=10, auto_deps={
    "tb_machine": 100  # Unusual: 100 machines for 10 allocations
}).execute()

# Warning: "Auto-dependency 'tb_machine' count (100) exceeds target count (10).
#           This is unusual but allowed. Most machines will have no allocations."
```

### Feature 3: Dependency Overrides

**Behavior:**
- `auto_deps={"table": {"count": N, "overrides": {...}}}` allows overrides for auto-deps
- Enables customization of auto-generated parent data
- Supports both static values and callables

**Files to Modify:**
- `src/fraiseql_data/builder.py`: Parse dict-of-dicts config

**Example:**
```python
builder.add("tb_allocation", count=10, auto_deps={
    "tb_organization": {
        "count": 1,
        "overrides": {
            "name": "Test Organization",
            "identifier": "ORG-TEST-001"
        }
    },
    "tb_machine": {
        "count": 3,
        "overrides": {
            "name": lambda i: f"Machine-{i}"
        }
    }
}).execute()

# Organization created with specific name/identifier
# Machines created with names: Machine-1, Machine-2, Machine-3
```

### Feature 4: Reuse Existing Data (Opt-In)

**Behavior:**
- `reuse_existing=True` queries database for existing dependency data
- Takes first N rows ordered by primary key
- Falls back to generation if insufficient data exists
- Useful for sequential tests or development environments

**Files to Modify:**
- `src/fraiseql_data/builder.py`:
  - Add `_fetch_existing_data()` method
  - Integrate with `_add_auto_dependencies()`

**Files to Create:**
- `src/fraiseql_data/reuse.py`: Data reuse utilities

**Example:**
```python
# First test creates org
builder.add("tb_organization", count=1).execute()

# Second test reuses existing org
builder.add("tb_allocation", count=10, auto_deps=True, reuse_existing=True).execute()
# Queries: SELECT * FROM tb_organization ORDER BY pk_organization LIMIT 1
# Reuses existing organization instead of creating duplicate
```

**Note:** Default is `reuse_existing=False` for test isolation.

## Edge Cases & Validation

### Circular Dependencies
- Auto-deps detects circular dependencies using existing dependency graph
- Raises `CircularDependencyError` with dependency path
- **Error Message:**
  ```
  CircularDependencyError: Circular dependency detected in auto-deps chain:
    tb_allocation → tb_machine → tb_location → tb_allocation

  Suggestion: Check foreign key constraints for cycles.
  Auto-deps cannot resolve circular dependencies.
  ```

### Self-Referencing Tables
- Auto-deps generates exactly 1 row (root with NULL parent) for self-ref tables
- **Warning Message:**
  ```
  AutoDepsWarning: Table 'tb_category' is self-referencing and was auto-generated with count=1 (root row only).
  For hierarchical data, manually add 'tb_category' with desired count before using auto-deps.
  ```

### Missing Tables in Dependency Chain
- If dependency table doesn't exist in schema, raise `TableNotFoundError`
- **Error Message:**
  ```
  TableNotFoundError: Auto-dependency resolution failed.
  Table 'tb_allocation' depends on 'tb_machine', but 'tb_machine' not found in schema 'public'.

  Dependency path: tb_allocation → tb_machine (missing)

  Suggestion: Verify table name and schema.
  ```

### Count Validation
- **Warn** (don't error) if auto-dep count > target count
- **Warning Message:**
  ```
  AutoDepsWarning: Auto-dependency 'tb_machine' count (100) exceeds target table 'tb_allocation' count (10).
  This is unusual but allowed. Most parent rows will have no child rows.
  ```

### Already in Plan
- Manual `.add()` takes precedence over auto-deps config
- **Warning Message:**
  ```
  AutoDepsWarning: Dependency 'tb_organization' already in plan with count=5.
  Ignoring auto_deps count=3. Using existing count=5.
  ```

### No Dependencies
- Table with no foreign keys: auto-deps is a no-op
- No warning needed (expected behavior)

### Nested Auto-Deps
- If manually added table also has `auto_deps=True`, recursively resolve
- **Example:**
  ```python
  builder.add("tb_organization", count=2, auto_deps=True)  # May have deps
  builder.add("tb_allocation", count=10, auto_deps=True)

  # If tb_organization has FKs, those are also auto-generated
  ```

### Reuse Existing - Insufficient Data
- Database has fewer rows than needed: reuse all + generate rest
- **Log Message:**
  ```
  INFO: Reusing 2 existing rows from 'tb_organization' (pk: 1, 2)
  INFO: Generating 3 additional rows for 'tb_organization' to meet count=5
  ```

## Test Strategy

### Unit Tests (test_auto_deps_basic.py)
- `test_auto_deps_minimal_single_level` - 1-level FK (allocation → machine)
- `test_auto_deps_minimal_multi_level` - 3-level FK (allocation → machine → location → org)
- `test_auto_deps_multi_path_deduplication` - Multiple paths to same table
- `test_auto_deps_with_explicit_counts` - Custom counts per dependency
- `test_auto_deps_with_overrides` - Overrides for auto-generated deps
- `test_auto_deps_already_in_plan_manual_wins` - Manual count takes precedence
- `test_auto_deps_false` - Default behavior (no auto-deps)

### Edge Case Tests (test_auto_deps_edge_cases.py)
- `test_auto_deps_circular_dependency` - Detects circular deps (error)
- `test_auto_deps_self_referencing` - Handles self-refs (1 root row)
- `test_auto_deps_missing_table` - Clear error for missing tables
- `test_auto_deps_no_dependencies` - Table with no FKs (no-op)
- `test_auto_deps_count_exceeds_target` - Warning for unusual counts
- `test_auto_deps_nested` - Table with auto_deps depends on table with auto_deps

### Isolation Tests (test_auto_deps_isolation.py)
- `test_auto_deps_no_reuse_by_default` - Creates new data each time
- `test_auto_deps_reuse_existing_full` - Reuses all needed rows
- `test_auto_deps_reuse_partial` - Reuses some, generates rest
- `test_auto_deps_reuse_none_available` - No existing data, generates all

### Batch Integration Tests (test_auto_deps_batch.py)
- `test_auto_deps_batch_deduplication` - Multiple tables auto-generate same dep
- `test_auto_deps_batch_with_manual` - Mix of manual and auto-deps in batch
- `test_auto_deps_batch_different_counts` - Conflicting auto-dep counts in batch

### Integration Tests (test_auto_deps_integration.py)
- `test_auto_deps_complex_hierarchy` - Real-world 5+ level hierarchy
- `test_auto_deps_multiple_tables_sequential` - Multiple .add() calls with auto-deps
- `test_auto_deps_with_overrides_and_reuse` - Complex scenario combining features

## Implementation Steps

### Phase 5-RED (Failing Tests)
1. Create `tests/test_auto_deps_basic.py` with 7 failing tests
2. Create `tests/test_auto_deps_edge_cases.py` with 6 failing tests
3. Create `tests/test_auto_deps_isolation.py` with 4 failing tests
4. Create `tests/test_auto_deps_batch.py` with 3 failing tests
5. Run tests - expect 20 failures

### Phase 5-GREEN (Implementation)

**Step 1: Core Dependency Tree Building**
- Implement `_build_dependency_tree(table)` in `builder.py`
  - Recursively walk FK dependencies using introspector
  - Build DAG of dependencies
  - Return deduplicated list in topological order (root → leaf)

**Step 2: Deduplication**
- Implement `_deduplicate_dependencies(dep_list)` in `builder.py`
  - Remove duplicate table names
  - Preserve topological order

**Step 3: Auto-Dependencies Addition**
- Implement `_add_auto_dependencies(table, auto_deps, reuse_existing)` in `builder.py`
  - Parse `auto_deps` parameter (bool, dict, dict-of-dicts)
  - Get dependency tree
  - Determine counts for each dependency (explicit or default to 1)
  - Check if already in plan (skip if manual)
  - Add dependencies to plan with counts/overrides

**Step 4: Reuse Existing Data**
- Implement `_fetch_existing_data(table, count)` in `builder.py`
  - Query: `SELECT * FROM {table} ORDER BY {pk} LIMIT {count}`
  - Return existing rows
  - Return count of rows fetched vs. needed

- Modify `execute()` to use reused data:
  - If reused data available, populate `generated_data` dict
  - Skip generation for tables with sufficient reused data
  - Generate additional rows if needed

**Step 5: Integration with add()**
- Modify `add()` method:
  - Accept `auto_deps` and `reuse_existing` parameters
  - Call `_add_auto_dependencies()` before adding target table
  - Handle warnings for conflicts

**Step 6: Logging and Warnings**
- Add logging for debug visibility:
  - Which tables were auto-added
  - Which tables were deduplicated
  - When manual count overrides auto-deps
- Implement warning system for unusual cases

**Step 7: Run Tests**
- Run all 20 tests - expect all to pass

### Phase 5-REFACTOR (Code Quality)

1. Extract dependency tree building to `src/fraiseql_data/dependency.py`:
   - Move `_build_dependency_tree()` → `DependencyGraph.build_tree()`
   - Move `_deduplicate_dependencies()` → `DependencyGraph.deduplicate()`

2. Extract reuse logic to `src/fraiseql_data/reuse.py`:
   - Create `ReuseStrategy` class
   - Implement `fetch_existing(table, count, conn)` method

3. Add comprehensive type hints:
   ```python
   def add(
       self,
       table: str,
       count: int,
       strategy: str = "faker",
       overrides: dict[str, Any] | None = None,
       auto_deps: bool | dict[str, int | dict[str, Any]] = False,
       reuse_existing: bool = False,
   ) -> "SeedBuilder":
   ```

4. Add docstrings with examples for all new methods

5. Improve error messages with helpful suggestions

6. Run linting (ruff)

7. Run all tests (56 existing + 20 new = 76 total)

### Phase 5-QA (Integration & Documentation)

1. Create `tests/integration/test_phase5_integration.py` with 3 comprehensive tests:
   - Complex real-world hierarchy (organization → ... → allocation)
   - Batch operations with mixed auto-deps and manual
   - Reuse existing with partial data

2. Update `README.md`:
   - Add "Phase 5 Features" section
   - Document auto-deps with examples
   - Update roadmap

3. Create `PHASE5_SUMMARY.md` with:
   - Feature overview
   - Implementation details
   - Examples and use cases
   - Known limitations

4. Run all tests - expect 79+ passing

5. Manual testing with real-world schemas

## Acceptance Criteria

✅ `auto_deps=True` generates 1 of each dependency (minimal)
✅ Multi-path dependencies are deduplicated (single instance)
✅ `auto_deps={"table": N}` allows explicit counts
✅ `auto_deps={"table": {"count": N, "overrides": {}}}` allows overrides
✅ Manual `.add()` takes precedence over auto-deps
✅ `reuse_existing=False` by default (test isolation)
✅ `reuse_existing=True` reuses existing DB data (first N by PK)
✅ Partial reuse: reuses available + generates rest
✅ Detects circular dependencies (error)
✅ Handles self-referencing tables (1 root row)
✅ Batch operations deduplicate dependencies
✅ Clear error messages for all edge cases
✅ Warnings for unusual but valid cases
✅ All tests pass (20 new unit tests + 3 integration tests)
✅ Documentation updated with examples
✅ Backwards compatible (existing code unchanged)

## DO NOT

❌ Implement "realistic" mode (ratio-based) - defer to Phase 6
❌ Implement even distribution - defer to Phase 6
❌ Change default behavior (auto_deps defaults to False)
❌ Auto-enable for all `.add()` calls (explicit opt-in only)
❌ Reuse existing data by default (breaks test isolation)
❌ Generate more than necessary (minimal by default)
❌ Error on unusual counts (warn instead)

## Success Metrics

- Reduces boilerplate for deep hierarchies (5+ levels): **80% less code**
- Maintains test isolation by default: **reuse_existing=False**
- Clear, predictable behavior: **deduplication rules documented**
- Easy to configure for complex cases: **progressive API**
- Backwards compatible: **existing code works unchanged**

## Timeline (Revised)

- Phase 5-RED: **1 hour** (write 20 failing tests)
- Phase 5-GREEN: **4 hours** (implement core functionality)
  - Step 1-2: Dependency tree + deduplication (1.5 hours)
  - Step 3: Auto-deps addition logic (1 hour)
  - Step 4: Reuse existing data (1 hour)
  - Step 5-7: Integration + testing (0.5 hours)
- Phase 5-REFACTOR: **1 hour** (extract to modules, cleanup, linting)
- Phase 5-QA: **1 hour** (integration tests, docs)
- **Total: ~7 hours**

## Performance Considerations

### Introspection Overhead
- Dependency tree building requires FK introspection per table
- **Mitigation:** Cache introspection results in `SchemaIntrospector`
- Deep hierarchies (10+ levels) may have noticeable overhead

### Reuse Query Performance
- `SELECT * FROM table ORDER BY pk LIMIT N` is efficient with indexed PK
- Large tables: no performance issue (LIMIT constrains result set)

### Deduplication
- Linear scan of dependency list (small N, typically < 20 tables)
- No performance concern

## Example Use Cases

### Use Case 1: Quick Test Data
```python
# Before (manual) - 4 lines
builder.add("tb_org", 1).add("tb_loc", 1).add("tb_machine", 1).add("tb_alloc", 10).execute()

# After (auto-deps) - 1 line
builder.add("tb_allocation", count=10, auto_deps=True).execute()
```

### Use Case 2: Realistic Distribution
```python
# Create realistic test scenario: 2 orgs, 10 machines, 100 allocations
builder.add("tb_allocation", count=100, auto_deps={
    "tb_organization": 2,
    "tb_machine": 10,
}).execute()
```

### Use Case 3: Specific Parent Data
```python
# Create allocations under specific organization
builder.add("tb_allocation", count=50, auto_deps={
    "tb_organization": {
        "count": 1,
        "overrides": {"name": "Acme Corp", "identifier": "ORG-ACME"}
    }
}).execute()
```

### Use Case 4: Development Environment (Reuse)
```python
# Development DB already has orgs/locations - reuse them
builder.add("tb_allocation", count=10, auto_deps=True, reuse_existing=True).execute()
```

### Use Case 5: Multi-Path Dependencies
```python
# Schema:
# tb_allocation → tb_machine → tb_organization
# tb_allocation → tb_contract → tb_organization

builder.add("tb_allocation", count=100, auto_deps=True).execute()

# Automatically deduplicates:
# 1 organization, 1 machine, 1 contract, 100 allocations
```

### Use Case 6: Batch with Auto-Deps
```python
with builder.batch() as batch:
    batch.add("tb_allocation", count=50, auto_deps=True)
    batch.add("tb_order", count=100, auto_deps=True)
    batch.add("tb_shipment", count=75, auto_deps=True)

# All three share same auto-generated dependencies (deduplicated)
```

### Use Case 7: Mixed Manual and Auto-Deps
```python
# Manual control over organizations, auto for the rest
builder.add("tb_organization", count=3, overrides={
    "name": lambda i: f"Organization-{i}"
})
builder.add("tb_allocation", count=100, auto_deps=True).execute()

# Uses 3 manually created orgs, auto-generates locations/machines/etc.
```

## Future Enhancements (Phase 6+)

- **Realistic Mode**: Ratio-based counts using heuristics
- **Smart Distribution**: Distribute child rows evenly across parents
- **Depth Limiting**: `auto_deps_depth=3` to limit recursion
- **Dependency Profiles**: Reusable configs like `auto_deps="testing"` or `auto_deps="production"`
- **Performance**: Parallel dependency generation
- **Reuse Strategy**: Advanced selection (random, weighted, last N)
- **Dry Run**: `auto_deps_plan()` to preview what would be generated
