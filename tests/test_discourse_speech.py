"""Speech-attribution discourse pass — segmentation + speaker tracking.

Pure-logic tests (no encoder/lexicon): the novel, bug-prone part is splitting a `"…," said X`
construction and carrying the speaker across a multi-sentence speech. bind_deixis (a lemma
swap on the resolved tree) is exercised end-to-end by the bridge; here we pin the parsing."""

import re

from gse.discourse.speech import _attribution, segment_document, segment_speech


def _split(text):
    """Sentence-split as the narrative emit does (period-then-capital/quote)."""
    blob = re.sub(r"\s+", " ", text).strip()
    return [p for p in re.split(r'(?<=[.!?])\s+(?=[A-Z"\'“])', blob) if p.strip()]


# --- single-sentence attribution ------------------------------------------------------------
def test_said_speaker():
    u = segment_speech('"I am tired," said Bob.')
    assert [x.content for x in u] == ["I am tired,"]
    assert u[0].speaker == "bob" and u[0].addressee is None


def test_said_speaker_to_addressee():
    (u,) = segment_speech('"You are late," said Bob to Jim.')
    assert u.speaker == "bob" and u.addressee == "jim"


def test_speaker_said_pronoun():
    (u,) = segment_speech('"Is that you, Bob?" he asked.')
    assert u.speaker == "he"


def test_adjective_stacked_np_head():
    (u,) = segment_speech('"Stop," said the tall man.')
    assert u.speaker == "man"  # not "tall"


def test_pp_modified_np_head():
    (u,) = segment_speech('"Wait," said the man in the doorway.')
    assert u.speaker == "man"  # not "doorway"


def test_determiner_and_adjective_dropped():
    (u,) = segment_speech('"Lost," said the old horse.')
    assert u.speaker == "horse"


def test_plain_narration_has_no_speaker():
    (u,) = segment_speech("The two men started up the street.")
    assert u.speaker is None and u.content == "The two men started up the street."


def test_said_nothing_is_not_attribution():
    # an SVO clause that merely contains a reporting verb is not a quote attribution
    assert _attribution("The policeman said nothing") is None
    assert _attribution("he said so") is None


# --- document-scope speaker tracking --------------------------------------------------------
def test_multisentence_speech_carries_speaker():
    story = '"Twenty years ago," said the man, "I dined here with Jimmy. He and I were raised here. I was eighteen."'
    utts = segment_document(_split(story))
    # every quoted clause of the one speech is attributed to the man, including the interior
    # sentences that carry no attribution of their own.
    spoken = [u for u in utts if u.speaker is not None]
    assert spoken and all(u.speaker == "man" for u in spoken)
    assert any("I was eighteen" in u.content for u in spoken)


def test_turn_taking_no_cross_attribution():
    story = '"Until five years ago," said the policeman. The man struck a match. "I dined here," said the man.'
    by_speaker = {}
    for u in segment_document(_split(story)):
        by_speaker.setdefault(u.speaker, []).append(u.content)
    # the policeman's line is the policeman's; the man's line is the man's; the action is
    # narration (no speaker) — never swallowed into a neighbouring speech.
    assert any("Until five years ago" in c for c in by_speaker.get("policeman", []))
    assert any("I dined here" in c for c in by_speaker.get("man", []))
    assert any("struck a match" in c for c in by_speaker.get(None, []))


def test_plain_narration_sentence_resets_turn():
    # a narration sentence between two speeches must not let the first speaker bleed forward
    story = '"Hello," said Bob. The room was quiet. "Goodbye."'
    utts = segment_document(_split(story))
    last = [u for u in utts if "Goodbye" in u.content][0]
    assert last.speaker is None  # unattributed after a narration reset, not "bob"
