# Second reading: Goddard's combinatorial identity of a prime vs. the draft

Scope note up front: everything below is checked only against F001–F094 and the draft. Where I say "NSM says," I mean "the founder quoted Goddard saying" (F090, F091). I do not claim that GSE's 72-name/58-coordinate basis, its eight banks, or any specific cross-bank exclusion is an NSM universal; nothing in the record establishes that, and the draft is right to say so in §2 and §9.

---

## 1. Is the hand-authored prime mis-described as "a signed cell plus later constraints"?

**Yes, partly.** The draft's atomic record is:

> "The atomic reading is seeded by hand with its exact prime content, sign, lexical role and an explicit claim of what the atom does and does not define. The bank laws then determine the consequences in the other banks." (§2)

That is a cell (`bank:sign`), a POS-like role, a prose "claim," and then the *general* rulebook runs. Two things are wrong with that against the record:

- **F091 (Goddard):** a form alone "is not necessarily adequate to indicate the intended primitive sense"; the prime's *basic combinatorial properties* are what identify which sense of a polysemous exponent is the prime. So the combinatorial profile is a **field of the prime record itself**, not a consequence computed afterward by laws that were written for all words.
- **F072 and F075:** the founder wants "a formal encoding of how the prime for evaluators like good/bad relate to semantic degrees-of-freedom collapse in other banks," and "every NSM atomic/prime word should have a hard-encoded propagation constraint … No uncertainty, just assignment." That is a per-prime, hand-written propagation rule — tier-0, definitional (F076) — not something derived from reviewed general laws.

The draft's phrase "hand-reviewed definition, like a letter in an alphabet" is correct in spirit but the record it specifies is too thin. Also, §2 says "for each other coordinate the rulebook must establish a written zero, proven silence, or an unresolved state." For a *prime*, an unresolved cell contradicts F075 ("no uncertainty, just assignment") and F088 (a prime is "a bunch of zeros or empty banks, with ONE bank that has a 1"). The hand author decides zero vs. empty for every other coordinate; the general rulebook can *check* that decision for contradiction but does not produce it.

**What belongs in the atomic lexical-unit record (a) — recorded profile of this prime's use:**

| Field | Content |
|---|---|
| `exponent_forms` | the surface form(s), including documented variants/allolexes (the ANU paper the draft cites supports this) |
| `prime_cell` | bank, sign (`+1`, or `−1` only via the 14 alias pairs), alias view |
| `combinatorial_frames` | the frames the prime enters as *this* sense: what it predicates, what slots it opens, what it can be modified by, what it cannot head — recorded from a pinned chart version, as this prime's own range of use |
| `exclusion_profile` | uses of the same form that are **not** the prime (e.g., "a countable noun use of this form is a different reading") — this is the homograph gate |
| `own_closure` | the hand decision for every other canonical coordinate: `0` or `∅`, with the reason; no `UNRESOLVED` permitted in an atom |
| `propagation_constraint` | the hand-encoded tier-0 rule for what this prime's presence does to other banks when it appears as a component of a non-atomic word (F072, F075, F076) |
| `provenance` | chart version, reviewer, date |

**What is separate (b) — a generally applicable bank law compiled from reviewed research:** a versioned relation over joint coordinate states, with a guard, a scope, allowed/forbidden tuples, witnesses, and a review state — exactly the §4 record. It applies to *any* located reading whose guard is proved. It is conditional, tier-1, "perfect in accuracy but not complete in scope" (F076). It may be `CANDIDATE`. A prime's `propagation_constraint` may *motivate* a general law, but the two are different artifacts with different authority, and the draft currently collapses them.

**Confidence: high** that the draft under-specifies the atom and mis-assigns its closure to the general rulebook.

---

## 2. Schematic example (no real lexical claims)

All symbols are placeholders. Constraints are sets of permitted joint tuples; we intersect sets, we do not run forward rules.

### 2a. The prime's profile rejects a homographic ordinary sense

Prime **P**, exponent form `"p"`, cell `EVAL:+1`. Its recorded profile:

- frames: predicates a substantive (`something/someone is p`); accepts a degree modifier
- exclusion: a use of `"p"` as a countable, independently referring noun is not P

Two source records arrive for form `"p"`:

- **R1:** POS=NOUN, plural form attested, typed IS-A pointer to an object class → fails the exclusion profile. R1 is routed to a *new non-atomic reading* `p/NOUN/R1`, which does **not** inherit P's `own_closure`.
- **R2:** POS=ADJ, gradable tag, predicative use attested → satisfies the frames. The link R2→P is certified.

Note what did the work: P's own `exclusion_profile`, not a global "NOUN ⇒ not-P" law. A general POS law may exist separately, but the prime does not depend on it.

### 2b. Two prime components jointly constrain a non-atomic reading

Reading **W** has certified own content `A:+1` (bank X) and `B:+1` (bank Y). Consider banks Z and V, each with domain `{−1, 0, +1, ∅}`.

- Law **L1** (guard: A in own content): Z ≠ −1 → Z ∈ {0, +1, ∅}
- Law **L2** (guard: B in own content): V ≠ +1 → V ∈ {−1, 0, ∅}
- Independent intersection leaves 3 × 3 = 9 joint tuples for (Z, V), including (∅, ∅).
- Joint law **L3** (guard: A and B both in own content *of the same located role*): the tuple (Z=∅, V=∅) is forbidden — when A and B co-occur, at least one of Z, V must be written.

L3 removes a configuration that neither L1 nor L2 removes. That is the "conjunctive" witness F073 asks for, and it is checkable: ablate A, L3 goes dormant, (∅, ∅) returns.

### 2c. A joint relation forces a value nobody wrote

Add a certified **obligation O**: W's definition contains a component of type T, and in this basis T is realizable only as `Z:+1` or `V:−1` (exactly two realizations; the exhaustiveness of that list is what the certificate asserts). Add a hard **source fact F** from a different channel that, under a reviewed law, is incompatible with `V:−1`.

Surviving (Z, V) tuples: every one has `Z = +1`. No source ever wrote Z. The reading of §7 step 5 — "a coordinate is signed … only when all surviving configurations agree" — then emits `Z:+1` with a derivation trail `{O, F, law}`.

Ablations the proof must run:

- drop O's exhaustiveness certificate → Z reopens to {0, +1, ∅} → `UNRESOLVED` (this is the one the draft names)
- drop A → L3 dormant, (∅, ∅) returns (the draft does not name this one)
- drop F → Z ∈ {0,+1}, V ∈ {−1,0,∅} with L3 and O still live → still may force nothing; report honestly

This is the Sudoku/Monty-Hall logic of F073: the forced cell is identified by what *cannot* go elsewhere, under a rule that guarantees the number is somewhere.

---

## 3. Audit of grammar / molecules / templates

**Grammar.** The draft says GSE's sub-prime bank relations "are closest to the associated *grammar*." That is an analogy, and it is a little too close. The grammar Goddard means (F090) is the combinatorics of *primes* — which prime enters which frame with which valency. Per Q1, that information lives in each prime's record. GSE's bank laws are relations over *coordinate states of a reading's vector*; they are a GSE compilation that may be *informed* by that grammar but are not it. The draft should say: prime combinatorics → prime record; bank laws → separate compiled registry; neither is an NSM universal. **Confidence: medium** — the analogy is defensible, but the draft risks treating registry rules as if they inherited NSM's authority.

**Molecules.** The draft's description ("a reusable complex meaning made of simpler content, potentially nested") is fine. What it omits: (i) a molecule's own GSE entry is just a non-atomic reading with its own vector; (ii) when a molecule occurs *inside another word's* definition, its content does not flow into the containing word automatically — **F041** restricts inheritance to a reviewed lexical-inheritance rule; (iii) a molecule's NSM explication is a structured text (ordering, scope, nesting, "like this"), and projecting that onto 58 signed coordinates loses structure. The lost part is a **remainder**, and the draft has no state for it.

**Four things that must stay distinct** (the draft's §3 table only has the last three plus `UNRESOLVED`/`CONFLICT`):

| Thing | Meaning | Where it goes | Effect on comparison |
|---|---|---|---|
| **Basis-inexpressible remainder** | the definition *does* say something here, but the fixed basis cannot encode it (structure, nested molecule, non-prime content) | a separate ledger entry on the reading, with the content preserved; the touched coordinate is **not** `∅`, because the silence proof fails | reading is `PARTIAL`; comparison must know the vector under-represents |
| **Unresolved cell** | surviving candidates disagree; more facts or a model selection could close it | `UNRESOLVED` output state | not a value; excluded from promotion |
| **Written zero** | the coordinate applies and a reviewed middle is written (plus, per F049, a distinct *provisional closure-zero* — see §4) | HDC row written as 0 | enters dot product and norm |
| **Proved silence** | a coverage/type proof says the definition has no content here | `∅`, no row | enters neither dot product nor norm; mask reported (F059, F060) |

The draft mentions "basis-inexpressible content" in §1 and "Preserve out-of-basis content" in §7, but never defines it as a state, so a builder would have nowhere to put it except `∅` or `UNRESOLVED` — both wrong. **Confidence: high.**

**Templates.** "A reusable shape for a family of definitions" is correct but inert. In this design a template is the natural *source of definitional obligations* — the "named definitional component must be represented" in the Exhaustive-obligation row of §4, and the bounded unit that the F049/F066 omission challenge needs. The draft never connects them. They must be admitted as `CANDIDATE` obligations with pinned research provenance, not assumed. Also, "derived macros" (§2) is undefined; either define it or delete it.

---

## 4. Specific unsupported or overbroad statements

1. **Atomic closure delegated to general laws.** "The bank laws then determine the consequences in the other banks." (§2) — contradicts F075 ("hard-encoded … No uncertainty, just assignment") and F091 (profile is part of the prime's account). Also "For each other coordinate the rulebook must establish … an unresolved state" (§2) — an atom cannot have unresolved cells under F075/F088. *Confidence: high.*

2. **Founder's evaluator/descriptor claim mis-answered.** §5 step 3: "not a license for a global … `GOOD excludes BIG` law. The official chart permits evaluation of things and degree with evaluation; the slot matters." F067's claim was that an *evaluator cannot be described by a descriptor* ("you can't be 'big good'"), which the founder asserts NSM makes "EXPLICITLY mutually exclusive." "The chart permits evaluation of things" is a different proposition and does not rebut it. The draft should instead say: F067's exclusion is a candidate law requiring a pinned citation (which neither the draft nor this reading can supply without outside search), scoped to the slot, with witnesses. *Confidence: medium-high.*

3. **Single ablation overclaimed.** "That ablation is the operational test of the Sudoku principle in F073–F074." (§7) F073 asks for both additive and *conjunctive* collapse; ablating only the exhaustiveness certificate tests the obligation, not the joint law. Component ablation is also required (see §2b). *Confidence: high.*

4. **Participant leakage hedged.** "A signed property of an argument is retained in its role; it is not projected to the target word automatically." (§3) F043 says participant, instrument, metaphorical and unaligned-class evidence "remain excluded" — not "not automatically." The only sanctioned routes are F043's own-denotatum rules and F041's re