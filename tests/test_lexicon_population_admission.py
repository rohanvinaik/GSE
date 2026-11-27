"""The admission gate (rebuild-lexicon-symbolic-closure task 8.2; Significance Weighting sections 14 and 16).

Every population here is written for the test. The banks are real bank names, but the facts are not lexical
claims.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from GSE.curation.lexicon_builder import admission, coherence
from GSE.curation.lexicon_builder.admission import (
    ADMITTED,
    DEGENERATE,
    FINDING,
    NARROWED,
    NO_REACH,
    UNCONFIRMED,
    UNEXPOSED,
    admission_round,
    judge,
)
from GSE.curation.lexicon_builder.cells import BANK_INDEX, NEG, POS, SILENT, ZERO, State
from GSE.curation.lexicon_builder.closure import close
from GSE.curation.lexicon_builder.coherence import Candidate, Derivation, Observation, Types, apply, censor, settle
from GSE.curation.lexicon_builder.relations import Relation, implies


def _obs(row, bank, states, root, generalizes=True):
    """The root's letters name its dataset: a0 and a1 are dataset a, b0 is dataset b."""
    return Observation(f"t:{row}", bank, states, root.split(":")[0].rstrip("0123456789"), root, generalizes)


def _world(n, observations, facts, derivations=(), relations=(), scopes=None, know=False):
    """`know` closes the stated facts under `relations` and lets those known consequences refute and expose."""
    readings = tuple(f"t:{i}" for i in range(n))
    s = settle(observations, readings)
    state = State.opening(readings)
    conflicts = apply(state, s, derivations)
    scopes = dict(scopes or {})
    close(state, relations, scopes)
    if know:
        general = State.opening(readings)
        apply(general, s.generalizing(), derivations)
        close(general, relations, scopes)
        s = s.excluding(conflicts).knowing(state, general)
    return s, Types.build(n, facts), state, list(relations), scopes


def _judge(candidates, world):
    s, types, state, relations, scopes = world
    return {v.candidate.rule_id: v for v in judge(candidates, s, types, state, relations, scopes)}


def _cell(state, row, bank):
    return int(state.masks[row, BANK_INDEX[bank]])


MOVE_ALIVE = Candidate((("MOVE", POS),), "ALIVE", POS, ("t:animal",))


def _near_miss(row):
    """A reading that neither moves nor lives: ALIVE stated outside {+1}, so it exposes MOVE => ALIVE."""
    return [_obs(row, "MOVE", ZERO, f"m{row}"), _obs(row, "ALIVE", ZERO, f"n{row}")]


def _animals():
    # Rows 0-1 are witnesses, row 2 is unknown, row 3 exposes the rule, rows 4-5 state nothing.
    return _world(
        6,
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "MOVE", POS, "a1"),
            _obs(1, "ALIVE", POS, "b1"),
            _obs(2, "MOVE", POS, "a2"),
            *_near_miss(3),
        ],
        {"t:animal": np.arange(6)},
    )


def test_an_exact_set_relation_with_no_counterexample_is_admitted_and_fires_beyond_its_witnesses():
    world = _animals()
    v = _judge([MOVE_ALIVE], world)[MOVE_ALIVE.rule_id]
    assert v.verdict == ADMITTED
    assert isinstance(v.relation, Relation)
    assert v.relation.scope == "coherence:t:animal"
    assert "2 stated witness readings" in v.relation.warrant
    s, types, state, relations, scopes = world
    close(state, [v.relation], {v.relation.scope: types.mask(MOVE_ALIVE.scope)})
    assert _cell(state, 2, "ALIVE") == POS
    assert _cell(state, 4, "ALIVE") & ZERO


def test_a_rule_the_population_could_not_have_broken_is_unexposed():
    # Every stated ALIVE is +1, so "MOVE => ALIVE" has witnesses and no counterexample only because nothing
    # else was ever stated (the shape of the old GOOD=0 => SOMETHING=+1).
    world = _world(
        4,
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "MOVE", POS, "a1"),
            _obs(1, "ALIVE", POS, "b1"),
            _obs(2, "MOVE", POS, "a2"),
        ],
        {"t:animal": np.arange(4)},
    )
    v = _judge([MOVE_ALIVE], world)[MOVE_ALIVE.rule_id]
    assert v.verdict == UNEXPOSED and v.relation is None and v.reach is None
    assert v.evidence.witnesses.tolist() == [0, 1] and not v.evidence.counterexamples.size


def _one_witness_many_unknowns(exposer):
    # Row 0 is the only witness; rows 1-40 move with ALIVE unstated; row 45 is the candidate exposer.
    obs = [_obs(0, "MOVE", POS, "a0"), _obs(0, "ALIVE", POS, "b0")]
    obs += [_obs(r, "MOVE", POS, f"a{r}") for r in range(1, 41)]
    return _world(50, obs + exposer, {"t:animal": np.arange(50)}, know=True)


def test_a_single_witness_rule_whose_only_exposer_is_reading_confined_is_unexposed():
    confined = [_obs(45, "MOVE", ZERO, "p45", generalizes=False), _obs(45, "ALIVE", ZERO, "p45", generalizes=False)]
    v = _judge([MOVE_ALIVE], _one_witness_many_unknowns(confined))[MOVE_ALIVE.rule_id]
    assert v.verdict == UNEXPOSED and v.evidence.unknown.size == 40 and not v.evidence.exposure.size


def test_a_stated_near_miss_exposes_and_the_rule_is_admitted():
    v = _judge([MOVE_ALIVE], _one_witness_many_unknowns(_near_miss(45)))[MOVE_ALIVE.rule_id]
    assert v.verdict == ADMITTED and v.evidence.exposure.tolist() == [45]
    assert v.evidence.witness_families == ("a", "b")


def test_an_exposer_whose_antecedent_bank_is_unstated_does_not_count():
    v = _judge([MOVE_ALIVE], _one_witness_many_unknowns([_obs(45, "ALIVE", ZERO, "n45")]))[MOVE_ALIVE.rule_id]
    assert v.verdict == UNEXPOSED and not v.evidence.exposure.size


def test_a_reading_outside_the_scope_does_not_expose_the_rule():
    world = _world(
        5,
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "MOVE", POS, "a1"),
            *_near_miss(4),
        ],
        {"t:animal": np.arange(4), "t:artifact": np.array([4])},
    )
    assert _judge([MOVE_ALIVE], world)[MOVE_ALIVE.rule_id].verdict == UNEXPOSED


# A law written for the test: a reading that does not move is not alive.
STILL_NOT_ALIVE = implies("law:still", "MOVE", ZERO, "ALIVE", ZERO, "a law written for the test")


def test_a_known_consequence_of_a_law_exposes_the_rule():
    # No source states ALIVE outside +1; the law derives ALIVE=0 on row 3 from its stated MOVE=0.
    obs = [
        _obs(0, "MOVE", POS, "a0"),
        _obs(0, "ALIVE", POS, "b0"),
        _obs(1, "MOVE", POS, "a1"),
        _obs(1, "ALIVE", POS, "b1"),
        _obs(2, "MOVE", POS, "a2"),
        _obs(3, "MOVE", ZERO, "m3"),
    ]
    unknown_law = _world(6, obs, {"t:animal": np.arange(6)}, relations=[STILL_NOT_ALIVE])
    assert _judge([MOVE_ALIVE], unknown_law)[MOVE_ALIVE.rule_id].verdict == UNEXPOSED
    known = _world(6, obs, {"t:animal": np.arange(6)}, relations=[STILL_NOT_ALIVE], know=True)
    v = _judge([MOVE_ALIVE], known)[MOVE_ALIVE.rule_id]
    assert v.evidence.exposure.tolist() == [3] and v.verdict == ADMITTED


def test_a_known_consequence_of_a_law_contradicts_but_never_confirms():
    # Row 1 moves and touches (stated); the law derives ALIVE=0 there, a known counterexample.
    law = implies("law:artifact", "TOUCH", POS, "ALIVE", ZERO, "a law written for the test")
    obs = [
        _obs(0, "MOVE", POS, "a0"),
        _obs(0, "ALIVE", POS, "b0"),
        _obs(1, "MOVE", POS, "a1"),
        _obs(1, "TOUCH", POS, "c1"),
        _obs(2, "MOVE", POS, "a2"),
    ]
    world = _world(4, obs, {"t:animal": np.arange(4)}, relations=[law], know=True)
    v = _judge([MOVE_ALIVE], world)[MOVE_ALIVE.rule_id]
    assert v.evidence.counterexamples.tolist() == [1] and v.verdict == FINDING
    # The same law's consequence agrees with MOVE => ALIVE{0} on row 1, and that is not a confirmation.
    moving_dead = Candidate((("MOVE", POS),), "ALIVE", ZERO, ("t:animal",))
    v = _judge([moving_dead], world)[moving_dead.rule_id]
    assert v.verdict == UNCONFIRMED and v.evidence.known_agreement.tolist() == [1]
    assert 1 not in v.evidence.unknown.tolist()


def test_unknowns_are_not_counterexamples_so_the_candidate_is_not_narrowed():
    v = _judge([MOVE_ALIVE], _animals())[MOVE_ALIVE.rule_id]
    assert v.evidence.unknown.tolist() == [2]
    assert not v.evidence.counterexamples.size and v.verdict == ADMITTED


def test_a_relation_whose_only_support_is_derived_is_refused():
    # ALIVE is decided on rows 0-1 by a derivation and by a closure law, never by a stated source.
    law = implies("law:test", "FEEL", POS, "ALIVE", POS, "a law written for the test")
    world = _world(
        4,
        [_obs(0, "MOVE", POS, "a0"), _obs(1, "MOVE", POS, "a1"), _obs(1, "FEEL", POS, "f1")],
        {"t:animal": np.arange(4)},
        derivations=[Derivation("t:0", "ALIVE", POS, "law:other", ("a0",))],
        relations=[law],
    )
    assert _cell(world[2], 0, "ALIVE") == POS and _cell(world[2], 1, "ALIVE") == POS
    v = _judge([MOVE_ALIVE], world)[MOVE_ALIVE.rule_id]
    assert v.verdict == UNCONFIRMED and v.relation is None


def _vehicles():
    # Rows 0-1 animals that move and live, row 2 an animal that moves, row 3 an animal that neither moves nor lives;
    # row 5 a vehicle that moves and is not alive, row 6 one that moves.
    return _world(
        7,
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "MOVE", POS, "a1"),
            _obs(1, "ALIVE", POS, "b1"),
            _obs(2, "MOVE", POS, "a2"),
            *_near_miss(3),
            _obs(5, "MOVE", POS, "a5"),
            _obs(5, "ALIVE", ZERO, "b5"),
            _obs(6, "MOVE", POS, "a6"),
        ],
        {"t:entity": np.arange(7), "t:animal": np.array([0, 1, 2, 3]), "t:artifact": np.array([4, 5, 6])},
    )


def test_a_relation_with_a_counterexample_is_narrowed_by_the_type_that_separates_it():
    broad = Candidate((("MOVE", POS),), "ALIVE", POS, ("t:entity",))
    verdicts = _judge([broad], _vehicles())
    v = verdicts[broad.rule_id]
    assert v.verdict == NARROWED and v.guards == ("t:animal",)
    assert v.evidence.counterexamples.tolist() == [5]
    child = verdicts["coherence:implication:[t:animal]:MOVE{+1}=>ALIVE{+1}"]
    assert child.verdict == ADMITTED
    assert child.reach.rows.tolist() == [2]


def test_witness_and_counterexample_sharing_every_type_is_a_finding_with_the_exact_readings():
    world = _world(
        2,
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "MOVE", POS, "a1"),
            _obs(1, "ALIVE", ZERO, "b1"),
        ],
        {"t:entity": np.arange(2), "t:animal": np.arange(2)},
    )
    cand = Candidate((("MOVE", POS),), "ALIVE", POS, ("t:entity",))
    v = _judge([cand], world)[cand.rule_id]
    assert v.verdict == FINDING and not v.guards
    assert "[t:0]" in v.note and "[t:1]" in v.note


def test_a_rule_whose_consequences_are_already_reached_has_no_reach():
    world = _world(
        3,
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "MOVE", POS, "a1"),
            _obs(1, "ALIVE", POS, "b1"),
            *_near_miss(2),
        ],
        {"t:animal": np.arange(3)},
    )
    v = _judge([MOVE_ALIVE], world)[MOVE_ALIVE.rule_id]
    assert v.verdict == NO_REACH and not v.reach.removed


def test_a_rule_implied_by_a_stronger_admitted_rule_in_the_same_round_has_no_reach():
    world = _world(
        6,
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            *_near_miss(1),
            _obs(2, "MOVE", POS, "a2"),
            _obs(3, "MOVE", POS, "a3"),
        ],
        {"t:animal": np.arange(6), "t:mammal": np.array([0, 1, 2])},
    )
    narrow = Candidate((("MOVE", POS),), "ALIVE", POS, ("t:mammal",))
    verdicts = _judge([narrow, MOVE_ALIVE], world)
    assert verdicts[MOVE_ALIVE.rule_id].verdict == ADMITTED
    assert verdicts[narrow.rule_id].verdict == NO_REACH
    assert MOVE_ALIVE.rule_id in verdicts[narrow.rule_id].note


def test_a_candidate_that_empties_a_cell_the_closure_holds_is_degenerate():
    # Row 2's ALIVE is 0 by a derivation; the rule would leave it with no lawful state.
    world = _world(
        4,
        [_obs(0, "MOVE", POS, "a0"), _obs(0, "ALIVE", POS, "b0"), _obs(2, "MOVE", POS, "a2"), *_near_miss(3)],
        {"t:animal": np.arange(4)},
        derivations=[Derivation("t:2", "ALIVE", ZERO, "law:test", ("a2",))],
    )
    v = _judge([MOVE_ALIVE], world)[MOVE_ALIVE.rule_id]
    assert v.verdict == DEGENERATE and ("t:2", "ALIVE") in v.reach.emptied


def test_plurality_needs_two_distinct_lawful_configurations_in_the_scope():
    rel = MOVE_ALIVE.relation("test")
    one = np.array([[POS, POS], [POS, POS]], dtype=np.uint8)
    two = np.array([[POS, POS], [ZERO, ZERO]], dtype=np.uint8)
    assert admission._plurality(rel, one) == (1, False)
    assert admission._plurality(rel, two) == (2, True)
    assert admission._plurality(rel, np.zeros((1, 2), dtype=np.uint8)) == (0, False)


def _artifacts():
    # Rows 0-1 are not alive and do not think (stated near-misses); row 2 is a person who thinks; row 3 is not
    # alive with THINK unstated.
    return _world(
        5,
        [
            _obs(0, "ALIVE", ZERO, "a0"),
            _obs(0, "THINK", ZERO, "k0"),
            _obs(1, "ALIVE", ZERO, "a1"),
            _obs(1, "THINK", SILENT, "k1"),
            _obs(2, "ALIVE", POS, "a2"),
            _obs(2, "THINK", POS, "k2"),
            _obs(3, "ALIVE", ZERO, "a3"),
        ],
        {"t:entity": np.arange(5), "t:artifact": np.array([0, 1, 3])},
    )


def test_a_censor_passes_the_same_gate_with_a_stated_near_miss_as_its_witness():
    c = censor(("t:entity",), "THINK", POS, if_terms=(("ALIVE", ZERO),))
    world = _artifacts()
    v = _judge([c], world)[c.rule_id]
    assert v.verdict == ADMITTED and c.kind == "censor"
    assert v.evidence.witnesses.tolist() == [0, 1]
    assert v.evidence.exposure.tolist() == [2]
    s, types, state, relations, scopes = world
    close(state, [v.relation], {v.relation.scope: types.mask(c.scope)})
    assert not _cell(state, 3, "THINK") & POS
    assert _cell(state, 4, "THINK") & POS


def test_a_censor_with_only_its_scope_as_condition_is_unexposed_or_contradicted():
    world = _artifacts()
    alone = censor(("t:artifact",), "THINK", POS)
    assert _judge([alone], world)[alone.rule_id].verdict == UNEXPOSED
    wide = censor(("t:entity",), "THINK", POS)
    assert _judge([wide], world)[wide.rule_id].evidence.counterexamples.tolist() == [2]


def test_a_censor_with_no_stated_near_miss_is_unconfirmed():
    world = _world(3, [], {"t:artifact": np.arange(3)})
    c = censor(("t:artifact",), "THINK", POS)
    assert _judge([c], world)[c.rule_id].verdict == UNCONFIRMED


def test_rules_admissible_alone_that_contradict_each_other_together_are_all_withheld():
    # Row 2 moves and feels: one rule says it is alive, the other that it is not.
    world = _world(
        6,
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "FEEL", POS, "c1"),
            _obs(1, "ALIVE", ZERO, "d1"),
            _obs(2, "MOVE", POS, "a2"),
            _obs(2, "FEEL", POS, "c2"),
            *_near_miss(3),
            _obs(4, "FEEL", ZERO, "c4"),
            _obs(4, "ALIVE", POS, "d4"),
        ],
        {"t:animal": np.arange(6)},
    )
    feel_not_alive = Candidate((("FEEL", POS),), "ALIVE", ZERO, ("t:animal",))
    verdicts = _judge([MOVE_ALIVE, feel_not_alive], world)
    for c, other in ((MOVE_ALIVE, feel_not_alive), (feel_not_alive, MOVE_ALIVE)):
        v = verdicts[c.rule_id]
        assert v.verdict == FINDING and other.rule_id in v.note
        assert ("t:2", "ALIVE") in v.collided
    s, types, state, relations, scopes = world
    r = admission_round(state, relations, scopes, s, types, [MOVE_ALIVE, feel_not_alive])
    assert not r.census["conflict"]
    assert not {MOVE_ALIVE.rule_id, feel_not_alive.rule_id} & {rel.rule_id for rel in r.admitted}


def test_verdicts_do_not_depend_on_the_order_of_candidates():
    world = _vehicles()
    cands = [
        Candidate((("MOVE", POS),), "ALIVE", POS, ("t:entity",)),
        Candidate((("MOVE", POS),), "ALIVE", POS, ("t:animal",)),
        Candidate((("ALIVE", POS),), "MOVE", POS, ("t:animal",)),
        censor(("t:artifact",), "ALIVE", POS | NEG),
    ]
    one = {k: v.verdict for k, v in _judge(cands, world).items()}
    two = {k: v.verdict for k, v in _judge(cands[::-1], world).items()}
    assert one == two


def test_a_round_discovers_admits_and_recloses():
    s, types, state, relations, scopes = _animals()
    r = admission_round(state, relations, scopes, s, types)
    assert MOVE_ALIVE.rule_id in {rel.rule_id for rel in r.admitted}
    assert _cell(state, 2, "ALIVE") == POS
    again = admission_round(state, relations + r.admitted, {**scopes, **r.scopes}, s, types)
    assert not again.admitted


# ------------------------------------------------------------------------------------------- no thresholds

_RATIO_OPS = (ast.Div, ast.FloorDiv, ast.Mod)
_ORDER_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_STATISTICS = {"max", "min", "argmax", "argmin", "mean", "average", "median", "percentile", "quantile", "corrcoef"}


def _number(node) -> bool:
    if isinstance(node, ast.UnaryOp):
        node = node.operand
    return isinstance(node, ast.Constant) and type(node.value) in (int, float)


def _violations(source: str) -> list[str]:
    """Every place a number could gate: a numeric literal or an ordering in a comparison, a ratio, a statistic,
    or a slice with a numeric bound (top-k)."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare):
            if any(isinstance(op, _ORDER_OPS) for op in node.ops):
                out.append(f"ordering comparison at line {node.lineno}")
            if any(_number(x) for x in [node.left, *node.comparators]):
                out.append(f"numeric literal in comparison at line {node.lineno}")
        elif isinstance(node, (ast.BinOp, ast.AugAssign)) and isinstance(node.op, _RATIO_OPS):
            out.append(f"ratio at line {node.lineno}")
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if name in _STATISTICS:
                out.append(f"statistic {name} at line {node.lineno}")
        elif isinstance(node, ast.Slice):
            if any(b is not None and _number(b) for b in (node.lower, node.upper)):
                out.append(f"numeric slice at line {node.lineno}")
    return out


def test_no_code_path_in_coherence_or_admission_compares_a_ratio_or_count_to_a_constant():
    for module in (coherence, admission):
        assert _violations(Path(module.__file__).read_text()) == [], module.__name__


def test_the_threshold_check_catches_every_banned_shape():
    planted = [
        "if rate >= 0.85:\n    pass",
        "if support > 40:\n    pass",
        "if len(counter) == 0:\n    pass",
        "risk = a / b",
        "risk //= b",
        "best = max(sides)",
        "top = scores[:10]",
        "if len(witnesses) > len(counterexamples):\n    pass",
    ]
    for snippet in planted:
        assert _violations(snippet), snippet
