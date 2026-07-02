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
  spell_learn(word) — 'Add to Dictionary' / learn spelling: add a word to the personal
    project dictionary so it is never flagged or corrected again (persists immediately).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from gse.api import GSEEncoder
from gse.nlp.spellcheck import correct, looks_non_lexical, _DEFAULT_LEXICON
from gse.nlp.spellcheck_context import correct_in_context, recover_rare_tail
from gse.nlp.spellcheck_entity import correct_entity, _DEFAULT_ENTITIES
from gse.nlp.hdc_speller import (default_speller, score_words, HDC_COMMIT_COS,
                                 HDC_OFFER_COS, HDC_TIEBREAK_COS, HDC_TIEBREAK_MARGIN)
from gse.nlp.spellcheck import _PRIOR_UNRANKED

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


def _display_name(name: str, surface: str) -> str:
    """Render a committed entity name in the surface's casing (names are single
    tokens by construction of the entity dictionary)."""
    return name[0].upper() + name[1:] if surface[:1].isupper() else name


def _entity_offers(ent, surf: str, n: int) -> List[Dict[str, Any]]:
    return [
        {"word": _display_name(c.name, surf), "edit_cost": c.edit_cost,
         "pagerank": round(c.pagerank, 3), "canon": c.canon,
         "note": "entity-name candidate"}
        for c in ent.ranked[:n]
    ]


def _apply_entity(payload: Dict[str, Any], surf: str, context: List[str], n: int) -> bool:
    """Run the entity leg on a name-like token the word path could not commit.
    Folds the result into ``payload``; returns True when it committed. The leg is
    structural end-to-end (edit model + alias-free name dictionary + pagerank prior
    + anchor corroboration) — no redirect/collated data in the path."""
    ent = correct_entity(surf, context_words=context)
    if not ent.fired:
        return False
    offers = _entity_offers(ent, surf, n)
    if not offers:
        return False
    payload["suggestions"] = offers + payload.get("suggestions", [])
    if ent.committed:
        disp = _display_name(ent.committed, surf)
        payload["top"] = disp
        payload["ambiguous"] = False
        payload["note"] = f"entity-name correction ({ent.note})"
        return True
    payload["ambiguous"] = True
    payload["note"] = "entity-name candidates offered (no decisive winner)"
    return False


def _hdc_recover(surf: str, sentence_initial: bool = False):
    """Keyboard-HDC ORTHOGONAL recovery for a token edit-distance ABSTAINED on (the far,
    length-preserving multi-key-slip residue: 'ecifentky' -> 'evidently'). Returns
    (word, cosine, commit) or None. Gated: input not shape-non-lexical; recovered word must
    ground and not be shape-non-lexical. `commit` is True only above the calibrated COMMIT
    cosine (auto-apply); between OFFER and COMMIT it is offered, not applied."""
    sp = default_speller()
    if sp is None or looks_non_lexical(surf, sentence_initial=sentence_initial):
        return None
    cands = sp.candidates(surf, k=1)
    if not cands:
        return None
    word, cos = cands[0]
    if cos < HDC_OFFER_COS or not _DEFAULT_LEXICON.grounds(word) or looks_non_lexical(word):
        return None
    return (word, cos, cos >= HDC_COMMIT_COS)


def _hdc_tiebreak(surf: str, candidate_words: List[str], sentence_initial: bool = False):
    """AMBIGUOUS-case confirmation: edit-distance found candidates but didn't commit. If
    exactly ONE candidate is a common English word and keyboard-HDC independently ranks it
    #1 among the candidates with a decisive cosine margin, return it to commit; else None.
    Restricted to the edit-distance candidates (never the lexicon) so it can only *confirm*,
    not introduce a word; the single-common-candidate rule preserves minimal-pair abstention
    (`weird`/`wired` -> two common candidates -> stays ambiguous)."""
    sp = default_speller()
    if sp is None or looks_non_lexical(surf, sentence_initial=sentence_initial):
        return None
    commons = [w for w in candidate_words if _DEFAULT_LEXICON.prior(w) != _PRIOR_UNRANKED]
    if len(commons) != 1:
        return None
    gold = commons[0]
    scored = score_words(surf, candidate_words)            # ranked by keyboard-HDC cosine
    if not scored or scored[0][0] != gold:
        return None
    best_c = scored[0][1]
    second_c = scored[1][1] if len(scored) > 1 else 0.0
    if best_c >= HDC_TIEBREAK_COS and (best_c - second_c) >= HDC_TIEBREAK_MARGIN:
        return (gold, best_c)
    return None


def _apply_tiebreak(payload: Dict[str, Any], surf: str, sentence_initial: bool = False) -> bool:
    """If HDC decisively confirms one common candidate for an ambiguous token, commit it.
    Returns True if it fired."""
    cands = [s.get("word") for s in payload.get("suggestions", []) if s.get("word")]
    if len(cands) < 2:
        return False
    rec = _hdc_tiebreak(surf, cands, sentence_initial=sentence_initial)
    if not rec:
        return False
    word = rec[0]
    payload["top"] = word
    payload["ambiguous"] = False
    payload["note"] = "ambiguity resolved by keyboard-HDC confirmation (edit-distance candidate)"
    for s in payload["suggestions"]:
        if s.get("word") == word:
            s["note"] = (s.get("note", "") + "; HDC-confirmed").lstrip("; ")
    return True


def _apply_hdc(payload: Dict[str, Any], surf: str, sentence_initial: bool = False) -> None:
    """If keyboard-HDC recovers an edit-distance-abstained token, fold it into `payload`:
    commit (set top) above the COMMIT cosine, else offer as a low-confidence suggestion."""
    rec = _hdc_recover(surf, sentence_initial=sentence_initial)
    if not rec:
        return
    word, cos, commit = rec
    entry = {"word": word, "score": round(cos, 3), "note": "keyboard-HDC orthogonal recovery"}
    payload["suggestions"] = [entry] + payload.get("suggestions", [])
    if commit:
        payload["top"] = word
        payload["ambiguous"] = False
        payload["note"] = "recovered by keyboard-HDC (edit-distance abstained)"
    else:
        payload["ambiguous"] = True
        payload["note"] = "keyboard-HDC suggestion offered (low confidence; not auto-applied)"


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
        name_like = bool(w) and w.isalpha() and w[:1].isupper()
        if name_like and tok.get("misspelled") and _DEFAULT_ENTITIES.grounds(w):
            tok = {"surface": w, "misspelled": False, "suggestions": [],
                   "note": "known entity name"}
        if w and tok.get("misspelled") and not tok.get("top"):   # edit-distance abstained
            if name_like:                                        # a name: the entity leg's business
                _apply_entity(tok, w, [], n)
            if not tok.get("top"):
                if [s for s in tok.get("suggestions", []) if s.get("word")]:
                    _apply_tiebreak(tok, w, sentence_initial=True)   # candidates exist -> confirm among them
                else:
                    _apply_hdc(tok, w, sentence_initial=True)        # true residue (no candidates) -> lexicon
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
                or surf.lower() in _CLITICS or surf.startswith("'")):
            out_tokens.append({"surface": t.token, "misspelled": False, "suggestions": []})
            continue
        # name-like: the entity leg's business (PROPN tag, or mid-sentence title-case)
        name_like = surf.isalpha() and (t.pos == "PROPN" or (surf.istitle() and i > 0))
        if _DEFAULT_LEXICON.grounds(surf):
            # a valid word: leave it alone — EXCEPT a rare-tail token in a predicate slot
            # it can't fill (cen after a subject pronoun). Slot-gated + common-target only.
            rec = (recover_rare_tail(toks, i, _encoder())
                   if _DEFAULT_LEXICON.is_rare_tail(surf) else None)
            if rec:
                out_tokens.append({"surface": t.token, "misspelled": True, "top": rec,
                                   "ambiguous": False,
                                   "suggestions": [{"word": rec, "note": "slot-confirmed recovery"}],
                                   "note": "rare-tail recovered: common word fills the predicate slot"})
                corrected[i] = rec
                continue
            # a NAME-LIKE token that grounds ONLY via the rare multilingual validity
            # tail ("Bosina"): never touched (it grounds), but entity-space neighbours
            # are OFFERED — offer-only is destruction-free by construction.
            if name_like and _DEFAULT_LEXICON.is_rare_tail(surf):
                ent = correct_entity(surf, context_words=grounded_content)
                if ent.fired and ent.ranked:
                    out_tokens.append({
                        "surface": t.token, "misspelled": False,
                        "suggestions": _entity_offers(ent, surf, n),
                        "note": "grounds only in the rare validity tail; "
                                "entity-name neighbours offered (never auto-applied)"})
                    continue
            out_tokens.append({"surface": t.token, "misspelled": False, "suggestions": []})
            continue
        # a name-like token that IS a known entity name is valid — first-class, not
        # dependent on Wiktionary coverage (never touched, same law as word grounding)
        if name_like and _DEFAULT_ENTITIES.grounds(surf):
            out_tokens.append({"surface": t.token, "misspelled": False, "suggestions": [],
                               "note": "known entity name"})
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
        if name_like and not payload.get("top"):
            # the entity leg: the word path has no business committing on a name, but
            # the NAME space (same edit model + grounding + prior discipline) does.
            # A commit lands in `corrected` via the payload["top"] application below.
            _apply_entity(payload, surf, grounded_content, n)
        if not payload.get("top") and not gated:    # edit-distance abstained -> try keyboard-HDC
            if [s for s in payload.get("suggestions", []) if s.get("word")]:
                _apply_tiebreak(payload, surf, sentence_initial=(i == 0))   # confirm among candidates
            else:
                _apply_hdc(payload, surf, sentence_initial=(i == 0))        # true residue -> lexicon
        out_tokens.append(payload)
        if payload["top"]:
            corrected[i] = payload["top"]
    return {
        "input": text,
        "deterministic": True,
        "tokens": out_tokens,
        "corrected": _join_tokens(corrected),
    }


_ALLOWLIST_PATH = os.path.join(_REPO_ROOT, "gse", "nlp", "data", "project_allowlist.txt")


@mcp.tool()
def spell_learn(word: str) -> Dict[str, Any]:
    """Add a word to the personal dictionary ('Add to Dictionary' / learn spelling) so it
    is never flagged, corrected, or recovered again — the standard spell-checker feature.
    Persists to the committed project allowlist and takes effect immediately.

    Args:
        word: a single alphabetic token to learn (e.g. a name, acronym, or jargon term).

    Returns {ok, word, learned|already_known}.
    """
    w = word.strip().lower()
    if not w.isalpha() or len(w) < 2:
        return {"ok": False, "error": "word must be a single alphabetic token (>=2 chars)"}
    if w in _DEFAULT_LEXICON.allowlist:
        return {"ok": True, "word": w, "already_known": True}
    with open(_ALLOWLIST_PATH, "a", encoding="utf-8") as f:
        f.write(w + "\n")
    _DEFAULT_LEXICON._allowlist = None              # invalidate cache -> reloads on next use
    return {"ok": True, "word": w, "learned": True,
            "dictionary_size": len(_DEFAULT_LEXICON.allowlist)}


def main() -> None:
    """Console entry point (pyproject [project.scripts]) — runs the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
