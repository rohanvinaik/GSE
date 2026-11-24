"""Exact request/source guards for the grouped own-coordinate transition."""

import importlib.util
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "checkpoint_canonical_projection",
    ROOT / "docs/readings/2026-11-13-ssl-explicit-genera/ssl_api_checkpoint_canonical_projection.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write(path, value):
    path.write_text(json.dumps(value))


def fixture(tmp_path, monkeypatch, value=1):
    baseline = tmp_path / "baseline.db"
    baseline.write_bytes(b"immutable candidate")
    source = tmp_path / "source.txt"
    source.write_text("exact primary meaning")
    claim = {
        "entry_id": "exact:think",
        "unit_id": "think",
        "bank": "THINK",
        "value": 1,
        "scope": "EXACT_SOURCE_DEFINITION_AND_OWN_COORDINATE_ONLY",
        "derivation": "Reviewed exact primary meaning and fixed basis definition",
    }
    review = {
        "baseline": {"path": str(baseline), "sha256": MODULE.fingerprint(baseline)},
        "source_pins": {str(source): MODULE.fingerprint(source)},
        "claims": [claim],
    }
    review_path = tmp_path / "review.json"
    write(review_path, review)
    request = SimpleNamespace(
        request_id="original-wire-id",
        entry_id=claim["entry_id"],
        bank="THINK",
        allowed_values=(-1, 0, 1),
        payload=lambda: {"source": "complete exact source", "bank": "THINK"},
        output_schema=lambda: {"type": "object"},
    )
    monkeypatch.setattr(MODULE, "make_questions", lambda *args: [request])
    directory = tmp_path / "witnesses"
    directory.mkdir()
    write(
        directory / "questions.json",
        {
            "format": "GSE.ssl-checkpoint-local-questions/1",
            "baseline_sha256": MODULE.fingerprint(baseline),
            "coordinates": [[claim["entry_id"], "THINK"]],
            "questions": [
                {"request_id": request.request_id, "request": request.payload(), "schema": request.output_schema()}
            ],
        },
    )
    write(
        directory / "answers.json",
        {
            "questions_sha256": MODULE.fingerprint(directory / "questions.json"),
            "transport": "true-98k-identity",
            "answers": [{"request_id": request.request_id, "raw_output": json.dumps({"THINK": value})}],
        },
    )
    audit = {
        "code": "TYPED_WITNESSES_RECORDED_NOT_ADMISSION",
        "baseline": review["baseline"],
        "review_sha256": MODULE.fingerprint(review_path),
        "questions_sha256": MODULE.fingerprint(directory / "questions.json"),
        "answers_sha256": MODULE.fingerprint(directory / "answers.json"),
        "transport": "true-98k-identity",
        "bank_writes": 0,
        "is_final_holdout": False,
        "records": [{"entry_id": claim["entry_id"], "bank": "THINK", "value": value, "request_id": request.request_id}],
    }
    write(directory / "audit.json", audit)
    return review_path, directory, review, audit


def test_matching_original_witness_only_creates_reviewed_own_anchor(tmp_path, monkeypatch):
    path, directory, _, _ = fixture(tmp_path, monkeypatch)
    _, claims, reservations = MODULE.verify_witnesses(path, directory)
    assert reservations == []
    manifest = MODULE.manifest_payload(claims, "review-pin", "audit-pin")
    assert set(manifest) == {"format", "anchors"}
    assert manifest["anchors"] == {
        "exact:think": [
            {
                "bank": "THINK",
                "value": 1,
                "source": "nsm_basis_correspondence:canonical-source-review-v1",
                "record_id": "think:review-pin:audit-pin:THINK",
                "family": "nsm_basis_correspondence",
                "scope": "lexical",
            }
        ]
    }


def test_explicit_null_reserves_without_assertion(tmp_path, monkeypatch):
    path, directory, _, _ = fixture(tmp_path, monkeypatch, None)
    _, claims, reservations = MODULE.verify_witnesses(path, directory)
    assert claims == []
    assert reservations == [{"entry_id": "exact:think", "bank": "THINK", "reason": "EXPLICIT_NULL"}]


def test_opposing_witness_is_not_silently_discarded(tmp_path, monkeypatch):
    path, directory, _, _ = fixture(tmp_path, monkeypatch, -1)
    with pytest.raises(ValueError, match="INDEPENDENT_DISAGREEMENT"):
        MODULE.verify_witnesses(path, directory)


@pytest.mark.parametrize("change", ["baseline", "source", "request", "transport", "scope", "duplicate", "outcome"])
def test_changed_authority_refused(tmp_path, monkeypatch, change):
    path, directory, review, audit = fixture(tmp_path, monkeypatch)
    if change == "baseline":
        Path(review["baseline"]["path"]).write_bytes(b"different head")
    elif change == "source":
        Path(next(iter(review["source_pins"]))).write_text("different meaning")
    elif change == "request":
        packet = MODULE.read(directory / "questions.json")
        packet["questions"][0]["request"]["source"] = "discarded context"
        write(directory / "questions.json", packet)
        audit["questions_sha256"] = MODULE.fingerprint(directory / "questions.json")
    elif change == "transport":
        audit["transport"] = "mislabelled-65k"
    elif change in ("scope", "duplicate"):
        if change == "scope":
            review["claims"][0]["scope"] = "ALL_SPELLINGS"
        else:
            review["claims"] *= 2
        write(path, review)
        audit["review_sha256"] = MODULE.fingerprint(path)
    else:
        audit["records"][0]["value"] = 0
    write(directory / "audit.json", audit)
    with pytest.raises(ValueError, match="CANONICAL_PROJECTION"):
        MODULE.verify_witnesses(path, directory)


def test_actual_pinned_storage_reader_relocation_is_exact():
    certificate = MODULE.read(
        ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/ssl-api-checkpoint/postwriter-validation.json"
    )
    pins, relocations = MODULE.checked_builder_pins(certificate["builder_source_pins"])
    assert len(relocations) == 1
    assert relocations[0]["reader"] in pins


@pytest.mark.parametrize("change", ["writer", "reader", "reader_extra", "other_pin"])
def test_relocation_does_not_authorize_other_changed_code(tmp_path, monkeypatch, change):
    storage = Path("GSE/curation/lexicon_builder/storage.py")
    reader = Path("GSE/lexicon/definitions.py")
    old = MODULE.subprocess.check_output(["git", "show", MODULE.HISTORICAL_STORAGE + ":" + str(storage)])
    current, moved = (ROOT / storage).read_text(), (ROOT / reader).read_text()
    monkeypatch.chdir(tmp_path)
    storage.parent.mkdir(parents=True)
    reader.parent.mkdir(parents=True)
    storage.write_text(current + ("\nUNREVIEWED = True\n" if change == "writer" else ""))
    reader.write_text(
        moved.replace('"NOT_FOUND"', '"IDENTIFIED"')
        if change == "reader"
        else moved + ("\nUNREVIEWED = True\n" if change == "reader_extra" else "")
    )
    monkeypatch.setattr(MODULE.subprocess, "check_output", lambda *args: old)
    pin = {"path": str(storage), "sha256": MODULE.hashlib.sha256(old).hexdigest()}
    if change == "other_pin":
        pin = {"path": str(reader), "sha256": "not-the-current-pin"}
    with pytest.raises(ValueError, match="CANONICAL_PROJECTION"):
        MODULE.checked_builder_pins([pin])


def legacy_auxiliary_build(path):
    """Build the real historical AUX producer and one context-bound ruling."""
    from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser, _entry
    from GSE.curation.lexicon_builder.completion import complete_dictionary
    from GSE.curation.lexicon_builder.evidence import collect_evidence
    from GSE.curation.lexicon_builder.pipeline import build_dictionary
    from GSE.curation.lexicon_builder.validation import validate_build

    parser = GSEClosedClassParser()
    parser.load()
    for word, entries in parser.entries.items():
        for index, native in enumerate(entries):
            if native.catalog != "auxiliary":
                continue
            bank = {"be": "BE", "do": "DO", "have": "HAVE"}[native.grammatical_features["lemma"]]
            entries[index] = _entry(
                word,
                native.catalog,
                native.pos,
                native.grammar_roles,
                {bank: 1},
                native.grammatical_features,
                list(native.native_encodings),
            )
    build_dictionary(collect_evidence({"gse_closed_class": parser}, ()), path)

    class TypedFixture:
        model = "typed-fixture-not-a-service"

        def __call__(self, payload, schema):
            return json.dumps({payload["bank"]: 0})

    report = complete_dictionary(path, TypedFixture(), 1, entry_ids=("gse_closed_class:auxiliary:is",), banks=("BODY",))
    assert report["outcomes"] == {"ASSIGNED": 1}
    replay = validate_build(path)
    assert replay["code"] == "REPLAY_VALIDATED"
    return replay


def test_real_auxiliary_source_transition_archives_model_context_and_replays(tmp_path):
    from GSE.curation.lexicon_builder.source_enrichment import revise_source_candidate
    from GSE.curation.lexicon_builder.validation import validate_build
    from GSE.lexicon_resource import ACTIVE_POINTER

    baseline, successor = tmp_path / "old.db", tmp_path / "new.db"
    replay = legacy_auxiliary_build(baseline)
    baseline_sha = MODULE.fingerprint(baseline)
    review = MODULE.auxiliary_review(baseline)
    assert len(review["claims"]) == 19
    assert sum(len(c["retired_model_requests"]) for c in review["claims"]) == 1
    manifest = tmp_path / "empty.json"
    write(manifest, {"format": "GSE.lexicon-rules/1", "anchors": {}})

    def apply(conn):
        changes = MODULE.apply_auxiliary_revision(conn, review, replay)
        MODULE.apply_projection(conn, [], manifest)
        return changes

    report = revise_source_candidate(
        baseline,
        successor,
        {
            "candidate_sha256": baseline_sha,
            "active_pointer_sha256": MODULE.fingerprint(ACTIVE_POINTER),
            "replay": replay,
        },
        apply,
        format_tag="GSE.test-source-revision/1",
        metadata_key="test_source_revision",
    )
    assert MODULE.fingerprint(baseline) == baseline_sha
    assert report["replay"]["code"] == "REPLAY_VALIDATED"
    assert report["changes"]["zero_assertions_added"] == 0
    with sqlite3.connect(successor) as conn:
        aux = conn.execute(
            "SELECT domains FROM definition_states WHERE entry_id LIKE 'gse_closed_class:auxiliary:%'"
        ).fetchall()
        assert len(aux) == 19
        assert all(all(d == [-1, 0, 1] for d in json.loads(row[0]).values()) for row in aux)
        assert conn.execute("SELECT COUNT(*) FROM accepted_model_receipts").fetchone()[0] == 0
        archive = json.loads(conn.execute("SELECT payload FROM model_reconsideration_archive").fetchone()[0])
        assert archive["archived_receipts"][0]["receipt"]["request"]["entry_id"] == "gse_closed_class:auxiliary:is"
        with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
            conn.execute("DELETE FROM model_reconsideration_archive")
        for claim in review["claims"]:
            raw = json.loads(
                conn.execute(
                    "SELECT payload FROM source_observations WHERE entry_id=?", (claim["entry_id"],)
                ).fetchone()[0]
            )
            assert raw == claim["after"]
            assert raw["features"]["native_encodings"] == claim["before"]["features"]["native_encodings"]
        assert (
            conn.execute(
                "SELECT value FROM primitive_values p JOIN definition_states d ON p.lexeme_id=d.lexeme_id "
                "WHERE d.entry_id='gse_closed_class:modal:can' AND p.primitive='CAN'"
            ).fetchone()[0]
            == 1
        )
    assert validate_build(successor)["code"] == "REPLAY_VALIDATED"


def test_changed_auxiliary_review_cannot_mutate_immutable_input(tmp_path):
    from GSE.curation.lexicon_builder.source_enrichment import revise_source_candidate
    from GSE.lexicon_resource import ACTIVE_POINTER

    baseline, successor = tmp_path / "old.db", tmp_path / "refused.db"
    replay = legacy_auxiliary_build(baseline)
    before = MODULE.fingerprint(baseline)
    review = MODULE.auxiliary_review(baseline)
    review["claims"][-1]["before"]["features"]["definition"] = "unreviewed definition"
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        revise_source_candidate(
            baseline,
            successor,
            {"candidate_sha256": before, "active_pointer_sha256": MODULE.fingerprint(ACTIVE_POINTER), "replay": replay},
            lambda conn: MODULE.apply_auxiliary_revision(conn, review, replay),
            format_tag="GSE.test-source-revision/1",
            metadata_key="test_source_revision",
        )
    assert MODULE.fingerprint(baseline) == before
    assert not successor.exists()


@pytest.mark.parametrize("change", [None, "scope", "construction"])
def test_chart_own_coordinate_uses_reviewed_structural_source_not_frame_values(tmp_path, change):
    from GSE.curation.external_sources.nsm_chart import NSMChartParser
    from GSE.curation.lexicon_builder.evidence import collect_evidence
    from GSE.curation.lexicon_builder.pipeline import build_dictionary
    from GSE.curation.lexicon_builder.validation import validate_build

    parser = NSMChartParser()
    parser.load()
    baseline = tmp_path / "chart.db"
    build_dictionary(collect_evidence({"nsm_chart": parser}, ()), baseline)
    entry, unit = "nsm_chart:v20:now", "nsm:v20:now"
    with sqlite3.connect(baseline) as conn:
        conn.row_factory = sqlite3.Row
        native = json.loads(
            conn.execute("SELECT payload FROM source_observations WHERE entry_id=?", (entry,)).fetchone()[0]
        )
        assert native["scope"] == "source_structure"
        if change:
            if change == "scope":
                native["scope"] = "lexical"
            else:
                native["features"]["definition_kind"] = "SENTENCE_CONSTRUCTION"
            conn.execute("UPDATE source_observations SET payload=? WHERE entry_id=?", (json.dumps(native), entry))
        claim = {
            "entry_id": entry,
            "unit_id": unit,
            "bank": "THEN",
            "value": -1,
            "definition": native["features"]["definition"],
            "pos": native["features"]["pos"],
            "identity_link": {"entry_ids": [entry]},
            "native_source": "nsm_chart",
            "native_record_id": native["record_id"],
            "native_observation_sha256": MODULE.observation_digest(native),
        }
        MODULE._set_metadata(conn, "prime_entries", {unit: [entry]})
        manifest = tmp_path / "reviewed-own-coordinate.json"
        write(manifest, MODULE.manifest_payload([claim], "review-pin", "audit-pin"))
        if change:
            with pytest.raises(ValueError, match="CANONICAL_PROJECTION_SOURCE_CHANGED"):
                MODULE.apply_projection(conn, [claim], manifest)
            return
        MODULE.apply_projection(conn, [claim], manifest)
        domains = json.loads(
            conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry,)).fetchone()[0]
        )
        assert domains["THEN"] == [-1]
        # The one reviewed assertion also activates the existing temporal
        # category law. This is justified closure, not imported frame content.
        assert domains["WHEN"] == [1]
        assert all(v == [-1, 0, 1] for b, v in domains.items() if b not in {"THEN", "WHEN"})
        assert (
            json.loads(conn.execute("SELECT payload FROM source_observations WHERE entry_id=?", (entry,)).fetchone()[0])
            == native
        )
    assert validate_build(baseline)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("change", [None, "source", "family", "scope"])
def test_wordnet_own_coordinate_uses_actual_native_producer_shape(tmp_path, change):
    from GSE.curation.lexicon_builder.evidence import collect_evidence
    from GSE.curation.lexicon_builder.pipeline import build_dictionary
    from GSE.curation.lexicon_builder.validation import validate_build

    # Exercise the real WordNet evidence adapter without loading or downloading
    # a corpus. The stub supplies only native synset operations, not observations.
    synset = SimpleNamespace(
        name=lambda: "people.n.01",
        definition=lambda: "(plural) any group of human beings collectively",
        pos=lambda: "n",
        hypernym_paths=lambda: [],
        lexname=lambda: "noun.group",
        examples=lambda: [],
        lemma_names=lambda: ["people"],
    )
    parser = SimpleNamespace(_wn=SimpleNamespace(synsets=lambda word: [synset]), entries={})
    baseline = tmp_path / "wordnet.db"
    build_dictionary(collect_evidence({"wordnet_hierarchy": parser}, ("people",)), baseline)
    entry, unit = "wordnet:people:people.n.01", "nsm:v20:people"
    with sqlite3.connect(baseline) as conn:
        conn.row_factory = sqlite3.Row
        native = json.loads(
            conn.execute("SELECT payload FROM source_observations WHERE entry_id=?", (entry,)).fetchone()[0]
        )
        assert (native["source"], native["family"], native["scope"]) == ("wordnet_hierarchy", "wordnet", "lexical")
        if change:
            native[change] = {"source": "wordnet", "family": "unreviewed", "scope": "source_structure"}[change]
            conn.execute(
                "UPDATE source_observations SET source=?, payload=? WHERE entry_id=?",
                (native["source"], json.dumps(native), entry),
            )
        claim = {
            "entry_id": entry,
            "unit_id": unit,
            "bank": "PEOPLE",
            "value": 1,
            "definition": native["features"]["definition"],
            "pos": native["features"]["pos"],
            "identity_link": {"entry_ids": [entry]},
            "native_source": native["source"],
            "native_record_id": native["record_id"],
            "native_observation_sha256": MODULE.observation_digest(native),
        }
        MODULE._set_metadata(conn, "prime_entries", {unit: [entry]})
        manifest = tmp_path / "reviewed-own-coordinate.json"
        write(manifest, MODULE.manifest_payload([claim], "review-pin", "audit-pin"))
        if change:
            with pytest.raises(ValueError, match="CANONICAL_PROJECTION_SOURCE_CHANGED"):
                MODULE.apply_projection(conn, [claim], manifest)
            return
        MODULE.apply_projection(conn, [claim], manifest)
        domains = json.loads(
            conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry,)).fetchone()[0]
        )
        assert domains["PEOPLE"] == [1]
        assert (
            json.loads(conn.execute("SELECT payload FROM source_observations WHERE entry_id=?", (entry,)).fetchone()[0])
            == native
        )
    assert validate_build(baseline)["code"] == "REPLAY_VALIDATED"
