#!/bin/bash
# Bootstrap fraiseql-seed monorepo structure
# This script creates the complete directory structure and boilerplate files

set -e

echo "🚀 Bootstrapping fraiseql-seed monorepo..."

# Create directory structure
echo "📁 Creating directory structure..."

# fraiseql-uuid directories
mkdir -p packages/fraiseql-uuid/src/fraiseql_uuid/{patterns,cli/commands}
mkdir -p packages/fraiseql-uuid/tests/{unit/patterns,integration}
mkdir -p packages/fraiseql-uuid/docs/patterns

# fraiseql-data directories
mkdir -p packages/fraiseql-data/src/fraiseql_data/{introspection,generators,cli/commands}
mkdir -p packages/fraiseql-data/tests/{unit/{generators,introspection},integration/fixtures}
mkdir -p packages/fraiseql-data/docs

# Shared directories
mkdir -p shared/{patterns,schemas}
mkdir -p examples/{printoptim-migration,specql-integration,standalone-uuid}
mkdir -p docs/{integration,workflows}
mkdir -p scripts

echo "✅ Directory structure created"
echo ""
echo "📝 Next steps:"
echo "  1. Run: uv sync"
echo "  2. Implement fraiseql-uuid core functionality"
echo "  3. Implement fraiseql-data core functionality"
echo "  4. Write tests"
echo "  5. Update documentation"
echo ""
echo "🎉 Monorepo structure ready!"
