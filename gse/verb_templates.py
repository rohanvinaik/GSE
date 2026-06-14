"""
Verb Argument Structure Templates for GSE.

Defines the expected argument structures for different verb classes,
enabling:
- Validation of sentence completeness
- Inference of implicit arguments
- Proper role assignment
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class ArgumentType(Enum):
    """Types of verb arguments."""
    REQUIRED = "required"       # Must be present (explicit or implicit)
    OPTIONAL = "optional"       # May be present
    IMPLICIT = "implicit"       # Often omitted but semantically present
    FORBIDDEN = "forbidden"     # Should not appear


@dataclass
class ArgumentSlot:
    """A slot in a verb's argument structure."""
    role: str                           # Semantic role (agent, patient, etc.)
    arg_type: ArgumentType              # Required, optional, etc.
    semantic_constraints: Set[str]      # Expected primitive banks
    syntactic_realization: List[str]    # How it's typically expressed
    default_primitive: Optional[str]    # Default if implicit


@dataclass
class VerbTemplate:
    """Complete argument structure template for a verb class."""
    name: str                           # Template name
    description: str                    # What this class does
    example_verbs: List[str]            # Verbs using this template
    arguments: List[ArgumentSlot]       # Expected arguments
    semantic_type: str                  # Action, state, event, etc.
    aspect_preference: Optional[str]    # Preferred aspect (telic, atelic)


# =============================================================================
# VERB TEMPLATES
# =============================================================================

VERB_TEMPLATES: Dict[str, VerbTemplate] = {
    # Transitive action verbs
    "transitive_action": VerbTemplate(
        name="transitive_action",
        description="Agent performs action on patient",
        example_verbs=["hit", "break", "eat", "build", "write", "read"],
        arguments=[
            ArgumentSlot(
                role="agent",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE", "SOMETHING"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="action",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"DO", "MOVE"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="DO"
            ),
            ArgumentSlot(
                role="patient",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMETHING", "SOMEONE"},
                syntactic_realization=["dobj", "obj"],
                default_primitive="SOMETHING"
            ),
            ArgumentSlot(
                role="instrument",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints={"SOMETHING"},
                syntactic_realization=["prep_with", "obl"],
                default_primitive=None
            ),
        ],
        semantic_type="action",
        aspect_preference="telic"
    ),

    # Intransitive action verbs
    "intransitive_action": VerbTemplate(
        name="intransitive_action",
        description="Agent performs action (no patient)",
        example_verbs=["run", "walk", "sleep", "laugh", "cry", "dance"],
        arguments=[
            ArgumentSlot(
                role="agent",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE", "SOMETHING"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="action",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"DO", "MOVE"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="DO"
            ),
            ArgumentSlot(
                role="manner",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints=set(),
                syntactic_realization=["advmod"],
                default_primitive=None
            ),
        ],
        semantic_type="action",
        aspect_preference="atelic"
    ),

    # Ditransitive verbs (transfer)
    "ditransitive": VerbTemplate(
        name="ditransitive",
        description="Agent transfers theme to recipient",
        example_verbs=["give", "send", "tell", "show", "teach", "offer"],
        arguments=[
            ArgumentSlot(
                role="agent",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="action",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"DO"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="DO"
            ),
            ArgumentSlot(
                role="theme",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMETHING"},
                syntactic_realization=["dobj", "obj"],
                default_primitive="SOMETHING"
            ),
            ArgumentSlot(
                role="recipient",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE"},
                syntactic_realization=["iobj", "dative", "prep_to"],
                default_primitive="SOMEONE"
            ),
        ],
        semantic_type="action",
        aspect_preference="telic"
    ),

    # Mental state verbs
    "mental_state": VerbTemplate(
        name="mental_state",
        description="Experiencer has mental state about content",
        example_verbs=["know", "believe", "think", "understand", "remember"],
        arguments=[
            ArgumentSlot(
                role="experiencer",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE", "I", "YOU"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="state",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"KNOW", "THINK"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="KNOW"
            ),
            ArgumentSlot(
                role="content",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints={"SOMETHING", "WORDS"},
                syntactic_realization=["ccomp", "dobj", "obj"],
                default_primitive="SOMETHING"
            ),
        ],
        semantic_type="state",
        aspect_preference="atelic"
    ),

    # Emotion verbs
    "emotion": VerbTemplate(
        name="emotion",
        description="Experiencer feels emotion about stimulus",
        example_verbs=["love", "hate", "fear", "enjoy", "like", "dislike"],
        arguments=[
            ArgumentSlot(
                role="experiencer",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="state",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"FEEL", "GOOD", "BAD"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="FEEL"
            ),
            ArgumentSlot(
                role="theme",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMETHING", "SOMEONE"},
                syntactic_realization=["dobj", "obj"],
                default_primitive="SOMETHING"
            ),
        ],
        semantic_type="state",
        aspect_preference="atelic"
    ),

    # Perception verbs
    "perception": VerbTemplate(
        name="perception",
        description="Experiencer perceives stimulus",
        example_verbs=["see", "hear", "smell", "taste", "feel", "notice"],
        arguments=[
            ArgumentSlot(
                role="experiencer",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="action",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SEE", "HEAR"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="SEE"
            ),
            ArgumentSlot(
                role="theme",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMETHING", "SOMEONE"},
                syntactic_realization=["dobj", "obj"],
                default_primitive="SOMETHING"
            ),
        ],
        semantic_type="state",
        aspect_preference="atelic"
    ),

    # Motion verbs
    "motion": VerbTemplate(
        name="motion",
        description="Theme moves from source to goal",
        example_verbs=["go", "come", "move", "travel", "arrive", "leave"],
        arguments=[
            ArgumentSlot(
                role="theme",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE", "SOMETHING"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="action",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"MOVE"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="MOVE"
            ),
            ArgumentSlot(
                role="source",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints={"WHERE", "HERE"},
                syntactic_realization=["prep_from", "obl"],
                default_primitive="WHERE"
            ),
            ArgumentSlot(
                role="goal",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints={"WHERE", "HERE"},
                syntactic_realization=["prep_to", "obl"],
                default_primitive="WHERE"
            ),
            ArgumentSlot(
                role="location",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints={"WHERE"},
                syntactic_realization=["prep_at", "prep_in", "obl"],
                default_primitive=None
            ),
        ],
        semantic_type="action",
        aspect_preference="telic"
    ),

    # Stative verbs
    "stative": VerbTemplate(
        name="stative",
        description="Theme is in a state",
        example_verbs=["be", "exist", "remain", "stay", "seem", "appear"],
        arguments=[
            ArgumentSlot(
                role="theme",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMETHING", "SOMEONE"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMETHING"
            ),
            ArgumentSlot(
                role="state",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"BE", "EXIST"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="BE"
            ),
            ArgumentSlot(
                role="attribute",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints=set(),
                syntactic_realization=["acomp", "attr"],
                default_primitive=None
            ),
            ArgumentSlot(
                role="location",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints={"WHERE"},
                syntactic_realization=["prep", "advmod"],
                default_primitive=None
            ),
        ],
        semantic_type="state",
        aspect_preference="atelic"
    ),

    # Communication verbs
    "communication": VerbTemplate(
        name="communication",
        description="Speaker communicates message to addressee",
        example_verbs=["say", "tell", "ask", "explain", "describe", "report"],
        arguments=[
            ArgumentSlot(
                role="agent",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="action",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SAY", "WORDS"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="SAY"
            ),
            ArgumentSlot(
                role="content",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints={"WORDS", "SOMETHING"},
                syntactic_realization=["ccomp", "dobj"],
                default_primitive="WORDS"
            ),
            ArgumentSlot(
                role="recipient",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints={"SOMEONE"},
                syntactic_realization=["iobj", "prep_to"],
                default_primitive="SOMEONE"
            ),
        ],
        semantic_type="action",
        aspect_preference="telic"
    ),

    # Causative verbs
    "causative": VerbTemplate(
        name="causative",
        description="Causer causes caused event",
        example_verbs=["make", "cause", "let", "force", "allow", "enable"],
        arguments=[
            ArgumentSlot(
                role="agent",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE", "SOMETHING"},
                syntactic_realization=["nsubj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="action",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"DO", "HAPPEN"},
                syntactic_realization=["ROOT", "verb"],
                default_primitive="DO"
            ),
            ArgumentSlot(
                role="patient",
                arg_type=ArgumentType.REQUIRED,
                semantic_constraints={"SOMEONE", "SOMETHING"},
                syntactic_realization=["dobj"],
                default_primitive="SOMEONE"
            ),
            ArgumentSlot(
                role="result",
                arg_type=ArgumentType.OPTIONAL,
                semantic_constraints={"DO", "BE"},
                syntactic_realization=["xcomp", "ccomp"],
                default_primitive="DO"
            ),
        ],
        semantic_type="action",
        aspect_preference="telic"
    ),
}

# Verb to template mapping
VERB_TO_TEMPLATE: Dict[str, str] = {}
for template_name, template in VERB_TEMPLATES.items():
    for verb in template.example_verbs:
        VERB_TO_TEMPLATE[verb] = template_name


class VerbTemplateHandler:
    """
    Handle verb argument structure templates.

    Provides:
    - Template lookup for verbs
    - Argument validation
    - Implicit argument inference
    - Decomposition guidance
    """

    def __init__(self):
        self.templates = VERB_TEMPLATES
        self.verb_to_template = VERB_TO_TEMPLATE

    def get_template(self, verb: str) -> Optional[VerbTemplate]:
        """Get the template for a verb."""
        verb_lower = verb.lower()
        template_name = self.verb_to_template.get(verb_lower)
        if template_name:
            return self.templates.get(template_name)
        return None

    def get_required_roles(self, verb: str) -> List[str]:
        """Get list of required semantic roles for a verb."""
        template = self.get_template(verb)
        if not template:
            return []
        return [
            slot.role for slot in template.arguments
            if slot.arg_type == ArgumentType.REQUIRED
        ]

    def get_optional_roles(self, verb: str) -> List[str]:
        """Get list of optional semantic roles for a verb."""
        template = self.get_template(verb)
        if not template:
            return []
        return [
            slot.role for slot in template.arguments
            if slot.arg_type == ArgumentType.OPTIONAL
        ]

    def validate_arguments(
        self,
        verb: str,
        present_roles: Set[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that required arguments are present.

        Returns:
            (is_valid, list of missing required roles)
        """
        template = self.get_template(verb)
        if not template:
            return True, []  # Unknown verb, assume valid

        missing = []
        for slot in template.arguments:
            if slot.arg_type == ArgumentType.REQUIRED:
                if slot.role not in present_roles:
                    missing.append(slot.role)

        return len(missing) == 0, missing

    def infer_implicit_arguments(
        self,
        verb: str,
        present_roles: Set[str]
    ) -> List[Tuple[str, str]]:
        """
        Infer implicit arguments that should be added to decomposition.

        Returns:
            List of (primitive, role) pairs for implicit arguments
        """
        template = self.get_template(verb)
        if not template:
            return []

        implicit = []
        for slot in template.arguments:
            if slot.role not in present_roles:
                if slot.arg_type in [ArgumentType.REQUIRED, ArgumentType.IMPLICIT]:
                    if slot.default_primitive:
                        implicit.append((slot.default_primitive, slot.role))

        return implicit

    def get_decomposition_primitives(self, verb: str) -> List[Tuple[str, str]]:
        """
        Get recommended primitives for a verb's decomposition.

        Returns:
            List of (primitive, role) pairs that should appear in decomposition
        """
        template = self.get_template(verb)
        if not template:
            return [("DO", "action")]  # Default for unknown verbs

        result = []
        for slot in template.arguments:
            if slot.default_primitive and slot.arg_type == ArgumentType.REQUIRED:
                result.append((slot.default_primitive, slot.role))

        return result

    def get_semantic_type(self, verb: str) -> str:
        """Get the semantic type (action, state, event) for a verb."""
        template = self.get_template(verb)
        if template:
            return template.semantic_type
        return "action"  # Default

    def get_aspect_preference(self, verb: str) -> Optional[str]:
        """Get the preferred aspect for a verb (telic, atelic)."""
        template = self.get_template(verb)
        if template:
            return template.aspect_preference
        return None


# Singleton instance
_handler = None


def get_verb_template_handler() -> VerbTemplateHandler:
    """Get or create the verb template handler singleton."""
    global _handler
    if _handler is None:
        _handler = VerbTemplateHandler()
    return _handler
