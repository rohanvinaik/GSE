"""Interactive REPL for the deterministic spell-checker.

    python -m gse.nlp.spellcheck_repl                 # interactive
    python -m gse.nlp.spellcheck_repl "teh wierd dog" # one-shot

Type a word to see the word-level noisy-channel correction + candidate trace; type a
sentence to see context-aware correction (structural re-parse + gloss overlap) of each
out-of-vocabulary token, with the corrected sentence and a per-token trace. Everything
is deterministic — the same input always yields the same output and trace.
"""
from __future__ import annotations

import sys
from typing import List

from gse.nlp.spellcheck import correct, _DEFAULT_LEXICON
from gse.nlp.spellcheck_context import correct_in_context

_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}


def _strip(tok: str) -> str:
    return tok.strip(".,;:!?\"'()[]").lower()


def _run_word(word: str) -> None:
    r = correct(word)
    if not r.fired:
        print(f"  '{word}' grounds — already a word, no correction.")
        return
    head = r.committed if r.committed else "ABSTAIN (ambiguous)"
    print(f"  '{word}' -> {head}")
    for c in r.ranked[:6]:
        print(f"       {c!r}")


def _run_sentence(text: str, encoder) -> None:
    trace = encoder.encode(text)
    toks = trace.tokens
    grounded_content = [
        t.lemma for t in toks
        if t.pos in _CONTENT_POS and _DEFAULT_LEXICON.grounds(t.lemma)
    ]
    surfaces = [t.token for t in toks]
    corrected: List[str] = list(surfaces)
    any_oov = False
    for i, t in enumerate(toks):
        surf = _strip(t.token)
        if not surf or _DEFAULT_LEXICON.grounds(surf):
            continue
        any_oov = True
        template = " ".join("___" if j == i else s for j, s in enumerate(surfaces))
        context = [w for w in grounded_content if w != t.lemma]
        r = correct_in_context(surf, context, encoder, sentence_template=template)
        head = r.committed if r.committed else "ABSTAIN"
        print(f"  [{surf}] -> {head}   ({r.note})")
        for c in r.ranked[:4]:
            print(f"       {c!r}")
        if r.committed:
            corrected[i] = r.committed
    if not any_oov:
        print("  (every token grounds — nothing to correct)")
    else:
        print(f"\n  corrected: {' '.join(corrected)}")


def main(argv: List[str]) -> None:
    print("GSE deterministic spell-checker. Loading lexicon + encoder...")
    from gse.api import GSEEncoder
    enc = GSEEncoder()
    # warm the vocab + wordnet so the first correction is not laggy
    _DEFAULT_LEXICON.grounds("warmup")

    def handle(line: str) -> None:
        line = line.strip()
        if not line:
            return
        if len(line.split()) == 1:
            _run_word(_strip(line))
        else:
            _run_sentence(line, enc)

    if argv:
        handle(" ".join(argv))
        enc.close()
        return

    print("Type a word or sentence (Ctrl-D / 'quit' to exit).")
    try:
        while True:
            try:
                line = input("\nspell> ")
            except EOFError:
                break
            if line.strip() in ("quit", "exit"):
                break
            handle(line)
    finally:
        enc.close()
        print("\nbye.")


if __name__ == "__main__":
    main(sys.argv[1:])
