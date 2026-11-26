# Engineering design: positive gloss composition to a fixpoint (round 3)

Rohan, 2026-11-26: fill the lexicon with POSITIVE reads from the sources provided for it; never assemble a definition
by exclusion. "We have information. We have vector representations… this is basically just a half-step removed from
embeddings."

## The object

Each definition `d` gets a signed vector over the 56 banks. A value at bank `b` is −1 or +1 with a provenance trace,
or 0 only through an approved negative channel. It is a discrete, traced analogue of a compositional embedding:
`v(d) = identity(genus head) ⊕ content(differentia words) ⊗ operators(gloss grammar)`.

## Basis (axioms, positive)

- **NSM prime exponents** (the chart's lexical units, `catalog.py` `_EXACT`/`_ADAPTED`, with their signs): e.g. "feel"
  is FEEL+, "bad" is GOOD−, "small" is BIG−.
- **Closed-class grammar entries** (`gse_closed_class`).
- **The source-stated and rule-derived values** already in the release.
- **The 89 verified NSM explications** (`data/external/references/notes/explications/*.verified.jsonl`). Each is read by
  this same composer, since it is written in primes. Its positive components become the explicated word's values,
  linked to that word's exact sense where the explication names it.

## What it takes to encode positive meaning (learned from three prototype runs, 2026-11-26)

These were measured on 3,000 random definitions in one pass. Nonzero banks per definition: 0.44 before; 2.80 in
run v1; 2.38 in run v2; 1.64 in run v3, with the rules below.

1. **A word's banks are its own denotatum.** This is Rohan's rule ("own state denotation" for BE, "own affective
   feeling denotatum" for FEEL, no evaluation of a noun's own). So the part of speech decides what a definition may
   contribute.
   - **Noun definition: its genus only.** The noun takes the genus's identity and its denoted values: "anger: a strong
     feeling" is FEEL+, "forger: a person who…" is SOMEONE+ ALIVE+.
   - A noun's differentia (relative clauses, purposes, participants) contributes nothing. "A hen that lays eggs" is
     BODY+, not DO+: what the referent does is not what the noun denotes.
   - Run v2 broke this rule and gave "layers" DO/CAUSE and "forger" CAUSE.
   - **Verb, adjective and adverb definitions: their content words compose.** These words describe what the defined
     word predicates: "inquisitory: diligent…" is GOOD+; "apologize: … regret" is FEEL+; "antipersonnel: designed to
     inflict death or injury" is DO+ CAUSE+ GOOD−.
2. **Identity enters only through a noun definition's genus.** A verb or adjective never takes a gloss noun's
   identity. Run v1 broke this rule: "overwhelmed" got SOMEONE+ from "superior", and "backed" got PART+ from "back".
3. **Closed-class words are not content.** Quantifiers, determiners and light verbs (several, any, many, some, make,
   do, be, have…) contribute nothing; run v1 read "several" as SAME−. Their meanings enter as grammar, not lexical
   content.
4. **Negation in scope flips content.** "not", "without", "lacking", "no", "never" and "non-" flip the scoped words'
   signs, ending at the clause boundary.
5. **The sense of each contributing word must be the one the gloss means.** This is the remaining error class in run
   v3, sense spill: "brad: a small nail" took QUANTITY from nail's unit-of-length sense; "banning" took QUANTITY from
   "ban" the currency; "angry" took SEE from "show".
   - **WordNet definitions:** the genus is the exact hypernym synset (`brad.n.01` → `nail.n.02`), never a parsed gloss
     word, so it cannot spill.
   - **Wiktionary definitions and every content word:** select the word's senses by the gloss's own grammar before
     its values carry. Use `GSE.symbolic.frame_selection` for verbs, and keep only adjective senses that can apply to
     their head noun. Where senses still disagree, carry the possible signs, never a pick.
6. **Every value is traced:** definition → contributing gloss word → that word's reading → … → a basis axiom. Sign
   disagreements are contested and carry both signs.

## Fixpoint

- Pass `k+1` re-composes every gloss using the readings from pass `k`. Values only ever get added; nothing is
  removed, and no stored value changes.
- It stops when a pass adds nothing, at a monotone fixpoint over the positive values.
- **Cost:** about 1–3 ms per gloss with cached readings, so roughly 10–20 minutes per pass over 401,596 glosses on one
  core. Passes parallelize across the 10 cores.

## What is never done

- A bank is never set to 0 because nothing produced it.
- Zeros come only from Rohan's MUST-NOT rulings, near-miss censors, source-stated zeros, and documented absences that
  pass the overlap check. The guard test enforces this.
- No thresholds or votes. No model decides a value.

## Guard (written first)

`tests/test_lexicon_zero_warrants.py` rejects any stored or derived zero whose warrant is not one of:

- a founder/convention rule;
- a source-stated zero;
- a censor record;
- a documented absence.

## Install and measure

- Store the result as the `derived:gloss-composition` channel. It is read by word senses under a
  `gloss-composition` warrant kind, which must trace each value to its gloss word.
- Measure:
  - H before and after;
  - banks per definition;
  - per-bucket gains;
  - contested counts;
  - 30 sampled chains (definition → gloss word → that word's reading → … → a basis axiom);
  - the five witness sentences.
