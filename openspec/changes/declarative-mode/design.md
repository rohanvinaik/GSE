# Design: declarative mode

## The mini-universe

Ogden's Basic English keeps English grammar to a small fixed set of patterns; Rohan's mode keeps that grammar
and lifts the 850-word limit ("almost Ogden's basic but with some fancier words"). Concretely, one line is one
clause:

```
SUBJECT [MODAL] [not] VERB [OBJECT] [PREPOSITION NOUN-PHRASE]*
NOUN-PHRASE := [DETERMINER] [ADJECTIVE]* NOUN+          head = last NOUN
```

- **Position decides role.** The first noun phrase is the subject; the next word is the verb (after an optional
  modal and `not`); the following noun phrase is the object; each preposition opens a phrase attached to the verb.
- **The slot decides the part of speech.** A word is read only through the senses its slot allows: `project` in
  the verb slot is the verb, in a noun phrase the noun. A word with no sense of the required part of speech in the
  active lexicon is a refusal, not a re-tag.
- **Capitalization is ignored** for grammar. Proper names are nouns; a sentence-initial verb is not promoted to a
  name, because a line without a subject is outside the mode.
- **Modals and negation** are operators on the event, using the same closed-class entries as standard GSE.
- **Out of the mode, by design:** pronouns, coordination, subordinate clauses, fronted phrases, imperatives,
  questions, passives. Each is refused by name. The consumer restates instead.

## Where it lives

- `GSE/nlp/declarative.py` (new): the line parser for the grammar above. It reads part-of-speech eligibility from
  the lexicon through the existing lexical lookup, and emits the same token and clause structures the standard
  front end produces, so everything downstream (the resolver, the narrative graph, the emit) is unchanged.
- **Declaration.** At the interface, `mode: declarative` on the request. For file-based callers that do not use
  the interface yet (Regenesis's narrative emit reads a story file), a header line `#mode: declarative`, read the
  same way the emit already reads `#genre:`. Intake normalizes both forms and records which one arrived.
- **No edits to the lexicon session's files.** `GSE/nlp/native.py` is untouched. The only shared touch point is
  the routing hook that selects the front end for a declared request.

## Verification

- **Positive witnesses:** every line of CareerForge's `data/spines/*.txt` reads with its named project as the
  subject; the probe lines in the proposal read correctly when restated declaratively.
- **MUST-NOT witnesses:** an imperative, a coordinated line and a fronted phrase are each refused as
  `NOT_DECLARATIVE_FORM`; none yields an event with an invented subject.
- **No regression:** the same probe and spine texts without the declaration produce byte-identical standard
  readings before and after the change.
- **End to end:** a declared CareerForge spine runs through Regenesis's emit and yields the same events as its
  direct reading.
