"""Readiness auditing preserves source uncertainty instead of inventing gold."""

import hashlib
import json
import sqlite3

import pytest

from scripts.audit_lexicon_evaluation_readiness import (
    VERSION,
    audit,
    identity_index,
    main,
    parse_pairs,
    parse_rankings,
)


@pytest.fixture
def lexicon(tmp_path):
    path = tmp_path / "lexicon.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            "CREATE TABLE builder_metadata (key TEXT, value TEXT);"
            "CREATE TABLE lexemes (id INTEGER, lemma TEXT, pos TEXT);"
            "CREATE TABLE definition_states (entry_id TEXT, lexeme_id INTEGER);"
        )
        conn.execute("INSERT INTO builder_metadata VALUES (?,?)", ("format", json.dumps(VERSION)))
        for i, (entry_id, word, pos) in enumerate(
            (
                ("big:1", "big", "adjective"),
                ("big:2", "big", "adjective"),
                ("large:1", "large", "adjective"),
                ("large:n", "large", "noun"),
            ),
            1,
        ):
            conn.execute("INSERT INTO lexemes VALUES (?,?,?)", (i, word, pos))
            conn.execute("INSERT INTO definition_states VALUES (?,?)", (entry_id, i))
    return path


def test_rank_parser_preserves_ties_and_nonconsecutive_ranks():
    assert parse_rankings("0\tbig || large\n\n3\thuge\n") == ((0, ("big", "large")), (3, ("huge",)))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "0 big",
        "-1\tbig",
        "0\tbig\n0\tlarge",
        "1\tbig\n0\tlarge",
        "0\tbig||big",
        "0\tbig\n1\tbig",
        "0\tbig||",
        "0\tbig\textra",
    ],
)
def test_rank_parser_rejects_malformed_groups(text):
    with pytest.raises(ValueError):
        parse_rankings(text)


@pytest.mark.parametrize("score,pos", [("nan", "A"), ("inf", "A"), ("-1", "A"), ("11", "A"), ("4", "X")])
def test_pair_parser_rejects_invalid_source_labels(score, pos):
    with pytest.raises(ValueError):
        parse_pairs(f"word1\tword2\tPOS\tSimLex999\nbig\tlarge\t{pos}\t{score}\n", simlex=True)


def test_readiness_keeps_identity_ambiguity_and_ties_without_writing_db(lexicon, tmp_path):
    root, cache = tmp_path / "project", tmp_path / "cache"
    cache.mkdir()
    (cache / "SimLex-999.txt").write_text("word1\tword2\tPOS\tSimLex999\nbig\tlarge\tA\t7.2\nlarge\tmissing\tA\t0\n")
    scalars = root / "data/external/scalar-adj/globalorder/data/demelo/gold_rankings"
    scalars.mkdir(parents=True)
    (scalars / "sizes.rankings").write_text("0\tbig||large\n1\tmissing\n")
    before = hashlib.sha256(lexicon.read_bytes()).hexdigest()
    result = audit(lexicon, project_root=root, benchmark_cache=cache)
    assert hashlib.sha256(lexicon.read_bytes()).hexdigest() == before
    assert result["bank_gold"] == "NOT_BANK_GOLD"
    assert result["semantic_correctness"] == "NOT_EVALUATED"
    assert result["build"]["definitions"] == 4
    simlex = result["cohorts"]["simlex999"]
    assert simlex["identity"]["outcomes"] == {
        "MISSING": 1,
        "UNIQUE_CANDIDATE": 1,
        "MULTIPLE_DEFINITIONS": 1,
    }
    assert simlex["identity"]["verified_sense_links"] == 0
    assert simlex["identity"]["examples"]["MULTIPLE_DEFINITIONS"][0]["candidate_entry_ids"] == ["big:1", "big:2"]
    scalar = result["cohorts"]["demelo"]
    assert (scalar["rank_groups"], scalar["tied_rank_groups"], scalar["word_occurrences"]) == (2, 1, 3)
    assert result["cohorts"]["wordsim353"]["code"] == "SOURCE_MISSING"
    assert result == audit(lexicon, project_root=root, benchmark_cache=cache)


def test_identity_index_rejects_orphan_definition(lexicon):
    with sqlite3.connect(lexicon) as conn:
        conn.execute("INSERT INTO definition_states VALUES ('orphan',99)")
    with pytest.raises(ValueError, match="UNMATCHED_BUILD_IDENTITY"):
        identity_index(lexicon)


def test_output_cannot_overwrite_database(lexicon):
    before = lexicon.read_bytes()
    with pytest.raises(SystemExit):
        main(["--lexicon-db", str(lexicon), "--output", str(lexicon)])
    assert lexicon.read_bytes() == before
