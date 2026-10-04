"""
Symbolic Proof Suite — Phase B7.

Validates the architecture-document line 154 query list end-to-end:
each of the user's specific requirements for "if the input is 'The dog
is cuter than the cat', we should be able to use the output to recover
[...]" becomes one test method here.

Anchors in ``sentence_architecture.md``:

* Line 154: the full validation query list.
* Line 159: "HDC space operations are the semantic grounding of the
  words/semantic architecture, so the two sentences should be *quite*
  similar in HDC space, but the exact set theory/order of operations/
  logical operations should be provably distinct for arbitrary
  truth/comparative operations on the primitives encoded in the input
  sentence."
* Line 164: "The API for engaging with the system should be pure python/
  order of operations/set theory."

This module is invokable as ``python -m gse.verification.symbolic_proof_suite``
or via the test runner (``tests/test_symbolic_proof_suite.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from gse.api import GSEEncoder
from gse.symbolic import (
    Comparison,
    clauses,
    entity_lemmas,
    evaluate_tree,
    from_trace,
    is_argument_swap_of,
    is_logically_equal_to,
    predicates,
    resolve,
    substitute,
    to_json,
)


@dataclass
class ProofResult:
    """One proof's outcome."""

    name: str
    passed: bool
    description: str
    detail: str = ""


@dataclass
class ProofSuiteResult:
    """Aggregate result over the full suite."""

    results: List[ProofResult] = field(default_factory=list)

    @property
    def n_passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def n_total(self) -> int:
        return len(self.results)

    def print_report(self) -> None:
        print()
        print("=" * 78)
        print("GSE Symbolic Proof Suite — line 154 architecture validation")
        print("=" * 78)
        for r in self.results:
            mark = "✓" if r.passed else "✗"
            print(f"  {mark} {r.name}")
            print(f"      {r.description}")
            if r.detail:
                print(f"      detail: {r.detail}")
        print()
        print(f"  Total: {self.n_passed}/{self.n_total} proofs passed.")
        print()


def _pipeline(encoder: GSEEncoder, sentence: str):
    """Encode → AST → resolve → evaluate. Returns the evaluated tree."""
    return evaluate_tree(resolve(from_trace(encoder.encode(sentence))))


# ---------------------------------------------------------------------------
# Individual proofs
# ---------------------------------------------------------------------------


def proof_recover_entities(encoder: GSEEncoder) -> ProofResult:
    """L154 requirement: 'recover what animals we're talking about'."""
    tree = _pipeline(encoder, "The dog is cuter than the cat")
    lemmas = entity_lemmas(tree)
    has_dog = "dog" in lemmas
    has_cat = "cat" in lemmas
    return ProofResult(
        name="recover_entities",
        passed=has_dog and has_cat,
        description="Symbolic layer recovers the two animals.",
        detail=f"entity lemmas = {lemmas}",
    )


def proof_recover_cuteness_assertion(encoder: GSEEncoder) -> ProofResult:
    """L154 requirement: 'cuteness information about the dog as being >0'.

    Symbolic layer should produce a Comparison predicate with the dog on
    the positive side.
    """
    tree = _pipeline(encoder, "The dog is cuter than the cat")
    preds = predicates(tree)
    comparisons = [p for p in preds if isinstance(p, Comparison)]
    if not comparisons:
        return ProofResult(
            name="recover_cuteness_assertion",
            passed=False,
            description="Comparison predicate exists.",
            detail=f"predicates = {[type(p).__name__ for p in preds]}",
        )
    c = comparisons[0]
    dog_on_lhs = _contains_lemma(c.lhs, "dog")
    cat_on_rhs = _contains_lemma(c.rhs, "cat")
    return ProofResult(
        name="recover_cuteness_assertion",
        passed=dog_on_lhs and cat_on_rhs and c.sign > 0,
        description="Comparison(lhs=dog, rhs=cat, sign>0) recovered.",
        detail=f"sign={c.sign}, dog_on_lhs={dog_on_lhs}, cat_on_rhs={cat_on_rhs}",
    )


def proof_distinguish_argument_swap(encoder: GSEEncoder) -> ProofResult:
    """L154 + L159: 'the cat is cuter than the dog' is *provably distinct*
    symbolically despite high HDC similarity."""
    tree_orig = _pipeline(encoder, "The dog is cuter than the cat")
    tree_swap = _pipeline(encoder, "The cat is cuter than the dog")
    # Symbolic distinction
    sym_distinct = not is_logically_equal_to(tree_orig, tree_swap)
    sym_swap = is_argument_swap_of(tree_orig, tree_swap)
    # HDC similarity (the architecture says they SHOULD be similar)
    hdc_sim = encoder.encode("The dog is cuter than the cat").vector.cosine(
        encoder.encode("The cat is cuter than the dog").vector
    )
    return ProofResult(
        name="distinguish_argument_swap",
        passed=sym_distinct and sym_swap and hdc_sim > 0.5,
        description="Symbolically distinct + structurally argument-swap, while HDC stays similar.",
        detail=(f"symbolic_distinct={sym_distinct}, is_argument_swap={sym_swap}, hdc_sim={hdc_sim:.4f}"),
    )


def proof_templating_preserves_structure(encoder: GSEEncoder) -> ProofResult:
    """L154 requirement: '<animal in lexicon> is cuter than <second animal in lexicon>'.

    Substitute entities and verify the template is structurally equivalent
    to the corresponding fresh-encoded sentence.
    """
    tree_orig = _pipeline(encoder, "The dog is cuter than the cat")
    templated = substitute(tree_orig, {"dog": "rabbit", "cat": "mouse"})
    tree_fresh = _pipeline(encoder, "The rabbit is cuter than the mouse")
    same_structure = is_logically_equal_to(templated, tree_fresh)
    return ProofResult(
        name="templating_preserves_structure",
        passed=same_structure,
        description="substitute(dog→rabbit, cat→mouse) ≡ fresh 'rabbit cuter than mouse'.",
        detail=f"logical_equality={same_structure}",
    )


def proof_causation_directionality(encoder: GSEEncoder) -> ProofResult:
    """SO and BECAUSE encode different causal directions despite shared content."""
    so = _pipeline(encoder, "Mike sang so Rex left")
    bc = _pipeline(encoder, "Mike left because Rex sang")
    # Both should produce a Causation predicate; with the cause being the
    # one who 'sang' in each case.
    so_preds = predicates(so)
    bc_preds = predicates(bc)
    so_causation = next((p for p in so_preds if type(p).__name__ == "Causation"), None)
    bc_causation = next((p for p in bc_preds if type(p).__name__ == "Causation"), None)
    if so_causation is None or bc_causation is None:
        return ProofResult(
            name="causation_directionality",
            passed=False,
            description="Both SO and BECAUSE produce a Causation predicate.",
            detail=f"so_preds={[type(p).__name__ for p in so_preds]}, bc_preds={[type(p).__name__ for p in bc_preds]}",
        )
    # In SO: "Mike sang so Rex left" → cause is sang (Mike's), effect is left (Rex's)
    so_cause_correct = _contains_lemma(so_causation.cause, "mike")
    so_effect_correct = _contains_lemma(so_causation.effect, "rex")
    # In BECAUSE: "Mike left because Rex sang" → cause is Rex's sang, effect is Mike's left
    bc_cause_correct = _contains_lemma(bc_causation.cause, "rex")
    bc_effect_correct = _contains_lemma(bc_causation.effect, "mike")
    return ProofResult(
        name="causation_directionality",
        passed=(so_cause_correct and so_effect_correct and bc_cause_correct and bc_effect_correct),
        description="SO: cause=left-side ent, BECAUSE: cause=right-side ent.",
        detail=(
            f"SO: cause_is_mike={so_cause_correct} effect_is_rex={so_effect_correct}; "
            f"BECAUSE: cause_is_rex={bc_cause_correct} effect_is_mike={bc_effect_correct}"
        ),
    )


def proof_json_roundtrip(encoder: GSEEncoder) -> ProofResult:
    """L152: 'decoded set of mathematical operations in a JSON ... can be
    processed and reconstructed'. Round-trip preserves structure."""
    from gse.symbolic import from_json

    tree = _pipeline(encoder, "The dog is cuter than the cat")
    json_str = to_json(tree)
    restored = from_json(json_str)
    same_structure = is_logically_equal_to(tree, restored)
    return ProofResult(
        name="json_roundtrip",
        passed=same_structure,
        description="Tree → JSON → tree preserves logical structure.",
        detail=f"logical_equality={same_structure}, json_bytes={len(json_str)}",
    )


def proof_bipolar_distinct_from_relational(encoder: GSEEncoder) -> ProofResult:
    """L10/L154: 'love'/'hate' (intense relational) and 'big'/'small'
    (true bipolar primitives) have categorically different similarity
    profiles. Big/small should be more strongly opposed in EVAL bank than
    love/hate."""
    from gse.primitives_v2 import DIMS_PER_BANK, SemanticBank

    bs_pos = encoder.encode("big").vector
    bs_neg = encoder.encode("small").vector
    bs_eval = bs_pos.with_bank_only(SemanticBank.EVALUATORS.value, DIMS_PER_BANK).cosine(
        bs_neg.with_bank_only(SemanticBank.EVALUATORS.value, DIMS_PER_BANK)
    )
    lh_pos = encoder.encode("love").vector
    lh_neg = encoder.encode("hate").vector
    lh_eval = lh_pos.with_bank_only(SemanticBank.EVALUATORS.value, DIMS_PER_BANK).cosine(
        lh_neg.with_bank_only(SemanticBank.EVALUATORS.value, DIMS_PER_BANK)
    )
    # The architecture says big/small should be MORE strongly opposite
    # than love/hate (which share both being intense+relational).
    passed = bs_eval <= lh_eval - 0.1 or bs_eval <= -0.9
    return ProofResult(
        name="bipolar_distinct_from_relational",
        passed=passed,
        description="big/small EVAL cos more negative than love/hate EVAL cos.",
        detail=f"big/small EVAL={bs_eval:.3f}, love/hate EVAL={lh_eval:.3f}",
    )


def proof_clause_nesting(encoder: GSEEncoder) -> ProofResult:
    """Multi-clause nesting (the inversion fix).

    In "Rex barks because the dog is cuter than the cat", the within-clause
    THAN comparison must nest as the *cause* of the clause-linking BECAUSE —
    ``Causation(cause=Comparison(dog, cat), effect=rex)`` — not the positional
    inverse ``Comparison(Causation(...), cat)``. See
    ``docs/COMPLEX_SENTENCE_DESIGN.md`` §0.
    """
    tree = _pipeline(encoder, "Rex barks because the dog is cuter than the cat")
    preds = predicates(tree)
    caus = next((p for p in preds if type(p).__name__ == "Causation"), None)
    if caus is None:
        return ProofResult(
            name="clause_nesting",
            passed=False,
            description="BECAUSE nests the THAN comparison as its cause.",
            detail=f"no Causation; preds={[type(p).__name__ for p in preds]}",
        )
    cause_is_comparison = type(caus.cause).__name__ == "Comparison"
    cause_has_pair = _contains_lemma(caus.cause, "dog") and _contains_lemma(caus.cause, "cat")
    effect_has_rex = _contains_lemma(caus.effect, "rex")
    return ProofResult(
        name="clause_nesting",
        passed=cause_is_comparison and cause_has_pair and effect_has_rex,
        description="BECAUSE nests the THAN comparison as its cause, not the inverse.",
        detail=(
            f"cause_is_Comparison={cause_is_comparison}, "
            f"cause⊇{{dog,cat}}={cause_has_pair}, effect∋rex={effect_has_rex}"
        ),
    )


def proof_clause_order_distinct(encoder: GSEEncoder) -> ProofResult:
    """Clause-order distinctness — the argument-swap jewel, lifted to clauses.

    "Mike sang because Rex left" vs "Rex left because Mike sang" must be
    *symbolically distinct* (cause/effect swapped) while staying *HDC-similar*
    — the same result as dog/cat comparison swap, one scale up
    (``complex_sentence_architecture.md`` §5).
    """
    a = _pipeline(encoder, "Mike sang because Rex left")
    b = _pipeline(encoder, "Rex left because Mike sang")
    sym_distinct = not is_logically_equal_to(a, b)
    hdc_sim = encoder.encode("Mike sang because Rex left").vector.cosine(
        encoder.encode("Rex left because Mike sang").vector
    )
    return ProofResult(
        name="clause_order_distinct",
        passed=sym_distinct and hdc_sim > 0.5,
        description="X because Y ≠ Y because X symbolically, while HDC stays similar.",
        detail=f"symbolic_distinct={sym_distinct}, hdc_sim={hdc_sim:.4f}",
    )


def proof_np_coordination(encoder: GSEEncoder) -> ProofResult:
    """NP-coordination — set-union of subjects sharing one predicate.

    "Spot and Rex are dogs" must recover *both* coordinated subjects (not drop
    one) and apply the single predicate over the union
    (``complex_sentence_architecture.md`` §3.3). The comparison form
    "Spot and Rex are cuter than the cat" must likewise keep both subjects and
    still recover the axis.
    """
    tree = _pipeline(encoder, "Spot and Rex are dogs")
    lemmas = entity_lemmas(tree)
    both_subjects = "spot" in lemmas and "rex" in lemmas
    preds = predicates(tree)
    has_type_assertion = any(type(p).__name__ == "TypeAssertion" for p in preds)

    cmp_tree = _pipeline(encoder, "Spot and Rex are cuter than the cat")
    cmp_lemmas = entity_lemmas(cmp_tree)
    both_in_comparison = "spot" in cmp_lemmas and "rex" in cmp_lemmas

    return ProofResult(
        name="np_coordination",
        passed=both_subjects and has_type_assertion and both_in_comparison,
        description="'Spot and Rex are dogs' keeps both subjects under one predicate.",
        detail=(
            f"both_subjects={both_subjects}, TypeAssertion={has_type_assertion}, "
            f"both_in_comparison={both_in_comparison} (lemmas={cmp_lemmas})"
        ),
    )


def proof_relative_clause(encoder: GSEEncoder) -> ProofResult:
    """Relative clause (embedded, nested span) restricts its antecedent.

    "The dog that barks is big" → a RelativeRestriction whose head is the dog
    and whose restriction asserts barking. And it must *compose in place*:
    "The dog that barks is cuter than the cat" → a Comparison whose lhs is the
    restricted dog, with both predicates recoverable (§M2b, the nested-span
    embedding).
    """
    tree = _pipeline(encoder, "The dog that barks is big")
    preds = predicates(tree)
    rr = next((p for p in preds if type(p).__name__ == "RelativeRestriction"), None)
    if rr is None:
        return ProofResult(
            name="relative_clause",
            passed=False,
            description="Relative clause produces a RelativeRestriction.",
            detail=f"preds={[type(p).__name__ for p in preds]}",
        )
    head_is_dog = _contains_lemma(rr.head, "dog")
    restriction_is_bark = _contains_lemma(rr.restriction, "bark")

    comp_tree = _pipeline(encoder, "The dog that barks is cuter than the cat")
    names = [type(p).__name__ for p in predicates(comp_tree)]
    composes = "Comparison" in names and "RelativeRestriction" in names

    return ProofResult(
        name="relative_clause",
        passed=head_is_dog and restriction_is_bark and composes,
        description="who/which/that restricts the antecedent and composes in place.",
        detail=(
            f"head∋dog={head_is_dog}, restriction∋bark={restriction_is_bark}, "
            f"composes_with_comparison={composes} ({names})"
        ),
    )


def proof_systematicity(encoder: GSEEncoder) -> ProofResult:
    """Systematicity — woodles-and-weedles, lifted to clauses.

    A multi-clause structure must decompose through the *same* machinery
    regardless of the content words in it. We isolate GSE's content-independence
    from spaCy's (fallible) parsing of nonsense words by substituting novel
    lemmas onto the symbolic tree: the predicate types, nesting, and clause
    count must be preserved while the entities become the novel ones. (Surface
    parsing of nonsense words is bounded by the spaCy front-end — the one
    non-deterministic component — which is why this operates on the tree.)
    """
    tree = _pipeline(encoder, "The dog that barks is cuter than the cat")
    novel = substitute(tree, {"dog": "zorble", "cat": "florp", "bark": "blib"})

    orig_types = [type(p).__name__ for p in predicates(tree)]
    novel_types = [type(p).__name__ for p in predicates(novel)]
    same_shape = orig_types == novel_types and len(clauses(tree)) == len(clauses(novel))

    novel_lemmas = entity_lemmas(novel)
    swapped = "zorble" in novel_lemmas and "florp" in novel_lemmas and "dog" not in novel_lemmas

    return ProofResult(
        name="systematicity",
        passed=same_shape and swapped,
        description="Novel content decomposes through the same clause machinery.",
        detail=(f"shape_preserved={same_shape} ({orig_types}), entities_swapped={swapped} ({novel_lemmas})"),
    )


def proof_control(encoder: GSEEncoder) -> ProofResult:
    """Control 'to' — controller carries out the inner infinitival clause.

    "Mike wants to leave" → ``Control(controller=Mike, inner=leave)`` (subject
    control). "Lady Macbeth persuaded Macbeth to kill the king" → controller is
    the object Macbeth (object control). And it must nest under a clause-linking
    operator: "Mike wants to leave because Rex barks" → a Causation whose effect
    is the Control (§M2c).
    """
    subj = _pipeline(encoder, "Mike wants to leave")
    subj_ctrl = next((p for p in predicates(subj) if type(p).__name__ == "Control"), None)
    subj_ok = subj_ctrl is not None and _contains_lemma(subj_ctrl.controller, "mike")

    obj = _pipeline(encoder, "Lady Macbeth persuaded Macbeth to kill the king")
    obj_ctrl = next((p for p in predicates(obj) if type(p).__name__ == "Control"), None)
    obj_ok = obj_ctrl is not None and _contains_lemma(obj_ctrl.controller, "macbeth")

    nested = _pipeline(encoder, "Mike wants to leave because Rex barks")
    nested_names = [type(p).__name__ for p in predicates(nested)]
    nests = "Causation" in nested_names and "Control" in nested_names

    return ProofResult(
        name="control",
        passed=subj_ok and obj_ok and nests,
        description="'to' control binds the controller and nests under because.",
        detail=(
            f"subject_control_mike={subj_ok}, object_control_macbeth={obj_ok}, "
            f"nests_under_because={nests} ({nested_names})"
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contains_lemma(node, lemma: str) -> bool:
    """True if some Atom/Entity in the subtree has this lemma."""
    if hasattr(node, "head"):  # Entity
        if node.head.lemma == lemma:
            return True
        if getattr(node, "possessor", None) is not None:
            return _contains_lemma(node.possessor, lemma)
        return False
    if hasattr(node, "lemma"):  # Atom
        return node.lemma == lemma
    if hasattr(node, "args"):  # Op — the verb lemma rides on ``primitive``
        if getattr(node, "primitive", None) == lemma:
            return True
        return any(_contains_lemma(a, lemma) for a in node.args)
    if hasattr(node, "atoms"):  # Phrase
        return any(a.lemma == lemma for a in node.atoms)
    # The verb lemma of an evaluated Event/Control predicate is a string field.
    if getattr(node, "verb", None) == lemma:
        return True
    # Predicates with content fields
    for fld in (
        "lhs",
        "rhs",
        "entity",
        "kind",
        "cause",
        "effect",
        "left",
        "right",
        "threshold",
        "purpose",
        "member",
        "predicate",
        "agent",
        "patient",
        "controller",
        "inner",
        "head",
        "restriction",
    ):
        sub = getattr(node, fld, None)
        if sub is not None and _contains_lemma(sub, lemma):
            return True
    return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


PROOFS = [
    proof_recover_entities,
    proof_recover_cuteness_assertion,
    proof_distinguish_argument_swap,
    proof_templating_preserves_structure,
    proof_causation_directionality,
    proof_json_roundtrip,
    proof_bipolar_distinct_from_relational,
    proof_clause_nesting,
    proof_clause_order_distinct,
    proof_np_coordination,
    proof_relative_clause,
    proof_control,
    proof_systematicity,
]


def run_all(encoder: Optional[GSEEncoder] = None) -> ProofSuiteResult:
    enc = encoder or GSEEncoder()
    suite = ProofSuiteResult()
    for proof in PROOFS:
        suite.results.append(proof(enc))
    return suite


def main():
    result = run_all()
    result.print_report()
    return 0 if result.n_passed == result.n_total else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
