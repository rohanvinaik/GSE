"""Closed-class layer: put each grammatical word in one of its documented homes, and only there.

``docs/LEXICON_REBUILD.md``: "Grammatical words have three homes: word-scale prime (tier-0),
sentence-scale operator (``comp_*`` / ``SYN_*`` / ``INTENSITY`` / ``QUANTITY``), or informational
zero — never decomposed as content." Layer 1 broke that for closed-class words with a WordNet noun
homograph (he = helium, are = 100 m², at = astatine, in = inch, does = the Department of Energy),
and layer 2's dominant-POS filter let adverbial connectives through (however, therefore, …) (#8).
Pronouns that ``gse/lexicon/pronouns.py`` encodes had no row at all (#9). This layer:

* gives a pronoun its designed word-scale prime (SOMEONE or SOMETHING, ``pronouns.py``): added
  where the word has no row, overwritten where layer 1 gave it a homograph;
* gives an inflected tier-0 word that word's prime (am/are/being → BE, as is/was/were/been already
  are; does/did → DO; has → HAVE), and ``cannot`` the primes of ``can`` and ``not``;
* gives five words the prime they realize (like → LIKE, underneath → BELOW, may/might/perhaps →
  MAYBE), the founder's decision of 2026-10-04;
* gives each periphrastic modal its one home, a single modality prime of Bank 7 (``GSE_V2.md``: LOGICAL;
  ``primitives_v2.BANK_7_UNIPOLAR``): could → CAN, should → MUST, would → MAYBE (GSE #66); ``shall``, a future
  like ``will``, is informational zero (the tense operator carries it);
* makes every other closed-class word informational zero: its primes are cleared and its row is
  KEPT, because ``gse.nlp.spellcheck`` reads its vocabulary from ``lexemes``.

Held deliberately: this/that/these/those are determiners in ``function_words.py`` as well as
pronouns, and rows are keyed by lemma, not POS, so a prime here would reach every determiner and
complementizer use; ``what`` is an operator row (``COMP_WHAT`` carries no word content); ``i`` and
``you`` are the tier-0 primes I and YOU, which ``pronouns.py`` encodes as SOMEONE (unsettled).
Multi-word pronouns (no one, each other, one another) have no single-token row.

This OVERWRITES rows that layer 1/layer 2 produced, so, like ``build_clean_quantifiers``, it MUST run
LAST in the build, or a layer re-run will re-clobber them. Idempotent: a second run changes nothing.
"""

from __future__ import annotations

import argparse
import sqlite3
from typing import Dict, List, Tuple

from gse.lexicon.pronouns import PRONOUN_ENCODINGS

CLEAN_DB = "data/lexicon_clean.db"
SOURCE = "closed_class"

#: Inflected forms of a tier-0 word take that word's prime; the contraction takes both of its words'.
TIER0_FORMS: Dict[str, Dict[str, int]] = {
    "am": {"BE": 1},
    "are": {"BE": 1},
    "being": {"BE": 1},
    "does": {"DO": 1},
    "did": {"DO": 1},
    "has": {"HAVE": 1},
    "cannot": {"CAN": 1, "NOT": 1},
}

#: Words that realize a prime (the founder's decision, 2026-10-04).
EXPONENTS: Dict[str, Dict[str, int]] = {
    "like": {"LIKE": 1},
    "underneath": {"BELOW": 1},
    "may": {"MAYBE": 1},
    "might": {"MAYBE": 1},
    "perhaps": {"MAYBE": 1},
}

#: The periphrastic modals (GSE #66). A grammatical word has one home (``docs/LEXICON_REBUILD.md``), and modality
#: is Bank 7's (``GSE_V2.md``: LOGICAL; ``primitives_v2.BANK_7_UNIPOLAR``: NOT, MAYBE, CAN, MUST, ...), so each
#: modal takes one Bank 7 prime from the routes ``docs/NSM_GRAMMAR_MAPPING.md`` names: could is can's past and
#: conditional form, CAN (as did is DO's); should is the weak deontic, MUST; would is the hypothetical, MAYBE.
#: should was GOOD + WANT until 2026-10-05, which put a grammatical word in the evaluation and volition banks.
PERIPHRASTIC_MODALS: Dict[str, Dict[str, int]] = {
    "could": {"CAN": 1},
    "should": {"MUST": 1},
    "would": {"MAYBE": 1},
}

#: Closed-class words (``gse.nlp.native``'s sets) with no content of their own: informational zero.
ZERO = frozenset(
    {
        "accordingly",
        "afterward",
        "afterwards",
        "amid",
        "anyhow",
        "anyway",
        "anywhere",
        "at",
        "behind",
        "besides",
        "consequently",
        "despite",
        "everywhere",
        "furthermore",
        "hence",
        "henceforth",
        "however",
        "in",
        "indeed",
        "instead",
        "likewise",
        "meantime",
        "meanwhile",
        "moreover",
        "nevertheless",
        "nonetheless",
        "nowadays",
        "nowhere",
        "otherwise",
        "over",
        "shall",
        "somewhere",
        "there",
        "thereby",
        "therefore",
        "throughout",
        "thus",
        "will",
    }
)

#: Pronouns of ``pronouns.py`` this layer leaves alone (see the module docstring).
HELD = frozenset({"this", "that", "these", "those", "what", "i", "you"})


def targets() -> Dict[str, Dict[str, int]]:
    """Every word this layer owns, mapped to its primes ({} is informational zero)."""
    out = {w: dict(e["primitives"]) for w, e in PRONOUN_ENCODINGS.items() if " " not in w and w not in HELD}
    out.update(TIER0_FORMS)
    out.update(EXPONENTS)
    out.update(PERIPHRASTIC_MODALS)
    out.update({w: {} for w in ZERO})
    return out


def action(has_row: bool, current: Dict[str, int], target: Dict[str, int]) -> str:
    """What the layer does to one word: 'keep', 'set', 'clear' or 'add'."""
    if not has_row:
        return "add" if target else "keep"
    if current == target:
        return "keep"
    return "set" if target else "clear"


def plan(con: sqlite3.Connection) -> List[Tuple[str, str, Dict[str, int], Dict[str, int]]]:
    """(word, action, current primes, target primes) for every word this layer owns."""
    out = []
    for word, target in sorted(targets().items()):
        row = con.execute("SELECT id FROM lexemes WHERE lemma=? LIMIT 1", (word,)).fetchone()
        current = (
            dict(con.execute("SELECT primitive, value FROM primitive_values WHERE lexeme_id=?", (row[0],)).fetchall())
            if row
            else {}
        )
        out.append((word, action(row is not None, current, target), current, target))
    return out


def apply(con: sqlite3.Connection, steps) -> None:
    """Write the plan in one transaction (the caller commits)."""
    for word, act, _current, target in steps:
        if act == "keep":
            continue
        if act == "add":
            cur = con.execute(
                "INSERT INTO lexemes(lemma,pos,sense_id,source,confidence,"
                "validation_status,component_type) VALUES(?,?,?,?,?,?,?)",
                (word, "x", "0", SOURCE, 1.0, SOURCE, SOURCE),
            )
            lex_id = cur.lastrowid
        else:
            lex_id = con.execute("SELECT id FROM lexemes WHERE lemma=? LIMIT 1", (word,)).fetchone()[0]
            con.execute("DELETE FROM primitive_values WHERE lexeme_id=?", (lex_id,))
            con.execute("UPDATE lexemes SET source=?, component_type=? WHERE id=?", (SOURCE, SOURCE, lex_id))
        con.executemany(
            "INSERT INTO primitive_values(lexeme_id,primitive,value,confidence,source) VALUES(?,?,?,?,?)",
            [(lex_id, p, v, 1.0, SOURCE) for p, v in target.items()],
        )


def main(clean_db: str = CLEAN_DB, dry_run: bool = False) -> dict:
    con = sqlite3.connect(clean_db)
    steps = plan(con)
    counts: Dict[str, int] = {}
    for word, act, current, target in steps:
        counts[act] = counts.get(act, 0) + 1
        if act != "keep":
            print(f"  {act:5s} {word:12s} {current or '{}'} -> {target or '{}'}")
    if not dry_run:
        apply(con, steps)
        con.commit()
    con.close()
    print(
        f"Closed-class layer ({'dry run' if dry_run else 'applied'}): {len(steps)} words: "
        + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    )
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--db", default=CLEAN_DB)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    main(a.db, a.dry_run)
