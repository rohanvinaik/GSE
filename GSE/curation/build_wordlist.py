"""Offline build of the word-VALIDITY list — the "is this a real token" gate source
for the spell-corrector (GSE/nlp/spellcheck.py). This is NOT meaning: it never touches
lexicon_clean (the closed 72-prime definitional basis). It only answers grounds():
"is this a real word the corrector should leave alone?"

Source: Wiktionary English titles dump (CC-BY-SA), which carries modern/technical/
academic terms standard dictionaries lack (refactor, regex, json, api, NSM, …). We
filter to single lowercase ASCII words and SUBTRACT the known-misspelling keys from the
confusion table — so a surface Wiktionary happens to document as a misspelling (e.g.
"teh") still triggers correction rather than being treated as valid.

Run:  python -m GSE.curation.build_wordlist [local_all_titles.gz]
Out:  data/wordlist_wiktionary.txt   (gitignored; one validity word per line)
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://dumps.wikimedia.org/enwiktionary/latest/enwiktionary-latest-all-titles-in-ns0.gz"
_UA = "GSE-spellcheck-build/1.0 (research; rohanpvinaik@gmail.com)"
OUT = Path(__file__).resolve().parents[2] / "data" / "wordlist_wiktionary.txt"
TRIE = OUT.with_suffix(".marisa")  # compact EXACT runtime artifact (~24MB RAM vs ~660MB set)
_WORD = re.compile(r"^[a-z]{2,20}$")


def _write_trie(words) -> None:
    import marisa_trie

    marisa_trie.Trie(words).save(str(TRIE))


def build_trie_from_txt() -> int:
    """Rebuild the marisa trie from an existing .txt (no re-download)."""
    with open(OUT, encoding="utf-8") as f:
        words = [w for w in (line.strip() for line in f) if w]
    _write_trie(words)
    return len(words)


def _lines(local_gz: str | None):
    if local_gz:
        with gzip.open(local_gz, "rt", encoding="utf-8", errors="replace") as f:
            yield from f
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            with gzip.open(resp, "rt", encoding="utf-8", errors="replace") as f:
                yield from f


def build(local_gz: str | None = None) -> int:
    from GSE.nlp.spellcheck import _DEFAULT_LEXICON as LX

    misspellings = set(LX.confusions.keys())  # exclude known typos
    words = set()
    for line in _lines(local_gz):
        w = line.strip().lower()
        if _WORD.match(w) and w not in misspellings:
            words.add(w)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(sorted(words)) + "\n", encoding="utf-8")
    _write_trie(words)  # compact exact runtime artifact alongside the .txt
    return len(words)


def build_from_kaikki(path: str | Path) -> dict:
    """Build the existing text validity resource from complete local JSON records.

    This establishes token membership only, never a semantic definition or bank.
    Malformed input fails before replacing a usable resource. A pre-existing trie
    must be rebuilt too, because runtime prefers it over the text resource.
    """
    from GSE.nlp.spellcheck import _DEFAULT_LEXICON as LX

    source = Path(path).resolve()
    words, excluded, rejected, spelling_only = set(), set(LX.confusions), set(), set()
    digest = hashlib.sha256()
    records = 0
    with source.open("rb") as stream:
        for line in stream:
            digest.update(line)
            record = json.loads(line)
            records += 1
            if not isinstance(record, dict) or not isinstance(record.get("word"), str):
                raise ValueError("INVALID_KAIKKI_WORD_RECORD")
            if record.get("lang_code") != "en":
                continue
            word = record["word"].lower()
            senses = record.get("senses", [])
            if not isinstance(senses, list) or any(not isinstance(sense, dict) for sense in senses):
                raise ValueError("INVALID_KAIKKI_SENSE_RECORD")
            if any(
                not isinstance(sense.get("tags", []), list)
                or any(not isinstance(tag, str) for tag in sense.get("tags", []))
                for sense in senses
            ):
                raise ValueError("INVALID_KAIKKI_SENSE_RECORD")
            # The dump documents erroneous forms as entries too. Only an
            # explicit misspelling tag on EVERY sense excludes this record.
            # Other records/senses for the same spelling still establish
            # ordinary membership; form-of/rare/archaic alone are not errors.
            if senses and all("misspelling" in sense.get("tags", []) for sense in senses):
                if _WORD.fullmatch(word):
                    spelling_only.add(word)
                continue
            if _WORD.fullmatch(word) and word in excluded:
                rejected.add(word)
            if _WORD.fullmatch(word) and word not in excluded:
                words.add(word)
    if not words:
        raise ValueError("EMPTY_VALIDITY_CORPUS")
    if TRIE.exists():
        _write_trie(words)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUT.with_suffix(".tmp")
    temporary.write_text("\n".join(sorted(words)) + "\n", encoding="utf-8")
    temporary.replace(OUT)
    report = {
        "format": "GSE.word-validity-build/1",
        "code": "MEMBERSHIP_ONLY",
        "source": str(source),
        "source_sha256": digest.hexdigest(),
        "records": records,
        "words": len(words),
        "known_misspellings_excluded": len(rejected),
        "native_spelling_only_words_excluded": len(spelling_only - words),
        "native_spelling_forms_with_independent_membership": len(spelling_only & words),
        "native_membership_policy": "EXCLUDE_EXPLICIT_ALL_SENSE_MISSPELLING_RECORDS_RETAIN_INDEPENDENT_SENSES",
        "output": str(OUT.resolve()),
        "output_sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "storage": "TEXT_AND_TRIE" if TRIE.exists() else "TEXT",
        "semantic_assignments": 0,
    }
    OUT.with_suffix(".receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--kaikki":
        print(json.dumps(build_from_kaikki(sys.argv[2]), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--trie-only":
        n = build_trie_from_txt()
        print(f"rebuilt {TRIE} from {OUT} ({n} words)")
    else:
        n = build(sys.argv[1] if len(sys.argv) > 1 else None)
        print(f"wrote {OUT} + {TRIE}  ({n} validity words; known misspellings excluded)")
