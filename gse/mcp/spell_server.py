"""SymbolicSpellCheck — an MCP server over GSE's deterministic spell-corrector.

Unlike a statistical checker, every suggestion here is (1) deterministic — same input,
same output, every run; (2) grounded — each candidate is a real word that grounds in
the GSE lexicon / WordNet; and (3) inspectable — each carries its trace (edit cost,
frequency prior, gloss-overlap, structural defects), so a calling model can EXPLAIN a
suggestion, not just emit it. Genuinely-ambiguous cases (``weird`` vs ``wired``) are
surfaced as ranked options rather than a confident-wrong commit — the phone-style
"did you mean" list, with provenance.

Tools:
  spell_suggest(text, n=5) — per out-of-vocabulary token, the top-n ranked suggestions
    (context-aware for sentences: structural re-parse + gloss overlap), plus a
    `corrected` rendering that applies confident picks and leaves ambiguous tokens.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from gse.api import GSEEncoder
from gse.nlp.spellcheck import correct, looks_non_lexical, _DEFAULT_LEXICON
from gse.nlp.spellcheck_context import correct_in_context

# clitics the native tokenizer splits off ("don't" -> "do" "n't"); rejoined for display
_CLITICS = {"n't", "'s", "'re", "'ve", "'ll", "'d", "'m"}


def _join_tokens(tokens: List[str]) -> str:
    out: List[str] = []
    join_next = False
    for tk in tokens:
        if tk in ("-", "–", "—") or "-" == tk:
            if out:
                out[-1] = out[-1] + tk
            else:
                out.append(tk)
            join_next = True                       # hyphen binds both sides: demi-word
            continue
        if join_next and out:
            out[-1] = out[-1] + tk
            join_next = False
            continue
        if out and (tk.lower() in _CLITICS or tk.startswith("'")):
            out[-1] = out[-1] + tk                  # clitic binds left: do n't -> don't
            continue
        out.append(tk)
    return " ".join(out)

mcp = FastMCP("SymbolicSpellCheck")

_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}
# Resolve the lexicon by ABSOLUTE path (repo root from this module), not cwd, so the
# server loads its data regardless of where/how it is launched.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LEXICON_DB = os.path.join(_REPO_ROOT, "data", "lexicon_clean.db")
_enc: GSEEncoder | None = None


def _encoder() -> GSEEncoder:
    global _enc
    if _enc is None:
        _enc = GSEEncoder(db_path=_LEXICON_DB)
    return _enc


def _strip(tok: str) -> str:
    # keep original casing — the shape gate (acronym/proper-noun) needs it; the
    # grounding/edit operations lowercase internally.
    return tok.strip(".,;:!?\"()[]")


def _freq_label(prior: int) -> str:
    from gse.nlp.spellcheck import _PRIOR_FUNCTION, _PRIOR_UNRANKED
    if prior == _PRIOR_FUNCTION:
        return "function-word"
    if prior == _PRIOR_UNRANKED:
        return "rare/unranked"
    return f"rank {prior}"


def _word_payload(surface: str, n: int) -> Dict[str, Any]:
    r = correct(surface)
    sugg = [
        {"word": c.word, "edit_cost": c.edit_cost, "frequency": _freq_label(c.prior),
         "score": round(c.score, 3)}
        for c in r.ranked[:n]
    ]
    return {
        "surface": surface,
        "misspelled": r.fired,
        "top": r.committed,
        "ambiguous": r.fired and r.committed is None and bool(sugg),
        "suggestions": sugg,
        "note": r.note,
    }


def _context_payload(surface: str, template: str, context: List[str], n: int) -> Dict[str, Any]:
    r = correct_in_context(surface, context, _encoder(), sentence_template=template)
    sugg = [
        {"word": c.word, "score": round(c.total, 3), "edit_frequency": round(c.noisy, 3),
         "structural_defects": c.defects, "gloss_overlap": round(c.gloss, 3)}
        for c in r.ranked[:n]
    ]
    return {
        "surface": surface,
        "misspelled": True,
        "top": r.committed,
        "ambiguous": r.committed is None and bool(sugg),
        "suggestions": sugg,
        "note": r.note,
    }


@mcp.tool()
def spell_suggest(text: str, n: int = 5) -> Dict[str, Any]:
    """Deterministically suggest corrections for misspelled words in `text`.

    A single word returns word-level suggestions (noisy-channel: edit distance +
    frequency prior). A sentence returns context-aware suggestions for each
    out-of-vocabulary token (adds structural re-parse + gloss-overlap signals) plus a
    `corrected` rendering. Every suggestion is grounded and carries its score trace;
    ambiguous tokens are surfaced as ranked options (top=null) rather than guessed.

    Args:
        text: a word or sentence to check.
        n: max suggestions per token (default 5).

    Returns a dict with per-token `tokens` (each: surface, misspelled, top, ambiguous,
    suggestions[], note) and a `corrected` sentence with confident picks applied.
    """
    words = text.split()
    if len(words) <= 1:
        w = _strip(text)
        tok = _word_payload(w, n) if w else {"surface": text, "misspelled": False, "suggestions": []}
        corrected = (tok.get("top") or text) if tok.get("misspelled") else text
        return {"input": text, "deterministic": True, "tokens": [tok], "corrected": corrected}

    trace = _encoder().encode(text)
    toks = trace.tokens
    surfaces = [t.token for t in toks]
    grounded_content = [
        t.lemma for t in toks
        if t.pos in _CONTENT_POS and _DEFAULT_LEXICON.grounds(t.lemma)
    ]
    out_tokens: List[Dict[str, Any]] = []
    corrected = list(surfaces)
    for i, t in enumerate(toks):
        surf = _strip(t.token)
        if (not surf or not any(c.isalpha() for c in surf)        # punctuation token
                or surf.lower() in _CLITICS or surf.startswith("'")
                or _DEFAULT_LEXICON.grounds(surf)):
            out_tokens.append({"surface": t.token, "misspelled": False, "suggestions": []})
            continue
        template = " ".join("___" if j == i else s for j, s in enumerate(surfaces))
        context = [w for w in grounded_content if w != t.lemma]
        payload = _context_payload(surf, template, context, n)
        # shape/POS gate: acronym/code/proper-noun -> offer, never auto-apply. Uses the
        # parser's PROPN tag plus shape, with sentence-initial capitals exempted.
        gated = (t.pos == "PROPN") or looks_non_lexical(surf, sentence_initial=(i == 0))
        if gated and payload.get("top"):
            payload["top"] = None
            payload["ambiguous"] = bool(payload["suggestions"])
            payload["note"] = "non-lexical (acronym/code/proper-noun): offered, not committed"
        out_tokens.append(payload)
        if payload["top"]:
            corrected[i] = payload["top"]
    return {
        "input": text,
        "deterministic": True,
        "tokens": out_tokens,
        "corrected": _join_tokens(corrected),
    }


if __name__ == "__main__":
    mcp.run()
