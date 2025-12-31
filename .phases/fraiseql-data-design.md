# fraiseql-data Design Document

**Status**: RFC - Request for Expert Review
**Created**: 2025-12-31
**Author**: Claude (Architecture Agent)
**Purpose**: Design comprehensive seed data generation solution for FraiseQL ecosystem

---

## 🎯 Problem Statement

### Current State: PrintOptim Backend Seed System

PrintOptim has a sophisticated **staging-based seed loading system** that works but has significant pain points:

**What Works Well**:
- ✅ Staging → Production pattern (UUID in seeds, INTEGER in production)
- ✅ Auto-generated staging schema (144 tables + 144 resolution functions)
- ✅ FK resolution via UUID→INTEGER lookup
- ✅ Topological sorting for dependency-safe loading
- ✅ Idempotent resolution (`ON CONFLICT DO NOTHING`)
- ✅ Two-pass handling for self-referencing tables

**Pain Points** (What fraiseql-data Should Solve):
- ❌ **1032-line custom introspection script** - Project-specific, hard to maintain
- ❌ **Hand-written SQL seed files** - 200+ files of manual INSERT statements
- ❌ **No realistic data generation** - All seed data manually created
- ❌ **No Faker integration** - Can't generate realistic names, emails, etc.
- ❌ **No pytest integration** - Tests can't generate test-specific data on the fly
- ❌ **Manual UUID pattern management** - UUIDs hand-crafted for debugging
- ❌ **Tight coupling** - Schema generator is PrintOptim-specific

### User Requirements

> "my use case is to be able to use it for easily integrating with fraiseql-backed APIs, to generate seed data at will for tests (that would ideally be generated from the pytest suite directly) - like currently, ../printoptim_backend has to deal with much hassle to achieve this"

**Primary Goals**:
1. **Pytest Integration**: Generate test data directly in test functions
2. **FraiseQL-Aware**: Understand Trinity pattern (pk_*, id, identifier)
3. **FK-Aware**: Auto-resolve dependencies and load in correct order
4. **Realistic Data**: Use Faker for realistic test data
5. **Pattern UUIDs**: Integrate fraiseql-uuid for debuggable UUIDs
6. **Generalized**: Work with any FraiseQL-compliant schema, not just PrintOptim

---

## 🏗️ Proposed Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│ USER CODE (Pytest Tests, Scripts)                           │
│                                                              │
│  from fraiseql_data import SeedBuilder, fixtures            │
│                                                              │
│  @fixtures.seed_data(tables=["tb_manufacturer"])            │
│  def test_api(db, seed):                                    │
│      manufacturer_id = seed.tb_manufacturer[0].id           │
│      ...                                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: SEED BUILDER API                                   │
│                                                              │
│  class SeedBuilder:                                         │
│    def add(table, count, strategy, **overrides)            │
│    def add_with_fk(table, parent_ref, **kwargs)            │
│    def build() -> Seeds                                     │
│    def execute(conn) -> Seeds                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: SCHEMA INTROSPECTION                               │
│                                                              │
│  class SchemaIntrospector:                                  │
│    def get_tables(schema) -> list[TableInfo]               │
│    def get_columns(table) -> list[ColumnInfo]              │
│    def get_foreign_keys(table) -> list[FKInfo]             │
│    def get_dependency_graph() -> DependencyGraph            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: DEPENDENCY RESOLUTION                              │
│                                                              │
│  class DependencyResolver:                                  │
│    def build_graph(tables) -> Graph                         │
│    def topological_sort() -> list[Table]                    │
│    def detect_cycles() -> list[SelfReference]               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: DATA GENERATORS                                    │
│                                                              │
│  ├─ FakerGenerator (realistic data)                         │
│  ├─ PatternUUIDGenerator (fraiseql-uuid integration)        │
│  ├─ SequentialGenerator (1, 2, 3, ...)                      │
│  ├─ ReferenceGenerator (FK lookups)                         │
│  └─ CustomGenerator (user-provided callables)               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 5: OUTPUT FORMATTERS                                  │
│                                                              │
│  ├─ SQLFormatter (generates INSERT statements)              │
│  ├─ DirectExecutor (executes via psycopg connection)        │
│  └─ StagingFormatter (generates staging table INSERTs)      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Design Decisions (Need Expert Input)

### Decision 1: API Design Philosophy

**Option A: Declarative Builder Pattern**
```python
builder = SeedBuilder(schema="catalog")
builder.add("tb_manufacturer", count=5, strategy="faker")
builder.add("tb_model", count=10, depends_on="tb_manufacturer")
seeds = builder.execute(conn)
```

**Option B: Fluent/Chainable Pattern**
```python
seeds = (SeedBuilder(schema="catalog")
    .table("tb_manufacturer").generate(5, strategy="faker")
    .table("tb_model").generate(10, fk_manufacturer=ref("tb_manufacturer"))
    .execute(conn))
```

**Option C: Decorator-Heavy (Django ORM style)**
```python
@seed_table("tb_manufacturer", count=5)
@seed_table("tb_model", count=10, fk_manufacturer=ref("tb_manufacturer"))
def test_models(seeds):
    assert len(seeds.tb_manufacturer) == 5
```

**Questions for Experts**:
- Which pattern feels most natural for pytest usage?
- Should we support multiple patterns?
- How does this compare to existing Python seed libraries (factory_boy, faker)?

---

### Decision 2: Staging Pattern Integration

**Option A: Direct Database Insertion** (Simple)
```python
# Generates and executes:
# INSERT INTO catalog.tb_manufacturer (id, identifier, name) VALUES (...)
seeds = builder.add("tb_manufacturer", count=5).execute(conn)
```

**Pros**:
- Simple, straightforward
- No staging schema needed
- Works with any PostgreSQL database

**Cons**:
- Loses PrintOptim's staging→production benefits
- Can't use PrintOptim's existing resolution functions
- Harder to debug FK issues

---

**Option B: Staging-Aware Mode** (PrintOptim Compatible)
```python
# Generates and executes:
# INSERT INTO staging.tb_manufacturer (id, fk_*_id, ...) VALUES (...)
# SELECT staging.fn_resolve_all_staging()
builder = SeedBuilder(schema="catalog", mode="staging")
builder.add("tb_manufacturer", count=5)
seeds = builder.execute(conn)  # Auto-resolves to production
```

**Pros**:
- Compatible with PrintOptim's existing system
- Leverages existing resolution functions
- Maintains UUID→INTEGER benefits

**Cons**:
- Requires staging schema to exist
- More complex implementation
- Tight coupling to PrintOptim's architecture

---

**Option C: Pluggable Backend** (Most Flexible)
```python
# Backend: Direct
builder = SeedBuilder(backend=DirectBackend(schema="catalog"))

# Backend: Staging (PrintOptim)
builder = SeedBuilder(backend=StagingBackend(
    staging_schema="staging",
    production_schema="catalog",
    resolve_fn="staging.fn_resolve_all_staging"
))
```

**Pros**:
- Supports both approaches
- Extensible for future backends
- Clear separation of concerns

**Cons**:
- More complex API
- Harder to document
- Potential over-engineering

**Questions for Experts**:
- Is PrintOptim's staging pattern common enough to warrant direct support?
- Should fraiseql-data be opinionated (direct insertion only)?
- Would other FraiseQL projects benefit from staging pattern?

---

### Decision 3: Faker Integration Strategy

**Option A: Auto-Detect from Column Names**
```python
# Column: "email" → Faker().email()
# Column: "first_name" → Faker().first_name()
# Column: "phone_number" → Faker().phone_number()
builder.add("tb_user", count=10, strategy="faker")  # Auto-maps
```

**Pros**:
- Zero configuration for common columns
- Works out of the box
- Follows convention over configuration

**Cons**:
- Magic behavior (harder to debug)
- May guess wrong
- Limited to common column names

---

**Option B: Explicit Mapping**
```python
builder.add("tb_user", count=10, strategy="faker", mapping={
    "email": "email",
    "first_name": "first_name",
    "phone_number": "phone_number",
    "birth_date": "date_of_birth"
})
```

**Pros**:
- Explicit, no magic
- Full control
- Clear what gets generated

**Cons**:
- Verbose
- Tedious for large tables
- Defeats purpose of auto-generation

---

**Option C: Hybrid (Auto + Overrides)**
```python
# Auto-detect, but allow overrides
builder.add("tb_user", count=10,
    strategy="faker",  # Auto-maps common columns
    overrides={
        "birth_date": lambda: fake.date_of_birth(minimum_age=18),
        "status": "active"  # Constant value
    }
)
```

**Pros**:
- Best of both worlds
- Flexible
- Reasonable defaults + customization

**Cons**:
- Still has some magic
- Need good documentation

**Questions for Experts**:
- What's the right balance between magic and explicitness?
- Should we use PostgreSQL column types (TEXT, INTEGER) for hints?
- How do we handle domain-specific columns (e.g., "machine_serial_number")?

---

### Decision 4: Foreign Key Resolution

**Option A: Reference Objects**
```python
manufacturers = builder.add("tb_manufacturer", count=5)
builder.add("tb_model", count=10, fk_manufacturer=manufacturers.random())
```

**Option B: Declarative References**
```python
builder.add("tb_manufacturer", count=5, key="mfg")
builder.add("tb_model", count=10, fk_manufacturer=ref("mfg"))
```

**Option C: Auto-Resolution**
```python
# If tb_model has fk_manufacturer, auto-find tb_manufacturer seeds
builder.add("tb_manufacturer", count=5)
builder.add("tb_model", count=10)  # Auto-links to manufacturer
```

**Questions for Experts**:
- How explicit should FK relationships be?
- Should we auto-detect and warn about missing FKs?
- What about many-to-many relationships?

---

### Decision 5: Trinity Pattern Assumptions

FraiseQL's Trinity pattern:
```sql
CREATE TABLE catalog.tb_manufacturer (
    pk_manufacturer INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    identifier TEXT NOT NULL UNIQUE,
    -- other columns
);
```

**Should fraiseql-data**:
- Assume all tables follow Trinity pattern?
- Validate Trinity compliance?
- Support non-Trinity tables?
- Auto-generate `identifier` from other columns?

**Questions for Experts**:
- Is Trinity pattern mandatory for FraiseQL projects?
- Should we enforce it or be more flexible?
- How do we handle tables that don't fit (lookup tables, junction tables)?

---

### Decision 6: Pytest Integration Depth

**Option A: Simple Fixtures**
```python
@pytest.fixture
def seed_manufacturers(db):
    return SeedBuilder(db).add("tb_manufacturer", count=5).execute()

def test_api(seed_manufacturers):
    assert len(seed_manufacturers) == 5
```

**Option B: Decorator-Based**
```python
@seed_data("tb_manufacturer", count=5)
@seed_data("tb_model", count=10)
def test_api(seeds):
    assert len(seeds.tb_manufacturer) == 5
```

**Option C: Context Managers**
```python
def test_api(db):
    with SeedContext(db) as seeds:
        seeds.add("tb_manufacturer", count=5)
        seeds.add("tb_model", count=10)
        # Auto-cleanup on exit
```

**Questions for Experts**:
- What feels most "pytest-native"?
- Should cleanup be automatic or manual?
- How do we handle test isolation (parallel tests)?

---

### Decision 7: UUID Pattern Integration

**Current fraiseql-uuid API**:
```python
from fraiseql_uuid import Pattern
pattern = Pattern()
uuid = pattern.generate(
    table_code="012345",
    seed_dir=21,
    function=0,
    scenario=0,
    test_case=0,
    instance=1
)
# → "01234521-0000-4000-8000-000000000001"
```

**How should fraiseql-data use this?**

**Option A: Auto-Encode Table Info**
```python
# fraiseql-data internally calls:
uuid = pattern.generate(
    table_code=hash_table_name("tb_manufacturer"),  # Auto-generate code
    seed_dir=21,  # Default
    instance=row_number  # 1, 2, 3, ...
)
```

**Option B: User-Provided Codes**
```python
builder.add("tb_manufacturer", count=5,
    uuid_table_code="013210",  # User specifies
    uuid_seed_dir=21
)
```

**Option C: Hybrid**
```python
# Use fraiseql-uuid for test data (debuggable)
builder.add("tb_manufacturer", count=5,
    uuid_strategy="pattern",  # Uses fraiseql-uuid
    uuid_table_code="013210"
)

# Use random UUIDs for production-like data
builder.add("tb_manufacturer", count=5,
    uuid_strategy="random"  # Standard gen_random_uuid()
)
```

**Questions for Experts**:
- Should fraiseql-data always use Pattern UUIDs?
- How do we map table names to table codes automatically?
- Is there a registry of table codes we should use?

---

## 📋 Implementation Phases

### Phase 1: Core Foundation (MVP)

**Goal**: Prove the concept with minimal viable functionality

**Deliverables**:
1. **Schema Introspection**
   - `SchemaIntrospector` class
   - Extract tables, columns, foreign keys
   - Basic dependency graph

2. **Dependency Resolution**
   - `DependencyResolver` class
   - Topological sort (Kahn's algorithm)
   - Cycle detection

3. **Simple Generators**
   - `SequentialGenerator` (1, 2, 3, ...)
   - `PatternUUIDGenerator` (fraiseql-uuid integration)
   - `ConstantGenerator` (fixed values)

4. **Direct Insertion Backend**
   - Generate SQL INSERT statements
   - Execute via psycopg connection
   - Return inserted records

5. **Basic Tests**
   - Test against simple schema (2-3 tables)
   - Verify FK resolution
   - Check topological order

**Success Criteria**:
- Can introspect a PostgreSQL schema
- Can generate seed data for simple table hierarchy
- Foreign keys correctly resolved
- Tests pass

**Estimated Complexity**: Medium (2-3 days of focused work)

---

### Phase 2: Realistic Data Generation

**Goal**: Add Faker integration and improve data quality

**Deliverables**:
1. **FakerGenerator**
   - Auto-detect common column names
   - Map to Faker methods
   - Support overrides

2. **Smart Type Inference**
   - Use PostgreSQL types for hints
   - TEXT → choose appropriate Faker method
   - INTEGER → choose range or ID
   - TIMESTAMPTZ → realistic dates

3. **Custom Generators**
   - User-provided callables
   - Lambda support
   - Generator functions

4. **Data Constraints**
   - Respect NOT NULL
   - Handle UNIQUE constraints
   - Support DEFAULT values

**Success Criteria**:
- Generate realistic names, emails, addresses
- Respect database constraints
- No duplicate violations

**Estimated Complexity**: Medium (2-3 days)

---

### Phase 3: Pytest Integration

**Goal**: Make seed generation seamless in tests

**Deliverables**:
1. **Pytest Fixtures**
   - `@pytest.fixture` for SeedBuilder
   - Database connection management
   - Transaction isolation

2. **Decorators**
   - `@seed_data()` decorator
   - Auto-cleanup after test
   - Seed data accessible in test function

3. **Context Managers**
   - `with SeedContext()` pattern
   - RAII cleanup
   - Rollback support

4. **Test Isolation**
   - Unique UUIDs per test
   - No cross-test contamination
   - Parallel test support

**Success Criteria**:
- Can write `@seed_data()` in test and it "just works"
- Automatic cleanup (no manual teardown)
- Tests can run in parallel without conflicts

**Estimated Complexity**: Medium-High (3-4 days)

---

### Phase 4: Staging Backend (PrintOptim Compatibility)

**Goal**: Support PrintOptim's staging pattern

**Deliverables**:
1. **StagingBackend**
   - Generate `staging.*` INSERTs
   - Transform `fk_*` to `fk_*_id UUID`
   - Call resolution function after insert

2. **Staging Schema Detection**
   - Auto-detect if staging schema exists
   - Use existing resolution functions
   - Fallback to direct insertion if not available

3. **PrintOptim Integration Test**
   - Test against actual PrintOptim schema
   - Verify compatibility with existing seeds
   - Ensure resolution functions work

**Success Criteria**:
- Can generate seed data for PrintOptim backend
- Compatible with existing staging schema
- Tests pass against PrintOptim database

**Estimated Complexity**: High (4-5 days, requires PrintOptim access)

---

### Phase 5: Advanced Features

**Goal**: Polish and production-readiness

**Deliverables**:
1. **Batch Operations**
   - Efficient bulk inserts
   - Transaction management
   - Error handling

2. **Seed Data Export**
   - Export to SQL files
   - Export to JSON/YAML
   - Import from external formats

3. **CLI Tool**
   - `fraiseql-data seed <table> --count 10`
   - `fraiseql-data export <schema> --output seeds.sql`
   - `fraiseql-data introspect <schema> --show-deps`

4. **Documentation**
   - API reference
   - Cookbook / examples
   - Migration guide (from PrintOptim)

**Success Criteria**:
- Production-ready library
- Comprehensive documentation
- CLI tool works end-to-end

**Estimated Complexity**: Medium (3-4 days)

---

## ❓ Open Questions for Expert Team

### Architecture & Design
1. Should fraiseql-data be opinionated (enforce Trinity pattern) or flexible?
2. Is the staging pattern worth supporting, or should we focus on direct insertion?
3. What's the right balance between auto-magic and explicit configuration?
4. Should we integrate with existing Python libraries (factory_boy, Faker) or build custom?

### API Design
5. Which API pattern feels most natural for pytest usage?
6. How should FK relationships be declared (references, auto-detect, explicit)?
7. Should UUID generation always use fraiseql-uuid Pattern, or allow random UUIDs?

### Integration
8. How should fraiseql-data integrate with FraiseQL GraphQL schema?
9. Should it understand GraphQL types and generate compatible seed data?
10. Should it support other FraiseQL components (fraiseql-core, fraiseql-auth)?

### Testing & Isolation
11. How do we ensure test isolation in parallel pytest execution?
12. Should seed data be transactional (auto-rollback) or persistent?
13. How do we handle test fixtures that depend on seed data?

### Performance
14. What's an acceptable performance target (e.g., generate 1000 rows in X seconds)?
15. Should we support async/await for database operations?
16. How do we optimize bulk inserts for large datasets?

### Compatibility
17. Should fraiseql-data work with any PostgreSQL database, or only FraiseQL-compliant ones?
18. What PostgreSQL versions should we support (13+, 14+, 15+)?
19. Should we support other databases (SQLite for testing, MySQL)?

### Maintenance
20. How do we keep schema introspection in sync with database changes?
21. Should we cache introspection results, or always query fresh?
22. How do we handle schema migrations (Alembic, manual ALTER TABLE)?

---

## ⚖️ Trade-off Analysis

### Simplicity vs. Power

**Simple (Direct Insertion Only)**:
- ✅ Easy to understand
- ✅ Works everywhere
- ✅ Fast to implement
- ❌ Loses PrintOptim staging benefits
- ❌ Less flexible

**Powerful (Multiple Backends)**:
- ✅ Supports PrintOptim staging
- ✅ Extensible architecture
- ✅ Future-proof
- ❌ Complex implementation
- ❌ Harder to document
- ❌ More surface area for bugs

---

### Auto-Magic vs. Explicit

**Auto-Magic (Convention over Configuration)**:
- ✅ Less boilerplate
- ✅ "Just works" for common cases
- ✅ Faster for users
- ❌ Harder to debug
- ❌ Surprising behavior
- ❌ Limited flexibility

**Explicit (Configuration over Convention)**:
- ✅ Clear, predictable
- ✅ No surprises
- ✅ Full control
- ❌ Verbose
- ❌ Tedious for simple cases
- ❌ Steeper learning curve

---

### Integration Depth

**Shallow (Library Only)**:
- ✅ Focused scope
- ✅ Easy to test
- ✅ Composable
- ❌ User writes more code
- ❌ Less opinionated

**Deep (Framework-Like)**:
- ✅ Batteries included
- ✅ pytest decorators work out of the box
- ✅ Opinionated best practices
- ❌ Tight coupling
- ❌ Harder to customize
- ❌ More dependencies

---

## 🚀 Recommendation

Based on analysis of PrintOptim's needs and FraiseQL ecosystem goals:

### Recommended Approach: **Hybrid (Pragmatic)**

**Phase 1 (MVP)**:
- Start simple: Direct insertion backend only
- Focus on pytest integration (biggest pain point)
- Use fraiseql-uuid for Pattern UUIDs
- Auto-detect + override for Faker

**Phase 2 (PrintOptim Compat)**:
- Add staging backend as plugin
- Keep direct insertion as default
- Document both approaches

**Phase 3 (Polish)**:
- CLI tools
- Advanced features based on real usage

**API Design**:
```python
# Recommended: Hybrid approach
from fraiseql_data import SeedBuilder, seed_data

# Simple case (auto-magic)
@seed_data("tb_manufacturer", count=5)
def test_simple(seeds):
    assert len(seeds.tb_manufacturer) == 5

# Complex case (explicit)
def test_complex(db):
    builder = SeedBuilder(db)
    mfg = builder.add("tb_manufacturer", count=5,
        strategy="faker",
        overrides={"status": "active"}
    )
    models = builder.add("tb_model", count=10,
        fk_manufacturer=mfg.random()
    )
    seeds = builder.execute()

    assert len(seeds.tb_manufacturer) == 5
    assert len(seeds.tb_model) == 10
```

**Rationale**:
- Solves immediate pytest integration pain
- Flexible enough for complex scenarios
- Doesn't lock us into architectural decisions
- Can add staging backend later without breaking changes
- Balances simplicity and power

---

## 📚 References

**Existing Libraries to Study**:
- `factory_boy` - Python test data generation (Django-focused)
- `faker` - Realistic fake data generation
- `mimesis` - High-performance fake data (faster than Faker)
- SQLAlchemy's seeding patterns
- Django fixtures
- Rails seeds.rb

**FraiseQL Ecosystem**:
- fraiseql-uuid (Pattern UUID generation)
- fraiseql-core (GraphQL schema)
- PrintOptim backend (staging pattern reference)

**PostgreSQL Resources**:
- information_schema documentation
- Topological sorting algorithms (Kahn's, Tarjan's)
- Bulk insert optimization (COPY vs INSERT)

---

## 🎯 Success Metrics

**For fraiseql-data to be considered successful**:

1. **Adoption**: Used in 3+ FraiseQL projects (PrintOptim, SpecQL, new projects)
2. **Productivity**: 50%+ reduction in time to write test seeds
3. **Maintenance**: Eliminates manual staging schema updates (auto-introspect)
4. **Quality**: 90%+ test coverage, comprehensive documentation
5. **Performance**: Generate 1000 rows in <5 seconds

**User Satisfaction Metrics**:
- "It just works" for simple cases
- Clear error messages when it doesn't
- Easy to debug generated SQL
- Comprehensive examples in docs

---

## 🤝 Next Steps

**For Expert Review Team**:

1. **Review this document** - Identify gaps, issues, concerns
2. **Answer open questions** - Especially architecture and API design
3. **Vote on options** - For each design decision, pick preferred option
4. **Propose alternatives** - If current options don't cover best approach
5. **Prioritize features** - Which phases are most critical?

**Output Expected**:
- Consensus on architecture (direct vs staging vs hybrid)
- Agreement on API design (builder pattern, decorators, etc.)
- Prioritized phase plan
- Go/No-Go decision for implementation

**Timeline**:
- Expert review: 1-2 days
- Revised design: 1 day
- Implementation start: After approval

---

**Document Version**: 1.0
**Last Updated**: 2025-12-31
**Status**: Awaiting Expert Review
