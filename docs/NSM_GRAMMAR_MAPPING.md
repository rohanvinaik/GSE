# NSM grammar → GSE banks: how grammatical words are assigned

> Research redone 2026-06-20 (sourced: official NSM charts — nsm-approach.net v20
> 2022, Griffith v19 2017, Goddard 2011; Goddard & Wierzbicka; Fähndrich 2014 for
> the computational scalar-operator adaptation). Purpose: stop treating grammatical
> words as word-lexicon noise. A grammatical word resolves to **one of three
> homes** — a word-scale prime, a GSE *sentence-scale operator*, or informational
> zero — never a decomposed content entry.

## The three homes (and why this works)

GSE's registry has **68 word-scale primes** (the lexicon basis, `tier_0_dispatch`)
and **29 sentence-scale operators** (`SENTENCE_SCALE` + the hierarchy markers:
`SYN_*`, `COMP_*`, `INTENSITY`, `QUANTITY`, `HIER_PLUS/MINUS`, `CERTAINTY`). The
sentence-scale layer is precisely where most grammatical words belong — they are
operators over clauses, not meanings of words.

### (1) Word-scale prime exponents → tier-0 (already grounded)
These grammatical words *are* the English exponent of a word-scale prime and are
grounded as axioms today via `canonical_decomposition`:

`i, you, not, if, because, can, must, maybe, do, be, have, with, without, one, two,
other, same, like, kind, part, when, where, here, now, before, after, above, below,
far, near, inside, side` (+ `then, toward, away, start, end, true, false, infer` —
GSE extensions).

### (2) Sentence-scale operators → NOT word entries, route to the operator
The architecture already has the slot; the word is informational-zero *at word
scale* but carries the named operator at sentence scale:

| word(s) | GSE operator |
|---|---|
| the, a, an | `SYN_DET` |
| but | `COMP_BUT` · so → `COMP_SO` · just → `COMP_JUST` · only → `COMP_ONLY` |
| how → `COMP_HOW` · what → `COMP_WHAT` · than → `COMP_THAN` · even → `COMP_EVEN` |
| as | `COMP_AS` (comparative use; `LIKE` for the prime use) |
| very | `INTENSITY` |
| much, many, all, some, (a) few, (a) little | `QUANTITY` (± `HIER_*`) |
| more, most; -er/-est | `HIER_PLUS` / `HIER_MAX` |
| is/was/will (tense), -ed/-s | `SYN_TENSE_PAST/PRES/FUT` |
| have+en (perfect), be+ing (progressive) | `SYN_ASPECT_PERF/PROG` |
| imperative / question framing | `SYN_MOOD_IMPER/INTER` |

This is a deliberate, **named** computational adaptation of canonical NSM: strict
NSM keeps `MUCH/MANY, ALL, SOME, VERY, MORE` as atomic *quantifier/intensifier
primes*, whereas GSE (like Fähndrich 2014) realizes them as **scalar operators**
(`QUANTITY`/`INTENSITY`/`HIER`). Document it as an adaptation, not canon.

### (3) Pure glue → informational zero (no prime, no operator)
NSM itself bans these from the metalanguage:

`of, to, and, or` — realized structurally; assign nothing.

### Periphrastic (decompose to a prime/operator combination, not a single entry)
- modals `would, could, should, may` → via `CAN` / `MAYBE` / `MUST` / `GOOD`+`WANT`
  (no atomic modal prime exists).
  Built (GSE #66, `build_clean_closed_class.PERIPHRASTIC_MODALS`), one Bank 7 prime each (a grammatical
  word has one home; modality is Bank 7, `GSE_V2.md`): `could → CAN` (can's past and conditional form),
  `should → MUST` (the weak deontic), `would → MAYBE` (the hypothetical), `may/might → MAYBE` (the founder's
  2026-10-04 decision);
  `shall`, a future like `will`, is informational zero and the tense operator carries it.
- `often` → `QUANTITY`(MANY) + `WHEN`(time); `most` → `QUANTITY` + `HIER_MAX`.
- **predicational copula "X is a Y"** ("a dog is an animal") → **`KIND`**, *not* a
  copular prime — this is class-membership, the `TypeAssertion` path. (Locational/
  existential `BE` are primes; the everyday equative copula is periphrasis.)

## Two findings to act on

1. **`THIS` is missing from tier-0.** `is_tier_0('this')` → False, but `THIS` is a
   canonical NSM **Determiner** prime (covers this/that/these/those — NSM has no
   proximal/distal split). Likely a missing word-scale exponent; check the registry.
2. **The grammatical-word noise in Layer-2** (`very→ONE`, `would→DO,SOMETHING`) was
   the decomposer trying to read these as *content* via their glosses. The fix
   ("if we do it again"): a grammatical word routes by this table — tier-0 prime /
   sentence-scale operator / zero — and is **never** sent through genus-differentia
   decomposition.

## Canon vs GSE inventory (divergence notes)
- NSM headline count **65** (stabilized 2014); GSE has **68 word-scale + 29 operators**.
- NSM replaced `HAVE`→`(IS) MINE` (2016); GSE retains `HAVE`. NSM has `LIVE/DIE`;
  GSE uses `ALIVE/DEAD`. GSE adds `CAUSE, EXIST, NUMBER, INFER, START, END, THEN,
  TOWARD, AWAY, WITH, WITHOUT, TRUE, FALSE` beyond canon.
- See [[reference-nsm-gold-sources]] for the GSE-72 vs NSM-65 reconciliation.

### Sources
Official charts: nsm-approach.net v20 (2022), Griffith v19 (2017), Goddard 2011.
Goddard & Wierzbicka, *Meaning and Universal Grammar* (2002). Fähndrich, Ahrndt &
Albayrak (2014), "Formal Language Decomposition into Semantic Primes" (the
scalar-operator adaptation). Wierzbicka, "'Semantic Primitives' fifty years later";
"It's mine!" (2016).
