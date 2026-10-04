"""Manual contract tests for gse.scale_definition."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enum import IntEnum

import pytest

from gse.scale_definition import (
    BankDef,
    PrimitiveInfo,
    ScaleDefinition,
)


@pytest.fixture
def banks_two():
    return [
        BankDef(name="alpha", primitives=["A1", "A2"]),
        BankDef(name="beta", primitives=["B1", "B2", "B3"]),
    ]


@pytest.fixture
def scale(banks_two):
    return ScaleDefinition(name="test", banks=banks_two)


# ---------- BankDef ----------


class TestBankDef:
    def test_defaults(self):
        b = BankDef(name="x", primitives=["P1"])
        assert b.name == "x"
        assert b.primitives == ["P1"]
        assert b.metadata == {}

    def test_immutable(self):
        b = BankDef(name="x", primitives=["P"])
        with pytest.raises(Exception):
            # frozen=True → can't mutate
            b.name = "y"


# ---------- PrimitiveInfo ----------


class TestPrimitiveInfo:
    def test_basic(self):
        info = PrimitiveInfo(name="GOOD", bank_index=2, bank_name="Evaluators", scale="word")
        assert info.name == "GOOD"
        assert info.bank_index == 2
        assert info.scale == "word"

    def test_defaults(self):
        info = PrimitiveInfo(name="X", bank_index=0, bank_name="A", scale="word")
        assert info.metadata == {}

    def test_immutable(self):
        info = PrimitiveInfo(name="X", bank_index=0, bank_name="A", scale="word")
        with pytest.raises(Exception):
            info.name = "Y"


# ---------- ScaleDefinition.__init__ ----------


class TestInit:
    def test_basic_fields(self, scale):
        assert scale.name == "test"
        assert scale.dimension == 8192
        assert scale.n_banks == 8
        assert scale.dims_per_bank == 1024  # 8192 / 8

    def test_custom_dimension(self, banks_two):
        s = ScaleDefinition(name="x", banks=banks_two, dimension=4096, n_banks=4)
        assert s.dimension == 4096
        assert s.dims_per_bank == 1024

    def test_hub_primitives_default_empty(self, scale):
        assert scale.hub_primitives == []

    def test_families_default_empty(self, scale):
        assert scale.families == {}

    def test_hub_primitives_preserved(self, banks_two):
        s = ScaleDefinition(name="x", banks=banks_two, hub_primitives=["A1", "B1"])
        assert s.hub_primitives == ["A1", "B1"]


# ---------- _build_bank_enum ----------


class TestBuildBankEnum:
    def test_returns_intenum(self, scale):
        assert issubclass(scale.bank_enum, IntEnum)

    def test_members_match_banks(self, scale):
        assert scale.bank_enum.alpha == 0
        assert scale.bank_enum.beta == 1

    def test_enum_name_uses_scale_title(self, scale):
        # ScaleDefinition.name = "test" → enum class name "TestBank"
        assert scale.bank_enum.__name__ == "TestBank"


# ---------- _build_registry ----------


class TestBuildRegistry:
    def test_all_primitives_registered(self, scale):
        # 2 + 3 = 5 primitives total
        assert len(scale.primitive_registry) == 5
        for p in ["A1", "A2", "B1", "B2", "B3"]:
            assert p in scale.primitive_registry

    def test_bank_index_correct(self, scale):
        assert scale.primitive_registry["A1"].bank_index == 0
        assert scale.primitive_registry["B1"].bank_index == 1

    def test_bank_name_correct(self, scale):
        assert scale.primitive_registry["A1"].bank_name == "alpha"
        assert scale.primitive_registry["B1"].bank_name == "beta"

    def test_scale_propagated(self, scale):
        assert scale.primitive_registry["A1"].scale == "test"


# ---------- get_primitive_info ----------


class TestGetPrimitiveInfo:
    def test_known(self, scale):
        info = scale.get_primitive_info("A1")
        assert info.name == "A1"
        assert info.bank_index == 0

    def test_unknown_returns_none(self, scale):
        assert scale.get_primitive_info("XYZZY") is None


# ---------- get_bank_primitives ----------


class TestGetBankPrimitives:
    def test_returns_bank_primitives(self, scale):
        result = scale.get_bank_primitives(0)
        assert set(result) == {"A1", "A2"}

    def test_other_bank(self, scale):
        result = scale.get_bank_primitives(1)
        assert set(result) == {"B1", "B2", "B3"}

    def test_unknown_bank_empty(self, scale):
        assert scale.get_bank_primitives(99) == []

    def test_cached(self, scale):
        r1 = scale.get_bank_primitives(0)
        r2 = scale.get_bank_primitives(0)
        # Same object reference due to caching
        assert r1 is r2


# ---------- get_all_primitives ----------


class TestGetAllPrimitives:
    def test_returns_all(self, scale):
        result = scale.get_all_primitives()
        assert set(result) == {"A1", "A2", "B1", "B2", "B3"}


# ---------- count_primitives ----------


class TestCountPrimitives:
    def test_total(self, scale):
        counts = scale.count_primitives()
        assert counts["total"] == 5

    def test_per_bank(self, scale):
        counts = scale.count_primitives()
        assert counts["bank_0_alpha"] == 2
        assert counts["bank_1_beta"] == 3


# ---------- primitives_per_bank_counts ----------


class TestPrimitivesPerBankCounts:
    def test_returns_dict(self, scale):
        counts = scale.primitives_per_bank_counts()
        assert counts == {0: 2, 1: 3}


# ---------- all_primitive_names property ----------


class TestAllPrimitiveNames:
    def test_returns_in_order(self, scale):
        names = scale.all_primitive_names
        assert names == ["A1", "A2", "B1", "B2", "B3"]

    def test_includes_all(self, scale):
        names = scale.all_primitive_names
        assert len(names) == 5


# ---------- __repr__ ----------


class TestRepr:
    def test_format(self, scale):
        s = repr(scale)
        assert "ScaleDefinition" in s
        assert "test" in s
        assert "primitives=5" in s
        assert "banks=2" in s


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
