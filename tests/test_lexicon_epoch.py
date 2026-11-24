"""Exercise two real epoch transitions and recover their persistent journals."""

import json
import sqlite3
from dataclasses import replace

import pytest

from GSE.curation.lexicon_builder.definition_frames import native_noun_frames, wiktionary_anatomy_frame
from GSE.curation.lexicon_builder.engine import Assertion
from GSE.curation.lexicon_builder.epoch import (
    EpochTransportRefusal,
    JournaledTransport,
    census,
    choose,
    fingerprint,
    parse_plan,
    record,
    run_arm,
)
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation, _record_id
from GSE.curation.lexicon_builder.grounded_rules import observed_conjunctions
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.sqlite_snapshot import copy_database
from scripts.run_lexicon_epochs import compare


class Rulings:
    identity = "synthetic-epoch-fixture"

    def __init__(self):
        self.calls = []

    def __call__(self, payload, schema):
        bank = payload["bank"]
        assert set(schema["properties"]) == {bank}
        assert bank not in payload["known"]
        self.calls.append((payload["entry_id"], bank))
        return json.dumps({bank: 1 if bank == "QUANTITY" else 0})


def native(lemma, ancestor):
    synset = lemma + ".n.01"
    identity = f"wordnet:{lemma}:{synset}"
    definition = Definition(identity, lemma, "noun", f"Synthetic measurement {lemma}.")
    observation = Observation(
        identity,
        "wordnet_hierarchy",
        identity,
        "wordnet",
        {
            "lemma": lemma,
            "pos": "noun",
            "definition": definition.definition,
            "synset_name": synset,
            "lemma_names": [lemma],
            "hypernym_paths": [["entity.n.01", ancestor, synset]],
        },
        "lexical",
        (identity,),
    )
    return definition, observation


@pytest.mark.parametrize(
    "gloss,expected",
    [
        ("A person who is able to read and write.", {"coordinated_person", "person_own_capacity"}),
        ("someone who can find paths through unexplored territory", {"person_own_capacity"}),
        ("someone who can be employed as a detective", set()),
        ("A person who can never read.", set()),
        ("A person who is able to books.", set()),
        ("a person who can read; a literate person", set()),
        ("a person who can read or a trained assistant", set()),
    ],
)
def test_person_capacity_frame_distinguishes_own_ability_and_preserves_overlap(gloss, expected):
    assert native_noun_frames(gloss) - {"explicit_person"} == expected


@pytest.mark.parametrize(
    "gloss,frame",
    [
        ("Someone who receives a gift.", "explicit_person"),
        ("A person who does not eat meat.", "explicit_person"),
        ("a person who is part mortal and part god", None),
        ("A person who draws maps or a machine that draws them.", None),
        ("A place where boats are built.", "explicit_place"),
        ("A kind of boat kept at a place where ships are repaired.", None),
        ("The time when the sun rises.", "explicit_time"),
        ("A device that shows the time when the sun rises.", None),
    ],
)
def test_explicit_genus_frame_tracks_the_referent(gloss, frame):
    broad_frames = {"explicit_person", "explicit_place", "explicit_time"}
    assert native_noun_frames(gloss) & broad_frames == ({frame} if frame else set())


@pytest.mark.parametrize(
    "gloss,matched",
    [
        ("The state of being absent.", True),
        ("a state in which action is feasible", True),
        ("the state of needing something that is absent or unavailable", False),
        ("The person who lives in a state of poverty.", False),
        ("a state in the northwestern United States", False),
        ("the state of inactivity; an act of stopping", False),
        ("the course of existence of an individual; the actions and events that occur in living", False),
    ],
)
def test_stative_genus_reserves_mixed_definitions(gloss, matched):
    assert ("explicit_stative" in native_noun_frames(gloss)) is matched


@pytest.mark.parametrize(
    "gloss,frame",
    [
        ("Something that happens at a given place and time.", "explicit_occurrence"),
        ("A natural event caused by something suddenly falling down.", "explicit_occurrence"),
        ("An event that is likely to occur.", None),
        ("The occurrence of yellow matter in the blood.", None),
        ("A person who observes an event.", None),
        ("The result of the act of cutting the rope.", None),
        ("The act of delivering a blow with the foot.", "agentive_intervention"),
        ("The act of putting a liquid into the body by means of a syringe.", "agentive_intervention"),
        ("The act of being put into a box.", None),
        ("The act of cutting the rope or the tool used to cut it.", None),
        ("The act of bleeding.", None),
        ("The act of hitting on someone.", None),
    ],
)
def test_event_and_action_frames_use_the_defining_construction(gloss, frame):
    tested = {"explicit_occurrence", "agentive_intervention"}
    assert native_noun_frames(gloss) & tested == ({frame} if frame else set())


@pytest.mark.parametrize(
    "gloss,frame",
    [
        ("the act of apprehending (especially apprehending a criminal)", "agentive_acquisition"),
        ("The act of making a purchase.", "agentive_acquisition"),
        ("the acquisition of something for payment", "agentive_acquisition"),
        ("The act of obtaining.", None),
        ("the act of acquiring something", None),
        ("the act of purchasing back something previously sold", None),
        ("becoming infected", None),
        ("the act of acquiring an infection", None),
        ("a person who apprehends a criminal", None),
        ("the act of buying or the object purchased", None),
        ("the act of being taken into custody", None),
        ("the state of inactivity following an interruption", None),
        ("an event that occurs when something passes from one state or phase to another", "qualified_occurrence"),
        ("the event of something burning (often destructive)", "qualified_occurrence"),
        ("a natural event caused by something suddenly falling down or caving in", "qualified_occurrence"),
        ("designated event that concludes a contest (especially a race)", "qualified_occurrence"),
        ("an event of collapse or a damaged structure", None),
        ("an event that might occur", None),
        ("the result of an event", None),
        ("an event of something falling (or a place where it fell)", None),
        ("the event of something falling\nan unrelated gloss", None),
    ],
)
def test_grounded_residual_frames_preserve_defining_head(gloss, frame):
    tested = {"agentive_acquisition", "qualified_occurrence"}
    assert native_noun_frames(gloss) & tested == ({frame} if frame else set())


def family(name, ancestor, left, right, audit):
    return {
        "id": name,
        **({"premises": left} if isinstance(left[0], list) else {"antecedent": left}),
        "consequent": right,
        "guards": [["pos", "noun"], ["wordnet_native_lemma", "true"], [f"wordnet_ancestor:{ancestor}", "true"]],
        "holdouts": [f"wordnet:{audit}:{audit}.n.01"],
        "warrant": {
            "kind": "DEFINITIONAL_DERIVATION",
            "warrant_id": name,
            "review_id": name,
            "reviewer": "synthetic-test",
            "source_refs": ["synthetic:epoch"],
            "statement": "Synthetic assignments establish the workflow contract.",
        },
    }


def test_exact_native_gloss_scope_propagates_across_sources(tmp_path):
    base, pointer = tmp_path / "base.db", tmp_path / "pointer.json"
    pointer.write_text("{}")
    wordnet = []
    for lemma, gloss in (
        ("back", "the part of a thing furthest from the viewer"),
        ("bit", "the part of a key that enters a lock"),
        ("alternative", "a part of a key or another tool"),
    ):
        definition, observation = native(lemma, "part.n.01")
        wordnet.append(
            (
                replace(definition, definition=gloss),
                replace(observation, features={**observation.features, "definition": gloss}),
            )
        )
    identity = "wiktionary:en-stop-test"
    gloss = "A part of a photographic system that reduces light."
    wiki = Definition(identity, "stop", "noun", gloss)
    features = {
        "identity_scheme": "GSE.wiktionary-native-leaf/1",
        "entry_id": identity,
        "lemma": "stop",
        "word": "stop",
        "pos": "noun",
        "native_id": "en-stop-test",
        "definition": gloss,
        "native_sense": {"glosses": [gloss]},
    }
    observation = Observation(
        identity,
        "wiktionary",
        _record_id("wiktionary", "stop", features),
        "wiktionary",
        features,
        "lexical",
        (identity,),
    )
    definitions, observations = zip(*wordnet, (wiki, observation))
    build_dictionary(EvidenceBundle(definitions, observations, (), ()), base)
    plan = {
        "format": "GSE.lexicon-epoch-plan/1",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": fingerprint(pointer),
        "epochs": 1,
        "audits_per_epoch": 2,
        "families": [
            {
                **family("exact-part", "part.n.01", ["SOMETHING", 1], ["PART", 1], "bit"),
                "antecedent": None,
                "guards": [["pos", "noun"], ["native_noun_frame:part_of", "true"]],
                "holdouts": ["wordnet:bit:bit.n.01", identity],
            }
        ],
    }

    class PartRulings:
        identity = "synthetic-part-frame"

        def __call__(self, payload, schema):
            assert payload["bank"] == "PART" and set(schema["properties"]) == {"PART"}
            return '{"PART":1}'

    inventory = census(base, parse_plan(plan))
    assert {row["entry_id"] for row in inventory["exact-part"]} == {
        "wordnet:back:back.n.01",
        "wordnet:bit:bit.n.01",
        identity,
    }
    # Reserve the only discovery sense while keeping it in the propagation census.
    assert (
        choose(
            base,
            inventory,
            parse_plan(plan),
            set(),
            set(),
            "zipf",
            {},
            {"entries": ["wordnet:back:back.n.01"], "lemmas": ["back"]},
        )
        is None
    )
    arm = run_arm(
        plan, base, pointer, tmp_path / "closure", inventory, "closure", PartRulings(), tmp_path / "model.lock"
    )
    assert arm["typed_questions_used"] == 3
    assert arm["epochs"][0]["code"] == "RULE_ADMITTED"
    assert arm["replay"]["entries_mismatched"] == 0
    assert {row["entry_id"] for row in arm["changes"]} == {
        "wordnet:back:back.n.01",
        "wordnet:bit:bit.n.01",
        identity,
    }
    assert all(row["bank"] == "PART" and row["before"] == [-1, 0, 1] and row["after"] == [1] for row in arm["changes"])


@pytest.mark.parametrize(
    "gloss,frame",
    [
        ("A biological organ of vertebrates that controls breathing.", "organ_gland"),
        ("A gland near the stomach which secretes fluid.", "organ_gland"),
        ("The long bone in the forearm.", "physical_structure"),
        ("A muscle having four heads.", "physical_structure"),
        ("A nerve ending that senses blood pressure.", "physical_structure"),
        ("A muscle twitch.", None),
        ("A muscle-like structure.", None),
        ("A muscular organ traditionally thought to be the seat of emotion.", None),
        ("An organ of desire.", None),
        ("A bone or a tool.", None),
        ("An organ that makes someone want to eat.", None),
    ],
)
def test_wiktionary_anatomy_want_scope_requires_physical_definition(gloss, frame):
    sense = {"glosses": [gloss], "topics": ["anatomy"]}
    assert wiktionary_anatomy_frame(gloss, "noun", sense) == frame
    assert wiktionary_anatomy_frame(gloss, "verb", sense) is None
    assert wiktionary_anatomy_frame(gloss, "noun", {**sense, "topics": []}) is None
    assert wiktionary_anatomy_frame(gloss, "noun", {**sense, "tags": ["figurative"]}) is None
    assert wiktionary_anatomy_frame(gloss, "noun", {**sense, "glosses": ["A different definition."]}) is None


def test_wiktionary_anatomy_scope_replays_without_filling_unknown_controls(tmp_path):
    from GSE.curation.lexicon_builder.foundation import lexical_context

    base, pointer = tmp_path / "base.db", tmp_path / "pointer.json"
    pointer.write_text("{}")
    records = (
        ("alpha", "A muscle.", ["anatomy"]),
        ("beta", "The long bone in the forearm.", ["anatomy"]),
        ("gamma", "A nerve ending that senses blood pressure.", ["anatomy"]),
        ("mental", "A muscle that controls wanting.", ["anatomy"]),
        ("unsupported", "A muscle.", []),
    )
    definitions, observations, assertions = [], [], []
    for word, gloss, topics in records:
        identity = "wiktionary:fixture-" + word
        definition = Definition(identity, word, "noun", gloss)
        features = {
            "identity_scheme": "GSE.wiktionary-native-leaf/1",
            "entry_id": identity,
            "lemma": word,
            "word": word,
            "pos": "noun",
            "native_id": "fixture-" + word,
            "definition": gloss,
            "native_sense": {"glosses": [gloss], "topics": topics},
        }
        observation = Observation(
            identity,
            "wiktionary",
            _record_id("wiktionary", word, features),
            "wiktionary",
            features,
            "lexical",
            (identity,),
        )
        definitions.append(definition)
        observations.append(observation)
        if word != "unsupported":
            assertions.append(Assertion("BODY", 1, "wiktionary", observation.record_id, "wiktionary"))
    build_dictionary(EvidenceBundle(tuple(definitions), tuple(observations), tuple(assertions), ()), base)
    plan = {
        "format": "GSE.lexicon-epoch-plan/1",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": fingerprint(pointer),
        "epochs": 1,
        "audits_per_epoch": 2,
        "families": [
            {
                **family("anatomy-want", "body_part.n.01", ["BODY", 1], ["WANT", 0], "beta"),
                "guards": [["pos", "noun"], ["wiktionary_anatomy_frame:physical_structure", "true"]],
                "holdouts": ["wiktionary:fixture-beta", "wiktionary:fixture-gamma"],
            }
        ],
    }
    families = parse_plan(plan)
    inventory = census(base, families)
    assert {r["entry_id"] for r in inventory["anatomy-want"]} == {
        "wiktionary:fixture-alpha",
        "wiktionary:fixture-beta",
        "wiktionary:fixture-gamma",
    }
    relation = families["anatomy-want"].relation()
    assert lexical_context(definitions[0], (), (relation,)) == {"pos": "noun"}
    forged = replace(observations[0], record_id="altered-record-identity")
    assert lexical_context(definitions[0], (forged,), (relation,)) == {"pos": "noun"}
    arm = run_arm(plan, base, pointer, tmp_path / "round", inventory, "zipf", Rulings(), tmp_path / "model.lock")
    assert arm["replay"]["code"] == "REPLAY_VALIDATED"
    assert arm["replay"]["entries_mismatched"] == 0
    assert len(arm["changes"]) == 3
    assert all(r["bank"] == "WANT" and r["before"] == [-1, 0, 1] and r["after"] == [0] for r in arm["changes"])


def test_two_generations_replay_and_resume_at_equal_budget(tmp_path):
    base, active = tmp_path / "base.db", tmp_path / "active.json"
    active.write_text("{}")
    durations = [native(word, "time_unit.n.01") for word in ("day", "minute", "hour", "second")]
    areas = [native(word, "area_unit.n.01") for word in ("are", "acre")]
    definitions, observations = zip(*durations, *areas)
    assertions = tuple(
        Assertion("SOMETHING", 1, "wordnet_hierarchy", definition.entry_id, "wordnet") for definition in definitions
    )
    manifest = tmp_path / "rules.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "GSE.lexicon-rules/1",
                "relations": [
                    {
                        "rule_id": "synthetic-area-quantity",
                        "banks": ["QUANTITY"],
                        "allowed_rows": [[1]],
                        "provenance": ["synthetic:epoch"],
                        "authority": "conditional",
                        "approved": True,
                        "guards": [["wordnet_ancestor:area_unit.n.01", "true"]],
                    }
                ],
            }
        )
    )
    build_dictionary(EvidenceBundle(definitions, observations, assertions, ()), base, manifest=manifest)
    plan = {
        "format": "GSE.lexicon-epoch-plan/1",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": fingerprint(active),
        "epochs": 2,
        "audits_per_epoch": 1,
        "families": [
            family("duration-quantity", "time_unit.n.01", ["SOMETHING", 1], ["QUANTITY", 1], "second"),
            family("duration-want", "time_unit.n.01", [["QUANTITY", 1], ["SOMETHING", 1]], ["WANT", 0], "hour"),
            family("area-body", "area_unit.n.01", ["QUANTITY", 1], ["BODY", 0], "acre"),
        ],
    }
    population = census(base, parse_plan(plan))
    record(tmp_path / "inventory.json", population)
    arms = {}
    for policy in ("closure", "zipf"):
        model = Rulings()
        args = (plan, base, active, tmp_path / policy, population, policy, model, tmp_path / "model.lock")
        arms[policy] = run_arm(*args)
        assert arms[policy]["typed_questions_used"] == 4 == len(model.calls)
        assert arms[policy]["replay"]["code"] == "REPLAY_VALIDATED"
        assert run_arm(*args) == arms[policy]
        assert len(model.calls) == 4
    assert [e["selected"]["family"] for e in arms["closure"]["epochs"]] == ["duration-quantity", "duration-want"]
    assert [e["selected"]["family"] for e in arms["zipf"]["epochs"]] == ["area-body", "duration-quantity"]
    assert arms["closure"]["epochs"][1]["premise_depends_on"] == arms["closure"]["admitted"][:1]
    assert arms["closure"]["new_cells"] == 8
    assert arms["zipf"]["new_cells"] == 6
    result = compare(tmp_path, plan)
    assert result["code"] == "EQUAL_BUDGET_FEEDBACK_VALIDATED"
    assert result["closure_minus_zipf_new_cells"] == 2
    assert result["second_generation_rules"][0]["interactions"][0]["joint_only"] == 4
    grounding = json.loads((tmp_path / "closure" / "grounded-chains-final.json").read_text())
    assert any(
        len(rule["rule_ids"]) == 2 and rule["consequent"] == ["WANT", 0] and len(rule["witnesses"]) == 4
        for rule in grounding["proposals"]
    )
    assert fingerprint(base) == plan["baseline_sha256"]
    assert fingerprint(active) == plan["active_pointer_sha256"]


def test_journal_replays_only_the_exact_question_and_charges_before_call(tmp_path):
    model = Rulings()
    transport = JournaledTransport(model, tmp_path, "audit", 1, tmp_path / "model.lock")
    payload = {"entry_id": "fixture", "bank": "WANT", "known": {}}
    schema = {"properties": {"WANT": {}}}
    assert transport(payload, schema) == '{"WANT": 0}'
    assert transport(payload, schema) == '{"WANT": 0}'
    with pytest.raises(ValueError, match="EPOCH_QUESTION_IDENTITY_CHANGED"):
        transport(payload, {"properties": {"BODY": {}}})
    with pytest.raises(EpochTransportRefusal, match="EPOCH_MODEL_BUDGET_EXHAUSTED"):
        transport({**payload, "entry_id": "different"}, schema)
    assert transport.count() == 1 == len(model.calls)


def test_interrupted_answer_keeps_its_budget_slot(tmp_path):
    class Interrupted:
        identity = "synthetic-interruption"

        def __init__(self):
            self.calls = 0

        def __call__(self, payload, schema):
            self.calls += 1
            raise KeyboardInterrupt

    model = Interrupted()
    transport = JournaledTransport(model, tmp_path, "audit", 2, tmp_path / "model.lock")
    payload = {"entry_id": "fixture", "bank": "WANT", "known": {}}
    schema = {"properties": {"WANT": {}}}
    with pytest.raises(KeyboardInterrupt):
        transport(payload, schema)
    with pytest.raises(EpochTransportRefusal, match="EPOCH_INTERRUPTED_MODEL_ATTEMPT"):
        transport(payload, schema)
    assert transport.count() == 1 == model.calls


def test_conjunctive_observation_records_real_opposition_to_proper_subsets():
    examples = [
        {"entry_id": "both", "baseline": {"QUANTITY": 1, "WANT": 0}, "consequent": ("BODY", 0)},
        {"entry_id": "left", "baseline": {"QUANTITY": 1}, "consequent": ("BODY", 1)},
        {"entry_id": "right", "baseline": {"WANT": 0}, "consequent": ("BODY", 1)},
    ]
    [report] = observed_conjunctions(examples)
    assert report["premises"] == (("QUANTITY", 1), ("WANT", 0))
    assert report["counterexamples"] == []
    assert {row["entry_id"] for row in report["proper_subset_counterexamples"]} == {"left", "right"}


@pytest.mark.parametrize("journal", ["delete", "wal"])
def test_database_snapshot_is_independent_and_sees_committed_wal(tmp_path, journal):
    source, target = tmp_path / "source.db", tmp_path / "target.db"
    with sqlite3.connect(source) as db:
        db.execute(f"PRAGMA journal_mode={journal}")
        db.execute("CREATE TABLE sample(value)")
        db.execute("INSERT INTO sample VALUES (1)")
        db.commit()
        copy_database(source, target)
        db.execute("INSERT INTO sample VALUES (2)")
        db.commit()
        with sqlite3.connect(target) as snapshot:
            assert snapshot.execute("SELECT value FROM sample").fetchall() == [(1,)]


def test_production_retention_protects_active_rollback_and_busy_database(tmp_path, monkeypatch):
    from scripts import run_lexicon_epochs

    first = tmp_path / "epoch-01"
    second = tmp_path / "epoch-02"
    first.mkdir()
    second.mkdir()
    retired = first / "candidate.db"
    busy = first / "teaching.db"
    active = second / "candidate.db"
    rollback = second / "teaching.db"
    report = first / "result.json"
    for file in (retired, busy, active, rollback, report, first / "teaching.db-wal"):
        file.write_bytes(b"fixture")
    monkeypatch.setattr(run_lexicon_epochs, "resolve_lexicon_path", lambda: active)
    arm = {"candidate_sha256": "snapshot", "epochs": [{"epoch": 1}, {"epoch": 2}]}
    release = {"path": str(active), "previous_path": str(rollback), "sha256": "snapshot"}
    result = run_lexicon_epochs.retire_published_work(tmp_path, arm, release)
    assert result["retired"] == ["epoch-01/candidate.db"]
    assert set(result["deferred"]) == {"epoch-01/teaching.db", "epoch-02/candidate.db", "epoch-02/teaching.db"}
    assert not retired.exists()
    assert all(file.is_file() for file in (busy, active, rollback, report))


def test_source_round_working_copy_is_removed_after_publication(tmp_path, monkeypatch):
    from GSE.curation.lexicon_builder import publication
    from scripts import audit_lexicon_runtime, revise_lexicon_wiktionary_anatomy

    source = tmp_path / "active.db"
    destination = tmp_path / "next.db"
    source.write_bytes(b"baseline")
    change = {"entry_id": "fixture", "bank": "BODY", "before": [-1, 0, 1], "after": [1]}
    stage = {"changes": [{"entry_id": "fixture", "domains": [{k: v for k, v in change.items() if k != "entry_id"}]}]}
    paths = []

    def revise(path):
        paths.append(path)
        path.write_bytes(b"successor")
        return {"candidate_sha256": "hash", "active_pointer_sha256": "pointer", "replay": {"entries_checked": 1}}

    def publish(candidate, output, gold, **kwargs):
        assert candidate.is_file()
        assert kwargs == {"expected_sha256": "hash", "expected_pointer_sha256": "pointer"}
        output.write_bytes(candidate.read_bytes())
        return {"code": "PUBLISHED_SPARSE_LEXICON", "path": str(output)}

    monkeypatch.setattr(revise_lexicon_wiktionary_anatomy, "exact_delta", lambda *_: (1, [change]))
    monkeypatch.setattr(audit_lexicon_runtime, "audit_sparse_runtime", lambda _: {"code": "SPARSE_RUNTIME_VALIDATED"})
    monkeypatch.setattr(publication, "publish_sparse", publish)
    result = revise_lexicon_wiktionary_anatomy.publish_revision(source, stage, destination, tmp_path / "gold", revise)
    assert result["activation_performed"] and result["working_database"] == "RETIRED"
    assert destination.read_bytes() == b"successor" and source.read_bytes() == b"baseline"
    assert not paths[0].parent.exists()


@pytest.mark.parametrize(
    "gloss,expected",
    [
        ("The state of being angry.", True),
        ("The state of being employed.", True),
        ("A state of being briefly airborne during a jump.", True),
        ("The state of being a peasant.", True),
        ("The state of being not ripe.", True),
        ("The state of being.", False),
        ("The state of being a.", False),
        ("The state of being in.", False),
        ("The state of being not.", False),
        ("The state of not existing.", False),
        ("A state of Germany.", False),
        ("The state of being angry or a fit of anger.", False),
        ("The state of being angry. Another reading follows.", False),
        ("", False),
    ],
)
def test_stative_being_requires_own_qualified_condition(gloss, expected):
    assert ("stative_being" in native_noun_frames(gloss)) is expected


@pytest.mark.parametrize(
    "guards,code",
    [
        ([], "EPOCH_REQUIRES_WITNESSED_NATIVE_SCOPE"),
        ([["pos", "noun"]], "EPOCH_REQUIRES_WITNESSED_NATIVE_SCOPE"),
        ([["pos", "noun"], ["wordnet_ancestor:time_period.n.01", "true"]], "EPOCH_REQUIRES_WITNESSED_NATIVE_SCOPE"),
        ([["pos", "noun"], ["wordnet_native_lemma", "true"]], "EPOCH_REQUIRES_WITNESSED_NATIVE_SCOPE"),
        (
            [["pos", "noun"], ["wordnet_native_lemma", "false"], ["wordnet_ancestor:time_period.n.01", "true"]],
            "UNSUPPORTED_LEXICAL_GUARD",
        ),
    ],
)
def test_unary_ancestry_plan_refuses_unwitnessed_scope(guards, code):
    item = family("period-when", "time_period.n.01", ["SOMETHING", 1], ["WHEN", 1], "beta")
    plan = {
        "format": "GSE.lexicon-epoch-plan/1",
        "baseline_sha256": "a" * 64,
        "active_pointer_sha256": "b" * 64,
        "epochs": 1,
        "audits_per_epoch": 1,
        "families": [{**item, "antecedent": None, "guards": guards}],
    }
    with pytest.raises(ValueError, match=code):
        parse_plan(plan)


def test_unary_native_ancestry_runs_through_real_epoch_cli(tmp_path, monkeypatch):
    import sys

    from scripts import run_lexicon_epochs

    base, pointer = tmp_path / "base.db", tmp_path / "pointer.json"
    pointer.write_text("{}")
    members = [native(word, "time_period.n.01") for word in ("alpha", "beta", "gamma", "unattested")]
    definition, observation = members[-1]
    members[-1] = (
        definition,
        replace(observation, features={**observation.features, "lemma_names": ["different_native_base"]}),
    )
    members.append(native("outside", "physical_object.n.01"))
    definitions, observations = zip(*members)
    build_dictionary(EvidenceBundle(definitions, observations, (), ()), base)
    item = family("period-when", "time_period.n.01", ["SOMETHING", 1], ["WHEN", 1], "beta")
    item.update(antecedent=None, holdouts=["wordnet:beta:beta.n.01", "wordnet:gamma:gamma.n.01"])
    plan = {
        "format": "GSE.lexicon-epoch-plan/1",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": fingerprint(pointer),
        "epochs": 1,
        "audits_per_epoch": 2,
        "families": [item],
    }
    path, directory = tmp_path / "plan.json", tmp_path / "round"
    path.write_text(json.dumps(plan))
    calls = []

    class IntervalRulings:
        identity = "fixture:interval#" + "f" * 64 + "@native-unary-test"

        def __init__(self, *args, **kwargs):
            pass

        def pin(self):
            return None

        def __call__(self, payload, schema):
            assert payload["bank"] == "WHEN" and set(schema["properties"]) == {"WHEN"}
            assert "WHEN" not in payload["known"]
            calls.append(payload["entry_id"])
            return '{"WHEN":1}'

    monkeypatch.setattr(run_lexicon_epochs, "ACTIVE_POINTER", pointer)
    monkeypatch.setattr(run_lexicon_epochs, "OllamaTransport", IntervalRulings)
    args = ["epochs", "init", "--plan", str(path), "--baseline", str(base), "--directory", str(directory)]
    monkeypatch.setattr(sys, "argv", args)
    run_lexicon_epochs.main()
    args[1] = "run"
    args.extend(["--policy", "zipf", "--model", "fixture:interval", "--model-digest", "f" * 64])
    run_lexicon_epochs.main()
    result = json.loads((directory / "zipf/arm-result.json").read_text())
    assert result["epochs"][0]["code"] == "RULE_ADMITTED"
    assert result["typed_questions_used"] == len(calls) == 3
    assert result["new_cells"] == 3 and result["reopened_cells"] == 0
    assert result["replay"]["code"] == "REPLAY_VALIDATED"
    assert result["replay"]["complete_search"] and result["replay"]["entries_mismatched"] == 0
    assert {row["entry_id"] for row in result["changes"]} == {
        "wordnet:alpha:alpha.n.01",
        "wordnet:beta:beta.n.01",
        "wordnet:gamma:gamma.n.01",
    }
    assert all(
        row["bank"] == "WHEN" and row["before"] == [-1, 0, 1] and row["after"] == [1] for row in result["changes"]
    )
    assert fingerprint(base) == plan["baseline_sha256"]
    assert fingerprint(pointer) == plan["active_pointer_sha256"]


@pytest.mark.parametrize(
    "gloss,expected",
    [
        ("A short period of time.", {"temporal_extent"}),
        ("The time period between two events.", {"temporal_extent"}),
        ("An indefinite interval of time spent waiting.", {"temporal_extent"}),
        ("A period of time during which nothing happens.", {"temporal_extent"}),
        ("A period in the periodic table.", set()),
        ("A period of time or the document that records it.", set()),
        ("A period of time and a place.", set()),
        ("A measurement of a period of time.", set()),
        ("The study of people.", set()),
        ("people who are old collectively", {"human_collective"}),
        ("The people of a country.", {"human_collective"}),
        ("A group of human beings considered collectively.", {"human_collective"}),
        ("A class of persons who live in one place.", {"human_collective"}),
        ("A person who lives in a group.", set()),
        ("People's clothing.", set()),
        ("People skills.", set()),
        ("A group of people's houses.", set()),
        ("The best people or things in a group.", set()),
        ("People and other animals.", set()),
        ("A group of people. Another definition follows.", set()),
        ("", set()),
    ],
)
def test_literal_extent_and_collective_frames_preserve_the_defining_head(gloss, expected):
    assert native_noun_frames(gloss) & {"temporal_extent", "human_collective"} == expected


@pytest.mark.parametrize(
    "frame,bank,glosses",
    [
        (
            "temporal_extent",
            "WHEN",
            (
                "A short period of time.",
                "The time period between two events.",
                "An interval of time spent waiting.",
                "A device measuring a period of time.",
            ),
        ),
        (
            "human_collective",
            "PEOPLE",
            (
                "People who share an interest.",
                "The people of a country.",
                "A group of persons who live in one place.",
                "A person who studies people.",
            ),
        ),
    ],
)
def test_literal_genus_rule_replays_across_sources_without_complement_zeros(tmp_path, frame, bank, glosses):
    base, pointer = tmp_path / "base.db", tmp_path / "pointer.json"
    pointer.write_text("{}")
    records = []
    for lemma, gloss in zip(("alpha", "beta", "control"), (glosses[0], glosses[1], glosses[3])):
        definition, observation = native(lemma, "entity_kind.n.01")
        records.append(
            (
                replace(definition, definition=gloss),
                replace(observation, features={**observation.features, "definition": gloss}),
            )
        )
    wiki_id, gloss = "wiktionary:literal-gamma", glosses[2]
    definition = Definition(wiki_id, "gamma", "noun", gloss)
    features = {
        "identity_scheme": "GSE.wiktionary-native-leaf/1",
        "entry_id": wiki_id,
        "lemma": "gamma",
        "word": "gamma",
        "pos": "noun",
        "native_id": "literal-gamma",
        "definition": gloss,
        "native_sense": {"glosses": [gloss]},
    }
    records.append(
        (
            definition,
            Observation(
                wiki_id,
                "wiktionary",
                _record_id("wiktionary", "gamma", features),
                "wiktionary",
                features,
                "lexical",
                (wiki_id,),
            ),
        )
    )
    definitions, observations = zip(*records)
    build_dictionary(EvidenceBundle(definitions, observations, (), ()), base)
    item = family("literal-genus", "entity_kind.n.01", ["SOMETHING", 1], [bank, 1], "beta")
    item.update(
        antecedent=None,
        guards=[["pos", "noun"], ["native_noun_frame:" + frame, "true"]],
        holdouts=["wordnet:beta:beta.n.01", wiki_id],
    )
    plan = {
        "format": "GSE.lexicon-epoch-plan/1",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": fingerprint(pointer),
        "epochs": 1,
        "audits_per_epoch": 2,
        "families": [item],
    }

    class LiteralRulings:
        identity = "synthetic-literal-genus"

        def __call__(self, payload, schema):
            assert payload["bank"] == bank and set(schema["properties"]) == {bank}
            assert bank not in payload["known"]
            return json.dumps({bank: 1})

    inventory = census(base, parse_plan(plan))
    assert len(inventory["literal-genus"]) == 3
    arm = run_arm(plan, base, pointer, tmp_path / "round", inventory, "zipf", LiteralRulings(), tmp_path / "model.lock")
    assert arm["epochs"][0]["code"] == "RULE_ADMITTED"
    assert arm["typed_questions_used"] == 3 and arm["new_cells"] == 3
    assert arm["reopened_cells"] == 0 and arm["replay"]["entries_mismatched"] == 0
    assert arm["replay"]["complete_search"]
    assert {r["entry_id"] for r in arm["changes"]} == {"wordnet:alpha:alpha.n.01", "wordnet:beta:beta.n.01", wiki_id}
    assert all(r["bank"] == bank and r["before"] == [-1, 0, 1] and r["after"] == [1] for r in arm["changes"])


def test_constraint_only_rule_is_taught_audited_admitted_and_replayed(tmp_path):
    """A disjunctive consequence must survive the full production learning path."""
    base, pointer = tmp_path / "base.db", tmp_path / "pointer.json"
    pointer.write_text("{}")
    definitions, observations = zip(*(native(word, "area_unit.n.01") for word in ("alpha", "beta", "gamma")))
    assertions = tuple(Assertion("SOMETHING", 1, "wordnet_hierarchy", d.entry_id, "wordnet") for d in definitions)
    build_dictionary(EvidenceBundle(definitions, observations, assertions, ()), base)
    proposal = family("synthetic-exclusion", "area_unit.n.01", ["SOMETHING", 1], ["WANT", 0], "beta")
    proposal.update(allowed_values=[0, 1], holdouts=["wordnet:beta:beta.n.01", "wordnet:gamma:gamma.n.01"])
    plan = {
        "format": "GSE.lexicon-epoch-plan/1",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": fingerprint(pointer),
        "epochs": 1,
        "audits_per_epoch": 2,
        "teaching_entry_ids": ["wordnet:alpha:alpha.n.01"],
        "families": [proposal],
    }

    class MaskRulings:
        identity = "synthetic-two-allowed-values"

        def __call__(self, payload, schema):
            assert payload["allowed_values"] == [-1, 0, 1]  # No proposed answer leaks into the question.
            return json.dumps({"WANT": 1 if payload["entry_id"] == "wordnet:beta:beta.n.01" else 0})

    inventory = census(base, parse_plan(plan))
    record(tmp_path / "inventory.json", inventory)
    arms = {
        policy: run_arm(
            plan, base, pointer, tmp_path / policy, inventory, policy, MaskRulings(), tmp_path / "model.lock"
        )
        for policy in ("closure", "zipf")
    }
    result = arms["closure"]
    [epoch] = result["epochs"]
    assert epoch["code"] == "RULE_ADMITTED" and result["typed_questions_used"] == 3
    assert result["new_cells"] == 0
    learning = epoch["specification_learning"]
    assert learning["total"]["lexicon"]["specification_gain_bits"] > 0
    assert learning["post_revision"]["lexicon"]["filled_banks"] == learning["baseline"]["lexicon"]["filled_banks"]
    assert result["replay"]["code"] == "REPLAY_VALIDATED" and result["replay"]["complete_search"]
    with sqlite3.connect(result["candidate"]) as conn:
        assert all(
            json.loads(row[0])["WANT"] == [0, 1] for row in conn.execute("SELECT domains FROM definition_states")
        )
    comparison = compare(tmp_path, plan)
    assert comparison["code"] == "EQUAL_BUDGET_JOINT_CONTRACTION_VALIDATED"
    assert comparison["format"] == "GSE.lexicon-epoch-comparison/2"
    assert comparison["joint_learning"]["code"] == "EXACT_JOINT_COMPARISON"
    assert all(arm["new_cells"] == 0 for arm in comparison["arms"].values())
    assert comparison["joint_learning"]["closure_minus_zipf_specification_gain_bits"] == 0
    assert all(
        arm["total"]["lexicon"]["specification_gain_bits"] > 0 for arm in comparison["joint_learning"]["arms"].values()
    )
    assert (tmp_path / "comparison-joint-v2.json").is_file()

    from scripts.run_lexicon_epochs import joint_learning

    incomplete = json.loads(json.dumps(arms))
    del incomplete["closure"]["epochs"][0]["specification_learning"]
    assert joint_learning(incomplete)["code"] == "JOINT_PHASE_MEASUREMENTS_UNAVAILABLE"
    unavailable = json.loads(json.dumps(arms))
    unavailable["closure"]["epochs"][0]["specification_learning"]["post_revision"]["lexicon"]["specification_bits"] = (
        None
    )
    assert joint_learning(unavailable)["code"] == "JOINT_PHASE_COUNTS_UNAVAILABLE"


def test_full_portfolio_changes_priority_beyond_two_rule_lookahead(tmp_path):
    base = tmp_path / "base.db"
    durations = [native(word, "time_unit.n.01") for word in ("da", "db", "dc", "dd")]
    areas = [native(f"area{i}", "area_unit.n.01") for i in range(9)]
    definitions, observations = zip(*durations, *areas)
    assertions = tuple(Assertion("SOMETHING", 1, "wordnet_hierarchy", d.entry_id, "wordnet") for d in definitions)
    build_dictionary(EvidenceBundle(definitions, observations, assertions, ()), base)
    plan = {
        "format": "GSE.lexicon-epoch-plan/1",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": "a" * 64,
        "epochs": 1,
        "audits_per_epoch": 1,
        "families": [
            family("first", "time_unit.n.01", ["SOMETHING", 1], ["THINK", 1], "da"),
            family("second", "time_unit.n.01", ["THINK", 1], ["FEEL", 0], "db"),
            family("third", "time_unit.n.01", ["FEEL", 0], ["WANT", 0], "dc"),
            family("isolated", "area_unit.n.01", ["SOMETHING", 1], ["HEAR", 0], "area8"),
        ],
    }
    families = parse_plan(plan)
    inventory = census(base, families)
    frequencies = {d.lemma: 1000 if d.lemma.startswith("area") else 1 for d in definitions}
    selected = choose(base, inventory, families, set(), set(), "closure", frequencies)
    assert selected["family"] == "first"
    pair_gain = selected["specification_gain_bits"] + max(b["complementary_bits"] for b in selected["bridge_options"])
    assert pair_gain < 9 * 1.584962500721156
    assert selected["portfolio_reach"]["marginal_bits"] > 9 * 1.584962500721156
    assert selected["portfolio_reach"]["code"] == "EXACT_DECLARED_PORTFOLIO"


@pytest.mark.parametrize("values", [[], [True, 0], [0, 0], [-1, 0, 1], [1]])
def test_exclusion_plan_rejects_malformed_or_vacuous_domains(values):
    proposal = family("synthetic-exclusion", "area_unit.n.01", ["SOMETHING", 1], ["WANT", 0], "beta")
    proposal["allowed_values"] = values
    with pytest.raises(ValueError, match="INVALID_EPOCH_ALLOWED_CONSEQUENTS"):
        parse_plan(
            {
                "format": "GSE.lexicon-epoch-plan/1",
                "baseline_sha256": "a" * 64,
                "active_pointer_sha256": "b" * 64,
                "epochs": 1,
                "audits_per_epoch": 1,
                "families": [proposal],
            }
        )


def counterexample_inputs(tmp_path):
    base, pointer = tmp_path / "counterexample-base.db", tmp_path / "pointer.json"
    pointer.write_text("{}")
    definitions, observations = zip(*(native(word, "area_unit.n.01") for word in ("alpha", "beta", "gamma")))
    assertions = tuple(Assertion("SOMETHING", 1, "wordnet_hierarchy", d.entry_id, "wordnet") for d in definitions)
    build_dictionary(EvidenceBundle(definitions, observations, assertions, ()), base)
    plan = {
        "format": "GSE.lexicon-epoch-plan/1",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": fingerprint(pointer),
        "epochs": 2,
        "audits_per_epoch": 1,
        "teaching_entry_ids": ["wordnet:alpha:alpha.n.01"],
        "families": [family("unconfirmed-want", "area_unit.n.01", ["SOMETHING", 1], ["WANT", 1], "beta")],
    }
    return base, pointer, plan, census(base, parse_plan(plan))


def test_legal_teaching_counterexample_is_written_preserved_and_blocks_parent(tmp_path):
    base, pointer, plan, inventory = counterexample_inputs(tmp_path)
    model = Rulings()  # A legal WANT=0 answer to a proposed WANT=+1 rule.
    args = (plan, base, pointer, tmp_path / "counterexample", inventory, "closure", model, tmp_path / "model.lock")
    result = run_arm(*args)
    first, second = result["epochs"]
    assert first["code"] == "RULE_CHALLENGED_BY_TEACHING"
    assert first["teaching"]["code"] == "REVIEWED_TEACHING_COUNTEREXAMPLE"
    assert first["surprise"]["expected_values"] == [1]
    assert first["surprise"]["observed_value"] == 0
    assert first["surprise"]["authority"] == "BOUNDED_MODEL_EVIDENCE_REQUIRES_SCOPE_REVIEW"
    assert second["code"] == "NO_ELIGIBLE_QUESTION"
    assert result["admitted"] == []
    assert result["typed_questions_used"] == len(model.calls) == 1
    assert result["pending_challenges"] == [
        {"epoch": 1, "family": "unconfirmed-want", "code": "RULE_CHALLENGED_BY_TEACHING"}
    ]
    assert result["replay"]["code"] == "REPLAY_VALIDATED"
    with sqlite3.connect(result["candidate"]) as conn:
        states = {
            entry: json.loads(domains)
            for entry, domains in conn.execute("SELECT entry_id,domains FROM definition_states")
        }
        assert states["wordnet:alpha:alpha.n.01"]["WANT"] == [0]
        assert states["wordnet:beta:beta.n.01"]["WANT"] == [-1, 0, 1]
        assert states["wordnet:alpha:alpha.n.01"]["THINK"] == [-1, 0, 1]
        assert conn.execute("SELECT COUNT(*) FROM accepted_model_receipts").fetchone()[0] == 1
    assert run_arm(*args) == result
    assert len(model.calls) == 1
    assert fingerprint(base) == plan["baseline_sha256"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"WANT":null}', "TEACHING_ABSTAINED"),
        ('{"WANT":true}', "TEACHING_INVALID_OUTPUT"),
        ('{"WANT":2}', "TEACHING_INVALID_OUTPUT"),
        ('{"WANT":0,"WANT":1}', "TEACHING_INVALID_OUTPUT"),
        ('{"WANT":0,"THINK":1}', "TEACHING_INVALID_OUTPUT"),
        ("{}", "TEACHING_INVALID_OUTPUT"),
        ("null", "TEACHING_INVALID_OUTPUT"),
        ("", "TEACHING_INVALID_OUTPUT"),
    ],
)
def test_invalid_or_abstained_teaching_is_not_an_assignment_or_signed_counterexample(tmp_path, raw, expected):
    base, pointer, plan, inventory = counterexample_inputs(tmp_path)
    plan["epochs"] = 1

    class InvalidRuling:
        identity = "synthetic-invalid-teaching"

        def __call__(self, payload, schema):
            return raw

    result = run_arm(
        plan, base, pointer, tmp_path / "invalid-round", inventory, "closure", InvalidRuling(), tmp_path / "model.lock"
    )
    assert result["epochs"][0]["teaching"]["code"] == expected
    assert result["admitted"] == result["pending_challenges"] == []
    assert result["changes"] == []
    assert result["typed_questions_used"] == 1
    assert result["candidate"] == str(base)
    assert fingerprint(base) == plan["baseline_sha256"]


def open_curriculum_inputs(tmp_path, *, resolved_alpha=False):
    from GSE.curation.lexicon_builder.learning_curriculum import plan_inventory

    base, pointer = tmp_path / "open-base.db", tmp_path / "pointer.json"
    pointer.write_text("{}")
    definitions, observations = zip(*(native(word, "time_unit.n.01") for word in ("alpha", "beta", "gamma", "delta")))
    assertions = tuple(Assertion("SOMETHING", 1, "wordnet_hierarchy", d.entry_id, "wordnet") for d in definitions)
    manifest = None
    if resolved_alpha:
        manifest = tmp_path / "known-alpha.json"
        manifest.write_text(
            json.dumps(
                {
                    "format": "GSE.lexicon-rules/1",
                    "relations": [
                        {
                            "rule_id": "synthetic-known-alpha",
                            "banks": ["QUANTITY"],
                            "allowed_rows": [[1]],
                            "provenance": ["synthetic:scheduling-control"],
                            "authority": "conditional",
                            "approved": True,
                            "guards": [["wordnet_native_lemma", "true"], ["wordnet_ancestor:alpha.n.01", "true"]],
                        }
                    ],
                }
            )
        )
    build_dictionary(EvidenceBundle(definitions, observations, assertions, ()), base, manifest=manifest)
    plan = {
        "format": "GSE.lexicon-epoch-plan/2",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": fingerprint(pointer),
        "epochs": 3,
        "audits_per_epoch": 2,
        "families": [],
        "teaching_entry_ids": ["wordnet:alpha:alpha.n.01"],
        "curriculum": {
            "banks": ["QUANTITY"],
            "frontier_limit": 4,
            "banks_per_entry": 1,
            "candidate_limit": 1,
            "audit_entry_ids": ["wordnet:beta:beta.n.01", "wordnet:gamma:gamma.n.01"],
            "scopes": [
                {
                    "id": "curriculum:units",
                    "guards": [
                        ["pos", "noun"],
                        ["wordnet_native_lemma", "true"],
                        ["wordnet_ancestor:time_unit.n.01", "true"],
                    ],
                }
            ],
        },
    }
    return base, pointer, plan, plan_inventory(base, plan)


def test_open_bank_discovery_review_audit_and_replay_resume_under_the_same_plan(tmp_path):
    from GSE.curation.lexicon_builder.learning_curriculum import REVIEW_FORMAT
    from GSE.curation.lexicon_builder.learning_state import LearningState

    base, pointer, plan, inventory = open_curriculum_inputs(tmp_path)
    directory, model = tmp_path / "learner", Rulings()
    args = (plan, base, pointer, directory, inventory, "closure", model, tmp_path / "model.lock")
    first = run_arm(*args)
    assert first["code"] == "LEARNING_REVIEW_REQUIRED"
    assert first["typed_questions_used"] == 1 == len(model.calls)
    [epoch] = first["epochs"]
    assert epoch["selected"]["task"] == "OPEN_BANK_TEACHING" and epoch["selected"]["family"] is None
    assert epoch["teaching"]["proposal_outcome"] == "NO_PROPOSED_ANSWER"
    assert first["admitted"] == [] and first["new_cells"] == 1
    [pending] = first["learning_state"]["pending"]
    assert pending["disposition"] == "AWAITING_WARRANT"
    assert pending["contract"]["banks"] == ["QUANTITY"]
    assert not (directory / "arm-result.json").exists()
    assert run_arm(*args) == first and len(model.calls) == 1
    item = family("learned-unit-quantity", "time_unit.n.01", ["SOMETHING", 1], ["QUANTITY", 1], "beta")
    item.update(antecedent=None, holdouts=["wordnet:beta:beta.n.01", "wordnet:gamma:gamma.n.01"])
    (directory / "reviews.json").write_text(
        json.dumps(
            {
                "format": REVIEW_FORMAT,
                "records": [{"mechanism_id": pending["mechanism_id"], "family": item}],
            }
        )
    )
    result = run_arm(*args)
    assert result["epochs"][1]["code"] == "RULE_ADMITTED"
    assert result["epochs"][1]["selected"]["task"] == "AUDIT_DISCOVERED_MECHANISM"
    assert result["typed_questions_used"] == len(model.calls) == 3
    assert model.calls.count(("wordnet:alpha:alpha.n.01", "QUANTITY")) == 1
    assert result["new_cells"] == 4 and result["reopened_cells"] == 0
    assert result["replay"]["code"] == "REPLAY_VALIDATED" and result["replay"]["complete_search"]
    assert result["epochs"][1]["specification_learning"]["rule_revision"]["lexicon"]["specification_gain_bits"] > 0
    with sqlite3.connect(result["candidate"]) as conn:
        for (encoded,) in conn.execute("SELECT domains FROM definition_states"):
            domains = json.loads(encoded)
            assert domains["QUANTITY"] == [1] and domains["THINK"] == [-1, 0, 1]
    assert result["learning_state"]["pending"] == []
    (directory / "reviews.json").unlink()  # Durable reviews are independent of the intake file.
    assert run_arm(*args) == result and len(model.calls) == 3
    state = LearningState(directory / "learning.sqlite", json.loads((directory / "arm.json").read_text()))
    assert state.reviewed()[0]["disposition"] == "ADMITTED"
    assert fingerprint(base) == plan["baseline_sha256"]
    assert fingerprint(pointer) == plan["active_pointer_sha256"]


def test_null_open_bank_answer_remains_unknown_and_proposes_no_rule(tmp_path):
    base, pointer, plan, inventory = open_curriculum_inputs(tmp_path)

    class Abstention:
        identity = "synthetic-open-null"

        def __call__(self, payload, schema):
            return json.dumps({payload["bank"]: None})

    result = run_arm(plan, base, pointer, tmp_path / "null", inventory, "zipf", Abstention(), tmp_path / "model.lock")
    assert result["typed_questions_used"] == 1
    assert result["epochs"][0]["teaching"]["code"] == "TEACHING_ABSTAINED"
    assert result["new_cells"] == 0 and result["learning_state"]["pending"] == []
    assert result["candidate"] == str(base)


def test_learning_review_cannot_change_the_observed_mechanism(tmp_path):
    from GSE.curation.lexicon_builder.learning_curriculum import REVIEW_FORMAT

    base, pointer, plan, inventory = open_curriculum_inputs(tmp_path)
    directory, model = tmp_path / "review-change", Rulings()
    args = (plan, base, pointer, directory, inventory, "zipf", model, tmp_path / "model.lock")
    first = run_arm(*args)
    [pending] = first["learning_state"]["pending"]
    item = family("changed", "time_unit.n.01", ["SOMETHING", 1], ["QUANTITY", 0], "beta")
    item.update(antecedent=None, holdouts=["wordnet:beta:beta.n.01", "wordnet:gamma:gamma.n.01"])
    (directory / "reviews.json").write_text(
        json.dumps(
            {
                "format": REVIEW_FORMAT,
                "records": [{"mechanism_id": pending["mechanism_id"], "family": item}],
            }
        )
    )
    with pytest.raises(ValueError, match="LEARNING_REVIEW_MECHANISM_CHANGED"):
        run_arm(*args)
    assert len(model.calls) == 1


def test_old_fixed_plan_cannot_silently_acquire_open_bank_curriculum(tmp_path):
    _, _, plan, _ = open_curriculum_inputs(tmp_path)
    plan["format"] = "GSE.lexicon-epoch-plan/1"
    with pytest.raises(ValueError, match="CURRICULUM_REQUIRES_VERSIONED_LEARNING_PLAN"):
        parse_plan(plan)


def test_resolved_frequent_word_does_not_hide_the_open_bank_frontier(tmp_path):
    from GSE.curation.lexicon_builder.learning_curriculum import choose_open

    base, _, plan, inventory = open_curriculum_inputs(tmp_path, resolved_alpha=True)
    plan["teaching_entry_ids"].append("wordnet:delta:delta.n.01")
    plan["curriculum"]["frontier_limit"] = 1
    selected = choose_open(base, plan, inventory, {}, set(), "zipf", {"alpha": 1000, "delta": 1})
    assert selected["entry_id"] == "wordnet:delta:delta.n.01"
    assert selected["family"] is None and selected["bank"] == "QUANTITY"


def test_equal_budget_comparison_consumes_discovered_inventory_and_actual_teaching_cost(tmp_path):
    from GSE.curation.lexicon_builder.learning_curriculum import REVIEW_FORMAT

    base, pointer, plan, inventory = open_curriculum_inputs(tmp_path)
    record(tmp_path / "inventory.json", inventory)
    arms = {}
    for policy in ("closure", "zipf"):
        model, directory = Rulings(), tmp_path / policy
        args = (plan, base, pointer, directory, inventory, policy, model, tmp_path / "model.lock")
        pending = run_arm(*args)["learning_state"]["pending"][0]
        item = family("discovered", "time_unit.n.01", ["SOMETHING", 1], ["QUANTITY", 1], "beta")
        item.update(antecedent=None, holdouts=["wordnet:beta:beta.n.01", "wordnet:gamma:gamma.n.01"])
        (directory / "reviews.json").write_text(
            json.dumps(
                {"format": REVIEW_FORMAT, "records": [{"mechanism_id": pending["mechanism_id"], "family": item}]}
            )
        )
        arms[policy] = run_arm(*args)
        assert arms[policy]["typed_questions_used"] == len(model.calls) == 3
        assert arms[policy]["code"] == "LEARNING_DECLARED_FRONTIER_EXHAUSTED"
    comparison = compare(tmp_path, plan)
    assert comparison["code"] == "EQUAL_BUDGET_JOINT_CONTRACTION_VALIDATED"
    assert comparison["equal_budget"] and comparison["budget"] == {"closure": 3, "zipf": 3}
    assert all(arm["direct_typed_assignments"] == arm["semantic_reviews"] == 1 for arm in comparison["arms"].values())
    assert comparison["joint_learning"]["closure_minus_zipf_specification_gain_bits"] == 0
    reference = arms["closure"]["learned_inventory"]["discovered"]
    path = tmp_path / "closure" / ("inventory-" + pending["mechanism_id"] + ".json")
    original = path.read_text()
    rows = json.loads(original)
    rows[0]["source_sha256"] = "0" * 64
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="EPOCH_LEARNED_INVENTORY_CHANGED"):
        compare(tmp_path, plan)
    path.write_text(original)
    assert reference["path"] == str(path)


def test_open_bank_curriculum_runs_through_the_public_epoch_entry_point(tmp_path, monkeypatch):
    import sys

    from scripts import run_lexicon_epochs

    base, pointer, plan, _ = open_curriculum_inputs(tmp_path)
    plan_path, directory = tmp_path / "plan.json", tmp_path / "public-round"
    plan_path.write_text(json.dumps(plan))
    model = Rulings()
    model.identity = "fixture:open#" + "f" * 64 + "@native-open-test"
    model.pin = lambda: None
    monkeypatch.setattr(run_lexicon_epochs, "ACTIVE_POINTER", pointer)
    monkeypatch.setattr(run_lexicon_epochs, "OllamaTransport", lambda *a, **k: model)
    args = ["epochs", "init", "--plan", str(plan_path), "--baseline", str(base), "--directory", str(directory)]
    monkeypatch.setattr(sys, "argv", args)
    run_lexicon_epochs.main()
    assert set(json.loads((directory / "inventory.json").read_text())) == {"curriculum:units"}
    args[1] = "run"
    args.extend(["--policy", "closure", "--model", "fixture:open", "--model-digest", "f" * 64])
    run_lexicon_epochs.main()
    [pending] = (directory / "closure").glob("review-pending-*.json")
    result = json.loads(pending.read_text())
    assert result["code"] == "LEARNING_REVIEW_REQUIRED" and result["typed_questions_used"] == 1
    assert result["epochs"][0]["selected"]["bank"] == "QUANTITY"
    run_lexicon_epochs.main()
    assert len(model.calls) == 1


def test_real_guard_imputer_refines_a_counterexample_and_replays_with_fresh_audits(tmp_path):
    pytest.importorskip("regenesis.promotion_ledger", reason="Integration: run with Regenesis on PYTHONPATH")
    from GSE.curation.lexicon_builder.learning_curriculum import REVIEW_FORMAT, plan_inventory
    from GSE.curation.lexicon_builder.learning_state import LearningState

    base, pointer = tmp_path / "contrast.db", tmp_path / "pointer.json"
    pointer.write_text("{}")
    members = []
    for word in ("alpha", "beta", "gamma", "delta", "epsilon", "cold"):
        definition, observation = native(word, "unit.n.01")
        subtype = "negative_unit.n.01" if word == "beta" else "positive_unit.n.01"
        observation = replace(
            observation,
            features={
                **observation.features,
                "hypernym_paths": [["entity.n.01", "unit.n.01", subtype, word + ".n.01"]],
            },
        )
        members.append((definition, observation))
    definitions, observations = zip(*members)
    assertions = tuple(Assertion("SOMETHING", 1, "wordnet_hierarchy", d.entry_id, "wordnet") for d in definitions)
    build_dictionary(EvidenceBundle(definitions, observations, assertions, ()), base)
    parent = family("broad-fixture", "unit.n.01", ["SOMETHING", 1], ["QUANTITY", 1], "beta")
    parent.update(antecedent=None, holdouts=["wordnet:beta:beta.n.01", "wordnet:gamma:gamma.n.01"])
    plan = {
        "format": "GSE.lexicon-epoch-plan/2",
        "baseline_sha256": fingerprint(base),
        "active_pointer_sha256": fingerprint(pointer),
        "epochs": 3,
        "audits_per_epoch": 2,
        "families": [parent],
        "teaching_entry_ids": ["wordnet:alpha:alpha.n.01"],
        "curriculum": {
            "banks": ["QUANTITY"],
            "frontier_limit": 4,
            "banks_per_entry": 1,
            "candidate_limit": 1,
            "audit_entry_ids": [f"wordnet:{word}:{word}.n.01" for word in ("beta", "gamma", "delta", "epsilon")],
            "scopes": [{"id": "curriculum:unit", "guards": parent["guards"]}],
        },
    }

    class ContrastRulings(Rulings):
        identity = "synthetic-native-contrast"

        def __call__(self, payload, schema):
            super().__call__(payload, schema)
            return json.dumps({"QUANTITY": 0 if payload["entry_id"] == "wordnet:beta:beta.n.01" else 1})

    directory, model = tmp_path / "contrast", ContrastRulings()
    args = (plan, base, pointer, directory, plan_inventory(base, plan), "closure", model, tmp_path / "model.lock")
    first = run_arm(*args)
    assert first["code"] == "LEARNING_REVIEW_REQUIRED" and first["typed_questions_used"] == 3
    first_epoch = first["epochs"][0]
    assert first_epoch["code"] == "RULE_WITHHELD_INDEPENDENT_AUDIT"
    refinement = first_epoch["refinement"]
    assert refinement["code"] == "IMPUTED_GUARDS_AWAITING_WARRANT"
    assert refinement["model_calls"] == refinement["bank_writes"] == 0
    assert refinement["counterexamples"][0]["value"] == 0
    [child] = [row for row in first["learning_state"]["pending"] if row["disposition"] == "AWAITING_WARRANT"]
    assert ["wordnet_ancestor:positive_unit.n.01", "true"] in child["contract"]["guards"]
    from GSE.curation.lexicon_builder.learning_refinement import propose_refinements

    phase = directory / "epoch-01"
    raw = json.loads((phase / "reviewed-input.json").read_text())
    audited = json.loads((phase / "audit.json").read_text())
    audited["candidates"][0]["audits"][0]["raw_output"] = '{"QUANTITY":1}'
    witness = next(row for row in args[4][parent["id"]] if row["entry_id"] == first_epoch["selected"]["entry_id"])
    with pytest.raises(ValueError, match="REFINEMENT_AUDIT_REPLAY_MISMATCH"):
        propose_refinements(
            raw, audited, parse_plan(plan)[parent["id"]], first_epoch["selected"], first_epoch["teaching"], witness
        )
    narrowed = {
        **parent,
        "id": "narrowed-fixture",
        "guards": child["contract"]["guards"],
        "holdouts": ["wordnet:delta:delta.n.01", "wordnet:epsilon:epsilon.n.01"],
    }
    invalid_review = {**narrowed, "holdouts": ["wordnet:gamma:gamma.n.01", "wordnet:delta:delta.n.01"]}
    (directory / "reviews.json").write_text(
        json.dumps(
            {"format": REVIEW_FORMAT, "records": [{"mechanism_id": child["mechanism_id"], "family": invalid_review}]}
        )
    )
    with pytest.raises(ValueError, match="INVALID_EPOCH_HOLDOUT_BUDGET_OR_OVERLAP"):
        run_arm(*args)
    control = LearningState(directory / "learning.sqlite", json.loads((directory / "arm.json").read_text()))
    assert (
        next(row for row in control.pending() if row["mechanism_id"] == child["mechanism_id"])["disposition"]
        == "AWAITING_WARRANT"
    )
    (directory / "reviews.json").write_text(
        json.dumps({"format": REVIEW_FORMAT, "records": [{"mechanism_id": child["mechanism_id"], "family": narrowed}]})
    )
    result = run_arm(*args)
    assert result["epochs"][1]["code"] == "RULE_ADMITTED" and len(result["admitted"]) == 1
    assert result["typed_questions_used"] == len(model.calls) == 5
    assert result["new_cells"] == 5 and result["replay"]["code"] == "REPLAY_VALIDATED"
    assert result["replay"]["complete_search"] and result["learning_state"]["pending"] == []
    with sqlite3.connect(result["candidate"]) as conn:
        for identity, encoded in conn.execute("SELECT entry_id,domains FROM definition_states"):
            domains = json.loads(encoded)
            assert domains["QUANTITY"] == ([-1, 0, 1] if identity == "wordnet:beta:beta.n.01" else [1])
            assert domains["THINK"] == [-1, 0, 1]
    state = LearningState(directory / "learning.sqlite", json.loads((directory / "arm.json").read_text()))
    assert {row["family"]["id"]: row["disposition"] for row in state.reviewed()} == {
        "broad-fixture": "RETIRED",
        "narrowed-fixture": "ADMITTED",
    }
    assert run_arm(*args) == result and len(model.calls) == 5
