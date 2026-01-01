"""CLI entry point for fraiseql-data - backwards compatibility wrapper.

This module provides backward compatibility for the old import path.
The actual CLI implementation is now in fraiseql_data.cli.main
"""

from fraiseql_data.cli.main import cli

__all__ = ["cli"]

if __name__ == "__main__":
    cli()
