# Declarative mode: a simplified-grammar reading, declared by the request

Program work ID: to be assigned by the owner. This change follows the one-interface contract of
`organize-package-by-subsystem` (`specs/gse-interface/spec.md`): the mode is expressed in the request itself,
routed by intake to one department, and refused by name where the input does not fit.

## Why

USER_INTENT (Rohan, 2026-11-25, verbatim): "Teach declaratives as an alternative mode. It's a complete
'mini-universe' in which the rules of grammar are swapped around into an extremely simple form, almost Ogden's
basic but with some fancier words. It would be like a video game with cheat codes active--standard GSE, but
with a 'special mode'."

CODE_OBSERVED (2026-11-25, GSE at `2492295`, through Regenesis's narrative emit and `GSEEncoder.encode`):
standard GSE reads plain declaratives correctly (`The engineer proves theorems in Lean.` → engineer —prove→
theorem) but misreads the registers consumers actually send. The causes are in the native token front end:

- `GSE/nlp/native.py:742–754` tags a sentence-initial title-case word PROPN unless it is a known verb followed by
  a determiner or pronoun. `Translate design intent…` → translate/PROPN design/VERB; `Manage project scope.` →
  manage/PROPN project/VERB; `Quickly develop…` → quickly/PROPN. The rule was written for names in narration.
- A noun compound with a plural head reads as subject + verb: `verification tools` → tool/VERB, `formal proofs`
  → proof/VERB, so the object becomes `verification` / `formal`.
- A fronted phrase becomes the subject (`In this role, you will execute formal proofs.` → role —execute→ you);
  a verb list loses its first conjunct into the subject (`you scope requirement —define→ property`).

CareerForge already writes its own input in a fixed simple form (`data/spines/*.txt`: one clause per line,
`NAME verb NOUN`, no pronouns, no coordination) because standard GSE reads good prose worst. A consumer that
controls its input should be able to say so, and get a reading whose roles come from the mode's grammar rather
than from heuristics tuned for narrative.

## What changes

- A request MAY declare `mode: declarative`. Intake routes it to the declarative reading department and records
  the mode on the slip. Without the declaration, GSE reads exactly as it does today.
- The mode is a closed grammar (the "mini-universe"): one clause per line, subject before verb, roles fixed by
  position, noun-phrase heads fixed by position, capitalization carrying no grammatical role. The vocabulary is
  the whole lexicon: Basic English's grammar, not its word list.
- A line that does not fit the grammar is refused by name (`NOT_DECLARATIVE_FORM`, with the failing position).
  The mode never falls back to standard heuristics and never guesses.
- The response has the same form as a standard reading, so downstream consumers (Regenesis, CareerForge) need no
  separate path; provenance records the mode.

## Out of scope

- Turning prose into declarative text. That is the consumer's own calling code (one-interface contract); for
  CareerForge postings it is an open owner decision.
- The lexicon. Word meanings come from the active lexicon unchanged; the lexicon session owns it.
- Changes to `GSE/nlp/native.py` or other files of the lexicon session. The mode is a separate module.
