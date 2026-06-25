"""Speech-attribution discourse pass — quoted-``I`` → speaker, quoted-``you`` → addressee.

Why a pre-pass and not an encoder change: handed ``"I am tired," said Bob`` as one clause,
the SVO clause builder mis-casts *Bob* as the patient of *tire* and drops the speech verb —
the speaker is destroyed before any tree exists, so no downstream resolver can recover it.
Splitting the quote from its attribution and encoding ``I am tired`` **in isolation** fixes
both faults at once: the quoted clause parses cleanly (``i is-tired``), and — knowing the
speaker is Bob — its deictic ``i`` is rebound to *bob*, its ``you`` to the addressee.

Coreference is lexical (``grounding._signature`` keys a referent by its head **lemma**), so
rewriting a deictic head's lemma to the speaker's makes the dialogue line corefer with
narration about that same entity, with no change to the resolver. The pass is deterministic
and degrades to plain narration on any construction it does not recognise — never worse than
encoding the raw sentence as today.

Public surface:
  * :func:`segment_speech` — one raw sentence → ordered :class:`Utterance` list.
  * :func:`bind_deixis`   — rewrite a resolved tree's deictic heads to speaker/addressee.
  * :func:`encode_utterances` — the one call an emit loop uses in place of ``enc.encode(s)``:
    segment → encode each clause → bind deixis → list of resolved trees.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import List, Optional

# Speech (attribution) verbs — surface forms; the attribution is recognised by one of these
# sitting next to the speaker NP. Kept deliberately finite (the register's common reporting
# verbs); extend as the corpus demands. A word not here simply isn't read as an attribution.
_SAY_VERBS = frozenset({
    "said", "says", "say", "asked", "asks", "ask", "replied", "replies", "reply",
    "answered", "answers", "answer", "cried", "cries", "cry", "exclaimed", "exclaims",
    "exclaim", "announced", "announces", "announce", "snapped", "snaps", "snap",
    "whispered", "shouted", "murmured", "muttered", "remarked", "continued", "added",
    "returned", "observed", "declared", "gasped", "called", "responded", "began",
})
# First/second-person deictic lemmas the binder rewrites (mirrors grounding._DEICTIC_PERSON).
_FIRST_PERSON = frozenset({"i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves"})
_SECOND_PERSON = frozenset({"you", "your", "yours", "yourself", "yourselves"})
# A PRONOUN attribution ("said he", "she said") is itself anaphoric: binding a quoted "I" to it
# must keep it a PRON so the document recency resolver carries it on to the prior declared proper
# noun (he→jim). Only a NAME attribution ("said Jim") freezes to PROPN.
_THIRD_PERSON_PRON = frozenset({"he", "she", "they", "him", "her", "them", "it",
                               "his", "hers", "their", "its"})
_BE_FORMS = frozenset({"was", "were", "is", "are", "been", "be", "being", "am"})
# Heads that can never be a SPEAKER: indefinites and discourse particles. They guard against
# reading a plain SVO clause that merely contains a reporting verb ("The policeman said
# *nothing*", "he said *so*") as a quote attribution and dropping the narration.
_NON_SPEAKER = frozenset({
    "nothing", "something", "anything", "everything", "nobody", "somebody", "anybody",
    "everybody", "someone", "anyone", "everyone", "none", "so", "it", "this", "that",
    "these", "those", "yes", "no", "all", "what", "which", "there", "here", "much",
})

# Tokens that are never the speaker head: determiners, possessives, adpositions, and the
# attributive adverbs ("reassuringly", "doubtfully") that trail a reporting verb.
_SKIP_BEFORE_HEAD = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "my", "your", "his", "her",
    "its", "our", "their", "to", "at", "in", "on", "of", "for", "with", "old", "young",
})
# A double-quoted span: an opening double quote, non-double-quote content, a closing one.
# Straight " and smart “ ” both open/close; single quotes are left alone (possessives /
# inner quotes like 'Big Joe' are too ambiguous to treat as dialogue delimiters).
_QUOTED_RE = re.compile(r"[“\"]([^“”\"]*)[”\"]")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
# An NP ends at a preposition or conjunction — so the speaker head is the NP's last word
# *before* a PP ("the man in the doorway" → man, not doorway), while an adjective-stacked NP
# still resolves to its noun ("the tall man" → man).
_NP_BOUNDARY = frozenset({
    "to", "in", "on", "at", "of", "with", "by", "for", "from", "into", "about",
    "over", "under", "near", "behind", "beside", "and", "but", "as", "that",
    "because", "when", "while", "who",
})


# Sentinel lemma the narrating first-person voice is tagged with. A PROVENANCE fact (this
# mention came from narration, not a quote), not a semantic-role guess — used downstream only
# as a soft prioritization signal (the narrator is the deictic frame). Narration-I → this;
# quoted-I → its speaker; an UNATTRIBUTED quoted-I is a character, left as "i" (never the narrator).
NARRATOR_TAG = "narrator"


@dataclass(frozen=True)
class Utterance:
    """One clause to encode, with deixis context and its provenance.

    ``content`` is the text to encode in isolation; ``speaker``/``addressee`` are head lemmas
    (lowercased, to corefer with narration) or ``None``. ``quoted`` marks dialogue content vs
    narration — so an unattributed quote (a character) is not mistaken for the narrator.
    """
    content: str
    speaker: Optional[str] = None
    addressee: Optional[str] = None
    quoted: bool = False


def _head_lemma(token: str) -> str:
    """Lowercased surface as a coreference key (narration lemmas are lowercase singulars)."""
    return token.lower()


def _np_head(words: list) -> Optional[str]:
    """Head of the leading noun phrase in ``words``: take up to the first PP/conjunction
    boundary, drop trailing ``-ly`` adverbs and leading determiners/possessives, and return
    the last remaining token. ``the tall man`` → man; ``the man in the doorway`` → man;
    ``[]`` / adverb-only → ``None``."""
    core = []
    for w in words:
        if w == "," or w.lower() in _NP_BOUNDARY:   # a comma ends the speaker NP: "said Madame,
            break                                   # lifting the mass" → Madame, not mass
        core.append(w)
    while core and core[-1].lower().endswith("ly"):   # trailing attributive adverb
        core.pop()
    while core and core[0].lower() in _SKIP_BEFORE_HEAD:
        core.pop(0)
    return core[-1] if core else None


# Common capitalized sentence-openers / interjections that are NOT vocative names.
_VOC_STOP = _NON_SPEAKER | frozenset({
    "oh", "well", "please", "now", "why", "ah", "dear", "sir", "madam", "god", "lord",
    "come", "look", "say", "give", "be", "do", "don", "let", "take", "merry", "good",
})


def _vocative(quoted: str) -> Optional[str]:
    """A capitalized NAME set off by a comma at the start or end of a quoted clause is the
    addressee (a vocative): "Jim, darling," / "Shall I put the chops on, Jim?". Conservative:
    a single capitalized word, comma-adjacent, not a common interjection/sentence-opener — the
    deterministic, text-agnostic half of you→addressee (the other half is explicit "to Y")."""
    for m in (re.match(r"\s*([A-Z][a-z]+)\s*,", quoted),
              re.search(r",\s*([A-Z][a-z]+)\s*[?!.\"”’']*\s*$", quoted)):
        if m and m.group(1).lower() not in _VOC_STOP:
            return _head_lemma(m.group(1))
    return None


def _attribution(fragment: str) -> Optional[tuple]:
    """If ``fragment`` (the non-quoted text around a quote) is a speech attribution, return
    ``(speaker, addressee)`` head lemmas; else ``None``. Handles ``said SPEAKER [to ADDR]``
    and ``SPEAKER said``, with adjective-stacked or PP-modified speaker NPs."""
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*|,", fragment)   # keep commas as NP boundaries
    if not words:
        return None
    low = [w.lower() for w in words]
    say_idx = next((i for i, w in enumerate(low) if w in _SAY_VERBS), None)
    if say_idx is None:
        return None
    # "was/were called X" is naming, not speech — not an attribution.
    if low[say_idx] == "called" and say_idx > 0 and low[say_idx - 1] in _BE_FORMS:
        return None

    after = words[say_idx + 1:]
    speaker = _np_head(after)                          # "said SPEAKER …"
    addressee = None
    if speaker is not None:
        after_low = [w.lower() for w in after]
        if "to" in after_low:                          # "… to ADDRESSEE"
            addressee = _np_head(after[after_low.index("to") + 1:])
    else:
        # "SPEAKER said" — the noun just before the verb (scan back past -ly adverbs/dets).
        for w in reversed(words[:say_idx]):
            wl = w.lower()
            if w == "," or wl in _NP_BOUNDARY:
                break
            if wl in _SKIP_BEFORE_HEAD or wl.endswith("ly"):
                continue
            speaker = w
            break
    if speaker is None or speaker.lower() in _NON_SPEAKER:
        return None
    return (_head_lemma(speaker), _head_lemma(addressee) if addressee else None)


def segment_speech(sentence: str) -> List[Utterance]:
    """Split one raw sentence into ordered utterances. A sentence with no double-quoted span
    is returned as a single narration utterance (the common, no-op case). A quoted span is
    paired with the nearest attribution among the surrounding non-quoted fragments; an
    unrecognised attribution leaves the quote speaker-less (still encoded in isolation,
    which already removes the ``said X`` pollution)."""
    quotes = list(_QUOTED_RE.finditer(sentence))
    if not quotes:
        return [Utterance(sentence)]

    # Non-quoted fragments, in order, are the attribution candidates.
    frags: List[str] = []
    pos = 0
    for m in quotes:
        frags.append(sentence[pos:m.start()])
        pos = m.end()
    frags.append(sentence[pos:])

    # The speaker/addressee for the whole sentence: the first fragment that parses as an
    # attribution (dialogue rarely switches speaker mid-sentence in this register).
    speaker = addressee = None
    for f in frags:
        attr = _attribution(f)
        if attr:
            speaker, addressee = attr
            break

    utts: List[Utterance] = []
    for m in quotes:
        content = m.group(1).strip()
        if content:
            utts.append(Utterance(content, speaker, addressee, quoted=True))
    # Keep any non-quoted fragment that is real narration (not a bare attribution) — so plot
    # carried outside the quotes ("He struck a match and said ...") is not dropped.
    for f in frags:
        if f.strip() and _attribution(f) is None and _WORD_RE.search(f):
            utts.append(Utterance(f.strip(), quoted=False))
    return utts or [Utterance(sentence)]


def _split_segments(sentence: str, inside_start: bool):
    """Split one sentence into ``(text, is_quoted)`` segments by toggling on double-quote
    chars, *continuing* the quote state from the previous sentence. Single quotes/apostrophes
    never toggle (possessives, contractions, inner 'quotes'). Returns (segments, inside_end)."""
    segs, cur, inside = [], [], inside_start
    for ch in sentence:
        if ch in "“”\"":
            segs.append(("".join(cur), inside))
            cur, inside = [], not inside
        else:
            cur.append(ch)
    segs.append(("".join(cur), inside))
    return segs, inside


def segment_document(sentences) -> List[Utterance]:
    """Document-scope speech segmentation — the multi-sentence completion of
    :func:`segment_speech`. A speech in this register spans many sentences inside one pair of
    quotes with ``said X`` stated once; per-sentence segmentation can't reach the interior
    sentences. This carries the open-quote speaker across sentence boundaries: an attribution
    sets the current speaker, which persists for every quoted clause until the quote closes.

    A sentence with no quote (and not inside an open one) is plain narration — never parsed as
    an attribution (so "The policeman said nothing." is not mistaken for `said SPEAKER`)."""
    records: List[dict] = []
    inside = False
    cur_speaker = cur_addr = None     # speaker of the currently-open quote
    span: List[int] = []              # record indices of the current open quote span
    pending = None                    # an attribution awaiting an immediate re-open

    for s_idx, sent in enumerate(sentences):
        has_quote = any(c in "“”\"" for c in sent)
        if not has_quote and not inside:
            if sent.strip():
                records.append({"content": sent.strip(), "speaker": None, "addressee": None, "quoted": False, "s_idx": s_idx})
            cur_speaker = cur_addr = pending = None       # a plain-narration line ends any turn
            continue
        segs, inside_after = _split_segments(sent, inside)
        for text, quoted in segs:
            t = text.strip()
            if quoted:
                if not t:
                    continue
                if not span and pending is not None:      # "Q1," said X, "Q2" / X said, "Q"
                    cur_speaker, cur_addr = pending
                    pending = None
                if cur_addr is None:                       # vocative ("Jim, …" / "…, Jim?") → addressee
                    voc = _vocative(t)
                    if voc and voc != cur_speaker:
                        cur_addr = voc
                        for i in span:                     # apply to the whole open turn
                            records[i]["addressee"] = voc
                records.append({"content": t, "speaker": cur_speaker, "addressee": cur_addr, "quoted": True, "s_idx": s_idx})
                span.append(len(records) - 1)
            else:
                # A narration segment closes the preceding quote: finalize ITS span here (not at
                # sentence end) so a later speaker's attribution can never back-patch an earlier
                # speech — the desync that mis-attributed whole speeches and swallowed narration.
                attr = _attribution(text)
                if attr is not None:
                    spk, addr = attr
                    for i in span:                        # "Q," said X — back-patch only this span
                        records[i]["speaker"] = spk
                        records[i]["addressee"] = addr
                    cur_speaker, cur_addr = spk, addr      # carry to an immediate re-open (pending)
                    pending = (spk, addr)
                elif t:
                    records.append({"content": t, "speaker": None, "addressee": None, "quoted": False, "s_idx": s_idx})
                if span:                                  # quote closed → finalize
                    span = []
                    if attr is None:                      # no fresh attribution → turn is over
                        cur_speaker = cur_addr = pending = None
        inside = inside_after

    # Reassemble an INTERRUPTED quote into one sub-script: a quote split mid-sentence by its
    # attribution ("That," he said, "is a great idea") is one clause — join its fragments (the
    # attribution was consumed as metadata, not content) → "That, is a great idea". Scoped to the
    # SAME sentence (s_idx): a cross-sentence continuation ("Hello." / "Care for wine?") stays
    # separate so each encodes as its own sentence (it already carries the speaker). Unattributed
    # (speaker=None) fragments are never merged — a run of them is a back-and-forth, not one turn.
    merged: List[dict] = []
    for r in records:
        prev = merged[-1] if merged else None
        if (r["quoted"] and r["speaker"] is not None and prev is not None
                and prev["quoted"] and prev["speaker"] == r["speaker"]
                and prev["addressee"] == r["addressee"] and prev["s_idx"] == r["s_idx"]):
            prev["content"] = prev["content"].rstrip() + " " + r["content"].lstrip()
        else:
            merged.append(dict(r))

    return [Utterance(r["content"], r["speaker"], r["addressee"], quoted=r["quoted"]) for r in merged]


def bind_deixis(tree, speaker: Optional[str], addressee: Optional[str]):
    """Rewrite a resolved tree's first-person heads to ``speaker`` and second-person heads to
    ``addressee`` (lemma only — enough to corefer; the I/YOU primitive is kept so the role
    classifier still reads the referent as animate). No-op if both are ``None``."""
    if not speaker and not addressee:
        return tree
    from gse.symbolic.grounding import _map_entities  # internal reuse: same walker resolve_document uses

    def rewrite(ent):
        lemma = (getattr(ent.head, "lemma", "") or "").lower()
        if speaker and lemma in _FIRST_PERSON:
            spos = "PRON" if speaker.lower() in _THIRD_PERSON_PRON else "PROPN"
            return replace(ent, head=replace(ent.head, lemma=speaker, pos=spos))
        if addressee and lemma in _SECOND_PERSON:
            apos = "PRON" if addressee.lower() in _THIRD_PERSON_PRON else "PROPN"
            return replace(ent, head=replace(ent.head, lemma=addressee, pos=apos))
        return ent

    return _map_entities(tree, rewrite)


def mark_narrator(tree):
    """Tag a NARRATION clause's first-person heads (``I``/``we``) as the narrator. Provenance,
    not a role guess: this mention came from narration, so it is the narrating voice — distinct
    from a quoted character's ``I`` (which bind_deixis routes to its speaker). The downstream
    compaction reads the tag only as a soft prioritization signal (the narrator is the frame)."""
    from gse.symbolic.grounding import _map_entities

    def rewrite(ent):
        if (getattr(ent.head, "lemma", "") or "").lower() in _FIRST_PERSON:
            return replace(ent, head=replace(ent.head, lemma=NARRATOR_TAG))
        return ent

    return _map_entities(tree, rewrite)


def _apply_deixis(tree, utt):
    """Quoted+attributed → bind I→speaker, you→addressee. Narration → tag first-person as the
    narrator. Unattributed quote (a character) → left untouched (never the narrator)."""
    if utt.speaker or utt.addressee:
        return bind_deixis(tree, utt.speaker, utt.addressee)
    if not utt.quoted:
        return mark_narrator(tree)
    return tree


def encode_utterances(enc, sentence: str) -> List:
    """Encode one raw sentence into a list of resolved trees, honouring dialogue deixis.

    Drop-in for ``[evaluate_tree(resolve(from_trace(enc.encode(sentence))))]`` in an emit
    loop: ``for s in sentences: trees.extend(encode_utterances(enc, s))``. A quoted clause is
    encoded in isolation (no ``said X`` pollution) and its deictic args rebound to the
    speaker/addressee; plain narration round-trips unchanged."""
    from gse.symbolic import from_trace, resolve, evaluate_tree

    out: List = []
    for utt in segment_speech(sentence):
        if not utt.content.strip():
            continue
        try:
            tree = evaluate_tree(resolve(from_trace(enc.encode(utt.content))))
        except Exception:
            continue
        out.append(_apply_deixis(tree, utt))
    return out


def encode_document_utterances_traced(enc, sentences) -> List:
    """Trace-RETAINING document-scope encode: like :func:`encode_document_utterances` but yields
    ``(trace, tree, utterance)`` triples instead of trees alone.

    The statement healer's metadata envelope (``gse.symbolic.healer.build_envelope``) must be laid
    down at parse/intake time, where the ``OperationTrace`` still exists — downstream of the
    document collapse it is gone. Plain :func:`encode_document_utterances` drops the trace; a healing
    caller uses this sibling to keep it, build the envelope per utterance, and carry it to the
    ``narrative.from_document(repair=)`` seam. The ``tree``/``utterance`` are byte-identical to what
    the plain twin produces — same ``segment_document`` loop, same deixis."""
    from gse.symbolic import from_trace, resolve, evaluate_tree

    out: List = []
    for utt in segment_document(sentences):
        if not utt.content.strip():
            continue
        try:
            trace = enc.encode(utt.content)
            tree = evaluate_tree(resolve(from_trace(trace)))
        except Exception:
            continue
        out.append((trace, _apply_deixis(tree, utt), utt))
    return out


def encode_document_utterances(enc, sentences) -> List:
    """Document-scope twin of :func:`encode_utterances` — the call an emit loop uses over the
    WHOLE ordered sentence list (``trees = encode_document_utterances(enc, sentences)``).
    Speaker attribution is carried across multi-sentence speeches (:func:`segment_document`),
    so an interior dialogue sentence's ``I``/``you`` still rebinds to the speaker/addressee.

    Trees only; delegates to :func:`encode_document_utterances_traced` (single loop) and discards
    the traces. A healing caller wanting the per-utterance trace calls the traced sibling directly."""
    return [tree for _trace, tree, _utt in encode_document_utterances_traced(enc, sentences)]
