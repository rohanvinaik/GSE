"""Check native state-definition routing through the actual sentence encoder."""

from collections import Counter, defaultdict
from pathlib import Path

from gse.api.encoder import GrammaticalDefinitionError, GSEEncoder
from gse.curation.lexicon_builder.epoch import fingerprint, read

NOTES = Path(__file__).resolve().parent


def audit(lexicon):
    source = read(NOTES / "019-stative-parent-preview.json")
    definitions = [row for row in source["definitions"] if row["entry_id"].startswith("wordnet:")]
    before = fingerprint(lexicon)
    results = []
    with GSEEncoder(lexicon) as encoder:
        encoder.conn.execute("PRAGMA query_only=ON")
        for number, row in enumerate(definitions):
            selected = encoder.lookup_definition(row["entry_id"])
            if selected["code"] != "IDENTIFIED":
                raise ValueError("STATE_CORPUS_DEFINITION_MISSING:" + row["entry_id"])
            domain = selected["selected"]["domains"]["BE"]
            for style, subject in (
                ("determined", "The " + row["lemma"]),
                ("capitalized", row["lemma"][:1].upper() + row["lemma"][1:]),
            ):
                text = subject + " is " + row["gloss"].removesuffix(".") + "."
                result = {
                    "entry_id": row["entry_id"], "lemma": row["lemma"], "gloss": row["gloss"],
                    "style": style, "text": text, "stored_BE_domain": domain,
                }
                try:
                    trace = encoder.encode(text)
                except GrammaticalDefinitionError as error:
                    result.update(code="ABSTAINED_GRAMMATICAL_REQUIREMENT", reason=str(error))
                else:
                    hits = [token for token in trace.tokens if token.token.casefold() == row["lemma"].casefold()]
                    if len(hits) != 1:
                        result.update(code="ABSTAINED_TOKEN_BOUNDARY")
                    else:
                        token = hits[0]
                        chosen = (token.lexical_evidence.get("selected_record") or {}).get("entry_id")
                        code = "IDENTIFIED_CORRECT" if chosen == row["entry_id"] else "WRONG" if chosen else "ABSTAINED"
                        value = token.word_primitives.get("BE")
                        expected = domain[0] if len(domain) == 1 and domain[0] else None
                        if chosen == row["entry_id"] and value != expected:
                            code = "WRONG_EMISSION"
                        if chosen is None and value is not None:
                            code = "UNSUPPORTED_SENSE_EMISSION"
                        result.update(
                            code=code, observed_entry_id=chosen, emitted_BE=value,
                            grounding=token.lexical_evidence.get("contextual_grounding"),
                        )
                results.append(result)
            if number % 100 == 0:
                print("STATE_CORPUS_PROGRESS", number, len(definitions), flush=True)
    if fingerprint(lexicon) != before:
        raise ValueError("STATE_CORPUS_LEXICON_CHANGED")
    counts = defaultdict(Counter)
    for row in results:
        counts[row["style"]][row["code"]] += 1
    wrong = [r for r in results if r["code"] in {"WRONG", "WRONG_EMISSION", "UNSUPPORTED_SENSE_EMISSION"}]
    return {
        "format": "gse.state-corpus-grounding/1",
        "code": "STATE_CORPUS_GROUNDING_VALIDATED" if not wrong else "STATE_CORPUS_GROUNDING_REVIEW_REQUIRED",
        "lexicon_sha256": before, "scope_snapshot_sha256": source["baseline_sha256"],
        "definitions": len(definitions), "cases": len(results), "by_class": dict(counts),
        "wrong": wrong, "results": results,
        "scope": "All native WordNet records in the frozen explicit-stative parent scope with their full "
        "definitions supplied as predicate context. This checks identity routing and storage-to-emission fidelity.",
    }
