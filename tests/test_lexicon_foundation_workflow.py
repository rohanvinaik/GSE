"""F148 obligations at the profile, solver, serialized artifact and real CLI boundaries."""

from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from gse.lexicon_builder.artifact import read_sparse, read_vectors
from gse.lexicon_builder.build import construct, source_matches
from gse.lexicon_builder.core import Cell, Law, Observation, RuleException, resolve
from gse.lexicon_builder.foundation import (
    decision_check,
    definition_status,
    examination_status,
    load_foundation,
    profile_seed,
    reconstruct_profile,
    reconstruction,
)
from gse.lexicon_builder.native_constraints import frame_constraints
from gse.lexicon_builder.reading import construct_reading
from gse.lexicon_builder.registry import load_rulebook, split_by_admission
from gse.lexicon_builder.surprise import comparison_status
from gse.lexicon_builder.tail import tail_task_status
from tests.lexicon_rulebook import certify_rule

SUBSTANTIVE_BLOCK = ("I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART")


def profile(prime: str) -> dict:
    return copy.deepcopy(next(p for p in load_foundation()["profiles"] if p["prime"] == prime))


def test_prime_content_is_reconstructed_without_copying_arguments_or_permissions():
    records = {r["prime"]: r for r in reconstruction(load_rulebook())["records"]}
    assert records["GOOD"]["vector"]["INTENSITY"] == "+1"
    assert records["GOOD"]["vector"]["BIG"] == "0"
    assert records["BIG"]["vector"]["GOOD"] == "0"
    assert records["WANT"]["vector"]["INTENSITY"] == "+1"
    # A permitted combination is not a component: "I want", "feel something good", "something good".
    assert records["I"]["vector"]["WANT"] == "empty"
    assert records["GOOD"]["vector"]["FEEL"] == "empty"
    assert records["FEEL"]["vector"]["GOOD"] == "empty"
    # An argument slot is a role: WANT's experiencer does not put SOMEONE into WANT.
    assert records["WANT"]["vector"]["SOMEONE"] == "0"
    # Families are metadata (F158 section 4): no WHEN in NOW, WHERE in HERE, or SOMEONE in I.
    assert records["NOW"]["vector"]["WHEN"] == "empty"
    assert records["HERE"]["vector"]["WHERE"] == "empty"
    assert records["I"]["vector"]["SOMEONE"] == "0"
    # The substantive block records the head: one +1 for a substantive head, all 0 otherwise.
    assert [records["I"]["vector"][c] for c in SUBSTANTIVE_BLOCK] == ["+1"] + ["0"] * 7
    assert {records["NOW"]["vector"][c] for c in SUBSTANTIVE_BLOCK} == {"0"}
    assert any(
        c["kind"] == "FORBIDS_CONSTRUCTION" and c["construction"] == "FEEL_ABOUT" for c in records["FEEL"]["claims"]
    )


def test_ablation_preserves_an_independent_degree_warrant():
    profile = copy.deepcopy(next(p for p in load_foundation()["profiles"] if p["prime"] == "GOOD"))
    original = next(c for c in profile["claims"] if c["kind"] == "ESTABLISHES_DEGREE_DOMAIN")
    profile["claims"].append({**original, "claim_id": "INDEPENDENT_DEGREE_WARRANT"})
    retained = {c["claim_id"] for c in profile["claims"] if c["claim_id"] != original["claim_id"]}
    result = construct_reading(profile_seed(profile, "good", retained), load_rulebook(), None)
    assert result["after_selection"]["forced"]["INTENSITY"] == "+1"
    retained.remove("INDEPENDENT_DEGREE_WARRANT")
    reopened = construct_reading(profile_seed(profile, "good", retained), load_rulebook(), None)
    assert "INTENSITY" not in reopened["after_selection"]["forced"]


def test_removing_a_silence_declaration_reopens_only_the_cells_it_supported():
    good = profile("GOOD")
    (boundary,) = [d for d in good["definition_axiom"]["decisions"] if d["state"] == "empty"]
    kept = {d["decision_id"] for d in good["definition_axiom"]["decisions"]} - {boundary["decision_id"]}
    whole = reconstruct_profile(good, load_rulebook())["vector"]
    ablated = reconstruct_profile(good, load_rulebook(), retained_decisions=kept)
    assert {c for c, v in ablated["vector"].items() if v == "unresolved"} == set(boundary["coordinates"])
    assert {c: v for c, v in ablated["vector"].items() if c not in boundary["coordinates"]} == {
        c: v for c, v in whole.items() if c not in boundary["coordinates"]
    }
    assert ablated["decision_checks"].pop(boundary["decision_id"]) == "UNRESOLVED"
    assert set(ablated["decision_checks"].values()) == {"RECONSTRUCTED"}


def test_removing_a_permission_or_argument_slot_cannot_erase_lexical_content():
    non_writing = {"PERMITS_COMBINATION", "REQUIRES_ARGUMENT", "FORBIDS_CONSTRUCTION", "BINDS_REFERENCE"}
    for prime in ("GOOD", "WANT", "FEEL", "I", "NOW", "HERE"):
        source = profile(prime)
        kept = {c["claim_id"] for c in source["claims"] if c["kind"] not in non_writing}
        removed = {c["claim_id"] for c in source["claims"]} - kept
        assert removed
        whole = reconstruct_profile(source, load_rulebook())
        stripped = reconstruct_profile(source, load_rulebook(), retained_claims=kept)
        assert stripped["vector"] == whole["vector"]
        assert stripped["definition_check"] == whole["definition_check"] == "RECONSTRUCTED"
        # Provenance follows the ablation: withheld claims are reported, never listed as premises.
        assert set(stripped["premise_record_ids"]) == kept and set(stripped["ablated"]["claims"]) == removed


def test_deictic_reference_is_a_context_binding_that_writes_no_cell():
    expected = {"I": "FIRST_PERSON_SPEAKER", "NOW": "UTTERANCE_TIME", "HERE": "SPEAKER_PLACE"}
    records = {r["prime"]: r for r in reconstruction(load_rulebook())["records"]}
    for prime, reference in expected.items():
        (binding,) = [c for c in records[prime]["claims"] if c["kind"] == "BINDS_REFERENCE"]
        assert binding["reference"] == reference
    # F159: I's tie to the speaker is context binding, not SAY; NOW's time and HERE's place write no WHEN or WHERE.
    assert records["I"]["vector"]["SAY"] == records["NOW"]["vector"]["SAY"] == "empty"
    assert records["NOW"]["vector"]["WHEN"] == records["HERE"]["vector"]["WHERE"] == "empty"


def test_every_judged_chart_line_is_typed_by_a_claim_of_its_kind():
    for source in load_foundation()["profiles"]:
        axiom = source["definition_axiom"]
        if axiom["review"] != "EXAMINED":
            continue
        assert examination_status(axiom["examination"], source["claims"]) == "VALID_EXAMINATION"
        claims = {c["claim_id"]: c for c in source["claims"]}
        for line in axiom["examination"]:
            if line["judgment"] == "COMBINATION":
                assert claims[line["typed_as"]]["constructions"]
    good = profile("GOOD")
    examination = good["definition_axiom"]["examination"]
    untyped = copy.deepcopy(examination)
    del untyped[0]["typed_as"]
    assert examination_status(untyped, good["claims"]) == "UNTYPED_EXAMINATION_LINE"
    mistyped = copy.deepcopy(examination)
    mistyped[0]["typed_as"] = "GOOD:05:ESTABLISHES_DEGREE_DOMAIN"  # a combination line typed as the degree claim
    assert examination_status(mistyped, good["claims"]) == "MISTYPED_EXAMINATION_LINE"
    assert examination_status(examination, None) == "MALFORMED_EXAMINATION"
    damaged = copy.deepcopy(good["claims"])
    next(c for c in damaged if c["claim_id"] == examination[0]["typed_as"])["kind"] = ["PERMITS_COMBINATION"]
    assert examination_status(examination, damaged) == "MALFORMED_CLAIM"  # a refusal, never a TypeError


def test_a_boundary_that_contradicts_a_rule_is_a_visible_foundation_conflict():
    good = profile("GOOD")
    decisions = good["definition_axiom"]["decisions"]
    degree = next(d for d in decisions if d["coordinates"] == ["INTENSITY"])
    boundary = next(d for d in decisions if d["state"] == "empty")
    decisions.remove(degree)
    boundary["coordinates"].append("INTENSITY")  # the author wrongly declares graded GOOD silent on degree
    assert definition_status(good["definition_axiom"]) == "VALID_EXAMINED"
    rebuilt = reconstruct_profile(good, load_rulebook())
    assert rebuilt["code"] == "CONFLICT" and rebuilt["definition_check"] == "CONFLICT"
    foundation = load_foundation()
    foundation["profiles"] = [good if p["prime"] == "GOOD" else p for p in foundation["profiles"]]
    assert reconstruction(load_rulebook(), foundation)["code"] == "FOUNDATION_CONFLICT"


def degree_credited_to(*rule_ids: str, extra_laws: tuple[dict, ...] = ()) -> dict:
    """GOOD rebuilt with its INTENSITY decision credited to the named laws."""
    good = profile("GOOD")
    degree = next(d for d in good["definition_axiom"]["decisions"] if d["coordinates"] == ["INTENSITY"])
    degree["derived_by"] = list(rule_ids)
    book = load_rulebook()
    book["laws"].extend(extra_laws)
    return reconstruct_profile(good, book)


PERMISSIVE_INTENSITY = certify_rule(
    {  # active for GOOD and covering INTENSITY, but allowing every legal state
        "rule_id": "TEST_ANY_INTENSITY_FOR_EVALUATORS",
        "review_state": "FOUNDER_APPROVED",
        "coordinates": ["INTENSITY"],
        "allowed": [["empty"], ["0"], ["+1"]],
        "guard": [["own_semantic_kind", "evaluator"]],
        "warrant": "mechanism-only negative witness",
    },
    positive="tests/test_lexicon_foundation_workflow.py::test_a_decision_credited_to_a_law_that_does_not_force_it_is_a_provenance_mismatch",
    must_not="tests/test_lexicon_foundation_workflow.py::test_a_decisions_own_cells_never_vouch_for_each_other",
)
SECOND_DEGREE_WARRANT = certify_rule(
    {  # an independent law that genuinely forces the same value
        "rule_id": "TEST_SECOND_DEGREE_WARRANT",
        "review_state": "FOUNDER_APPROVED",
        "coordinates": ["INTENSITY"],
        "allowed": [["+1"]],
        "guard": [["own_degree_domain", "graded_property"]],
        "warrant": "mechanism-only redundant warrant",
    },
    positive="tests/test_lexicon_foundation_workflow.py::test_a_decision_credited_to_a_law_that_does_not_force_it_is_a_provenance_mismatch",
    must_not="tests/test_lexicon_foundation_workflow.py::test_a_decisions_own_cells_never_vouch_for_each_other",
)


def test_a_decision_credited_to_a_law_that_does_not_force_it_is_a_provenance_mismatch():
    def check(rebuilt: dict) -> str:
        return rebuilt["decision_checks"]["GOOD:D2"]

    assert check(degree_credited_to("OWN_DEGREE_BEARING_CONTENT")) == "RECONSTRUCTED"
    assert check(degree_credited_to("NO_SUCH_LAW")) == "CITED_LAW_UNKNOWN"
    assert check(degree_credited_to("OWN_AFFECTIVE_FEELING")) == "CITED_LAW_INACTIVE"  # its guard fails for GOOD
    assert check(degree_credited_to("EVALUATOR_EXCLUDES_SIZE")) == "CITED_LAW_DOES_NOT_COVER"
    # F159's witness: an active law that merely permits every INTENSITY state earns no credit,
    # even though another law supplies the answer and the value itself is right.
    permissive = degree_credited_to("TEST_ANY_INTENSITY_FOR_EVALUATORS", extra_laws=(PERMISSIVE_INTENSITY,))
    assert permissive["vector"]["INTENSITY"] == "+1" and check(permissive) == "CITED_LAW_DOES_NOT_FORCE"
    assert permissive["definition_check"] == "PROVENANCE_MISMATCH"
    both = degree_credited_to(
        "OWN_DEGREE_BEARING_CONTENT", "TEST_ANY_INTENSITY_FOR_EVALUATORS", extra_laws=(PERMISSIVE_INTENSITY,)
    )
    assert check(both) == "CITED_LAW_DOES_NOT_FORCE"  # every cited law must force the value
    redundant = degree_credited_to(
        "OWN_DEGREE_BEARING_CONTENT", "TEST_SECOND_DEGREE_WARRANT", extra_laws=(SECOND_DEGREE_WARRANT,)
    )
    assert check(redundant) == "RECONSTRUCTED"  # redundant forcing warrants are both credited


def test_a_decisions_own_cells_never_vouch_for_each_other():
    vector = {"THINK": "0", "KNOW": "0"}
    joint = {"TEST_JOINT": (("THINK", "KNOW"), (("0", "0"), ("+1", "+1")))}
    # Covering both cells, the law cannot choose between its two rows on its own: no credit.
    assert decision_check("0", ["TEST_JOINT"], ["THINK", "KNOW"], vector, ["TEST_JOINT"], joint) == (
        "CITED_LAW_DOES_NOT_FORCE"
    )
    # KNOW's final state cannot supply its own independent premise.
    assert decision_check("0", ["TEST_JOINT"], ["THINK"], vector, ["TEST_JOINT"], joint) == "CITED_LAW_NOT_ROOTED"
    # A separately rooted KNOW does support the same consequence.
    joint["KNOW_ROOT"] = (("KNOW",), (("0",),))
    assert decision_check("0", ["TEST_JOINT"], ["THINK"], vector, ["TEST_JOINT", "KNOW_ROOT"], joint) == "RECONSTRUCTED"
    assert (
        decision_check("0", ["TEST_JOINT"], ["FEEL"], vector, ["TEST_JOINT"], joint) == "COORDINATE_NOT_RECONSTRUCTED"
    )


def test_two_decisions_cannot_root_each_other_through_one_relation():
    # A = B, decided as two separate decisions. Each credits the relation through the other's final
    # value, so neither is rooted in an independent premise; a rooted check must refuse at least one.
    vector = {"THINK": "0", "KNOW": "0"}
    equal = {"TEST_EQUAL": (("THINK", "KNOW"), (("0", "0"), ("+1", "+1")))}
    first = decision_check("0", ["TEST_EQUAL"], ["THINK"], vector, ["TEST_EQUAL"], equal)
    second = decision_check("0", ["TEST_EQUAL"], ["KNOW"], vector, ["TEST_EQUAL"], equal)
    assert "RECONSTRUCTED" not in {first, second}


def test_the_one_hot_head_law_fires_only_for_a_prime_profile():
    ordinary = Observation("box:NOUN:fixture", "fixture", "rec-1", "own_role", "substantive", True)
    result = resolve("box:NOUN:fixture", (ordinary,))
    assert "SUBSTANTIVE_HEAD_IS_ONE_HOT" not in result.fired_rules
    assert not {"I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART"} & set(result.forced())
    prime = Observation("box:NOUN:fixture", "fixture", "rec-1", "lexical_unit_kind", "PRIME", True)
    assert "SUBSTANTIVE_HEAD_IS_ONE_HOT" in resolve("box:NOUN:fixture", (ordinary, prime)).fired_rules


def test_an_ordinary_homograph_never_inherits_a_prime_boundary():
    native = {
        "usas": {"records": [{"record_id": "USAS:good", "values": {"pos": "ADJ", "alternatives": ["A5.1+"]}}]},
        "framenet": {"records": [{"record_id": "FN:good", "values": {"pos": "a", "frame": "Desirability"}}]},
    }
    book = load_rulebook()
    reading = construct("good", source_matches(native, book)[0], native, book, None)
    fired = reading["after_selection"]["fired_rules"]
    assert reading["after_selection"]["forced"]["GOOD"] == "+1"
    assert not any(rule.startswith("PRIME_BOUNDARY:") for rule in fired)
    assert any(len(domain) > 1 for domain in reading["after_selection"]["domains"].values())


def test_an_unexamined_profile_never_applies_its_drafted_boundary():
    you = profile("YOU")
    # Deliberately withdraw examination in this fixture; production may examine all primes.
    axiom = you["definition_axiom"]
    axiom["unexamined_boundary_proposal"] = [
        c for d in axiom.pop("decisions") if d["state"] == "empty" for c in d["coordinates"]
    ]
    axiom["review"] = "DRAFT"
    assert axiom["unexamined_boundary_proposal"]
    rebuilt = reconstruct_profile(you, load_rulebook())
    assert rebuilt["definition_check"] == "BOUNDARY_PENDING"
    for coordinate in you["definition_axiom"]["unexamined_boundary_proposal"]:
        assert rebuilt["vector"][coordinate] != "empty"


def test_the_loader_refuses_a_definition_that_is_not_a_warranted_partition():
    good = profile("GOOD")["definition_axiom"]
    assert definition_status(good) == "VALID_EXAMINED"
    cases = {
        "NOT_A_PARTITION": lambda a: a["decisions"][-1]["coordinates"].pop(),
        "UNKNOWN_AUTHORITY": lambda a: a["decisions"][0].update(authority=["MODEL"]),
        "SILENCE_CLAIMS_DERIVATION": lambda a: a["decisions"][-1].update(derived_by=["OWN_DEGREE_BEARING_CONTENT"]),
        "UNDERIVED_DECISION": lambda a: a["decisions"][1].update(derived_by=[]),
        "ILLEGAL_STATE": lambda a: a["decisions"][0].update(coordinates=["FEEL"], state="-1"),
        "MISSING_EXAMINATION": lambda a: a.update(examination=[]),
        "DRAFT_WITH_DECISIONS": lambda a: a.update(review="DRAFT"),
        "UNKNOWN_REVIEW": lambda a: a.update(review="APPROVED"),
    }
    for code, damage in cases.items():
        axiom = copy.deepcopy(good)
        damage(axiom)
        assert definition_status(axiom) == code
    assert definition_status(None) == "MISSING_DEFINITION"
    # F159: adversarial value types get a named refusal, never a TypeError.
    adversarial = [
        ("MALFORMED_DECISION", lambda a: a["decisions"][0].update(decision_id=["GOOD:D1"])),
        ("MALFORMED_DECISION", lambda a: a["decisions"][0].update(state={"value": "+1"})),
        ("MALFORMED_DECISION", lambda a: a["decisions"][0].update(coordinates=["GOOD", 3])),
        ("MALFORMED_DECISION", lambda a: a["decisions"][1].update(derived_by=[1])),
        ("UNKNOWN_AUTHORITY", lambda a: a["decisions"][0].update(authority=[["FOUNDER"]])),
        ("MISSING_WARRANT", lambda a: a["decisions"][0].update(location=None)),
        ("MALFORMED_EXAMINATION", lambda a: a["examination"][0].update(judgment=["COMBINATION"])),
        ("MALFORMED_EXAMINATION", lambda a: a["examination"][0].update(line=42)),
        ("MALFORMED_DECISION", lambda a: a.update(decisions=[*a["decisions"], "D9"])),
    ]
    for code, damage in adversarial:
        axiom = copy.deepcopy(good)
        damage(axiom)
        assert definition_status(axiom) == code


def test_local_exception_retracts_only_conditional_support_and_refuses_self_confirmation():
    conditional = Law("CORPUS_RULE", ("FEEL",), ((Cell.PLUS,),), (), "independent corpus", "CONDITIONAL")
    independent = Law("INDEPENDENT_SOURCE", ("FEEL",), ((Cell.PLUS,),), (), "another source")
    exception = RuleException("reading", "CORPUS_RULE", "reference", "counterexample-1", "narrower guard needed")
    kept = resolve("reading", laws=(conditional, independent), exceptions=(exception,))
    assert kept.forced()["FEEL"] == Cell.PLUS
    reopened = resolve("reading", laws=(conditional,), exceptions=(exception,))
    assert "FEEL" not in reopened.forced()
    assert reopened.trace[0]["code"] == "CONDITIONAL_RULE_RETRACTED"
    assert resolve("other-reading", laws=(conditional,), exceptions=(exception,)).forced()["FEEL"] == Cell.PLUS
    with pytest.raises(ValueError, match="foundational"):
        resolve(
            "reading",
            laws=(independent,),
            exceptions=(RuleException("reading", "INDEPENDENT_SOURCE", "ref", "r", "x"),),
        )
    with pytest.raises(ValueError, match="independent evidence"):
        RuleException("reading", "CORPUS_RULE", "builder", "own-vector", "x", "DERIVED_VECTOR")


@pytest.fixture
def source_fixture(tmp_path):
    root, nltk = tmp_path / "external", tmp_path / "nltk"
    (root / "usas").mkdir(parents=True)
    (nltk / "framenet_v17").mkdir(parents=True)
    (root / "usas/semantic_lexicon_en.tsv").write_text(
        "lemma\tpos\tsemantic_tags\nafraid\tADJ\tE5-\nsad\tADJ\tE4.1-\nmad\tADJ\tE4.1+\npleasure\tNOUN\tE4.2+\n"
    )
    (nltk / "framenet_v17/luIndex.xml").write_text(
        '<index><lu ID="1" name="afraid.a" frameID="1" frameName="Fear"/>'
        '<lu ID="2" name="sad.a" frameID="2" frameName="Emotion_directed"/>'
        '<lu ID="3" name="mad.a" frameID="2" frameName="Emotion_directed"/>'
        '<lu ID="4" name="pleasure.n" frameID="3" frameName="Experiencer_focus"/></index>'
    )
    return root, nltk


def test_real_cli_builds_profiles_structures_and_fear_without_initializing_a_model(tmp_path, source_fixture):
    sources, nltk = source_fixture
    output = tmp_path / "run"
    command = [
        sys.executable,
        "-m",
        "gse.lexicon_builder",
        "build",
        "--words",
        "good",
        "want",
        "afraid",
        "sad",
        "mad",
        "pleasure",
        "the",
        "a",
        "this",
        "unseen-token",
        "--sources",
        str(sources),
        "--nltk",
        str(nltk),
        "--model",
        "NOT_INSTALLED",
        "--output",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["model"] is None and manifest["fill"] is False
    records = list(read_sparse(output / "sparse.jsonl"))
    afraid = next(r for r in records if r["word"] == "afraid")
    assert afraid["cells"]["WANT"]["state"] == "+1"
    assert afraid["cells"]["NOT"]["state"] == "+1"
    assert afraid["cells"]["GOOD"]["state"] == "-1"
    assert afraid["cells"]["SOMETHING"] == {"state": "0", "domain": ["0"], "written": True, "value": 0}
    assert afraid["cells"]["DO"]["state"] == "unresolved"
    assert afraid["cells"]["DO"]["written"] is None
    assert not any(r["provenance"]["model_requests"] for r in records)
    for word in ("sad", "mad"):
        assert next(r for r in records if r["word"] == word)["cells"]["FEEL"]["state"] == "unresolved"
    words = {r["word"]: r for r in map(json.loads, (output / "words.jsonl").read_text().splitlines())}
    # MUST-NOT: pleasure has no thought part, so the emotion template never reaches it; its noun keeps a head reading.
    assert not any(str(r.get("rule_id", "")).startswith("EMOTION_") for r in words["pleasure"]["readings"])
    assert all(
        r["source_scope"] in {"LEMMA_POS_HEAD_CONTRACT", "FRAMENET_NOUN_TARGET"} for r in words["pleasure"]["readings"]
    )
    assert words["the"]["structural_entries"][0]["operation"] == "BIND_DEFINITE_REFERENCE"
    assert words["this"]["structural_entries"][0]["basis_gaps"] == ["THIS"]
    assert words["unseen-token"]["code"] == "PARTIAL_NO_APPLICABLE_RULE"
    # Only an examined prime exports a complete vector; every ordinary reading here stays partial.
    exported = list(read_vectors(output / "vectors.jsonl"))
    assert {v["reading_id"] for v in exported} == {"prime:GOOD", "prime:WANT"}
    assert all(r["code"] != "CANDIDATE_COMPLETE" for r in records if not r["reading_id"].startswith("prime:"))
    damaged = copy.deepcopy(afraid)
    damaged["cells"]["DO"]["written"] = False
    path = tmp_path / "damaged.jsonl"
    path.write_text(json.dumps(damaged) + "\n")
    with pytest.raises(ValueError, match="SPARSE_MASK_MISMATCH"):
        list(read_sparse(path))


def test_real_cli_exception_and_empty_worklist_boundaries(tmp_path):
    payload = {
        "reading_id": "fixture",
        "law_contract": "DIRECT_CONSTRAINTS",
        "laws": [
            {
                "rule_id": "R",
                "coordinates": ["FEEL"],
                "allowed": [["+1"]],
                "guard": [],
                "warrant": "source",
                "tier": "CONDITIONAL",
            }
        ],
        "exceptions": [
            {
                "reading_id": "fixture",
                "rule_id": "R",
                "source": "reference",
                "record_id": "counterexample",
                "reason": "scope exception",
            }
        ],
    }
    source, output = tmp_path / "input.json", tmp_path / "output.json"
    source.write_text(json.dumps(payload))
    subprocess.run(
        [sys.executable, "-m", "gse.lexicon_builder", "resolve", "--input", str(source), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "FEEL" not in json.loads(output.read_text())["forced"]
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gse.lexicon_builder",
            "build",
            "--word-file",
            str(empty),
            "--output",
            str(tmp_path / "empty-run"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "EMPTY_WORKLIST" in result.stderr


def predicate(name: str, *arguments: str, negated: bool = False) -> dict:
    """A VerbNet predicate; an argument with parentheses or named E, E0, E1 is an event."""
    typed = [{"type": "Event" if "(" in a or a in {"E", "E0", "E1"} else "ThemRole", "value": a} for a in arguments]
    return {"predicate": {"value": name, **({"bool": "!"} if negated else {})}, "arguments": typed}


def test_native_causation_and_presupposed_existence_have_distinct_contracts():
    # kill: "because of this, after this, this other someone was not living anymore" (GW16 [15a]).
    frame = {
        "class": "fixture",
        "predicates": [
            predicate("cause", "Agent", "E"),
            predicate("alive", "start(E)", "Patient"),
            predicate("alive", "result(E)", "Patient", negated=True),
            predicate("exist", "during(E)", "Patient"),
        ],
    }
    projected = frame_constraints(frame, load_rulebook())
    result = resolve("fixture", laws=projected["laws"])
    assert result.forced()["CAUSE"] == Cell.PLUS and result.forced()["DO"] == Cell.PLUS
    assert "BECAUSE" not in result.forced() and "EXIST" not in result.forced()
    assert any(r["code"] == "PARTICIPANT_EXISTENCE_PRESUPPOSITION" for r in projected["unmapped"])
    event_cause = {"predicates": [predicate("cause", "E0", "E1"), predicate("state", "result(E1)", "Patient")]}
    result = resolve("event", laws=frame_constraints(event_cause, load_rulebook())["laws"])
    assert result.forced()["HAPPEN"] == Cell.PLUS and "DO" not in result.forced()


EMOTION_VERB = {"usas": {"records": [{"values": {"pos": "VERB", "alternatives": ["E5-"]}}]}}


@pytest.mark.parametrize(
    ("witness", "predicates", "native", "companion"),
    [
        (
            "say",
            [predicate("transfer_info", "during(E)", "Agent", "?Recipient", "Topic"), predicate("cause", "Agent", "E")],
            None,
            None,
        ),
        (
            "know as",
            [predicate("characterize", "during(E)", "Theme", "Predicate"), predicate("cause", "Agent", "E")],
            None,
            None,
        ),
        ("continue", [predicate("continue", "E", "Predicate"), predicate("cause", "Agent", "E")], None, None),
        (
            "hit at",
            [predicate("cause", "Agent", "E"), predicate("contact", "during(E)", "Agent", "Patient", negated=True)],
            None,
            None,
        ),
        (
            "an unaligned emotion",
            [predicate("cause", "Cause", "E"), predicate("emotional_state", "during(E)", "Emotion", "Experiencer")],
            None,
            None,
        ),
        (
            "frighten",
            [predicate("cause", "Cause", "E"), predicate("emotional_state", "during(E)", "Emotion", "Experiencer")],
            EMOTION_VERB,
            "NONE",
        ),
        ("run the horse", [predicate("motion", "during(E0)", "Theme"), predicate("cause", "Agent", "E0")], None, "DO"),
        ("start", [predicate("begin", "E", "Theme"), predicate("cause", "Agent", "E")], None, "DO"),
        (
            "throw away",
            [
                predicate("motion", "during(E1)", "Theme"),
                predicate("contact", "end(E0)", "Agent", "Theme"),
                predicate("cause", "Agent", "E"),
            ],
            None,
            "DO",
        ),
        ("walk alone", [predicate("motion", "during(E)", "Theme"), predicate("cause", "Theme", "E")], None, None),
    ],
)
def test_cause_needs_something_to_happen_to_another_participant(witness, predicates, native, companion):
    """Option B (F144) read through NSM: something happens to another participant (GW16), not a wanted effect."""
    projected = frame_constraints({"class": "fixture", "predicates": predicates}, load_rulebook(), native)
    forced = resolve(witness, laws=projected["laws"]).forced()
    if companion is None:
        # Not a causative event: CAUSE and DO stay unresolved, never 0, and the predicate stays in the derivation.
        assert "CAUSE" not in forced and "DO" not in forced, witness
        assert any(r["code"] == "NO_CHANGE_TO_ANOTHER_PARTICIPANT" for r in projected["unmapped"]), witness
    else:
        assert forced["CAUSE"] == Cell.PLUS, witness
        assert ("DO" in forced) == (companion == "DO"), witness


def test_withholding_a_rule_never_widens_the_cause_rule():
    """A join refused by a rule's own condition stays refused when that rule is withheld."""
    book = load_rulebook()
    for rule in book["native_predicate_rules"]:
        if rule["rule_id"] == "VN_AFFECTIVE_STATE":
            rule["review_state"] = "PROPOSED"
    admitted, _ = split_by_admission(book)
    assert all(r["rule_id"] != "VN_AFFECTIVE_STATE" for r in admitted["native_predicate_rules"])
    emotion = [predicate("cause", "Cause", "E"), predicate("emotional_state", "during(E)", "Emotion", "Experiencer")]
    unaligned = frame_constraints({"class": "fixture", "predicates": emotion}, admitted)
    assert "CAUSE" not in resolve("unaligned", laws=unaligned["laws"]).forced()
    assert {r["code"] for r in unaligned["unmapped"]} >= {
        "UNALIGNED_AFFECTIVE_READING",
        "NO_CHANGE_TO_ANOTHER_PARTICIPANT",
    }
    # With its emotion tag the join holds, so the experiencer's feeling is a caused change; the withheld rule writes no FEEL.
    aligned = frame_constraints({"class": "fixture", "predicates": emotion}, admitted, EMOTION_VERB)
    forced = resolve("aligned", laws=aligned["laws"]).forced()
    assert forced["CAUSE"] == Cell.PLUS and "FEEL" not in forced


@pytest.mark.parametrize(
    ("expected", "actual", "code"),
    [
        ("+1", "+1", "AGREES"),
        ("+1", "unresolved", "UNRESOLVED_REFERENCE_COMPONENT"),
        ("0", "unresolved", "UNRESOLVED_REFERENCE_STATE"),
        ("empty", "+1", "ADDITION_CHALLENGE"),
        ("0", "+1", "FALSE_ADDITION"),
        ("+1", "empty", "FALSE_OMISSION"),
        ("+1", "-1", "WRONG_POLE"),
        ("0", "empty", "ZERO_SILENCE_DISAGREEMENT"),
        ("+1", "conflict", "SOURCE_CONFLICT"),
        (None, "+1", "INVALID_REFERENCE_STATE"),
        ("+1", None, "INVALID_ACTUAL_STATE"),
    ],
)
def test_two_sided_comparison_never_confuses_unknown_absence_and_silence(expected, actual, code):
    assert comparison_status(expected, actual) == code


def test_tail_tasks_are_bounded_sourced_and_have_no_gold_answer():
    task = {
        "reading_id": "r",
        "coordinate": "THEN",
        "options": ["-1", "empty"],
        "reason": "UNRESOLVED_COMPONENT",
        "source_record_ids": ["source:1"],
    }
    assert tail_task_status(task) == "VALID_TAIL_TASK"
    assert tail_task_status({**task, "answer": "-1"}) == "FIELD_MISMATCH"
    # F078/F158: a written 0 that survives the rules is a legal choice.
    assert tail_task_status({**task, "options": ["0", "+1"]}) == "VALID_TAIL_TASK"
    assert tail_task_status({**task, "coordinate": "FEEL", "options": ["-1", "empty"]}) == "ILLEGAL_OPTIONS"
    assert tail_task_status({**task, "reason": []}) == "UNDIAGNOSED_TASK"
    assert tail_task_status({**task, "source_record_ids": []}) == "MISSING_SOURCE_EVIDENCE"
    assert tail_task_status(None) == "MALFORMED_TASK"
