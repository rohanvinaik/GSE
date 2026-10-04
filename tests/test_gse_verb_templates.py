"""Manual contract tests for gse.verb_templates."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.verb_templates import (
    VERB_TEMPLATES,
    VerbTemplateHandler,
    get_verb_template_handler,
)


@pytest.fixture
def handler():
    return VerbTemplateHandler()


class TestGetTemplate:
    def test_known_verb_returns_template(self, handler):
        t = handler.get_template("hit")
        assert t is not None
        assert t.name == "transitive_action"

    def test_unknown_verb_returns_none(self, handler):
        assert handler.get_template("zxqvnonsense") is None

    def test_case_insensitive(self, handler):
        t = handler.get_template("HIT")
        assert t is not None


class TestGetRequiredRoles:
    def test_transitive_action_roles(self, handler):
        roles = handler.get_required_roles("hit")
        assert "agent" in roles
        assert "patient" in roles
        assert "action" in roles

    def test_intransitive_action_roles(self, handler):
        roles = handler.get_required_roles("run")
        assert "agent" in roles
        # Should NOT include patient (intransitive)
        assert "patient" not in roles

    def test_unknown_verb_empty_list(self, handler):
        assert handler.get_required_roles("zxqv") == []


class TestGetOptionalRoles:
    def test_returns_list(self, handler):
        result = handler.get_optional_roles("hit")
        assert isinstance(result, list)

    def test_unknown_verb_empty(self, handler):
        assert handler.get_optional_roles("zxqv") == []


class TestValidateArguments:
    def test_all_required_present_valid(self, handler):
        valid, missing = handler.validate_arguments("hit", {"agent", "action", "patient"})
        assert valid
        assert missing == []

    def test_missing_required_invalid(self, handler):
        valid, missing = handler.validate_arguments("hit", {"agent"})
        assert not valid
        assert "patient" in missing or "action" in missing

    def test_unknown_verb_valid(self, handler):
        valid, missing = handler.validate_arguments("zxqv", set())
        assert valid
        assert missing == []

    def test_extra_roles_ok(self, handler):
        """Extra (non-required) roles don't invalidate."""
        valid, _ = handler.validate_arguments("hit", {"agent", "action", "patient", "extra"})
        assert valid


class TestInferImplicitArguments:
    def test_missing_required_inferred(self, handler):
        # If patient is missing, the default primitive should be inferred
        result = handler.infer_implicit_arguments("hit", {"agent", "action"})
        # Should infer a patient default
        roles_inferred = {r for _, r in result}
        assert "patient" in roles_inferred

    def test_all_present_returns_empty(self, handler):
        result = handler.infer_implicit_arguments("hit", {"agent", "action", "patient", "instrument"})
        # All required + the optional instrument supplied → only implicit gaps left
        # (none for hit). Should be empty or minimal.
        for primitive, role in result:
            assert role not in {"agent", "action", "patient", "instrument"}

    def test_unknown_verb_returns_empty(self, handler):
        assert handler.infer_implicit_arguments("zxqv", set()) == []


class TestGetDecompositionPrimitives:
    def test_known_verb_returns_pairs(self, handler):
        result = handler.get_decomposition_primitives("hit")
        assert len(result) > 0
        for primitive, role in result:
            assert isinstance(primitive, str)
            assert isinstance(role, str)

    def test_unknown_verb_default(self, handler):
        result = handler.get_decomposition_primitives("zxqv")
        assert result == [("DO", "action")]


class TestGetSemanticType:
    def test_known_verb(self, handler):
        assert handler.get_semantic_type("hit") == "action"

    def test_unknown_verb_default_action(self, handler):
        assert handler.get_semantic_type("zxqv") == "action"


class TestGetAspectPreference:
    def test_known_verb_returns_aspect(self, handler):
        result = handler.get_aspect_preference("hit")
        # transitive_action has telic aspect preference
        assert result == "telic"

    def test_unknown_verb_returns_none(self, handler):
        assert handler.get_aspect_preference("zxqv") is None


class TestSingletonHandler:
    def test_returns_handler_instance(self):
        h = get_verb_template_handler()
        assert isinstance(h, VerbTemplateHandler)

    def test_singleton_same_instance(self):
        h1 = get_verb_template_handler()
        h2 = get_verb_template_handler()
        assert h1 is h2


class TestTemplateStructure:
    def test_verb_templates_dict_nonempty(self):
        assert len(VERB_TEMPLATES) > 0

    def test_each_template_has_required_fields(self):
        for name, t in VERB_TEMPLATES.items():
            assert t.name == name
            assert isinstance(t.description, str)
            assert isinstance(t.example_verbs, list)
            assert isinstance(t.arguments, list)
            assert t.semantic_type
            # aspect_preference can be None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
