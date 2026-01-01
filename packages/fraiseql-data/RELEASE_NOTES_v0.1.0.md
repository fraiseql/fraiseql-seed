# fraiseql-data v0.1.0 Release Notes

**Release Date**: 2026-01-01
**Status**: Production Ready ✅

---

## 🎉 First Stable Release

fraiseql-data v0.1.0 marks the first production-ready release of the zero-guessing test data generation framework for LLM-assisted development.

---

## 📦 What's Included

### Core Features (Phases 1-6 Complete)

1. **Phase 1**: Schema Introspection & Faker Integration
   - Automatic PostgreSQL schema discovery
   - 30+ intelligent column-to-Faker mappings
   - Trinity pattern support (pk_*, id, identifier)

2. **Phase 2**: Self-Referencing Tables
   - Automatic handling of self-referential foreign keys
   - Nullable FK support for hierarchical data

3. **Phase 3**: UNIQUE Constraints
   - Single and multi-column UNIQUE constraint detection
   - Automatic retry logic (up to 10 attempts)
   - Collision avoidance for generated data

4. **Phase 4**: CHECK Constraints
   - Automatic satisfaction of simple CHECK constraints
   - Domain-based validation (email, phone, etc.)
   - Warning system for complex constraints

5. **Phase 5**: Auto-Dependency Resolution
   - Topological sort for foreign key dependencies
   - `auto_deps=True` flag for zero-config generation
   - Automatic parent table seeding

6. **Phase 6**: Seed Common Baseline
   - Environment-specific seed data (dev, staging, prod)
   - Instance range management (1-1,000 seed common, 1,001+ test data)
   - FK validation against seed common baseline
   - YAML/JSON/SQL format support

### Additional Features

- **Export/Import**: JSON and CSV export formats
- **StagingBackend**: In-memory testing without database
- **Custom Generators**: Pluggable data generation
- **Batch Operations**: Conditional chaining for complex workflows
- **@seed_data Decorator**: pytest integration

---

## 📊 Performance

**Measured Throughput**: ~8,500 rows/second

| Scenario | Rows | Time | Throughput |
|----------|------|------|------------|
| Single table | 1,000 | 0.132s | 7,569 rows/sec |
| Single table | 10,000 | 1.131s | 8,842 rows/sec |
| With auto-deps | 1,000 | 0.089s | 11,243 rows/sec |
| In-memory | 100,000 | 11.934s | 8,380 rows/sec |

See `BENCHMARKS.md` for detailed performance analysis.

---

## 🧪 Quality Metrics

- **Test Coverage**: 86% (exceeds 85% target)
- **Tests**: 99/99 passing (100% pass rate)
- **Linting**: 0 errors (ruff check clean)
- **Type Coverage**: Comprehensive type annotations

See `COVERAGE.md` for detailed coverage report.

---

## 📚 Documentation

### New Documentation Files

1. **`docs/API.md`** - Complete API reference
   - SeedBuilder class documentation
   - Seeds object interface
   - Exception reference
   - Models and type annotations

2. **`BENCHMARKS.md`** - Performance benchmarks
   - Measured throughput for different scenarios
   - Optimization tips
   - Comparison to manual SQL scripts

3. **`TROUBLESHOOTING.md`** - Common issues and solutions
   - Installation issues
   - Database connection problems
   - Foreign key troubleshooting
   - UNIQUE and CHECK constraint solutions
   - Seed common issues
   - Performance optimization

4. **`COVERAGE.md`** - Test coverage report
   - Per-module coverage statistics
   - Areas needing improvement
   - Coverage goals for future versions

### Enhanced README

- Added comprehensive table of contents (55+ sections)
- Reorganized for better navigation
- Linked to detailed API documentation
- Updated examples for all 6 phases

---

## 🛠️ Breaking Changes

None - this is the first stable release.

---

## 🐛 Bug Fixes

- Fixed StagingBackend import (now properly exported)
- Removed legacy `orchestrator.py` stub
- Cleaned up unused `fraiseql_seed` directory

---

## 🔧 Improvements

### Code Quality
- Removed unused orchestrator module
- Exported StagingBackend in backends/__init__.py
- Consistent version across all files (0.1.0)

### Documentation
- Extracted API reference from README to dedicated file
- Added table of contents to README
- Created comprehensive troubleshooting guide
- Documented performance benchmarks

### Developer Experience
- 86% test coverage provides confidence
- Clear error messages with actionable suggestions
- Extensive examples for all features

---

## 📦 Installation

```bash
# Via pip
pip install fraiseql-data==0.1.0

# Via uv (recommended)
uv pip install fraiseql-data==0.1.0

# From source
git clone https://github.com/your-org/fraiseql-seed.git
cd fraiseql-seed/packages/fraiseql-data
uv pip install -e .
```

---

## 🚀 Quick Start

```python
from fraiseql_data import SeedBuilder

# Connect to PostgreSQL
import psycopg
conn = psycopg.connect("postgresql://user:pass@localhost/dbname")

# Generate seed data
builder = SeedBuilder(conn, "public", seed_common="db/seed_common/")
seeds = (
    builder
    .add("tb_user", count=100)
    .add("tb_post", count=500, auto_deps=True)  # Auto-generates users
    .execute()
)

# Access generated data
print(f"Generated {len(seeds.tb_user)} users")
print(f"Generated {len(seeds.tb_post)} posts")
```

See README.md for complete examples.

---

## 🎯 Use Cases

1. **TDD Workflows**: Fresh test data for every test run
2. **LLM-Assisted Development**: Zero-guessing data generation
3. **Staging Environments**: Realistic data for demo/QA
4. **Performance Testing**: Generate millions of rows quickly
5. **Database Migrations**: Test data for schema changes

---

## 🧭 Roadmap

### v0.2.0 (Q1 2026)
- Improve auto_deps coverage to 90%+
- Add CLI tool (`fraiseql-data seed ...`)
- Performance optimization for large schemas (500+ tables)
- Multi-database support (SQLite, MySQL)

### v0.3.0 (Q2 2026)
- GraphQL schema integration
- `reuse_existing` feature
- SQL export format
- Enhanced seed common validation

### v1.0.0 (Q3 2026)
- Production hardening
- Comprehensive documentation
- Migration guides from other tools
- Performance optimization for 1M+ rows

---

## 🤝 Integration

### Works Great With

- **confiture**: Fast PostgreSQL migrations (300-600× faster builds)
- **fraiseql**: GraphQL framework for Python
- **fraiseql-uuid**: Pattern UUIDs for debugging
- **pytest**: Test framework integration via @seed_data decorator
- **Faker**: Realistic data generation (30+ built-in mappings)

---

## 🙏 Acknowledgments

- Built with TDD discipline (Phases 1-6 documented)
- Inspired by factory_boy, but database-first
- Designed for LLM-assisted development workflows

---

## 📝 License

MIT License - See LICENSE file

---

## 🔗 Links

- **GitHub**: [fraiseql-seed repository]
- **Documentation**: `README.md`, `docs/API.md`
- **Issues**: [GitHub Issues]
- **PyPI**: [fraiseql-data on PyPI]

---

## 🎓 Getting Help

1. **README.md** - Quick start and examples
2. **docs/API.md** - Complete API reference
3. **TROUBLESHOOTING.md** - Common issues and solutions
4. **BENCHMARKS.md** - Performance tips
5. **GitHub Issues** - Bug reports and feature requests

---

**Thank you for using fraiseql-data!** 🎉

We're excited to see what you build with zero-guessing test data generation.
