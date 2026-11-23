"""Primary NSM inventory and explicit definition-anchor coverage.

The chart's frames describe combinations, not a bag of the prime's own banks.
Coordinate mappings below are an audit crosswalk, never assertion-producing rules.
A fully resolved vector still requires independent semantic validation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict

from gse.curation.schema import ALL_PRIMITIVES, BIPOLAR_PAIRS
from gse.primitives_v2 import PRIMITIVE_REGISTRY

from .engine import Assertion, DomainRestriction, Relation, propagate
from .evidence import Definition, validate_assertion_competence
from .foundation import BANKS, CONVENTION_VERSION, DESIGN_SOURCE, lexical_context, validate_lexical_guards
from .resolution import resolve_dictionary

SENTENCE_DURATION_UNIT = "nsm:v20:some-time"
SENTENCE_DURATION_SOURCE_RECORD = "nsm_chart:v20:some-time"

SOURCE = {
    "title": "Chart of NSM Semantic Primes",
    "version": "v20",
    "date": "2022-05-10",
    "path": "data/external/references/nsm-primes-chart-v20-2022.txt",
    "url": "https://nsm-approach.net",
    "sha256": "5847b39219381181f98a2afbfc57b149ad16cd77157ca0d205b341d1466cf732",
}

# (stable unit key, exact chart heading, chart exponent forms, complete box frames)
_CHART_BOXES = (
    (
        "i",
        "I~ME",
        ("I", "ME"),
        "I want to do/know/say something\nI want this, I don’t want this\nI don’t know\nsomething bad can happen to me\nsomeone like me",
    ),
    (
        "you",
        "YOU",
        ("YOU",),
        "I want you to do/know/say something\nsomething bad can happen to you\nyou are someone like me",
    ),
    (
        "someone",
        "SOMEONE",
        ("SOMEONE",),
        "this someone, the same someone,\nsomeone else, this other someone\nsomeone does/says something",
    ),
    (
        "people",
        "PEOPLE",
        ("PEOPLE",),
        "these people, many people, some\npeople, few people\nmany people think like this:...\npeople can say...\npeople of one kind",
    ),
    (
        "body",
        "BODY",
        ("BODY",),
        "people’s bodies\na body of one kind, bodies of two kinds\nsomething bad happens inside\nsomeone’s body\nsomeone feels something in the body",
    ),
    (
        "something",
        "SOMETHING~THING",
        ("SOMETHING", "THING"),
        "this something~thing, the same\nsomething~thing, something else\nsomething big, something small\nsomething of one kind",
    ),
    (
        "words",
        "WORDS",
        ("WORDS",),
        "many words, other words, one word\nwords of one kind\nsay something with (not with) words, say\nsomething in other words\nsay these words",
    ),
    (
        "parts",
        "(HAVE) PARTS",
        ("(HAVE) PARTS",),
        "people’s bodies have many parts\none/two of these parts...\nsomething of this kind has two/many\nparts\nthis part, the same part, this other part",
    ),
    (
        "kinds",
        "KINDS",
        ("KINDS",),
        "people of one/two/many kinds\nthis kind, the same kind, another kind,\nthis other kind\nsomething/someone of one kind\na place of one kind",
    ),
    (
        "this",
        "THIS",
        ("THIS",),
        "this someone/something, these people,\nthis kind, this part\nat this time, in this place\nbecause of this\nit is like this:...",
    ),
    (
        "same",
        "THE SAME",
        ("THE SAME",),
        "the same someone, the same thing, the\nsame kind\nat the same time, in the same place\nsomeone says/does/thinks/knows/\nwants/feels the same",
    ),
    (
        "other",
        "OTHER~ELSE",
        ("OTHER", "ELSE"),
        "someone else, something else, at\nanother time, somewhere else\nsome other kinds, some other parts\nthis other kind, this other part, this other\nsomeone, this other thing",
    ),
    (
        "much-many",
        "MUCH~MANY",
        ("MUCH", "MANY"),
        "many people, many things, many kinds\npeople’s bodies have many parts\nsomething of this kind has many parts\nat many times, in many places\nmuch of this something (e.g. water)\nmuch more, many more",
    ),
    (
        "two",
        "TWO",
        ("TWO",),
        "two someones/people, two things, two\nkinds\ntwo of these parts\nsomething of this kind has two parts\ntwo of these things/people\ntwo more things",
    ),
    (
        "one",
        "ONE",
        ("ONE",),
        "one someone, one thing, one kind\none of these parts\none of these things/people\nin one place, at one time\nsomething of one kind\none more thing",
    ),
    (
        "little-few",
        "LITTLE~FEW",
        ("LITTLE", "FEW"),
        "few people, few things\na little of this something (e.g. water)\nvery little, very few",
    ),
    (
        "some",
        "SOME",
        ("SOME",),
        "some people, some things, some kinds\nsome of these parts\nsome of these things/people\nat some times, in some places\nsome of this something (e.g. water)",
    ),
    (
        "all",
        "ALL",
        ("ALL",),
        "all people, all things, all kinds\nall of these parts\nat all times, in all places\nall of this something (e.g. water)",
    ),
    (
        "time",
        "TIME~WHEN",
        ("TIME", "WHEN"),
        "(at) this time, (at) the same time, at\nsome other time, at this other time\nat some times, at many times\nat the time when ...",
    ),
    ("now", "NOW", ("NOW",), "something is happening here now\nwhen I say this now, ..."),
    ("moment", "MOMENT", ("MOMENT",), "it happens in one moment\na moment before, a moment after\nat this moment"),
    (
        "short-time",
        "A SHORT TIME",
        ("A SHORT TIME",),
        "a short time before\na short time after\na very short time\n[for a short time = for some time, a\nshort time]",
    ),
    (
        "long-time",
        "A LONG TIME",
        ("A LONG TIME",),
        "a long time before\na long time after\na very long time\n[for a long time = for some time, a long\ntime]",
    ),
    (
        "some-time",
        "(FOR) SOME TIME",
        ("(FOR) SOME TIME",),
        "some time before\nsome time after\nit happens like this for some time\nsomeone does this for some time\n[during this time = at this time, for some\ntime]",
    ),
    ("after", "AFTER", ("AFTER",), "after this\nsome time after\na short time after\na long time after"),
    ("before", "BEFORE", ("BEFORE",), "before this\nsome time before\na short time before\na long time before"),
    (
        "want",
        "WANT",
        ("WANT",),
        "I want this\nsomeone wants something\nsomeone wants to do/know/say\nsomething\nsomeone wants someone else to do/\nknow/say something\nsomeone wants something to happen\nI want it very much",
    ),
    (
        "dont-want",
        "DON’T WANT",
        ("DON’T WANT",),
        "I don’t want this\nsomeone doesn’t want this\nsomeone doesn’t want to do/say it\nsomeone doesn’t want it to happen",
    ),
    (
        "feel",
        "FEEL",
        ("FEEL",),
        "someone feels something (good/bad)\nsomeone feels something (good/bad) in\nthis part of the body\nsomeone feels like this",
    ),
    (
        "know",
        "KNOW",
        ("KNOW",),
        "I know\nthis someone knows it\nthis someone knows something (many\nthings) about someone/something\npeople can know this\n[I know that...= it is like this: ..., I know it]",
    ),
    (
        "say",
        "SAY",
        ("SAY",),
        "I say: ...\nsomeone says something (good/bad)\n(to someone)\nsomeone says something (good/bad)\n(about someone/something)\nsomeone says something like this: “--”\nsomeone says something with words\nsomeone says a word to someone",
    ),
    (
        "do",
        "DO",
        ("DO",),
        "someone does something (to someone\nelse)\nsomeone does something with\nsomething else/part of the body\nsomeone does something with someone\nelse\nsomeone does something good (for\nsomeone else)/bad (to someone else)",
    ),
    (
        "think",
        "THINK",
        ("THINK",),
        "someone thinks about someone else/\nsomething\nsomeone thinks something good/bad\nabout someone else/something\nsomeone thinks like this: “- -”\nmany people think like this: “- -”",
    ),
    ("hear", "HEAR", ("HEAR",), "someone hears something\npeople can feel something bad when\nthey hear this word"),
    (
        "see",
        "SEE",
        ("SEE",),
        "someone sees someone/something (in\na place)\npeople can/can’t see well in this place\nsomeone/people can/can’t see this\nsomething\npeople can see this place",
    ),
    ("not", "NOT~DON’T", ("NOT", "DON’T"), "not good, not bad\nnot like this\nI don’t know\nsomeone can’t do this"),
    (
        "can",
        "CAN",
        ("CAN",),
        "something (good/bad) can happen\nthis someone can/can’t do it now\nsomeone can’t do something\nsomeone can’t not (≈ ‘have to’) do\nsomething\nit can be like this: …",
    ),
    (
        "because",
        "BECAUSE",
        ("BECAUSE",),
        "because of this\nit happened because this someone did\nsomething before\n... not because of anything else",
    ),
    (
        "like",
        "LIKE~AS~WAY",
        ("LIKE", "AS", "WAY"),
        "it happens like this:...\nit is like this:...\nsomeone thinks like this: “--”\nsomeone like me\nthis someone does it like this\nit happens as this someone wants\nit is good if someone does/says it in this\nway, not in some other way",
    ),
    ("maybe", "MAYBE", ("MAYBE",), "maybe it is like this, maybe it is not\nlike this\nmaybe someone else can do it"),
    (
        "if",
        "IF",
        ("IF",),
        "if it happens like this for some time, ...\nif you do this, ...\nif someone does something like this, ...",
    ),
    (
        "more",
        "MORE~ANYMORE",
        ("MORE", "ANYMORE"),
        "someone wants more, someone does\nmore, someone knows more\nsomeone wants to know/say more\n(about it)\none more, two more, many more\nnot living anymore\nnot like this anymore",
    ),
    (
        "very",
        "VERY",
        ("VERY",),
        "very big, very small, very good, very\nbad, very far, very near, a very short\ntime, a very long time\nI want it very much (=very)\nvery very big, very very good, very very\nfar etc.",
    ),
    (
        "die",
        "DIE",
        ("DIE",),
        "all people die at some time\nthis someone died at this time/in this\nplace\nafter someone dies, ...",
    ),
    (
        "happen",
        "HAPPEN",
        ("HAPPEN",),
        "something happens\nsomething happens to someone\nsomething happens to something\nsomething happens somewhere (in a\nplace)\nsomething happens in someone/\nsomething",
    ),
    (
        "be-somewhere",
        "BE (SOMEWHERE)",
        ("BE (SOMEWHERE)",),
        "someone is somewhere (in a place)\nsomething is somewhere (in a place)\nsomeone is with someone else",
    ),
    (
        "live",
        "LIVE",
        ("LIVE",),
        "someone lives for a long time\nmany people live in this place\nthis someone lives with someone else\nit is good if someone lives like this",
    ),
    (
        "mine",
        "(IS) MINE",
        ("(IS) MINE",),
        "this thing (knife, shirt, etc.) is mine\n[this thing is someone else’s = someone\nelse can say about this thing: “it is\nmine”]",
    ),
    (
        "be-someone-something",
        "BE (SOMEONE/\nSOMETHING)",
        ("BE (SOMEONE/SOMETHING)",),
        "this someone is someone like me\nthis is something of one kind\nthis is something big/small\nI know who this someone is",
    ),
    (
        "there-is",
        "THERE IS",
        ("THERE IS",),
        "there is something in this place\nthere is someone in this place\nthere are two/many kinds of ...",
    ),
    ("inside", "INSIDE", ("INSIDE",), "inside this something\ninside this part of someone’s body"),
    (
        "touch",
        "TOUCH",
        ("TOUCH",),
        "something touches something else\n(somewhere)\nsomething touches part of someone’s\nbody\nsomeone/people can/can’t touch this\nsomething",
    ),
    (
        "move",
        "MOVE",
        ("MOVE",),
        "someone moves (in this place)\nsomething moves in this place\nparts of this someone’s body move as\nthis someone wants",
    ),
    ("small", "SMALL", ("SMALL",), "something small\na small place\nvery small"),
    ("big", "BIG", ("BIG",), "something big\na big place\nvery big"),
    (
        "good",
        "GOOD",
        ("GOOD",),
        "something good, someone good\nsomething good happens\ndo something good (for someone)\nfeel something good\nthis is good\nit is good if...",
    ),
    (
        "bad",
        "BAD",
        ("BAD",),
        "something bad, someone bad\nsomething bad happens\ndo something bad (to someone)\nfeel something bad\nthis is bad\nit is bad if...",
    ),
    ("true", "TRUE", ("TRUE",), "this is true\nthis is not true"),
    (
        "place",
        "PLACE~WHERE~\nSOMEWHERE",
        ("PLACE", "WHERE", "SOMEWHERE"),
        "(in) this place, (in) the same place,\nsomewhere else, (in) this other place\nin some places, in many places\nin the place where ...\nthere are many places in this place",
    ),
    ("here", "HERE", ("HERE",), "something is happening here now\npeople here"),
    (
        "side",
        "ON (ONE) SIDE",
        ("ON (ONE) SIDE",),
        "on this side, on the same side\non one side, on two sides\non all sides",
    ),
    ("below", "BELOW", ("BELOW",), "below this place\nfar below this place"),
    ("above", "ABOVE", ("ABOVE",), "above this place\nfar above this place\nsomeone above other people"),
    ("far", "FAR", ("FAR",), "far from this place\nfar above/below this place"),
    ("near", "NEAR", ("NEAR",), "near this place\nnear someone"),
)

# Chart notes and function-word/portmanteau inventory, preserved without converting
# grammatical participants into own-word lexical assertions.
CHART_NOTES = "CHART OF NSM SEMANTIC PRIMES [v20, 10 May 2022]\nSemantic primes are the vocabulary of the Natural Semantic Metalanguage. The chart displays the English words for the primes and some of their combinatorial possibilities, according to NSM grammar.\nMore complex combinations are also possible. In some languages, two primes e.g. feel and hear may be expressed by the same word. In some languages, a prime can have two or more\nexponents (allolexes), e.g. English other and else. Sometimes a combination of two or more primes, e.g. like this, can be expressed by a single portmanteau word. [hello@nsm-approach.net].\nFor more resources visit https://nsm-approach.net\nUsing NSM in explications\nDon’t include any complex English-specific words,\nno matter how common and seemingly basic, e.g.\nand, or, make.\nEnsure that you use semantic primes only in\nallowable syntactic frames. Do not resort to non-\nNSM syntax even if English grammar allows it. For\nexample, avoid ‘do something about it’ and ‘feel\ngood/bad about something’; semantic primes DO\nand FEEL do not have any “about” valency.\nAvoid the following non-universal constructions:\n- relative clauses (e.g. someone who did this)\n- comparative (e.g. better than, more than)\n- indirect speech (e.g. this someone said that ...)\nWhenever possible, explications should be written\nentirely in semantic primes but some explications\nrequire use of semantic molecules in addition to\nprimes. Semantic molecules are a well-defined set\nof non-primitive meanings that function as units in\nthe meanings of more complex concepts.\nFunction words and portmanteaus\nThese are some of the main function words and\nportmanteau expressions in English-based NSM.\n‘in’, e.g. in this place; in one moment\n‘at’, e.g. at this time; at this moment\n‘of’, e.g. one of these people; something of one kind\n‘with’, e.g. do something with someone/something\n‘about’, e.g. think/say about something/someone\n‘these’: variant of ‘this’ used with a plural noun\n‘it’ (dummy subject), e.g. it is good if ..., it is bad if...\n‘it’ for ‘this thing’\n‘a lot’: a variant of ‘very much~many’\n‘well’: an adverbial variant of ‘good’\n‘such’: portmanteau of ‘like’ and ‘this’\n‘they’ or ‘them’ for ‘these people’ or ‘these things’\n‘everywhere’: portmanteau based on ‘all’ and ‘place’\n‘often’, ‘sometimes’, ‘always’, ‘never’: portmanteaus\nbased on quantifiers and ‘time’\nsingular ‘they’ for ‘this someone’ (if you want to use\nthis portmanteau, please note it in the text)\x0c"

# EXACT means the existing coordinate names the chart unit; it does not assert
# that the entire lexical signature contains only that coordinate.
_EXACT = {
    "i": "I",
    "you": "YOU",
    "someone": "SOMEONE",
    "people": "PEOPLE",
    "body": "BODY",
    "something": "SOMETHING",
    "words": "WORDS",
    "two": "TWO",
    "one": "ONE",
    "moment": "MOMENT",
    "before": "BEFORE",
    "want": "WANT",
    "feel": "FEEL",
    "know": "KNOW",
    "say": "SAY",
    "do": "DO",
    "think": "THINK",
    "hear": "HEAR",
    "see": "SEE",
    "not": "NOT",
    "can": "CAN",
    "because": "BECAUSE",
    "like": "LIKE",
    "maybe": "MAYBE",
    "if": "IF",
    "happen": "HAPPEN",
    "touch": "TOUCH",
    "move": "MOVE",
    "big": "BIG",
    "good": "GOOD",
    "true": "TRUE",
    "here": "HERE",
    "above": "ABOVE",
    "far": "FAR",
}
_ADAPTED = {
    "this": (
        "SOMETHING",
        1,
        "Approved demonstrative object-reference anchor; which object is designated is a grammatical/contextual binding.",
    ),
    "dont-want": (
        "WANT",
        -1,
        "Approved NOT WANT pole; zero remains orthogonal to wanting, and sentence negation retains its grammatical scope.",
    ),
    "parts": ("PART", 1, "Registry PART is singular; chart specifies (HAVE) PARTS and its relational frames."),
    "kinds": ("KIND", 1, "Registry KIND is singular; identify the taxonomic sense rather than the kindness homograph."),
    "same": ("SAME", 1, "Registry positive identity pole represents the chart form THE SAME."),
    "other": ("SAME", -1, "Existing bipolar convention folds OTHER into SAME; ELSE is a chart allolex."),
    "time": ("WHEN", 1, "Chart TIME~WHEN is represented by registry WHEN; preserve both chart forms."),
    "now": (
        "THEN",
        -1,
        "Existing bipolar convention folds NOW into THEN; the chart does not list THEN as a separate prime.",
    ),
    "short-time": ("LONG_TIME", -1, "Existing bipolar convention folds SHORT_TIME into LONG_TIME."),
    "long-time": ("LONG_TIME", 1, "Registry spelling omits the chart article A."),
    "after": ("BEFORE", -1, "Existing bipolar convention folds AFTER into BEFORE."),
    "die": ("ALIVE", -1, "Candidate alignment to DEAD pole; event DIE versus state DEAD requires semantic validation."),
    "live": (
        "ALIVE",
        1,
        "Candidate alignment to ALIVE; verbal LIVE and state ALIVE require sense-specific validation.",
    ),
    "be-somewhere": (
        "BE",
        1,
        "Registry BE is shared with specification; a location sense must remain separately identified.",
    ),
    "be-someone-something": (
        "BE",
        1,
        "Registry BE is shared with location; a specification sense must remain separately identified.",
    ),
    "mine": (
        "HAVE",
        1,
        "Candidate possession alignment; chart (IS) MINE includes first-person perspective absent from HAVE alone.",
    ),
    "there-is": ("EXIST", 1, "Registry EXIST is the proposed existential coordinate, not an English spelling match."),
    "inside": ("OUTSIDE", -1, "Existing bipolar convention folds INSIDE into OUTSIDE."),
    "small": ("BIG", -1, "Existing bipolar convention folds SMALL into BIG."),
    "bad": ("GOOD", -1, "Existing bipolar convention folds BAD into GOOD."),
    "place": ("WHERE", 1, "Chart PLACE~WHERE~SOMEWHERE shares registry WHERE; preserve the full exponent set."),
    "side": ("SIDE", 1, "Registry SIDE omits chart relational frame ON (ONE) SIDE."),
    "below": ("ABOVE", -1, "Existing bipolar convention folds BELOW into ABOVE."),
    "near": ("FAR", -1, "Existing bipolar convention folds NEAR into FAR."),
}
_METADATA = {
    "much-many": (
        "QUANTITY",
        "Current quantity hierarchy has MANY; a complete definition and hierarchy level require explicit anchors.",
    ),
    "little-few": (
        "QUANTITY",
        "Current quantity hierarchy has FEW; a complete definition and hierarchy level require explicit anchors.",
    ),
    "some": ("QUANTITY", "Current quantity hierarchy has SOME; no ordinary SOME coordinate exists."),
    "all": ("QUANTITY", "Current quantity hierarchy has ALL; no ordinary ALL coordinate exists."),
    "more": (
        None,
        "Chart MORE applies to several predicates and quantities; hierarchy must target an explicitly known nonzero base.",
    ),
    "very": (
        "INTENSITY",
        "Current intensity hierarchy represents VERY; the chart also permits repeated intensity modification.",
    ),
}
_MISSING = {
    "some-time": "No distinct FOR SOME TIME coordinate; LONG_TIME and WHEN do not by themselves specify this duration unit.",
}

# Existing founder anchors have exact identities. Listing them here documents
# approval; only an explicitly supplied build manifest can activate an anchor.
_APPROVED_CORRESPONDENCES = {
    "this": ("SOMETHING", 1, "gse:prime:this", "word-and-sentence-boundary", None),
    "dont-want": ("WANT", -1, "gse:prime:dont-want", "want-polarity", None),
    "want": ("WANT", 1, "wordnet:want:desire.v.01", "want-polarity", None),
    "very": ("INTENSITY", 1, "wordnet:very:very.r.01", "ordinal-stability", 1),
}

# Definition identity only. These links do not promote chart correspondences
# into assignments or imply that a definition has a complete prime signature.
# Native lexical definitions and grammatical records were inspected separately
# from their spellings. Remaining units retain the primary chart's own scope.
_NATIVE_PRIME_DEFINITIONS = {
    "dont-want": "gse:prime:dont-want",
    "this": "gse:prime:this",
    "want": "wordnet:want:desire.v.01",
    "very": "wordnet:very:very.r.01",
    "someone": "gse_closed_class:pronoun:someone",
    "something": "gse_closed_class:pronoun:something",
    "not": "gse_closed_class:negation:not",
    "can": "gse_closed_class:modal:can",
    "maybe": "gse_closed_class:modal:maybe",
    "like": "gse_closed_class:preposition:like",
    "i": "gse_closed_class:pronoun:i",
    "you": "gse_closed_class:pronoun:you",
    "because": "gse_closed_class:conjunction:because",
    "if": "gse_closed_class:conjunction:if",
    "before": "gse_closed_class:conjunction:before",
    "after": "gse_closed_class:conjunction:after",
    "all": "gse_closed_class:determiner:all",
    "above": "gse_closed_class:preposition:above",
    "below": "gse_closed_class:preposition:below",
    "inside": "gse_closed_class:preposition:inside",
    "people": "wordnet:people:people.n.01",
    "body": "wordnet:body:body.n.01",
    "words": "wordnet:word:word.n.01",
    "parts": "wordnet:part:part.n.01",
    "kinds": "wordnet:kind:kind.n.01",
    "know": "wordnet:know:know.v.01",
    "hear": "wordnet:hear:hear.v.01",
    "see": "wordnet:see:see.v.01",
    "do": "wordnet:do:perform.v.01",
    "happen": "wordnet:happen:happen.v.01",
    "same": "wordnet:same:same.a.01",
    "other": "wordnet:other:other.a.01",
    "one": "wordnet:one:one.s.01",
    "two": "wordnet:two:two.s.01",
    "here": "wordnet:here:here.r.01",
    "true": "wordnet:true:true.a.01",
}
_CHART_CONSTRUCTIONS = frozenset(
    {"short-time", "long-time", "some-time", "be-somewhere", "mine", "be-someone-something", "there-is", "side"}
)
_CHART_LEMMAS = {
    "much-many": "many",
    "little-few": "few",
    "short-time": "a short time",
    "long-time": "a long time",
    "some-time": "for some time",
    "be-somewhere": "be somewhere",
    "be-someone-something": "be someone or something",
    "there-is": "there is",
    "side": "on one side",
}


def foundation_prime_links() -> dict[str, tuple[str, ...]]:
    """Return explicit primary-unit identities, never a lemma-selected vector."""
    return {
        f"nsm:v20:{key}": (_NATIVE_PRIME_DEFINITIONS.get(key, f"nsm_chart:v20:{key}"),) for key, _, _, _ in _CHART_BOXES
    }


def chart_definition_records() -> tuple[dict, ...]:
    """Primary-source identities for units without a demonstrated native match.

    The full box is contextual evidence, not an explication invented here. A
    lexical unit's POS is deliberately unspecified: an English exponent's POS
    does not prove that every allowable NSM frame has that grammatical type.
    No candidate coordinate or frame participant becomes a bank assertion.
    """
    records = []
    for key, heading, forms, frames in _CHART_BOXES:
        if key in _NATIVE_PRIME_DEFINITIONS:
            continue
        kind = "GRAMMATICAL_CONSTRUCTION" if key in _CHART_CONSTRUCTIONS else "LEXICAL_UNIT"
        records.append(
            {
                "entry_id": f"nsm_chart:v20:{key}",
                "unit_id": f"nsm:v20:{key}",
                "lemma": _CHART_LEMMAS.get(key, key),
                "pos": "nsm_construction" if key in _CHART_CONSTRUCTIONS else "nsm_lexical_unit",
                "definition": f"NSM v20 {kind.lower().replace('_', ' ')} {heading.replace(chr(10), '')}. "
                "The source identifies this elementary meaning through its exponent forms and allowable frames; "
                "these frames are preserved as context, not asserted as the unit's own bank values.",
                "definition_kind": kind,
                "chart_heading": heading,
                "forms": tuple(forms),
                "frame_text": frames,
                "source_reference": dict(SOURCE),
                "chart_notes": CHART_NOTES,
                "frames_are": "COMBINATORIAL_NOT_OWN_WORD_ASSIGNMENTS",
            }
        )
    return tuple(records)


def native_foundation_words() -> tuple[str, ...]:
    """Native WordNet lemmas required by explicit prime links, not guessed senses."""
    return tuple(
        sorted({entry.split(":")[1] for entry in _NATIVE_PRIME_DEFINITIONS.values() if entry.startswith("wordnet:")})
    )


def catalog_inventory(*, legacy_duration: bool = False) -> dict:
    """Return independent JSON-compatible primary boxes and audited mappings."""
    entries = []
    for key, heading, forms, frames in _CHART_BOXES:
        mapping: dict
        if key == "some-time" and not legacy_duration:
            mapping = {
                "code": "METADATA",
                "bank": None,
                "value": None,
                "note": "Sentence duration and temporal offset carry an interval with unspecified extent.",
                "construction": {
                    "field": "duration",
                    "extent": "unspecified",
                    "relations": ["during", "before", "after"],
                    "source": DESIGN_SOURCE + "#word-and-sentence-boundary",
                },
            }
        elif key in _EXACT:
            mapping = {
                "code": "EXACT",
                "bank": _EXACT[key],
                "value": 1,
                "note": "Coordinate correspondence only; complete lexical signature is not asserted.",
            }
        elif key in _ADAPTED:
            bank, value, note = _ADAPTED[key]
            mapping = {"code": "ADAPTED", "bank": bank, "value": value, "note": note}
        elif key in _METADATA:
            bank, note = _METADATA[key]
            mapping = {"code": "METADATA", "bank": bank, "value": None, "note": note}
        else:
            mapping = {"code": "MISSING", "bank": None, "value": None, "note": _MISSING[key]}
        mapping["assignment_approved"] = False
        mapping["correspondence_approved"] = key in _APPROVED_CORRESPONDENCES or (
            key == "some-time" and not legacy_duration
        )
        mapping["approved_claims"] = []
        if key in _APPROVED_CORRESPONDENCES:
            bank, value, entry_id, section, level = _APPROVED_CORRESPONDENCES[key]
            mapping["approved_claims"].append(
                {
                    "entry_id": entry_id,
                    "bank": bank,
                    "value": value,
                    "hierarchy_level": level,
                    "source": DESIGN_SOURCE + "#" + section,
                    "version": CONVENTION_VERSION,
                    "scope": "EXACT_DEFINITION_ONLY",
                    "signature_complete": False,
                }
            )
        entries.append(
            {
                "unit_id": f"nsm:v20:{key}",
                "chart_heading": heading,
                "forms": list(forms),
                "frame_text": frames,
                "mapping": mapping,
            }
        )
    return {
        "format": "gse.nsm-catalog/1",
        "source": dict(SOURCE),
        "units": entries,
        "chart_notes": CHART_NOTES,
        "frames_are": "COMBINATORIAL_NOT_OWN_WORD_ASSIGNMENTS",
        "basis": basis_audit(),
    }


def basis_audit() -> dict:
    """Measure the build basis separately from old schema and runtime counts."""
    negative = {negative for _, negative in BIPOLAR_PAIRS}
    collapsed = set(ALL_PRIMITIVES) - negative
    hierarchy = collapsed & {"HIER_PLUS", "HIER_MINUS"}
    ordinary = collapsed - hierarchy - {"NUMBER"}
    runtime = set(PRIMITIVE_REGISTRY)
    return {
        "format": "gse.lexicon-basis-audit/1",
        "legacy_schema_symbols": len(ALL_PRIMITIVES),
        "bipolar_pairs": len(BIPOLAR_PAIRS),
        "legacy_collapsed_coordinates": len(collapsed),
        "ordinary_lexical_coordinates": len(BANKS),
        "hierarchy_markers": sorted(hierarchy),
        "hierarchy_marker_count": len(hierarchy),
        "collapsed_count_equation": {
            "ordinary": len(ordinary),
            "hierarchy": len(hierarchy),
            "total": len(collapsed),
        },
        "number": {
            "classification": "META",
            "ordinary_coordinate": False,
            "runtime_registered": "NUMBER" in runtime,
            "legacy_schema_registered": "NUMBER" in ALL_PRIMITIVES,
        },
        "runtime_registry_symbols": len(runtime),
        "runtime_only_symbols": sorted(runtime - set(ALL_PRIMITIVES)),
        "schema_only_symbols": sorted(set(ALL_PRIMITIVES) - runtime),
        "build_basis_matches_ordinary_collapsed_schema": set(BANKS) == ordinary,
        "coordinates": list(BANKS),
    }


def proposal_template() -> dict:
    """Create review inputs without inventing any prime's lexical assignments."""
    inventory = catalog_inventory()
    entries = []
    common = (
        ("DEFINITION_IDENTITY", "Identify the intended prime sense and its explicit dictionary definition IDs."),
        ("OWN_WORD_PROJECTION", "Specify which cells are intrinsic lexical meaning and cite their projection law."),
        (
            "FRAME_ROLE_SEPARATION",
            "Separate the prime's own meaning from participant and complement roles in its frames.",
        ),
        ("SIGNATURE_CLOSURE", "Specify warranted zero and nonzero cells; leave every unsupported cell unknown."),
        ("GOLD_VALIDATION", "Supply independently justified reference signatures and rule-consistency checks."),
    )
    for unit in inventory["units"]:
        mapping = unit["mapping"]
        approved_claims = mapping["approved_claims"]
        construction = mapping.get("construction")
        extra = {
            "EXACT": ("COORDINATE_CORRESPONDENCE_APPROVAL", "Confirm the candidate coordinate for this exact sense."),
            "ADAPTED": ("ADAPTATION_EQUIVALENCE", mapping["note"]),
            "METADATA": (
                "HIERARCHY_BASE_AND_LEVEL",
                "Specify a nonzero base, hierarchy level and target scope without making NUMBER an ordinary cell.",
            ),
            "MISSING": (
                "BASIS_REPRESENTATION",
                "Propose how the current basis represents this unit, or identify a required basis revision.",
            ),
        }[mapping["code"]]
        entries.append(
            {
                "unit_id": unit["unit_id"],
                "chart_heading": unit["chart_heading"],
                "forms": unit["forms"],
                "frame_text": unit["frame_text"],
                "mapping_candidate": mapping,
                "definition_ids": [claim["entry_id"] for claim in approved_claims],
                "existing_approved_claims": approved_claims,
                "proposed_assertions": [],
                "proposed_relations": [],
                "proposed_hierarchy": {},
                "bank_values": {bank: None for bank in BANKS},
                "undefined_decisions": [
                    {"code": code, "question": question, "status": "UNDECIDED", "answer": None, "provenance": []}
                    for code, question in (common[1:] if approved_claims else common if construction else (*common, extra))
                ],
                "acknowledged_decisions": [
                    {
                        "code": "DEFINITION_IDENTITY_AND_COMPONENT",
                        "status": "APPROVED",
                        "answer": claim,
                        "provenance": [claim["source"]],
                    }
                    for claim in approved_claims
                ]
                + (
                    [{
                        "code": "SENTENCE_CONSTRUCTION",
                        "status": "APPROVED",
                        "answer": construction,
                        "provenance": [construction["source"]],
                    }]
                    if construction else []
                ),
                "approved": False,
            }
        )
    return {
        "format": "gse.nsm-projection-proposal/1",
        "code": "REVIEW_TEMPLATE_UNAPPROVED",
        "source": inventory["source"],
        "basis": inventory["basis"],
        "entries": entries,
        "unknown_representation": "JSON_NULL_IS_UNASSIGNED_NOT_ZERO",
        "rules_manifest_compatible": False,
        "semantic_validation": "NOT_CHECKED",
    }


def catalog_report(
    anchors: dict[str, tuple[Assertion, ...]],
    definitions: tuple[Definition, ...],
    relations: tuple[Relation, ...],
    *,
    prime_entries: dict[str, tuple[str, ...]] | None = None,
    native_assertions: dict[str, tuple[Assertion, ...]] | None = None,
    native_domain_restrictions: dict[str, tuple[DomainRestriction, ...]] | None = None,
    evidence_banks: dict[str, tuple[str, ...]] | None = None,
    observations_by_entry: dict | None = None,
    legacy_duration: bool = False,
) -> dict:
    """Replay explicit unit-to-definition links, never identify by lemma spelling.

    Anchors supplied here are the build's declared authority records, not a gold
    standard. Bounded joint closure and semantic correctness remain distinct;
    each linked definition records whether its constraint search was complete.

    Omitting native inputs preserves the legacy /1 anchor-only report. /2 is
    the source-and-anchor foundation, deliberately excluding model completions.
    Callers validate native source competence and exact observation provenance
    before supplying these definition-keyed records; identity links are still
    explicit manifest declarations, never inferred from the resulting values.
    """
    inventory = catalog_inventory(legacy_duration=legacy_duration)
    units = inventory["units"]
    unit_ids = {unit["unit_id"] for unit in units}
    if not isinstance(anchors, dict) or not isinstance(prime_entries, (dict, type(None))):
        raise ValueError("INVALID_CATALOG_LINKS")
    prime_entries = {} if prime_entries is None else prime_entries
    if set(prime_entries) - unit_ids:
        raise ValueError("UNKNOWN_CATALOG_UNIT")
    if any(not isinstance(definition, Definition) for definition in definitions):
        raise ValueError("INVALID_CATALOG_DEFINITION")
    by_id = {definition.entry_id: definition for definition in definitions}
    if len(by_id) != len(definitions):
        raise ValueError("DUPLICATE_CATALOG_DEFINITION")
    if set(anchors) - by_id.keys():
        raise ValueError("UNKNOWN_ANCHOR_DEFINITION")
    claimed = set()
    for entries in prime_entries.values():
        if not isinstance(entries, (tuple, list)) or any(
            not isinstance(entry, str) or entry not in by_id for entry in entries
        ):
            raise ValueError("UNKNOWN_CATALOG_DEFINITION")
        if len(set(entries)) != len(entries) or claimed.intersection(entries):
            raise ValueError("AMBIGUOUS_CATALOG_DEFINITION")
        claimed.update(entries)
    native_mode = any(value is not None for value in (native_assertions, native_domain_restrictions, evidence_banks))
    native_assertions = {} if native_assertions is None else native_assertions
    native_domain_restrictions = {} if native_domain_restrictions is None else native_domain_restrictions
    evidence_banks = {} if evidence_banks is None else evidence_banks
    observations_by_entry = {} if observations_by_entry is None else observations_by_entry
    if not isinstance(observations_by_entry, dict) or set(observations_by_entry) - by_id.keys():
        raise ValueError("INVALID_CATALOG_OBSERVATIONS")
    if any(not isinstance(records, (tuple, list)) for records in observations_by_entry.values()):
        raise ValueError("INVALID_CATALOG_OBSERVATIONS")
    for supplied, kind in ((native_assertions, Assertion), (native_domain_restrictions, DomainRestriction)):
        if not isinstance(supplied, dict) or set(supplied) - by_id.keys():
            raise ValueError("INVALID_CATALOG_NATIVE_EVIDENCE")
        for records in supplied.values():
            if not isinstance(records, (tuple, list)) or any(not isinstance(record, kind) for record in records):
                raise ValueError("INVALID_CATALOG_NATIVE_EVIDENCE")
            for record in records:
                record.__post_init__()
                validate_assertion_competence(record)
                if record.bank not in BANKS or record.source.startswith("model:") or record.family == "model":
                    raise ValueError("INVALID_CATALOG_NATIVE_EVIDENCE")
    if not isinstance(evidence_banks, dict) or set(evidence_banks) - by_id.keys():
        raise ValueError("INVALID_CATALOG_RELEVANCE")
    for banks in evidence_banks.values():
        if (
            not isinstance(banks, tuple)
            or any(not isinstance(bank, str) or bank not in BANKS for bank in banks)
            or len(set(banks)) != len(banks)
        ):
            raise ValueError("INVALID_CATALOG_RELEVANCE")
    propagate(BANKS, (), relations)
    validate_lexical_guards(relations)
    for entry_id, assertions in anchors.items():
        if not isinstance(assertions, (tuple, list)) or any(not isinstance(a, Assertion) for a in assertions):
            raise ValueError("INVALID_CATALOG_ANCHORS")
        propagate(
            BANKS,
            tuple(assertions),
            relations,
            lexical_context(by_id[entry_id], observations_by_entry.get(entry_id, ()), relations),
        )
    results = []
    search_checks: list[bool] = []
    outcomes = Counter()
    for unit in units:
        links = []
        for entry_id in sorted(prime_entries.get(unit["unit_id"], ())):
            definition = by_id[entry_id]
            declared = tuple(anchors.get(entry_id, ()))
            native = tuple(native_assertions.get(entry_id, ()))
            restrictions = tuple(native_domain_restrictions.get(entry_id, ()))
            relevance = tuple(sorted(evidence_banks.get(entry_id, ())))
            assertions = native + declared
            resolution = resolve_dictionary(
                BANKS,
                assertions,
                relations,
                lexical_context(definition, observations_by_entry.get(entry_id, ()), relations),
                evidence_banks=relevance,
                domain_restrictions=restrictions,
            )
            inference = next(record for record in resolution.trace if record["kind"] == "INFERENCE_SCOPE")
            search_checks.append(inference["complete_search"])
            outcome = (
                "CONFLICT"
                if resolution.code == "CONFLICT"
                else ("NO_FOUNDATION_EVIDENCE" if native_mode else "NO_DECLARED_ANCHORS")
                if not assertions and not restrictions
                else ("RESOLVED_FOUNDATION_CLOSURE" if native_mode else "RESOLVED_ANCHOR_CLOSURE")
                if resolution.code == "RESOLVED"
                else ("PARTIAL_FOUNDATION_CLOSURE" if native_mode else "PARTIAL_ANCHOR_CLOSURE")
            )
            if not native_mode and not assertions:
                outcome = "NO_DECLARED_ANCHORS"  # Exact legacy /1 report semantics.
            links.append(
                {
                    "entry_id": entry_id,
                    "definition": asdict(definition),
                    "code": outcome,
                    "resolution": resolution.code,
                    "anchors": [asdict(a) for a in declared],
                    "assignments": {} if resolution.code == "CONFLICT" else resolution.assignments,
                    "unresolved_banks": sorted(bank for bank, domain in resolution.domains.items() if len(domain) > 1),
                    "empty_domains": sorted(bank for bank, domain in resolution.domains.items() if not domain),
                    "conflicts": list(resolution.conflicts),
                    "conditional_exceptions": [
                        record for record in resolution.trace if record["kind"] == "CONDITIONAL_EXCEPTION"
                    ],
                    "gold": "NOT_CHECKED",
                    "inference": inference,
                }
            )
            if native_mode:
                links[-1].update(
                    {
                        "native_assertions": [asdict(a) for a in native],
                        "native_domain_restrictions": [asdict(r) for r in restrictions],
                        "evidence_banks": list(relevance),
                        "domains": {bank: sorted(values) for bank, values in resolution.domains.items()},
                        "evidence_guards": [
                            record for record in resolution.trace if record["kind"] == "EVIDENCE_GUARD"
                        ],
                        "authority": {
                            "identity": "EXPLICIT_MANIFEST_LINK",
                            "anchors": "DECLARED_MANIFEST_AUTHORITY",
                            "native_evidence": "EXACT_DEFINITION_SOURCE_PROVENANCE",
                            "closure": "APPROVED_RELATIONS",
                            "model_completions": "EXCLUDED",
                        },
                    }
                )
        if not links:
            code = "UNLINKED"
        elif any(link["code"] == "CONFLICT" for link in links):
            code = "CONFLICT"
        elif all(
            link["code"] == ("RESOLVED_FOUNDATION_CLOSURE" if native_mode else "RESOLVED_ANCHOR_CLOSURE")
            for link in links
        ):
            code = "RESOLVED_FOUNDATION_CLOSURE" if native_mode else "RESOLVED_ANCHOR_CLOSURE"
        elif any(
            link["code"] == ("NO_FOUNDATION_EVIDENCE" if native_mode else "NO_DECLARED_ANCHORS") for link in links
        ):
            code = "MISSING_FOUNDATION_EVIDENCE" if native_mode else "MISSING_DECLARED_ANCHORS"
        else:
            code = "PARTIAL_FOUNDATION_CLOSURE" if native_mode else "PARTIAL_ANCHOR_CLOSURE"
        outcomes[code] += 1
        results.append(
            {
                "unit_id": unit["unit_id"],
                "chart_heading": unit["chart_heading"],
                "mapping": unit["mapping"],
                "code": code,
                "definitions": links,
            }
        )
    mapped = {unit["mapping"]["bank"] for unit in units if unit["mapping"]["bank"] is not None}
    report = {
        "format": "gse.nsm-catalog-coverage/2" if native_mode else "gse.nsm-catalog-coverage/1",
        "source": inventory["source"],
        "basis": inventory["basis"],
        "units": results,
        "prime_units": len(units),
        "mapping_counts": dict(sorted(Counter(u["mapping"]["code"] for u in units).items())),
        "coverage_counts": dict(sorted(outcomes.items())),
        "gse_coordinates_without_direct_chart_unit": sorted(set(BANKS) - mapped),
        "readiness": {
            "code": "SEMANTIC_FOUNDATION_NOT_VALIDATED",
            "gold": "NOT_CHECKED",
            "all_units_linked": "UNLINKED" not in outcomes,
            ("all_foundation_domains_resolved" if native_mode else "all_anchor_domains_resolved"): outcomes[
                "RESOLVED_FOUNDATION_CLOSURE" if native_mode else "RESOLVED_ANCHOR_CLOSURE"
            ]
            == len(units),
            "mapping_complete": all(u["mapping"]["code"] != "MISSING" for u in units),
            "founder_signature_completeness": "NOT_ESTABLISHED",
        },
        "inference_scope": "GENERALIZED_ARC_CONSISTENCY_AND_BOUNDED_JOINT_SUPPORT",
        "complete_search": bool(search_checks) and all(search_checks),
    }
    if native_mode:
        report["evidence_scope"] = "SOURCE_AND_AUTHORED_ANCHOR_FOUNDATION"
        report["model_completions"] = "EXCLUDED_FROM_FOUNDATION_REPLAY"
    return report
