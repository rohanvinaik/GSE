"""Two-sign public intent tests for lexical facts, protection, and exact healing."""

import json
import sqlite3
import subprocess
import sys

from gse.curation.personal_dictionary import entries, identity, learn, membership, validated_concurrence
from gse.frequency import FrequencyDatabase
from gse.lexical_evidence import lookup_lexeme, raw_concreteness, raw_vad, structural_epa
from gse.nlp.heal import apply_edits, boundaries, suggest
from gse.nlp.morphology import NEGATION, REVERSAL, negation_evidence, resolve_negation


def test_lexical_zero_absence_and_unread_are_distinct(tmp_path):
    path = tmp_path / "lexicon.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            "CREATE TABLE lexemes(id INTEGER,lemma TEXT,pos TEXT,source TEXT);"
            "CREATE TABLE primitive_values(lexeme_id INTEGER,primitive TEXT,value INTEGER);"
        )
        conn.executemany(
            "INSERT INTO lexemes VALUES(?,?,?,?)",
            [(1, "only", "x", "operator"), (2, "happy", "a", "first"), (3, "happy", "a", "second")],
        )
        conn.execute("INSERT INTO primitive_values VALUES(2,'GOOD',1)")
    assert lookup_lexeme("only", path)["state"] == "no_primes"
    assert lookup_lexeme("absent", path)["state"] == "no_row"
    assert lookup_lexeme("happy", path)["state"] == "primes"
    assert lookup_lexeme("happy", path)["selected_record"]["id"] == 2
    assert lookup_lexeme("happy", path)["ambiguous"]
    assert not lookup_lexeme("happy", path)["sense_resolved"]
    assert lookup_lexeme("happy", tmp_path / "missing.db")["state"] == "unread"
    assert not (tmp_path / "missing.db").exists()


def test_frequency_does_not_replace_general_rank_with_local_or_default(tmp_path):
    path = tmp_path / "frequency.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            "CREATE TABLE frequency(word TEXT,david47k_rank INTEGER,local_rank INTEGER);"
            "INSERT INTO frequency VALUES('local',NULL,1); INSERT INTO frequency VALUES('general',5,90);"
        )
    assert FrequencyDatabase(str(path)).evidence("local")["state"] == "unranked"
    assert FrequencyDatabase(str(path)).evidence("local")["david47k_rank"] is None
    assert FrequencyDatabase(str(path)).evidence("general")["david47k_rank"] == 5
    assert FrequencyDatabase(str(path)).evidence("none")["state"] == "unranked"
    assert FrequencyDatabase(str(path)).evidence("the", applicable=False)["state"] == "not_applicable"
    assert FrequencyDatabase(str(tmp_path / "missing.db")).evidence("general")["state"] == "unread"
    assert not (tmp_path / "missing.db").exists()


def test_raw_rating_states_and_scales_have_no_network_fallback(tmp_path, monkeypatch):
    import socket

    monkeypatch.setattr(
        socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network forbidden"))
    )
    vad = tmp_path / "vad.tsv"
    vad.write_text("Word\tValence\tArousal\tDominance\nhappy\t0.9\t0.4\t0.6\n")
    concrete = tmp_path / "concrete.csv"
    concrete.write_text("Word,Bigram,Conc.M,Conc.SD,Unknown,%known\nidea,0,1.5,0.2,0,100\n")
    assert raw_vad("happy", vad)["value"] == {"valence": 0.9, "arousal": 0.4, "dominance": 0.6}
    assert raw_vad("absent", vad)["state"] == "absent"
    assert raw_vad("happy", tmp_path / "missing")["state"] == "unread"
    assert raw_concreteness("idea", concrete)["value"] == {
        "concreteness": 1.5,
        "known_percent": 100.0,
        "n_ratings": None,
    }
    assert raw_concreteness("idea", concrete)["scale"] == {"min": 1.0, "max": 5.0}
    assert raw_concreteness("absent", concrete)["state"] == "absent"
    assert structural_epa({"SOMETHING": 1})["state"] == "absent"
    assert structural_epa({"GOOD": 1})["value"]["E"] == 1.0


def test_prefix_requires_lexical_evidence_and_reversal_never_becomes_negation():
    assert resolve_negation("inside") is None
    assert negation_evidence("inside")["decision"] == "lexical"
    assert resolve_negation("under") is None
    assert resolve_negation("unloyal") == ("loyal", NEGATION)
    assert resolve_negation("unkind") == ("kind", NEGATION)
    assert resolve_negation("unlock") == ("lock", REVERSAL)
    assert negation_evidence("unlock")["feature"] != NEGATION


def test_vad_declares_version_and_accepts_negative_v2_without_guessing_scale(tmp_path):
    path = tmp_path / "vad.tsv"
    path.write_text("term\tvalence\tarousal\tdominance\nsad\t-0.9\t0.1\t-0.4\n")
    assert raw_vad("sad", path)["scale"] == {"min": -1.0, "max": 1.0}
    assert raw_vad("sad", path)["value"]["valence"] == -0.9
    assert raw_vad("sad", path, version="1")["state"] == "unread"
    old_hash = raw_vad("sad", path)["provenance"]["sha256"]
    path.write_text("sad\t0.1\t0.2\t0.3\n")
    assert raw_vad("sad", path)["state"] == "unread"
    assert raw_vad("sad", path, version="1")["value"]["valence"] == 0.1
    assert raw_vad("sad", path, version="1")["provenance"]["sha256"] != old_hash
    path.write_text("Word\tValence\tArousal\tDominance\nsad\t-0.1\t0.2\t0.3\n")
    assert raw_vad("sad", path)["state"] == "unread"
    path.write_text("wrong\theader\tnot\tdata\n")
    assert raw_vad("sad", path)["state"] == "unread"


def test_dictionary_atomic_merges_aliases_and_preserves_confirmed_definition(tmp_path):
    path = tmp_path / "dictionary.json"
    assert learn(
        {
            "surface": "Concept Loom",
            "source": "confirmed",
            "definition": "A defined concept.",
            "aliases": ["CL"],
            "review_status": "reviewed",
        },
        path=path,
    )["ok"]
    before = identity(path)["sha256"]
    assert (
        learn(
            {
                "surface": "Concept Loom",
                "source": "draft",
                "definition": "An incompatible draft.",
                "aliases": ["LoomConcept"],
            },
            path=path,
        )["code"]
        == "merged"
    )
    assert entries(path)[0].definition == "A defined concept."
    assert entries(path)[0].source == "confirmed"
    assert membership("loomconcept", path)["state"] == "member"
    assert before != identity(path)["sha256"]
    original = path.read_bytes()
    assert not learn({"surface": "Other Term", "aliases": ["CL"]}, path=path)["ok"]
    assert not learn({"surface": "a1!"}, path=path)["ok"]
    assert path.read_bytes() == original
    assert entries(path)[0].semantic_status == "pending"
    assert not list(tmp_path.glob(".dictionary-*"))


def test_entry_upgrade_retains_definition_provenance_without_certifying_it(tmp_path):
    path = tmp_path / "dictionary.json"
    assert learn({"surface": "Draft Term", "definition": "An initial draft.", "source": "draft"}, path=path)["ok"]
    assert learn({"surface": "Draft Term", "source": "confirmed"}, path=path)["ok"]
    record = entries(path)[0]
    assert record.source == "confirmed"
    assert record.definition == "An initial draft."
    assert record.definition_source == "draft"
    assert record.semantic_status == "pending"
    assert learn(
        {"surface": "Draft Term", "source": "confirmed", "definition": "The confirmed definition."}, path=path
    )["ok"]
    assert entries(path)[0].definition == "The confirmed definition."
    assert entries(path)[0].definition_source == "confirmed"


def test_dictionary_does_not_promote_malformed_or_too_small_agreement(tmp_path):
    path = tmp_path / "dictionary.json"
    assert validated_concurrence({"GOOD": 1, "FEEL": 1}, {"GOOD": 1, "KNOW": 1})["state"] == "invalid"
    assert validated_concurrence({"GOOD": True, "FEEL": 1}, {"GOOD": 1, "FEEL": 1})["state"] == "invalid"
    assert not learn({"surface": "A Term", "semantic_status": "validated"}, path=path)["ok"]
    path.write_text(json.dumps({"schema": "wrong", "entries": []}))
    assert identity(path)["state"] == "unread"
    assert membership("A Term", path)["state"] == "unread"


def test_healing_preserves_every_unaffected_utf8_byte_and_guards(tmp_path):
    path = tmp_path / "dictionary.json"
    assert learn({"surface": "Zerum", "kind": "name", "aliases": ["zerrum"]}, path=path)["ok"]
    text = '"I beleive,"\r\nPapert said: 10 µm déterminants anser zerrum `teh` <teh>.'
    out = suggest(text.encode("utf-8"), dictionary_path=path)
    assert out["corrected"] == text.replace("beleive", "believe")
    assert out["corrected"].encode("utf-8") == text.encode("utf-8").replace(b"beleive", b"believe")
    assert (
        next(record for record in out["ledger"] if record["original"] == "zerrum")["reason"] == "protected_dictionary"
    )
    assert next(record for record in out["ledger"] if record["original"] == "déterminants")["decision"] == "kept"
    assert suggest(b"\xff")["reason"] == "invalid_utf8"


def test_located_edits_refuse_ambiguous_alignment_and_overlap():
    text = "beleive beleive"
    out = apply_edits(
        text,
        [
            {"span": [0, 7], "original": "beleive", "replacement": "believe", "decision": "applied"},
            {"span": [0, 4], "original": "bele", "replacement": "bell", "decision": "applied"},
        ],
    )
    assert out["corrected"] == text
    assert all(record["reason"] == "overlap" for record in out["ledger"])
    assert (
        apply_edits(text, [{"span": [0, 7], "original": "absent", "replacement": "believe", "decision": "applied"}])[
            "ledger"
        ][0]["reason"]
        == "unaligned"
    )
    assert (
        suggest(
            "beleive",
            original_text="be<b>leive",
            source_map=[{"reduced": [0, 2], "original": [0, 2]}, {"reduced": [2, 7], "original": [5, 10]}],
        )["ledger"][0]["reason"]
        == "unaligned"
    )


def test_source_map_retains_removed_markup_and_crlf():
    original = "<p>beleive</p>\r\n"
    out = suggest("beleive", original_text=original, source_map=[{"reduced": [0, 7], "original": [3, 10]}])
    assert out["corrected"] == "believe"
    assert out["original_corrected"] == "<p>believe</p>\r\n"
    assert out["ledger"][0]["original_span"] == [3, 10]


def test_boundary_capital_alone_only_offers_and_witness_applies_exact_gap():
    text = "we wait Alice runs\r\n"
    assert boundaries(text, apply=True)["corrected"] == text
    out = boundaries(
        text,
        apply=True,
        evidence=[{"position": 7, "state": "licensed", "rule": "complete_clause_before_independent_clause"}],
    )
    assert out["corrected"] == "we wait. Alice runs\r\n"
    assert len(out["before_sentences"]) == 1
    assert len(out["after_sentences"]) == 2


def test_mcp_and_direct_healing_have_identical_text_and_ledgers():
    from gse.mcp.spell_server import spell_suggest

    text = '"I beleive it is teh thing,"\r\nPapert said.'
    direct = suggest(text)
    wrapped = spell_suggest(text)
    assert wrapped == direct
    assert direct["corrected"] == text.replace("beleive", "believe").replace("teh", "the")


def test_standalone_cli_shares_exact_source_and_ledger():
    text = '\t"I beleive it,"\r\nPapert said.  '
    process = subprocess.run(
        [sys.executable, "-m", "gse.nlp.spellcheck_repl", "--json", text],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(process.stdout) == suggest(text)


def test_learning_drafts_passes_actual_intersection_through_validation(tmp_path):
    path = tmp_path / "dict.json"
    out = learn("Test Term", path=path, drafts=({"FEEL": 1, "GOOD": 1}, {"FEEL": 1, "GOOD": 1}))
    assert out["ok"]
    assert out["curation"]["state"] == "review_required"
    assert entries(path)[0].semantic_status == "pending"
    before = path.read_bytes()
    out = learn("Other Term", path=path, drafts=({"FEEL": 1, "GOOD": 1}, {"FEEL": 1, "KNOW": 1}))
    assert out["code"] == "invalid_decomposition_drafts"
    assert path.read_bytes() == before


def test_dictionary_survives_restart_and_failed_atomic_replace(tmp_path, monkeypatch):
    from gse.curation import personal_dictionary

    path = tmp_path / "dict.json"
    assert learn({"surface": "Zerum Loom", "aliases": ["ZerumLoom"], "source": "draft"}, path=path)["ok"]
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from gse.curation.personal_dictionary import membership; print(membership('ZerumLoom', sys.argv[1])['state'])",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert process.stdout.strip() == "member"
    before = path.read_bytes()

    def failed_replace(*args):
        raise OSError("injected replacement failure")

    monkeypatch.setattr(personal_dictionary.os, "replace", failed_replace)
    assert learn("Another Term", path=path)["code"] == "store_unread"
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".dictionary-*"))


def test_learning_invalidates_protection_and_multiword_entries_protect_all_parts(tmp_path, monkeypatch):
    from gse.curation import personal_dictionary
    from gse.nlp.spellcheck import correct

    path = tmp_path / "dict.json"
    monkeypatch.setattr(personal_dictionary, "DEFAULT_PATH", path)
    assert correct("beleive").committed == "believe"
    assert learn("beleive", path=path)["ok"]
    assert correct("beleive").fired is False
    assert learn({"surface": "recieve teh", "aliases": ["seperate teh"]}, path=path)["ok"]
    assert suggest("recieve teh")["corrected"] == "recieve teh"
    assert suggest("seperate teh")["corrected"] == "seperate teh"


def test_overlap_refuses_insertion_inside_replacement_and_empty_input_is_explicit():
    text = "beleive"
    out = apply_edits(
        text,
        [
            {"span": [0, 7], "original": text, "replacement": "believe", "decision": "applied"},
            {"span": [3, 3], "original": "", "replacement": ".", "decision": "applied"},
        ],
    )
    assert out["corrected"] == text
    assert all(record["reason"] == "overlap" for record in out["ledger"])
    assert suggest("")["ledger"] == []
    assert suggest("teh", original_text=123)["reason"] == "malformed_input"
    assert apply_edits("x", [None])["ledger"][0]["reason"] == "malformed_edit"
