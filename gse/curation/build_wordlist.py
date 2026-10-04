"""Offline build of the word-VALIDITY list — the "is this a real token" gate source
for the spell-corrector (gse/nlp/spellcheck.py). This is NOT meaning: it never touches
lexicon_clean (the closed 72-prime definitional basis). It only answers grounds():
"is this a real word the corrector should leave alone?"

Source: Wiktionary English titles dump (CC-BY-SA), which carries modern/technical/
academic terms standard dictionaries lack (refactor, regex, json, api, NSM, …). We
filter to single lowercase ASCII words and SUBTRACT the known-misspelling keys from the
confusion table — so a surface Wiktionary happens to document as a misspelling (e.g.
"teh") still triggers correction rather than being treated as valid.

Run:  python -m gse.curation.build_wordlist [local_all_titles.gz]
Out:  data/wordlist_wiktionary.txt   (gitignored; one validity word per line)
"""

from __future__ import annotations

import gzip
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
    from gse.nlp.spellcheck import _DEFAULT_LEXICON as LX

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


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--trie-only":
        n = build_trie_from_txt()
        print(f"rebuilt {TRIE} from {OUT} ({n} words)")
    else:
        n = build(sys.argv[1] if len(sys.argv) > 1 else None)
        print(f"wrote {OUT} + {TRIE}  ({n} validity words; known misspellings excluded)")
