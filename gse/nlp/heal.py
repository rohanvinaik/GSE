"""Reusable deterministic healing with source-aligned, byte-preserving ledgers.

Transport-free: MCP and other callers share this operation and policy identity.
All edits use half-open Unicode code-point offsets over the exact decoded input.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from gse.api import GSEEncoder
from gse.curation import personal_dictionary
from gse.nlp.hdc_speller import (
    HDC_COMMIT_COS,
    HDC_OFFER_COS,
    HDC_TIEBREAK_COS,
    HDC_TIEBREAK_MARGIN,
    default_speller,
    score_words,
)
from gse.nlp.spellcheck import _DEFAULT_LEXICON, _PRIOR_UNRANKED, correct, looks_non_lexical
from gse.nlp.spellcheck_context import correct_in_context, recover_rare_tail
from gse.nlp.spellcheck_entity import _DEFAULT_ENTITIES, correct_entity

POLICY = "gse.heal/1"
_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LEXICON_DB = os.path.join(_REPO_ROOT, "data", "lexicon_clean.db")
_enc: GSEEncoder | None = None


def resource_provenance() -> dict:
    """Actual resource snapshots with explicit stale/unattested process caches."""
    from gse.nlp.healing_resources import provenance

    return provenance()


def _encoder() -> GSEEncoder:
    global _enc
    if _enc is None:
        _enc = GSEEncoder(db_path=_LEXICON_DB)
    return _enc


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
        {"word": c.word, "edit_cost": c.edit_cost, "frequency": _freq_label(c.prior), "score": round(c.score, 3)}
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
        {
            "word": c.word,
            "score": round(c.total, 3),
            "edit_frequency": round(c.noisy, 3),
            "structural_defects": c.defects,
            "gloss_overlap": round(c.gloss, 3),
        }
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
        {
            "word": _display_name(c.name, surf),
            "edit_cost": c.edit_cost,
            "pagerank": round(c.pagerank, 3),
            "canon": c.canon,
            "note": "entity-name candidate",
        }
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
    common_words = {
        entry["word"]
        for entry in payload.get("suggestions", [])
        if entry.get("word") and _DEFAULT_LEXICON.prior(entry["word"]) != _PRIOR_UNRANKED
    }
    offers = _entity_offers(ent, surf, n)
    if not offers:
        return False
    payload["suggestions"] = offers + payload.get("suggestions", [])
    corroborated = any(candidate.name == ent.committed and candidate.corroboration > 0 for candidate in ent.ranked)
    word_confirmed = common_words == {ent.committed}
    if ent.committed and (corroborated or word_confirmed):
        disp = _display_name(ent.committed, surf)
        payload["top"] = disp
        payload["ambiguous"] = False
        payload["note"] = (
            f"entity-name correction ({'anchor corroboration' if corroborated else 'unique ranked word-space confirmation'}; {ent.note})"
        )
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
    scored = score_words(surf, candidate_words)  # ranked by keyboard-HDC cosine
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


_WORDS = re.compile(r"[^\W_]+(?:[-_'’][^\W_]+)*", re.UNICODE)
_MARKUP = re.compile(r"```[\s\S]*?```|`[^`\r\n]*`|<[^>]*>|\]\([^\r\n)]*\)")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manifest(text: str) -> list[dict[str, Any]]:
    """Located sentence manifests; punctuation is retained in its source slice."""
    out = []
    for match in re.finditer(r"[^.!?\r\n]+(?:[.!?]+[\"'’”]*|(?=\r?\n|$))", text):
        if match.group().strip():
            out.append({"id": len(out), "span": [match.start(), match.end()], "text": match.group()})
    return out


def apply_edits(text: str, edits: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply exact, disjoint approved spans. Refuse malformed/alignment/overlap.

    Every unaffected slice is copied unchanged. Overlapping requests are both
    refused, so request order cannot pick a winner. Offered/kept records remain.
    """
    records = [
        dict(edit) if isinstance(edit, dict) else {"decision": "refused", "reason": "malformed_edit"} for edit in edits
    ]
    active = []
    for record in records:
        if record.get("decision") != "applied":
            continue
        span = record.get("span")
        if (
            not isinstance(span, (list, tuple))
            or len(span) != 2
            or any(type(value) is not int for value in span)
            or not 0 <= span[0] <= span[1] <= len(text)
            or not isinstance(record.get("replacement"), str)
        ):
            record.update(decision="refused", reason="malformed_edit")
        elif text[span[0] : span[1]] != record.get("original"):
            record.update(decision="refused", reason="unaligned")
        else:
            active.append(record)
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            a, b = left["span"], right["span"]
            if (
                max(a[0], b[0]) < min(a[1], b[1])
                or a[0] < b[0] < a[1]
                or b[0] < a[0] < b[1]
                or (a[0] == b[0] and (a[0] == a[1] or b[0] == b[1]))
            ):
                left.update(decision="refused", reason="overlap")
                right.update(decision="refused", reason="overlap")
    result = text
    for record in sorted(
        (record for record in active if record["decision"] == "applied"),
        key=lambda record: record["span"][0],
        reverse=True,
    ):
        start, end = record["span"]
        result = result[:start] + record["replacement"] + result[end:]
    return {"corrected": result, "ledger": records}


def _map_span(text: str, original: str, span: list[int], segments: list[dict[str, Any]]) -> list[int] | None:
    """Map only a uniquely retained, exact segment; discontinuities are refused."""
    previous_reduced = previous_original = -1
    candidates = []
    for segment in segments:
        try:
            r0, r1 = segment["reduced"]
            o0, o1 = segment["original"]
            if (
                any(type(value) is not int for value in (r0, r1, o0, o1))
                or not 0 <= r0 <= r1 <= len(text)
                or not 0 <= o0 <= o1 <= len(original)
                or r0 < previous_reduced
                or o0 < previous_original
                or text[r0:r1] != original[o0:o1]
            ):
                return None
            previous_reduced, previous_original = r1, o1
            if r0 <= span[0] and span[1] <= r1:
                candidates.append([o0 + span[0] - r0, o0 + span[1] - r0])
        except KeyError, TypeError, ValueError:
            return None
    return candidates[0] if len(candidates) == 1 else None


@dataclass
class _Context:
    text: str
    trace_tokens: list
    content: list[str]
    source_counts: dict[str, int]
    trace_matches: dict[str, list[tuple[int, Any]]]
    error: dict | None


@dataclass
class _Proposal:
    payload: dict
    keep_reason: str | None = None
    leg: str = "policy"
    evidence: list | None = None


def _blank(surface: str, reason: str | None = None) -> _Proposal:
    return _Proposal({"surface": surface, "misspelled": False, "suggestions": []}, reason, evidence=[])


def _prepare_input(text, n, original_text):
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            return None, {
                "state": "refused",
                "reason": "invalid_utf8",
                "policy": POLICY,
                "ledger": [],
                "corrected": None,
            }
    if (
        not isinstance(text, str)
        or type(n) is not int
        or n < 1
        or (original_text is not None and not isinstance(original_text, str))
    ):
        return None, {
            "state": "refused",
            "reason": "malformed_input",
            "policy": POLICY,
            "ledger": [],
            "corrected": None,
        }
    return text, None


def _dictionary_spans(text: str, dictionary: dict, path) -> list:
    spans = []
    if dictionary["state"] != "unread":
        for entry in personal_dictionary.entries(path):
            for spelling in (entry.surface, *entry.aliases):
                for match in re.finditer(r"(?<!\w)" + re.escape(spelling) + r"(?!\w)", text, flags=re.IGNORECASE):
                    spans.append((match.start(), match.end(), entry))
    return spans


def _membership(surface: str, start: int, end: int, dictionary_spans: list, path) -> dict:
    member = personal_dictionary.membership(surface, path)
    for left, right, entry in dictionary_spans:
        if left <= start and end <= right:
            return {"state": "member", "entry": asdict(entry), "phrase_span": [left, right]}
    return member


def _guard_reason(surface: str, start: int, markup: list, dictionary: dict, member: dict) -> str | None:
    if any(left <= start < right for left, right in markup):
        return "markup"
    if member["state"] == "member":
        return "protected_dictionary"
    if dictionary["state"] == "unread":
        return "dictionary_unread"
    if not surface.isascii() or any(character.isdigit() for character in surface):
        return "non_ascii_or_unit_or_digit"
    if any(character in surface for character in "-_’'"):
        return "compound_identifier_or_clitic"
    if len(surface) < 2:
        return "short_surface"
    return None


def _read_context(text: str, spans: list) -> _Context:
    tokens, error = [], None
    if len(spans) > 1:
        try:
            tokens = _encoder().encode(text).tokens
        except Exception as exc:
            error = {"state": "unread", "reason": type(exc).__name__}
    content = [token.lemma for token in tokens if token.pos in _CONTENT_POS and _DEFAULT_LEXICON.grounds(token.lemma)]
    counts: dict[str, int] = {}
    matches: dict[str, list[tuple[int, Any]]] = {}
    for match in spans:
        key = match.group().casefold()
        counts[key] = counts.get(key, 0) + 1
    for index, token in enumerate(tokens):
        matches.setdefault(token.token.casefold(), []).append((index, token))
    return _Context(text, tokens, content, counts, matches, error)


def _aligned_token(surface: str, context: _Context):
    key = surface.casefold()
    matches = context.trace_matches.get(key, [])
    pair = matches.pop(0) if context.source_counts[key] == len(matches) and matches else None
    if pair:
        context.source_counts[key] -= 1
    return pair if pair else (None, None)


def _grounded_proposal(surface: str, index, token, name_like: bool, n: int, context: _Context) -> _Proposal:
    result = _blank(surface, "valid_word")
    if token is None:
        return result
    rarity = _DEFAULT_LEXICON.rarity_evidence(surface)
    if rarity["state"] == "unread":
        result.keep_reason, result.evidence = "rarity_unread", [rarity]
        return result
    if rarity["state"] != "rare_tail":
        return result
    result.evidence = [rarity]
    recovery = recover_rare_tail(context.trace_tokens, index, _encoder())
    if recovery:
        result.payload.update(
            misspelled=True,
            top=recovery,
            ambiguous=False,
            suggestions=[{"word": recovery, "note": "slot-confirmed recovery"}],
        )
        result.keep_reason, result.leg = None, "rare_tail"
    elif name_like:
        entity = correct_entity(surface, context_words=context.content)
        if entity.fired and entity.ranked:
            result.payload.update(suggestions=_entity_offers(entity, surface, n), note="valid name; offers only")
    return result


def _orthogonal_recovery(payload: dict, surface: str, sentence_initial: bool, leg: str) -> str:
    if payload.get("suggestions"):
        return "HDC_tiebreak" if _apply_tiebreak(payload, surface, sentence_initial=sentence_initial) else leg
    _apply_hdc(payload, surface, sentence_initial=sentence_initial)
    return "HDC_recovery" if payload.get("suggestions") else leg


def _unknown_proposal(
    surface: str, start: int, end: int, ordinal: int, name_like: bool, n: int, context: _Context
) -> _Proposal:
    leg = "context" if context.trace_tokens else "word"
    template = context.text[:start] + "___" + context.text[end:]
    payload = (
        _context_payload(surface, template, context.content, n) if context.trace_tokens else _word_payload(surface, n)
    )
    gated = name_like or looks_non_lexical(surface, sentence_initial=(ordinal == 0))
    if gated:
        payload.update(top=None, ambiguous=bool(payload.get("suggestions")))
    if name_like and _apply_entity(payload, surface, context.content, n):
        leg = "entity"
    if not payload.get("top") and not gated:
        leg = _orthogonal_recovery(payload, surface, ordinal == 0, leg)
    evidence = [{"source": leg, "note": payload.get("note"), "suggestions": payload.get("suggestions", [])}]
    return _Proposal(payload, leg=leg, evidence=evidence)


def _proposal(surface: str, start: int, end: int, ordinal: int, n: int, context: _Context) -> _Proposal:
    index, token = _aligned_token(surface, context)
    name_like = surface.istitle() or (token is not None and token.pos == "PROPN")
    if _DEFAULT_LEXICON.grounds(surface):
        return _grounded_proposal(surface, index, token, name_like, n, context)
    if name_like and _DEFAULT_ENTITIES.grounds(surface):
        return _blank(surface, "known_entity")
    return _unknown_proposal(surface, start, end, ordinal, name_like, n, context)


def _located_decision(
    proposal: _Proposal, surface: str, start: int, end: int, member: dict, text: str, original: str, segments
) -> tuple[dict, dict]:
    payload = proposal.payload
    replacement = payload.get("top") if payload.get("misspelled") else None
    if replacement and surface.istitle() and proposal.leg != "entity":
        replacement = replacement[0].upper() + replacement[1:]
    decision = (
        "kept"
        if proposal.keep_reason
        else "applied"
        if replacement
        else "offered"
        if payload.get("suggestions")
        else "kept"
    )
    reason = (
        proposal.keep_reason or payload.get("note") or ("clear_correction" if replacement else "no_grounded_candidate")
    )
    mapped = _map_span(text, original, [start, end], segments) if segments is not None else None
    if decision == "applied" and mapped is None:
        decision, reason = "refused", "unaligned"
        payload["top"] = None
    record = {
        "span": [start, end],
        "original_span": mapped,
        "original": surface,
        "replacement": replacement,
        "leg": proposal.leg,
        "evidence": proposal.evidence,
        "decision": decision,
        "reason": reason,
        "coordinate": "input",
        "dictionary": member,
    }
    payload.update(span=[start, end], decision=decision, reason=reason)
    return record, payload


def _healing_result(
    text: str, original: str, segments, dictionary: dict, context: _Context, tokens: list, ledger: list
) -> dict:
    applied = apply_edits(text, ledger)
    original_edits = [
        {**record, "span": record["original_span"]} for record in applied["ledger"] if record["decision"] == "applied"
    ]
    original_corrected = apply_edits(original, original_edits)["corrected"]
    return {
        "input": text,
        "corrected": applied["corrected"],
        "original_corrected": original_corrected,
        "deterministic": True,
        "state": "partial" if context.error or dictionary["state"] == "unread" else "read",
        "tokens": tokens,
        "ledger": applied["ledger"],
        "policy": POLICY,
        "dictionary": dictionary,
        "original_sha256": _hash(original),
        "input_sha256": _hash(text),
        "measured_sha256": _hash(applied["corrected"]),
        "encoding": "utf-8",
        "source_map": segments,
        "context": context.error or {"state": "read" if context.trace_tokens else "not_applicable"},
        "before_sentences": _manifest(text),
        "after_sentences": _manifest(applied["corrected"]),
    }


def suggest(
    text: str | bytes,
    n: int = 5,
    *,
    original_text: str | None = None,
    source_map: list[dict[str, Any]] | None = None,
    dictionary_path=None,
) -> dict[str, Any]:
    """Shared correction policy: guard, propose, decide, then apply located edits.

    Offsets are half-open Unicode code points in exact UTF-8-decoded input.
    Reduced-to-original maps must be monotone exact retained segments. No token
    reconstruction or guessed mapping can change punctuation, markup, or CRLF.
    """
    text, refusal = _prepare_input(text, n, original_text)
    if refusal is not None:
        return refusal
    original = text if original_text is None else original_text
    segments = (
        [{"reduced": [0, len(text)], "original": [0, len(text)]}]
        if source_map is None and original == text
        else source_map
    )
    dictionary = personal_dictionary.identity(dictionary_path)
    dictionary_spans = _dictionary_spans(text, dictionary, dictionary_path)
    spans = list(_WORDS.finditer(text))
    markup = [match.span() for match in _MARKUP.finditer(text)]
    context = _read_context(text, spans)
    tokens, ledger = [], []
    for ordinal, match in enumerate(spans):
        surface, (start, end) = match.group(), match.span()
        member = _membership(surface, start, end, dictionary_spans, dictionary_path)
        guard = _guard_reason(surface, start, markup, dictionary, member)
        proposal = _blank(surface, guard) if guard else _proposal(surface, start, end, ordinal, n, context)
        record, payload = _located_decision(proposal, surface, start, end, member, text, original, segments)
        ledger.append(record)
        tokens.append(payload)
    return _healing_result(text, original, segments, dictionary, context, tokens, ledger)


def boundaries(text: str, *, apply: bool = False, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Offer ambiguous capital/newline stops; apply only explicit structural witnesses.

    An accepted witness is ``{"position": int, "state": "licensed", "rule":
    "complete_clause_before_independent_clause"}``. It must identify a whitespace
    gap after a word and before a capital. A capital alone never warrants a stop.
    """
    records = []
    witnesses = {item.get("position"): item for item in (evidence or []) if isinstance(item, dict)}
    for match in re.finditer(r"(?<=[a-z])([ \t]+|\r?\n)(?=[A-Z][a-z])", text):
        position = match.start()
        witness = witnesses.get(position)
        licensed = (
            witness is not None
            and witness.get("state") == "licensed"
            and witness.get("rule") == "complete_clause_before_independent_clause"
        )
        records.append(
            {
                "span": [position, position],
                "original": "",
                "replacement": ".",
                "decision": "applied" if apply and licensed else "offered",
                "leg": "boundary",
                "reason": "structural_witness" if licensed else "ambiguous_capital",
                "evidence": [witness] if witness else [],
                "coordinate": "input",
            }
        )
    result = apply_edits(text, records)
    return {
        "input": text,
        **result,
        "policy": POLICY,
        "original_sha256": _hash(text),
        "measured_sha256": _hash(result["corrected"]),
        "before_sentences": _manifest(text),
        "after_sentences": _manifest(result["corrected"]),
    }


def learn(word: str | dict[str, Any], *, path=None) -> dict[str, Any]:
    """The persistent typed learning operation shared by every spelling door."""
    if isinstance(word, str) and word.strip().lower() in _DEFAULT_LEXICON.allowlist:
        return {"ok": True, "code": "already_known", "already_known": True, "word": word.strip().lower()}
    return personal_dictionary.learn(word, path=path)
