"""Frozen specification for GSE #88, revision 4."""

import importlib.util
import itertools
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from gse.api import GSEEncoder
from gse.nlp.native import NativeNLP

DEGREE_WORDS = (
    "very",
    "quite",
    "rather",
    "too",
    "always",
    "never",
    "often",
    "usually",
    "almost",
    "nearly",
    "somewhat",
    "also",
)
SKIP_WORDS = DEGREE_WORDS + ("really", "sometimes")
CONTRACTED_BASES = (
    "it",
    "he",
    "she",
    "that",
    "this",
    "there",
    "here",
    "what",
    "who",
    "where",
    "how",
)
BOOL_PAIRS = tuple(itertools.product((False, True), repeat=2))
BOOL_TRIPLES = tuple(itertools.product((False, True), repeat=3))

READING_ROWS = (
    ((False, False, False, False), "NO_READING"),
    ((False, False, False, True), "NOUN"),
    ((False, False, True, False), "ADJ"),
    ((False, False, True, True), "ADJ"),
    ((False, True, False, False), "MODIFIER"),
    ((False, True, False, True), "MODIFIER"),
    ((False, True, True, False), "MODIFIER"),
    ((False, True, True, True), "MODIFIER"),
    ((True, False, False, False), "PARTICIPLE"),
    ((True, False, False, True), "PARTICIPLE"),
    ((True, False, True, False), "PARTICIPLE"),
    ((True, False, True, True), "PARTICIPLE"),
    ((True, True, False, False), "MODIFIER"),
    ((True, True, False, True), "MODIFIER"),
    ((True, True, True, False), "MODIFIER"),
    ((True, True, True, True), "MODIFIER"),
)

LEFT_ROWS = (
    ((), False),
    (("OTHER",), False),
    (("SKIP",), False),
    (("BE",), True),
    (("CONTRACTED_BE",), True),
    (("BE", "SKIP"), True),
    (("BE", "SKIP", "SKIP"), True),
    (("BE", "SKIP", "SKIP", "SKIP"), True),
    (("CONTRACTED_BE", "SKIP", "SKIP", "SKIP"), True),
    (("OTHER", "BE"), True),
    (("OTHER", "SKIP"), False),
    (("BE", "OTHER"), False),
    (("BE", "OTHER", "SKIP"), False),
    (("BE", "unknown-role", "SKIP"), False),
    (("BE", 0, "SKIP"), False),
    (("BE", None, "SKIP"), False),
    (("BE", [], "SKIP"), False),
    (("BE", {}, "SKIP"), False),
    (("BE", ["BE"], "SKIP"), False),
    (("BE", {"role": "BE"}, "SKIP"), False),
    (("BE", "SKIP", "OTHER", "SKIP"), False),
    (("BE",) + ("SKIP",) * 257, True),
    (("CONTRACTED_BE",) + ("SKIP",) * 257, True),
    (("OTHER",) + ("SKIP",) * 257, False),
    (("SKIP",) * 257, False),
    (("be", "skip"), False),
    (("BE", "skip"), False),
    (("be", "SKIP"), False),
)

ROLE_PATTERNS = (
    (
        "plain",
        "",
        ("OTHER", "SKIP", "BE", "BE", "OTHER", "SKIP", "BE", "BE"),
    ),
    (
        "oddly",
        "",
        ("SKIP", "SKIP", "BE", "BE", "OTHER", "SKIP", "BE", "BE"),
    ),
    (
        "very",
        "",
        ("SKIP", "SKIP", "BE", "BE", "SKIP", "SKIP", "BE", "BE"),
    ),
    (
        "'s",
        "it",
        (
            "CONTRACTED_BE",
            "CONTRACTED_BE",
            "BE",
            "BE",
            "CONTRACTED_BE",
            "CONTRACTED_BE",
            "BE",
            "BE",
        ),
    ),
)

PARTICIPLE_ROWS = (
    ("served", "serve", "PARTICIPLE"),
    ("killed", "kill", "PARTICIPLE"),
    ("gone", "go", "PARTICIPLE"),
    ("seen", "see", "PARTICIPLE"),
    ("cooks", "cook", "NOT_PARTICIPLE"),
    ("red", "read", "NOT_PARTICIPLE"),
    ("indeed", "inde", "NOT_PARTICIPLE"),
    ("sing", "sing", "NOT_PARTICIPLE"),
    ("hit", "hit", "NOT_PARTICIPLE"),
    ("fooed", "fooed", "NOT_PARTICIPLE"),
    ("", "", "NOT_PARTICIPLE"),
    ("served", "", "NOT_PARTICIPLE"),
    (" served", " served", "NOT_PARTICIPLE"),
)


def test_table_left_role_truths():
    from gse.nlp.native import copula_left_role

    for word, previous, answers in ROLE_PATTERNS:
        for facts, wanted in zip(BOOL_TRIPLES, answers):
            assert copula_left_role(word, previous, *facts) == wanted

    for word in SKIP_WORDS:
        for has_a in (False, True):
            assert copula_left_role(word, "is", has_a, False, False) == "SKIP"
            assert copula_left_role(word.upper(), "IS", has_a, False, False) == "SKIP"

    for base in CONTRACTED_BASES:
        for has_a in (False, True):
            assert copula_left_role("'s", base, has_a, False, False) == "CONTRACTED_BE"
            assert copula_left_role("'S", base.upper(), has_a, False, False) == "CONTRACTED_BE"

    for base in ("someone", "Duncan", "", "unknown", "it "):
        for has_a in (False, True):
            assert copula_left_role("'s", base, has_a, False, False) == "OTHER"

    boundary_rows = (
        ("ugly", True, "OTHER"),
        ("daily", True, "OTHER"),
        ("oddly", False, "SKIP"),
        ("only", False, "OTHER"),
        ("only", True, "OTHER"),
        ("here", False, "OTHER"),
        ("there", False, "OTHER"),
        ("today", False, "OTHER"),
        ("indeed", False, "OTHER"),
        ("", False, "OTHER"),
        ("!", False, "OTHER"),
        (" really", False, "SKIP"),
        ("really ", False, "OTHER"),
    )
    for word, has_a, wanted in boundary_rows:
        assert copula_left_role(word, "", has_a, False, False) == wanted

    for word in ("am", "is", "are", "was", "were", "be", "been", "being"):
        assert copula_left_role(word, "", False, True, False) == "BE"
    for word in ("not", "n't", "unknown"):
        assert copula_left_role(word, "", False, False, True) == "SKIP"


def test_table_participle_truths():
    from gse.nlp.native import copula_participle_kind

    for word, lemma, qualifying_code in PARTICIPLE_ROWS:
        for has_v, closed_nonverb in BOOL_PAIRS:
            wanted = qualifying_code if has_v and not closed_nonverb else "NOT_PARTICIPLE"
            assert copula_participle_kind(word, lemma, has_v, closed_nonverb) == wanted
            assert copula_participle_kind(word.upper(), lemma.upper(), has_v, closed_nonverb) == wanted


def test_table_modifier_truths():
    from gse.nlp.native import copula_modifier_context

    ordinary_rows = (
        (False, False, "NOT_MODIFIER"),
        (False, True, "MODIFIER"),
        (True, False, "NOT_MODIFIER"),
        (True, True, "NOT_MODIFIER"),
    )
    for has_a, has_r, ordinary_code in ordinary_rows:
        for word in ("good", "daily", "DAILY", ""):
            for next_kind in (
                "PARTICIPLE",
                "NOT_PARTICIPLE",
                "",
                "unknown",
                "participle",
                "Participle",
                [],
                {},
            ):
                wanted = "NOT_MODIFIER"
                if isinstance(next_kind, str) and next_kind == "PARTICIPLE":
                    wanted = "MODIFIER" if word in ("daily", "DAILY") else ordinary_code
                assert copula_modifier_context(word, has_a, has_r, next_kind) == wanted


def test_table_complement_truths():
    from gse.nlp.native import copula_complement_reading

    for left, eligible in LEFT_ROWS:
        for facts, eligible_code in READING_ROWS:
            roles = list(left)
            original = list(roles)
            wanted = eligible_code if eligible else "NOT_COMPLEMENT"
            assert copula_complement_reading(roles, *facts) == wanted
            assert roles == original

    for nonlist in ("BE", "", False, True, 0, 1):
        for facts, unused_code in READING_ROWS:
            assert copula_complement_reading(nonlist, *facts) == "NOT_COMPLEMENT"


def test_table_degree_truths():
    from gse.nlp.native import copula_degree_reading

    for word in DEGREE_WORDS:
        assert copula_degree_reading(word, False) == "DEGREE_ADV"
        assert copula_degree_reading(word, True) == "DEFER"
        assert copula_degree_reading(word.upper(), False) == "DEGREE_ADV"
        assert copula_degree_reading(word.upper(), True) == "DEFER"

    for word in (
        "really",
        "sometimes",
        "here",
        "pretty",
        "so",
        "",
        "very ",
    ):
        for previous_nominal in (False, True):
            assert copula_degree_reading(word, previous_nominal) == "DEFER"


def test_table_lexical_and_code_boundaries():
    from gse.nlp.native import (
        copula_complement_reading,
        copula_degree_reading,
        copula_left_role,
        copula_modifier_context,
        copula_participle_kind,
    )

    for nonstring in (False, True, 0, 1, [], ["is"]):
        assert copula_left_role(nonstring, "", False, False, False) == "OTHER"
        assert copula_left_role("'s", nonstring, False, False, False) == "OTHER"
        assert copula_degree_reading(nonstring, False) == "DEFER"
        assert copula_participle_kind(nonstring, "", False, False) == "NOT_PARTICIPLE"
        assert copula_participle_kind("served", nonstring, True, False) == "NOT_PARTICIPLE"
        assert copula_modifier_context("daily", False, True, nonstring) == "NOT_MODIFIER"

    assert copula_left_role("IS", "", False, True, False) == "BE"
    assert copula_participle_kind("SERVED", "SERVE", True, False) == "PARTICIPLE"
    assert copula_modifier_context("DAILY", True, True, "PARTICIPLE") == "MODIFIER"
    assert copula_modifier_context("DAILY", True, True, "participle") == "NOT_MODIFIER"
    assert copula_complement_reading(["be", "skip"], False, False, True, True) == "NOT_COMPLEMENT"
    assert copula_complement_reading(["BE", "SKIP"], False, False, True, True) == "ADJ"

    assert copula_left_role("plain", "", 0, 1, 0) == "BE"
    assert copula_participle_kind("served", "serve", 1, 0) == "PARTICIPLE"
    assert copula_modifier_context("good", 0, 1, "PARTICIPLE") == "MODIFIER"
    assert copula_complement_reading(["BE"], 0, 0, 1, 1) == "ADJ"
    assert copula_degree_reading("very", 0) == "DEGREE_ADV"
    assert copula_degree_reading("very", 1) == "DEFER"


@pytest.mark.parametrize(
    "sentence, surface, next_kind, modifier_code, reading_code, wanted_pos",
    (
        (
            "He is evil indeed.",
            "evil",
            "NOT_PARTICIPLE",
            "NOT_MODIFIER",
            "ADJ",
            "ADJ",
        ),
        (
            "It is red.",
            "red",
            "NOT_PARTICIPLE",
            "NOT_MODIFIER",
            "ADJ",
            "ADJ",
        ),
        (
            "The food is good served cold.",
            "good",
            "PARTICIPLE",
            "NOT_MODIFIER",
            "ADJ",
            "ADJ",
        ),
        (
            "The reports are daily inspected.",
            "daily",
            "PARTICIPLE",
            "MODIFIER",
            "MODIFIER",
            "ADV",
        ),
    ),
)
def test_table_participle_caller(sentence, surface, next_kind, modifier_code, reading_code, wanted_pos):
    import gse.nlp.native as native
    from gse.nlp.native import (
        copula_complement_reading,
        copula_modifier_context,
        copula_participle_kind,
    )

    # Hand-worked rows, then their production-caller replay.
    assert copula_participle_kind("red", "read", True, False) == "NOT_PARTICIPLE"
    assert copula_participle_kind("indeed", "inde", True, True) == "NOT_PARTICIPLE"
    assert copula_participle_kind("served", "serve", True, False) == "PARTICIPLE"
    assert copula_modifier_context("good", True, True, "PARTICIPLE") == "NOT_MODIFIER"
    assert copula_modifier_context("daily", True, True, "PARTICIPLE") == "MODIFIER"

    with (
        patch.object(
            native,
            "copula_participle_kind",
            wraps=copula_participle_kind,
        ) as part_spy,
        patch.object(
            native,
            "copula_modifier_context",
            wraps=copula_modifier_context,
        ) as modifier_spy,
        patch.object(
            native,
            "copula_complement_reading",
            wraps=copula_complement_reading,
        ) as reading_spy,
    ):
        tokens = {token.text: token.pos_ for token in NativeNLP()(sentence)}

    assert tokens.get(surface) == wanted_pos
    assert len(modifier_spy.call_args_list) == len(reading_spy.call_args_list)

    target_rows = []
    for modifier_call, reading_call in zip(modifier_spy.call_args_list, reading_spy.call_args_list):
        word, has_a, has_r, observed_next = modifier_call.args
        if word == surface:
            target_rows.append((modifier_call.args, reading_call.args))
            assert observed_next == next_kind
            assert copula_modifier_context(word, has_a, has_r, observed_next) == modifier_code
            roles, participle, modifier, actual_a, actual_n = reading_call.args
            assert participle is False
            assert modifier is (modifier_code == "MODIFIER")
            assert actual_a == has_a
            assert copula_complement_reading(roles, participle, modifier, actual_a, actual_n) == reading_code
    assert target_rows

    current_part_rows = []
    for observed_call in part_spy.call_args_list:
        word, lemma, has_v, closed_nonverb = observed_call.args
        if word == surface:
            current_part_rows.append(observed_call.args)
            assert copula_participle_kind(word, lemma, has_v, closed_nonverb) == "NOT_PARTICIPLE"
    assert current_part_rows

    if sentence == "He is evil indeed.":
        indeed_rows = []
        for observed_call in part_spy.call_args_list:
            word, lemma, has_v, closed_nonverb = observed_call.args
            if word == "indeed":
                indeed_rows.append(observed_call.args)
                assert copula_participle_kind(word, lemma, has_v, closed_nonverb) == "NOT_PARTICIPLE"
        assert indeed_rows

    if sentence == "The food is good served cold.":
        encoder = GSEEncoder()
        try:
            encoded = {
                token.token: {
                    "pos": token.pos,
                    "roles": tuple(token.sent_primitives),
                }
                for token in encoder.encode(sentence).tokens
            }
            good = encoded.get("good", {})
            assert good.get("pos") == "ADJ"
            assert "SYN_COMPL" in good.get("roles", ())
            assert "SYN_ADV_MOD" not in good.get("roles", ())
        finally:
            encoder.close()


@pytest.mark.parametrize("word", SKIP_WORDS)
def test_table_skip_caller(word):
    import gse.nlp.native as native
    from gse.nlp.native import (
        copula_complement_reading,
        copula_left_role,
    )

    assert copula_left_role(word, "is", False, False, False) == "SKIP"
    assert copula_left_role(word, "is", True, False, False) == "SKIP"
    assert copula_complement_reading(["BE", "SKIP"], False, False, True, True) == "ADJ"

    with (
        patch.object(native, "copula_left_role", wraps=copula_left_role) as role_spy,
        patch.object(
            native,
            "copula_complement_reading",
            wraps=copula_complement_reading,
        ) as reading_spy,
    ):
        tokens = {token.text: token.pos_ for token in NativeNLP()(f"He is {word} evil.")}

    assert tokens.get("evil") == "ADJ"
    word_rows = []
    for observed_call in role_spy.call_args_list:
        observed_word, previous, has_a, is_be, is_neg = observed_call.args
        if observed_word == word:
            word_rows.append(observed_call.args)
            assert copula_left_role(observed_word, previous, has_a, is_be, is_neg) == "SKIP"
    assert word_rows

    eligible_rows = []
    for observed_call in reading_spy.call_args_list:
        roles, participle, modifier, has_a, has_n = observed_call.args
        if roles == ["BE", "SKIP"]:
            eligible_rows.append(observed_call.args)
            assert copula_complement_reading(roles, participle, modifier, has_a, has_n) == "ADJ"
    assert eligible_rows


@pytest.mark.parametrize("base", CONTRACTED_BASES)
def test_table_contraction_caller(base):
    import gse.nlp.native as native
    from gse.nlp.native import (
        copula_complement_reading,
        copula_left_role,
    )

    assert copula_left_role("'s", base, False, False, False) == "CONTRACTED_BE"
    assert copula_complement_reading(["CONTRACTED_BE"], False, False, True, True) == "ADJ"

    with (
        patch.object(native, "copula_left_role", wraps=copula_left_role) as role_spy,
        patch.object(
            native,
            "copula_complement_reading",
            wraps=copula_complement_reading,
        ) as reading_spy,
    ):
        tokens = {token.text: token.pos_ for token in NativeNLP()(f"{base.capitalize()}'s evil.")}

    assert tokens.get("evil") == "ADJ"
    contraction_rows = []
    for observed_call in role_spy.call_args_list:
        word, previous, has_a, is_be, is_neg = observed_call.args
        if word == "'s" and previous == base:
            contraction_rows.append(observed_call.args)
            assert copula_left_role(word, previous, has_a, is_be, is_neg) == "CONTRACTED_BE"
    assert contraction_rows

    eligible_rows = []
    for observed_call in reading_spy.call_args_list:
        roles, participle, modifier, has_a, has_n = observed_call.args
        if roles == ["CONTRACTED_BE"]:
            eligible_rows.append(observed_call.args)
            assert copula_complement_reading(roles, participle, modifier, has_a, has_n) == "ADJ"
    assert eligible_rows


@pytest.mark.parametrize(
    "skip_words",
    (
        ("not", "really", "very"),
        ("really",) * 257,
    ),
)
def test_table_walk_caller(skip_words):
    import gse.nlp.native as native
    from gse.nlp.native import copula_complement_reading

    expected_roles = ["BE"] + ["SKIP"] * len(skip_words)
    assert copula_complement_reading(expected_roles, False, False, True, True) == "ADJ"

    sentence = "It is " + " ".join(skip_words) + " good."
    with patch.object(
        native,
        "copula_complement_reading",
        wraps=copula_complement_reading,
    ) as reading_spy:
        tokens = {token.text: token.pos_ for token in NativeNLP()(sentence)}

    assert tokens.get("good") == "ADJ"
    complete_rows = []
    for observed_call in reading_spy.call_args_list:
        roles, participle, modifier, has_a, has_n = observed_call.args
        if roles == expected_roles:
            complete_rows.append(observed_call.args)
            assert copula_complement_reading(roles, participle, modifier, has_a, has_n) == "ADJ"
    assert complete_rows


def test_table_barrier_caller():
    import gse.nlp.native as native
    from gse.nlp.native import (
        copula_complement_reading,
        copula_left_role,
    )

    assert copula_left_role("here", "is", False, False, False) == "OTHER"
    assert copula_complement_reading(["OTHER"], False, False, True, True) == "NOT_COMPLEMENT"

    # evil reaches the walk; today could return earlier as a closed adverb.
    with (
        patch.object(native, "copula_left_role", wraps=copula_left_role) as role_spy,
        patch.object(
            native,
            "copula_complement_reading",
            wraps=copula_complement_reading,
        ) as reading_spy,
    ):
        tokens = {token.text: token.pos_ for token in NativeNLP()("He is here evil.")}

    assert tokens.get("evil") is not None
    barrier_rows = []
    for observed_call in role_spy.call_args_list:
        word, previous, has_a, is_be, is_neg = observed_call.args
        if word == "here":
            barrier_rows.append(observed_call.args)
            assert copula_left_role(word, previous, has_a, is_be, is_neg) == "OTHER"
    assert barrier_rows

    assert reading_spy.call_args_list
    for observed_call in reading_spy.call_args_list:
        roles, participle, modifier, has_a, has_n = observed_call.args
        assert roles == ["OTHER"]
        assert copula_complement_reading(roles, participle, modifier, has_a, has_n) == "NOT_COMPLEMENT"


def test_table_modifier_deferral_caller():
    import gse.nlp.native as native
    from gse.nlp.native import (
        copula_complement_reading,
        copula_modifier_context,
        copula_participle_kind,
    )

    assert copula_participle_kind("zorb", "", False, False) == "NOT_PARTICIPLE"
    assert copula_participle_kind("served", "serve", True, False) == "PARTICIPLE"
    assert copula_modifier_context("zorb", False, True, "PARTICIPLE") == "MODIFIER"
    assert copula_complement_reading(["BE"], False, True, False, True) == "MODIFIER"

    nlp = NativeNLP()
    present = (object(),)
    # Current v,n,a,s,r; next v,n,a,s,r; left a,s.
    synset_results = (
        (),
        present,
        (),
        (),
        present,
        present,
        (),
        (),
        (),
        (),
        (),
        (),
    )
    with (
        patch.object(native.wn, "synsets", side_effect=synset_results) as synset_spy,
        patch.object(native.wn, "morphy", side_effect=(None, "serve")) as lemma_spy,
        patch.object(native, "resolve_degree", return_value=None),
        patch.object(
            native,
            "copula_complement_reading",
            wraps=copula_complement_reading,
        ) as reading_spy,
    ):
        # Production caller, with controlled lexical facts for the deferred row.
        actual = nlp._pos("zorb", 1, ["is", "zorb", "served"])

    assert actual == "ADV"
    assert synset_spy.call_count == 12
    assert lemma_spy.call_count == 2
    assert reading_spy.call_count == 1
    assert reading_spy.call_args.args == (
        ["BE"],
        False,
        True,
        False,
        True,
    )


def test_table_determined_very_caller():
    import gse.nlp.native as native
    from gse.nlp.native import (
        copula_complement_reading,
        copula_degree_reading,
    )

    assert copula_degree_reading("very", True) == "DEFER"
    assert copula_complement_reading(["OTHER"], False, False, True, True) == "NOT_COMPLEMENT"

    nlp = NativeNLP()

    # Exact executable remainder of the supplied HEAD _pos for this spelling.
    # No claim is made that its resulting POS was separately measured at HEAD.
    low = "very"
    lemma = native.wn.morphy(low, "v") or ""
    has_v = bool(native.wn.synsets(low, pos="v") or lemma)
    has_n = bool(native.wn.synsets(low, pos="n"))
    has_a = bool(native.wn.synsets(low, pos="a") or native.wn.synsets(low, pos="s"))
    person_is_noun = bool("person" not in native._STOP and native.wn.synsets("person", pos="n"))

    if lemma and lemma != low and not low.endswith("s") and not has_n:
        legacy_expected = "VERB"
    elif low in native._IRREGULAR_PAST_VERB:
        legacy_expected = "VERB"
    elif native.resolve_degree(low) is not None:
        legacy_expected = "ADJ"
    elif has_a and person_is_noun:
        legacy_expected = "ADJ"
    elif has_n:
        legacy_expected = "NOUN"
    elif has_v:
        legacy_expected = "VERB"
    elif has_a:
        legacy_expected = "ADJ"
    else:
        legacy_expected = "NOUN"

    with (
        patch.object(
            native,
            "copula_degree_reading",
            wraps=copula_degree_reading,
        ) as degree_spy,
        patch.object(
            native,
            "copula_complement_reading",
            wraps=copula_complement_reading,
        ) as reading_spy,
        patch.object(
            native,
            "copula_modifier_context",
            wraps=native.copula_modifier_context,
        ) as modifier_spy,
    ):
        tokens = {token.text: token.pos_ for token in nlp("He is the very person we need.")}

    assert tokens.get("very") == legacy_expected

    degree_rows = []
    for observed_call in degree_spy.call_args_list:
        word, previous_nominal = observed_call.args
        if word == "very":
            degree_rows.append(observed_call.args)
            assert previous_nominal is True
            assert copula_degree_reading(word, previous_nominal) == "DEFER"
    assert degree_rows

    assert len(modifier_spy.call_args_list) == len(reading_spy.call_args_list)
    very_rows = []
    for modifier_call, reading_call in zip(modifier_spy.call_args_list, reading_spy.call_args_list):
        word, actual_a, actual_r, next_kind = modifier_call.args
        if word == "very":
            very_rows.append(reading_call.args)
            roles, participle, modifier, reading_a, reading_n = reading_call.args
            assert roles == ["OTHER"]
            assert copula_complement_reading(roles, participle, modifier, reading_a, reading_n) == "NOT_COMPLEMENT"
    assert very_rows


@pytest.mark.parametrize(
    "sentence, surface",
    (
        ("It is necessary to do this.", "necessary"),
        ("He is evil.", "evil"),
        ("Cawdor begins being dead.", "dead"),
        ("Lady Macbeth is evil.", "evil"),
        ("Lady Macbeth is evil and greedy.", "evil"),
        ("The rules are simple.", "simple"),
        ("The food was not good.", "good"),
        ("That's good.", "good"),
        ("It's not good.", "good"),
        ("It is ugly.", "ugly"),
        ("It is sometimes good.", "good"),
    ),
)
def test_flip_predicate_adjective_pos(sentence, surface):
    tokens = {token.text: token.pos_ for token in NativeNLP()(sentence)}
    assert tokens.get(surface) == "ADJ"


@pytest.mark.parametrize(
    "sentence, surface",
    (
        ("The food was not good.", "good"),
        ("That's good.", "good"),
        ("It's not good.", "good"),
        ("It is ugly.", "ugly"),
    ),
)
def test_flip_encoder_adjective_and_complement(sentence, surface):
    encoder = GSEEncoder()
    try:
        tokens = {
            token.token: {
                "pos": token.pos,
                "roles": tuple(token.sent_primitives),
            }
            for token in encoder.encode(sentence).tokens
        }
        token = tokens.get(surface, {})
        assert token.get("pos") == "ADJ"
        assert "SYN_COMPL" in token.get("roles", ())
        assert "SYN_ADV_MOD" not in token.get("roles", ())
    finally:
        encoder.close()


@pytest.mark.parametrize("sentence", ("The food was not good.", "It's not good."))
def test_flip_negated_assertion_survives(sentence):
    encoder = GSEEncoder()
    try:
        tokens = {token.token: token.pos for token in encoder.encode(sentence).tokens}
        assert tokens.get("good") == "ADJ"

        probe_path = Path(__file__).with_name("test_reading_probes_ring2.py")
        module_name = "_gse88_existing_ring2_probe"
        probe_spec = importlib.util.spec_from_file_location(module_name, probe_path)
        assert probe_spec is not None
        assert probe_spec.loader is not None
        probe_module = importlib.util.module_from_spec(probe_spec)
        previous_module = sys.modules.get(module_name)
        sys.modules[module_name] = probe_module
        try:
            probe_spec.loader.exec_module(probe_module)
            projector = getattr(probe_module, "_negated", None)
            assert callable(projector)
            assert projector(encoder, sentence) == [("TYPE_ASSERT", None)]
        finally:
            if previous_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous_module
    finally:
        encoder.close()


@pytest.mark.parametrize(
    "sentence, surface, wanted",
    (
        ("He is greedy.", "greedy", "ADJ"),
        ("Lady Macbeth is greedy.", "greedy", "ADJ"),
        ("Lady Macbeth is evil and greedy.", "greedy", "ADJ"),
        ("He is a cook.", "cook", "NOUN"),
        ("He is president.", "president", "NOUN"),
        ("They are friends.", "friends", "NOUN"),
        ("They are cooks.", "cooks", "NOUN"),
        ("Someone's cold was severe.", "cold", "NOUN"),
        ("Duncan's guards became drunk.", "guards", "NOUN"),
        ("It is ugly today.", "today", "ADV"),
        ("The reports are daily inspected.", "daily", "ADV"),
        ("He's gone.", "gone", "VERB"),
        ("He was killed by Macbeth.", "killed", "VERB"),
        ("He has never seen it.", "seen", "VERB"),
        ("It is really good.", "really", "ADV"),
        ("He is here today.", "today", "ADV"),
    ),
)
def test_guard_existing_pos(sentence, surface, wanted):
    tokens = {token.text: token.pos_ for token in NativeNLP()(sentence)}
    assert tokens.get(surface) == wanted


@pytest.mark.parametrize(
    "sentence, surface",
    (
        ("He is greedy.", "greedy"),
        ("Lady Macbeth is greedy.", "greedy"),
        ("He is evil.", "evil"),
        ("He is a cook.", "cook"),
    ),
)
def test_guard_existing_complement_role(sentence, surface):
    encoder = GSEEncoder()
    try:
        tokens = {token.token: tuple(token.sent_primitives) for token in encoder.encode(sentence).tokens}
        assert surface in tokens
        assert "SYN_COMPL" in tokens.get(surface, ())
        assert "SYN_ADV_MOD" not in tokens.get(surface, ())
    finally:
        encoder.close()
