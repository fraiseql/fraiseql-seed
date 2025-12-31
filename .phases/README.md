# fraiseql-data Implementation Phases

This directory contains detailed implementation plans for **fraiseql-data**: an AI/LLM-native seed data generation library for FraiseQL projects.

## 🎯 Vision

Enable LLMs to write complete, working tests **without guessing** data structures, UUIDs, or foreign key relationships.

## 📋 Phase Overview

### Phase 1: Zero-Guessing Core (Current)

**Goal**: Build MVP that eliminates guessing for LLMs

| Sub-Phase | Status | Objective | Duration |
|-----------|--------|-----------|----------|
| **GREENFIELD** | 📝 Ready | Project setup, dependencies, tooling | 2-3 hours |
| **RED** | 📝 Ready | Write comprehensive failing tests | 3-4 hours |
| **GREEN** | 📝 Ready | Implement core functionality | 1-2 days |
| **REFACTOR** | 📝 Ready | Optimize, add error handling | 4-6 hours |
| **QA** | 📝 Ready | Edge cases, performance, docs | 1 day |

**Total Phase 1 Estimate**: 3-5 days

**Deliverables**:
- ✅ Schema introspection (PostgreSQL information_schema)
- ✅ Auto-Faker data generation (30+ column mappings)
- ✅ Foreign key auto-resolution
- ✅ Pattern UUID integration (fraiseql-uuid)
- ✅ Trinity pattern support (pk_*, id, identifier)
- ✅ `@seed_data()` pytest decorator
- ✅ SeedBuilder API
- ✅ Clear error messages
- ✅ Comprehensive documentation

---

## 🚀 Quick Start

### Run Phase 1-GREENFIELD

```bash
# Follow phase plan
cat .phases/phase-1-greenfield.md

# Execute steps
cd /home/lionel/code/fraiseql-seed
uv init --lib --name fraiseql-data
# ... (continue with phase plan)
```

### Run Phase 1-RED

```bash
# Create test files
cat .phases/phase-1-red.md

# Verify tests fail
uv run pytest tests/ -v
# Expected: All tests FAIL (implementation doesn't exist)
```

### Run Phase 1-GREEN

```bash
# Implement functionality
cat .phases/phase-1-green.md

# Verify tests pass
uv run pytest tests/ -v
# Expected: All tests PASS
```

### Run Phase 1-REFACTOR

```bash
# Optimize and polish
cat .phases/phase-1-refactor.md

# Verify tests still pass (faster)
uv run pytest tests/ -v
uv run mypy src/ --strict
```

### Run Phase 1-QA

```bash
# Add edge cases and docs
cat .phases/phase-1-qa.md

# Full validation
uv run pytest tests/ -v --cov=src/fraiseql_data
# Expected: 40+ tests pass, >90% coverage
```

---

## 📊 Success Metrics

### Phase 1 Complete When:

- ✅ All 40+ tests pass
- ✅ Code coverage >90%
- ✅ Type checking passes (mypy --strict)
- ✅ Linting passes (ruff)
- ✅ Documentation complete (API + Troubleshooting)
- ✅ Performance: 1000 rows in <5 seconds
- ✅ **LLM can write tests without guessing** (validated)

---

## 🎓 Example: What LLMs Can Do After Phase 1

**Before fraiseql-data (lots of guessing)**:
```python
def test_manufacturer_api():
    # LLM has to guess:
    manufacturer_id = uuid.uuid4()  # What UUID?
    db.execute(
        "INSERT INTO tb_manufacturer (id, identifier, name) VALUES (%s, %s, %s)",
        (manufacturer_id, "acme-corp", "Acme Corp")  # What structure?
    )
    # Test code...
```

**After fraiseql-data (zero guessing)**:
```python
@seed_data("tb_manufacturer", count=5)
def test_manufacturer_api(seeds):
    # LLM just references seed data - no guessing!
    manufacturer = seeds.tb_manufacturer[0]
    # Test code using manufacturer.id, manufacturer.identifier, etc.
```

---

## 📁 Phase Plan Structure

Each phase plan follows this structure:

### Common Sections
- **Phase**: GREENFIELD | RED | GREEN | REFACTOR | QA
- **Objective**: Clear goal for this phase
- **Context**: Why this phase matters
- **Files to Create/Modify**: Exact file paths
- **Implementation Steps**: Detailed code examples
- **Verification**: Commands to validate success
- **Acceptance Criteria**: Checklist for completion
- **DO NOT**: Things to avoid

---

## 🔄 Workflow

```
GREENFIELD → RED → GREEN → REFACTOR → QA
    ↓         ↓      ↓         ↓        ↓
  Setup    Tests  Impl    Optimize  Validate
```

**TDD Cycle**:
1. **RED**: Write tests that fail
2. **GREEN**: Make tests pass (minimal implementation)
3. **REFACTOR**: Optimize without changing behavior
4. **QA**: Validate with edge cases and docs

---

## 📖 Phase Details

### Phase 1-GREENFIELD: Project Setup
**File**: `phase-1-greenfield.md`

Set up Python package with UV, dependencies, and testing infrastructure.

**Key deliverables**:
- pyproject.toml with dependencies
- Package structure (src/ layout)
- Test fixtures (db_conn, test_schema)
- Pytest configuration

### Phase 1-RED: Failing Tests
**File**: `phase-1-red.md`

Write comprehensive tests that define desired behavior.

**Test files**:
- test_introspection.py (schema discovery)
- test_generators.py (data generation)
- test_builder.py (SeedBuilder API)
- test_decorator.py (@seed_data decorator)
- test_integration.py (end-to-end workflows)

### Phase 1-GREEN: Implementation
**File**: `phase-1-green.md`

Implement features to make all tests pass.

**Implementation files**:
- introspection.py (PostgreSQL introspection)
- generators.py (Faker, Pattern UUID, Trinity)
- dependency.py (topological sort)
- builder.py (SeedBuilder API)
- decorators.py (pytest decorator)
- backends/direct.py (direct INSERT execution)

### Phase 1-REFACTOR: Optimization
**File**: `phase-1-refactor.md`

Optimize performance, improve error handling, add polish.

**Improvements**:
- Custom exceptions with helpful messages
- Introspection caching
- Bulk insert optimization
- Better type hints and docstrings

### Phase 1-QA: Quality Assurance
**File**: `phase-1-qa.md`

Validate with edge cases, performance tests, documentation.

**QA additions**:
- test_edge_cases.py (nullable, zero count, large count)
- test_error_messages.py (validate helpful errors)
- test_performance.py (benchmark 1000+ rows)
- test_real_world.py (complex realistic scenarios)
- docs/API.md (API reference)
- docs/TROUBLESHOOTING.md (common issues)

---

## 🎯 After Phase 1: Next Steps

Once Phase 1 is complete and validated:

### Option A: PrintOptim Integration (Recommended)
- Test fraiseql-data with real PrintOptim schema (144 tables)
- Migrate 5-10 existing seed files to fraiseql-data
- Validate performance and ergonomics
- Identify gaps for Phase 2

### Option B: Staging Backend Support
- Add StagingBackend for PrintOptim's staging pattern
- Auto-detection (if staging schema exists, use it)
- Maintain backward compatibility with direct INSERT

### Option C: Advanced Features
- Self-referencing tables (circular dependencies)
- GraphQL schema integration
- CLI tool (`fraiseql-data seed ...`)
- Export formats (SQL, JSON)

**Decision**: Validate Phase 1 with real usage before committing to Phase 2 scope.

---

## 🤝 Development Principles

### For This Project

1. **AI/LLM-First**: Every design decision optimizes for LLM usage
2. **Zero Guessing**: LLMs should write tests without knowing data structures
3. **Clear Errors**: Error messages include suggestions and examples
4. **Auto-Magic + Explicit**: Simple by default, explicit when needed
5. **Trinity Pattern**: First-class support for FraiseQL patterns

### From CLAUDE.md

- ✅ Use UV for package management
- ✅ Use psycopg (v3), NOT psycopg2
- ✅ Use ruff for linting
- ✅ Use mypy for type checking
- ✅ TDD workflow (RED → GREEN → REFACTOR → QA)
- ✅ Modern Python 3.11+ type hints

---

## 📚 References

### Related Projects
- **fraiseql-uuid**: Pattern UUID generation (debuggable UUIDs)
- **PrintOptim backend**: Staging pattern reference implementation
- **FraiseQL**: GraphQL framework with Trinity pattern

### Inspiration
- factory_boy (Python test fixtures)
- Faker (realistic data generation)
- pytest (testing framework)

### Documentation
- [fraiseql-data Design Document](fraiseql-data-design.md)
- [PrintOptim Seeding Skill](/home/lionel/.claude/skills/printoptim-seeding.md)
- [FraiseQL Testing Skill](/home/lionel/.claude/skills/fraiseql-testing.md)

---

## 🐛 Issues & Questions

### Common Questions

**Q: Why not use factory_boy?**
A: factory_boy is Django-focused and doesn't understand FraiseQL patterns (Trinity, Pattern UUIDs). We need FraiseQL-native tooling.

**Q: Why decorator-based instead of fixtures-only?**
A: Decorators are more concise for LLMs to generate. Single line vs multiple lines of setup code.

**Q: Why auto-generate Trinity columns?**
A: LLMs shouldn't have to know about pk_*, id, identifier. These are FraiseQL implementation details.

**Q: What about staging pattern?**
A: Phase 1 uses direct INSERT (simpler). Staging backend added in Phase 2 if PrintOptim validation shows it's needed.

---

## ✅ Phase Completion Checklist

### Phase 1-GREENFIELD
- [ ] UV project initialized
- [ ] Dependencies installed (psycopg, faker, fraiseql-uuid)
- [ ] Package structure created (src/ layout)
- [ ] Test fixtures working (db_conn, test_schema)
- [ ] Can import fraiseql_data module

### Phase 1-RED
- [ ] All test files created
- [ ] Tests cover core functionality
- [ ] All tests FAIL (implementation missing)
- [ ] Tests are readable and document behavior

### Phase 1-GREEN
- [ ] All core modules implemented
- [ ] All Phase 1-RED tests PASS
- [ ] Type hints pass mypy
- [ ] Linting passes ruff

### Phase 1-REFACTOR
- [ ] Custom exceptions with helpful messages
- [ ] Introspection caching implemented
- [ ] Code quality improved (no duplication)
- [ ] Docstrings added
- [ ] All tests still PASS

### Phase 1-QA
- [ ] Edge case tests added
- [ ] Error message validation tests pass
- [ ] Performance benchmarks pass (<5s for 1000 rows)
- [ ] Real-world scenario tests pass
- [ ] API documentation written
- [ ] Troubleshooting guide written
- [ ] Code coverage >90%

---

## 🎉 Success!

When all Phase 1 checklists are complete:

✅ **fraiseql-data Zero-Guessing Core is COMPLETE**

LLMs can now write tests without guessing:
- ✅ No manual seed data creation
- ✅ No UUID guessing
- ✅ No FK relationship guessing
- ✅ No Trinity pattern knowledge required

**Next**: Validate with real usage (PrintOptim), then decide on Phase 2 scope.

---

**Current Status**: Phase plans written, ready for implementation
**Start With**: phase-1-greenfield.md
**Questions**: Review fraiseql-data-design.md for architectural context
