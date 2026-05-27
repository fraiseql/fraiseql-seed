"""Tests for Seeds and SeedRow discoverable API."""

import pytest
from fraiseql_data.models import SeedRow, Seeds


@pytest.fixture
def seeds():
    """Create a Seeds object with two tables."""
    s = Seeds()
    s.add_table("tb_org", [{"pk": 1, "name": "Org A"}, {"pk": 2, "name": "Org B"}])
    s.add_table("tb_user", [{"pk": 10, "name": "Alice"}])
    return s


class TestSeedsGetitem:
    def test_existing_table(self, seeds):
        rows = seeds["tb_org"]
        assert len(rows) == 2
        assert rows[0].pk == 1

    def test_missing_table_raises_keyerror(self, seeds):
        with pytest.raises(KeyError, match="tb_missing"):
            seeds["tb_missing"]


class TestSeedsLen:
    def test_counts_tables(self, seeds):
        assert len(seeds) == 2

    def test_empty_seeds(self):
        assert len(Seeds()) == 0


class TestSeedsIter:
    def test_yields_table_names(self, seeds):
        names = list(seeds)
        assert "tb_org" in names
        assert "tb_user" in names
        assert len(names) == 2


class TestSeedsContains:
    def test_existing_table(self, seeds):
        assert "tb_org" in seeds

    def test_missing_table(self, seeds):
        assert "tb_missing" not in seeds


class TestSeedsTables:
    def test_returns_list(self, seeds):
        tables = seeds.tables()
        assert isinstance(tables, list)
        assert set(tables) == {"tb_org", "tb_user"}


class TestSeedsItems:
    def test_yields_pairs(self, seeds):
        pairs = dict(seeds.items())
        assert "tb_org" in pairs
        assert len(pairs["tb_org"]) == 2
        assert len(pairs["tb_user"]) == 1


class TestSeedsRepr:
    def test_repr(self, seeds):
        r = repr(seeds)
        assert "Seeds(" in r
        assert "tb_org(2)" in r
        assert "tb_user(1)" in r

    def test_empty_repr(self):
        assert repr(Seeds()) == "Seeds()"


class TestSeedsGetattr:
    def test_backward_compat(self, seeds):
        rows = seeds.tb_org
        assert len(rows) == 2

    def test_missing_raises_attributeerror(self, seeds):
        with pytest.raises(AttributeError, match="tb_missing"):
            seeds.tb_missing  # noqa: B018


class TestSeedRowRepr:
    def test_repr(self):
        row = SeedRow(_data={"pk": 1, "name": "Alice"})
        r = repr(row)
        assert "SeedRow(" in r
        assert "'pk': 1" in r
