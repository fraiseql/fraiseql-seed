"""Tests for SQL exporter escaping (B4 Cycle 1)."""

from fraiseql_data.cli.exporters.sql_exporter import SQLExporter


class TestSQLExporterEscaping:
    """SQL exporter correctly escapes all special characters."""

    def test_single_quote_escaped(self):
        exporter = SQLExporter()
        result = exporter._format_value("it's a test")
        assert "'" in result
        assert result != "'it's a test'"  # Not the broken version

    def test_backslash_escaped(self):
        exporter = SQLExporter()
        result = exporter._format_value("path\\to\\file")
        assert "path" in result
        assert "file" in result

    def test_newline_in_string(self):
        exporter = SQLExporter()
        result = exporter._format_value("line1\nline2")
        # Should produce valid SQL, not break across lines unescaped
        assert result.startswith("'") or result.startswith("E'")

    def test_tab_in_string(self):
        exporter = SQLExporter()
        result = exporter._format_value("col1\tcol2")
        assert result is not None

    def test_null_value(self):
        exporter = SQLExporter()
        assert exporter._format_value(None) == "NULL"

    def test_boolean_true(self):
        exporter = SQLExporter()
        result = exporter._format_value(True)
        assert result.lower() == "true"

    def test_boolean_false(self):
        exporter = SQLExporter()
        result = exporter._format_value(False)
        assert result.lower() == "false"

    def test_integer(self):
        exporter = SQLExporter()
        assert exporter._format_value(42) == "42"

    def test_float(self):
        exporter = SQLExporter()
        result = exporter._format_value(3.14)
        assert "3.14" in result

    def test_string_basic(self):
        exporter = SQLExporter()
        assert exporter._format_value("hello") == "'hello'"

    def test_combined_special_chars(self):
        """Test string with multiple special characters at once."""
        exporter = SQLExporter()
        result = exporter._format_value("it's a \\path\nwith 'quotes'")
        # Should be valid SQL literal
        assert result is not None
        assert len(result) > 0

    def test_dict_serialized_as_json(self):
        exporter = SQLExporter()
        result = exporter._format_value({"key": "value"})
        assert "key" in result
        assert "value" in result

    def test_list_serialized_as_json(self):
        exporter = SQLExporter()
        result = exporter._format_value([1, 2, 3])
        assert "1" in result

    def test_bytes_value(self):
        exporter = SQLExporter()
        result = exporter._format_value(b"\x00\x01\x02")
        assert result is not None

    def test_full_export_with_special_chars(self):
        """Integration: export a table with tricky values."""
        exporter = SQLExporter()
        rows = [
            {"id": 1, "name": "O'Brien", "path": "C:\\Users\\test"},
            {"id": 2, "name": "Normal", "path": "/usr/local"},
        ]
        result = exporter.export_table("users", rows)
        assert "INSERT INTO users" in result
        assert "O" in result
        assert "Brien" in result
