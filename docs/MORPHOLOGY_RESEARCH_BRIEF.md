# Morphology as a word-scale operation tier — research brief

> **Status: research brief / load-bearing tangent.** A deliberate side-step off the L2
> register-flywheel path: a principled treatment of morphology, to be *applied*
> (comparative slice first) and then *returned from*. It need not be exhaustive, but it
> is **load-bearing on the system design** — it decides what counts as a *lexeme* vs a
> *computation*, which touches the closed-basis claim — so it is worked up to that
> scale. The implementation style throughout is the "spell-check" propose→coherence-
> resolve shape already validated by `gse/nlp/contractions.py`.

## 0. Why this exists, and why it's load-bearing

The L2 audit surfaced the lemmatizer *mangling* real words (`together`→`togeth`,
`larger` left un-reduced, `earlier`→`earli`). The first instincts — a hand-rolled
orthographic-inversion table, then a Wiktionary lookup DB — are the **wrong type of
fix**: a per-case rule pile (classical-AI brittleness) or a flat lookup (off the
architecture). The right type is the one GSE already uses for grammar: a **typed
operation triggered by a marker**, decomposing surface into operands, with
**coherence as the arbiter**. Inflection is grammar; grammar is operations; so
morphology is a **word-scale operation tier**, parallel to the `WITHIN_CLAUSE` /
`CLAUSE_LINKING` tiers in `gse/symbolic/tiers.py`.

This is load-bearing because morphology is where surface words meet the **closed
72-prime basis**. Get it right and the *representational collapse* extends down to the
word scale — inflected and transparently-derived forms are **computed** from a base's
primitive decomposition rather than each demanding its own storage. Get it wrong and
the project drifts toward storing every surface form (the brittleness GSE exists to
avoid) or toward minting non-words that poison grounding.

## 1. The organizing principle — two axes, not one

My first draft used a single axis (inflection now, derivation later). That is the
wrong cut. There are **two** axes, and the second is the load-bearing one.

**Axis 1 — what the morphology *does* (descriptive):**
- **Inflection** marks a grammatical feature on the *same* word; identity preserved
  (`large→larger`, `walk→walked`). `ran` *is* `run` (the two-lens word identity).
- **Derivation** forms a *new* lexeme, usually changing category or meaning
  (`teach→teacher`, `kind→unkind`, `quick→quickly`).

**Axis 2 — whether the meaning is *computable from the base* (the load-bearing one):**
- **Compositional** — the form's meaning *is* a function of the base's primitive
  decomposition: `unkind = NOT(kind)`, `teacher = SOMEONE who DOES teach`,
  `larger = large × degree`. → handled as an **operation over primitives**, native to
  GSE, **computed not stored**.
- **Lexicalized / opaque** — the meaning has drifted and is *not* recoverable from the
  parts: `transmission` (car part) ≠ `transmit`; `apartment` ≠ `apart`;
  `understand` ≠ `under`+`stand`. → a **lexicon / definition** concern, grounded
  separately (the stored lexeme, or the unknown-word → parse-the-definition branch).

The two axes are **independent**, and Axis 2 is what the architecture turns on:

| | compositional (computed) | lexicalized (grounded) |
|---|---|---|
| **inflectional** | `larger`, `walked`, `dogs` — *always* compositional | (∅ — inflection doesn't lexicalize meaning) |
| **derivational** | `unkind`, `teacher`, `quickly`, `hopeless` | `transmission`, `apartment`, `understand` |

So the real boundary is **not** inflection-vs-derivation. It is **compositional
morphology** (all inflection + *transparent* derivation → operations over primitives)
**vs lexicalized forms** (→ the lexicon/definition pipeline). Negation prefixes
(`un-/in-/dis-/non-`) sit squarely in the compositional box and reuse machinery GSE
*already has* (the sign flip) — they are near-term, not "later."

## Part A — The research: the inventory of English morpho-lexical phenomena

English morphology is a **mostly-closed system** — the reason it is tractable, the
same reason the NSM basis is.

### A.1 Inflection — the eight affixes (productive, feature-marking, base preserved)

| affix | category | feature | feeds |
|---|---|---|---|
| `-s/-es` | N | number=plural | NP/quantity |
| `-'s/'` | N | case=possessive | possessive bind (clitic; cf. `contractions`) |
| `-s/-es` | V | agr=3sg.pres | `morph` |
| `-ed` | V | tense=past | `morph` Tense=Past |
| `-ed/-en` | V | aspect=past-participle | `morph` (perfect/passive) |
| `-ing` | V | aspect=progressive/gerund | `morph` |
| `-er` | ADJ/ADV | degree=comparative | `SET_DIFF`/`Comparison` |
| `-est` | ADJ/ADV | degree=superlative | extreme/`BoundaryCase` |

All inflection is compositional: `base × feature`, base = the word-lens lemma.

### A.2 Derivation — mapped by compositionality

**Compositional (→ operation over primitives; computed):**

| affix | composition | primitive operation |
|---|---|---|
| `un-/in-/dis-/non-` | `NOT(base)` | **NEGATION — the existing sign flip** (`unkind`=`NOT(kind)`; flips `{GOOD,BAD}`, intensity preserved — the vision-doc `dislike`=`NOT(like)`) |
| `-er` agentive | `SOMEONE who DOES base` | AGENT frame over the verb (`teacher`) |
| `-ee` | `SOMEONE to whom base is DONE` | PATIENT frame (`employee`) |
| `-ly` (de-adj) | `in a base WAY` | manner |
| `-ness/-ity/-ment/-tion` | `the STATE/FACT of base` | quality/state nominalizer |
| `-ful` / `-less` | `HAVING / NOT HAVING much base` | HAVE / NOT-HAVE (`hopeful`/`hopeless`) |
| `-able/-ible` | `CAN be base-ed` | CAN + PATIENT |
| `re-` | `DO base AGAIN` | iterative |

**Lexicalized / opaque (→ lexicon or definition pipeline; grounded, not computed):**
`transmission`, `apartment`, `understand`, `awful` (≠ "full of awe"), `business`. The
parts no longer compose to the meaning; the surface is its own concept.

### A.3 The realization layer (orthography + irregulars)

The productive affixes are spelled via **four** regular processes (this set is closed,
which makes the inverse finite): (1) bare concatenation, (2) consonant doubling
(`big→bigger`), (3) silent-`e` drop (`large→larger`, `nice→nicer`), (4) `y→i`
(`happy→happier`; `+e` before `-s`: `baby→babies`; sibilant `-es`: `box→boxes`).

Plus **finite closed lists** (legitimately enumerable — a fact of the language, like
the NSM primes; *not* the rejected lookup DB): ablaut (`sing/sang/sung`, `foot/feet`),
suppletion (`go/went`, `good/better/best`, `be/am/was`), zero (`sheep`), foreign
(`cacti`, `criteria`), periphrastic degree (`more/most X`, the polysyllabic case).

## Part B — The principled design: the spell-check operation system

A morphological operation is `gse/nlp/contractions.py` generalized into the operator
algebra.

### B.1 The four-step shape (identical to the contraction resolver)

1. **Recognize a candidate marker** — a possible process on the surface (`-er/-est/-s/
   -ed/-ing`, a prefix, an ablaut/suppletion pattern).
2. **Propose base candidate(s)** via the *inverse formation model* — the four A.3
   processes run backward (`strip + {stem, stem+e, un-double, i→y}`); the finite lists
   for irregulars. This is the "error model": small and complete, not an open pile.
3. **Resolve by coherence** — keep the candidate that **grounds**: a real lexeme of the
   expected category in the closed lexicon, where the clause coheres. *The lexicon is
   the oracle; the formation model only proposes.* (Candidate-**ranking**,
   inflected/derived→known-base — **not** grounding a new word; the base is then
   grounded by the existing integrator. Consistent with
   `feedback_ground_via_existing_pipeline`.)
4. **Emit the decomposition** — for inflection, `base × feature` (feature → `morph`/
   operator); for compositional derivation, the **primitive composition** itself
   (`NOT(base)`, `AGENT(base)` …) — computed over the 72-prime basis.

### B.2 The decision procedure (where compositional vs lexicalized is adjudicated)

Order of attempts, coherence-gated at each step — no new branch, just the existing
lookup → operation → unknown-word flow:

1. **Lexicon lookup** of the surface. A hit means it is a **stored lemma** (base words)
   *or* a **lexicalized form** (`transmission`) — either way, grounded; done.
2. **Miss → morphological operation.** Inflection reduces to `base × feature`;
   transparent derivation **composes** the primitives (`unkind→NOT(kind)`). Accept iff
   the proposed base grounds and the result coheres.
3. **Still nothing → unknown-word resolution** (the typo/slang/proper-noun branches,
   the broader spell-check). 

So a stored lexicalized form is taken as-is; an unstored but transparent form is
**computed** (productivity, without storage); only genuine unknowns fall through. This
is exactly the representational collapse at the word scale.

### B.3 Collision resolution by coherence (`-er` three ways, by construction)

- `bigger` → COMPARATIVE proposes `big` (gradable ADJ, grounds) → comparative. ✓
- `teacher` → COMPARATIVE proposes `teach` (a verb, not gradable → comparison doesn't
  cohere) → declines; AGENTIVE derivation grounds it as `AGENT(teach)`. ✓
- `water` → neither comparative nor agentive base grounds → base word. ✓
- `together` → `togeth` doesn't ground → base word. ✓

The hard disambiguation is *free*: only the reading that grounds survives. No
ordered rule list, no disambiguation table.

### B.4 Placement — two lenses, one tier

The operation outputs the **word-lens identity** (the base / its primitive
decomposition) and a **sentence-lens feature** (degree, tense, number → the `morph`
channel and the operator algebra). It lives in a `tiers.py`-parallel **word-scale**
registration; the lemmatizer's suffix-stripping is **retired** for these cases and
*consumes* the operation instead. Compositional forms are computed; lexicalized forms
stay in the lexicon. Nothing about morphology lives in ad-hoc stripping anymore.

## Part C — Why this prevents drift (the load-bearing payoff)

- **Closed-basis integrity.** Transparent derivations are computed over the 72 primes
  (`unkind` = the sign-flipped decomposition of `kind`), not admitted as new basis
  elements. The basis stays closed and definitional
  (`feedback_gse_lexicon_definitional_only`); morphology never silently grows it.
- **Representational collapse, word scale.** Productive inflected/derived forms need no
  storage — the operation computes them — so coverage doesn't mean enumerating
  surfaces. This is claim 5 of the vision doc, one level down.
- **Negation is already ours.** `un-/in-/dis-` route to the existing sign flip; the
  most common derivational class is near-zero new machinery, and handling it
  *consistently* (every negated adjective, seen or novel) is the anti-brittleness claim
  in microcosm.
- **One pipeline.** Lexicalized forms and true unknowns flow through the *existing*
  lookup → integrator → unknown-word path; no parallel grounding module
  (`feedback_ground_via_existing_pipeline`).

## Part D — Worked first cut (the only build now): the comparative

Scope for the immediate build = **comparative + superlative only**. It exercises the
whole shape end-to-end and sets the template the rest follow.

- **Marker**: `-er`/`-est`; periphrastic `more/most X`; suppletive via the finite list
  (`better/best→good`, `worse/worst→bad`).
- **Formation model (inverse)**: strip `-er/-est`, propose `{stem, stem+e, un-double,
  i→y}` (the four A.3 processes backward).
- **Resolve**: pick the candidate that is a **known gradable adjective**.
  `larger→large`, `earlier→early`, `nicer→nice`, `happier→happy`, `bigger→big`,
  `taller→tall`; `together`/`water` decline.
- **Emit**: `base × degree=comparative`, feeding the existing `SET_DIFF`/`Comparison`.
  Retire the lemmatizer's ADJ `-er/-est` strip in favor of this operation.

**Flagged clean second example (not now): negation prefixes** — the cleanest
*compositional derivation*, reusing the existing sign flip; the natural step after the
comparative proves the pattern.

### Integration points
- New module (likely `gse/nlp/morphology.py`) defining the operation(s) in the
  `contractions.py` style with a shared propose→resolve core.
- `NativeNLP._lemma` consumes the operation's base (stops ADJ comparative stripping);
  the feature rides the existing `morph` channel / operator algebra.
- `tiers.py`-parallel registration so word-scale operations are first-class.

### Verification (clean and effective)
- A **morphology ladder** (new, proof-suite style): regular (`taller→tall`),
  orthographic (`bigger/nicer/happier/larger/earlier`), suppletive (`better→good`),
  false-strip declines (`together`, `water`), collision decline (`teacher`).
- `tests/test_lemma_invariants.py` stays green (`ran`=`run`, `big/bigger/biggest`).
- `tests/test_l1_ladder.py` stays green.

## Part E — Deferred (named, not built)

- Other inflection (plural / 3sg / past / participle / progressive) — same shape,
  comparative's template.
- The rest of compositional derivation (agentive, nominalizers, `-ly`, `-ful/-less`)
  after negation.
- Orthographic-variation error models (archaic `u↔v`, typo, phonetic) — same
  propose→coherence-resolve core, different formation model; this is where this tier
  and the broader failed-word resolver converge.
- Full irregular/foreign coverage — start with the high-frequency closed list.

## The one honest caveat

This does not make English spelling disappear. The four orthographic processes and the
finite irregular lists are encoded — but **once, completely, as the definition of the
operations**, coherence-gated, inside the operator algebra. That is categorically
different from an ad-hoc per-case lemmatizer patch or a runtime DB: complete instead of
case-by-case, unified instead of scattered, self-disambiguating instead of
rule-ordered, and — for transparent derivation — **computed over the closed basis
rather than stored**. Clean and effective, at the scale the design load demands.

## Implemented lexical-selection policy (typed prose repair)

The historical research brief above is retained as design provenance. The runtime
now implements negative-prefix recognition as `negation_evidence`, with the tuple
API `resolve_negation` as its compatibility projection. A supported base by itself
does not license stripping a known surface: `inside` retains its containment
reading and `under` is no longer proposed as `un` + `der`. For known lexical
surfaces, a WordNet antonym link to the proposed base verifies the operation.
Adjective negation and action reversal retain separate feature codes; `unlock`
is reversal and never a negative evaluative sign. A genuinely absent form may
compose via productive `un-`/`non-` plus a grounded adjective (`unloyal`). Other
unverified apparent prefixes remain unresolved; missing lexical resources remain
unread. These are bounded lexical policies, not proof of all derivations.

Degree resolution also checks the complete surface's adjective-lemma evidence
before selecting among orthographic candidates. This preserves `number`, `inner`,
`forest` and `layer`, selects `cute` rather than `cut` for `cuter`, and retains
`cleaner` → `clean` despite the surface's separate noun reading. Known surfaces
without a licensed adjective base decline; genuinely novel supported formations
can still use the productive inverse model.

Recognition is separate from encoder composition admission. `negation_admission`
examines the encoder's actual selected surface/base rows and all candidate-row
ambiguity. Closed-class/operator bases, absent bipolar content, incompatible
POS, unresolved row ambiguity, designed zero surfaces and conflicting represented
primes refuse an override. A compatible existing row can be extended only when
every represented prime and sign survives the computed result. Thus `unkind`
retains GOOD -1 while recovering the base's SOMETHING; `independent` cannot have
its ALIVE +1 overwritten by ALIVE -1; verbal `dislike` cannot be computed from
closed-class LIKE. Recognition/sign evidence remains visible even when admission
preserves the stored decomposition. Generic POS rows remain a declared coarse
lexical projection, never verified sense resolution.
