# Independent second reading: GSE lexicon construction

**Reading posture.** I take F001–F089 as governing intent, with later statements overriding earlier ones (so: unpaired coordinates are 0/+1 per F040, not balanced ternary as loosely said in F046; primes are hand-defined per F075/F088; the sub-prime relation is the true atomic per F088; typed field-filling per F078; "silent" is a distinct state per F059). I have not seen the Harmonizing, triagegeist, wayfinder, significance_weighting, constrained-hallucination, SquishOS, or cell_tracking materials (F058, F060, F068, F078), nor the image in F060. Where a founder statement leans on those, I say so and treat the content as unavailable. I make no empirical claims about what any resource actually says about any specific word; every example below is labeled with what would need to be certified.

---

## 1. Primes as smallest stable contents; relations between banks as smallest operations

**Plain statement of the distinction (F088).** A prime word like *good*, *big*, *someone*, *move* is the smallest thing you can *store and carry around* as a definition: a 58-cell vector with one cell lit (+1, or −1 for the aliased pole) and everything else either written 0 or left silent. That is the "electron." But the smallest thing the *builder does* is not "write a prime." It is "apply a rule that says: given what is in bank A, bank B must be such-and-such." Those rules are the "quarks." They have no standalone existence as a word — you cannot look up "the rule that descriptors need a host" in a dictionary — but every word, including every prime, is built out of them. The 14 opposite-pole aliases are the purest case (F076): "*bad* is *good* with one sign flipped, everything else identical" is a relation, not a word, and it is applied to two words.

So the two claims "primes are atomic" and "relations are atomic" are not in conflict. They are atomic in different senses:

- a prime is atomic as **content** (no stable smaller definition exists);
- a relation is atomic as **operation** (no smaller step of construction exists).

**Why a hand-defined prime must still undergo relational closure.** The founder (F075, F088) says the 72 prime readings are written by hand, like amino acids or alphabet letters. Agreed. But "written by hand" only fixes the lit cell. It does not, by itself, fix the other 57 cells, and the four-state write mask (written 0 / silent / unresolved / conflict) means every one of those 57 cells is a decision, not a default. The relation rulebook is what makes that decision principled: once *big*'s own cell is +1, every relation that triggers on BIG fires, and whatever it forces on the other banks must be what the hand definition says. If the hand definition and the fixpoint of the rules disagree, one of them is wrong. Hence the closure test: **closure(prime vector) must equal prime vector, with zero conflicts and zero unresolved cells.** F072 and F075 say essentially this — primes are the "zero-order" test of propagation, and running them should be "no uncertainty, just assignment."

**Challenging "all other banks silent by axiom."** This earlier claim (not a founder assertion; it appears to be assistant design) fails on three counts:

1. *It conflates two mask states.* "Silent by axiom" says every non-lit cell is silence (no row). But F088 says primes are "a bunch of zeros or empty banks," which keeps both states open, and F059 insists silence (definition does not speak) is different from 0 (definition speaks and says "middle"). Whether *good*'s BIG cell is silent (goodness says nothing about size) versus *good*'s THING cell is written 0 (goodness is an evaluator, and the reading is not an object — if the design chooses to *assert* that) is exactly the decision the rulebook must make per cell. An axiom that says "all silent" has quietly made 57 decisions without justification.

2. *It makes closure vacuous.* If every other bank is silent by fiat, no relation can be tested against the primes, and the primes stop being the zero-order test F072 asks for. The founder's own example in F067 (*exceptional* = GOOD lit + VERY lit) shows an intensifier bank being lit by a relation; a rulebook that says "VERY may combine with evaluators" is being checked when *very* and *good* are closed. If the rulebook forces something on a prime that the hand definition left silent, that is a finding, not an error to be suppressed.

3. *It cannot distinguish "we did not look" from "the definition does not speak."* Silence must be *proven* silence (F059: "leave a bank empty where the definition of the word is definitionally silent"). For a prime, the proof is "no relation fires on this bank from the lit cell, and the hand definer certifies the bank is inapplicable." That is a positive act, done once per prime per bank, and recorded. "By axiom" skips the record.

What survives of the earlier claim: for most primes, after closure, most cells will indeed be silent. That is the expected *result*, not an axiom.

**One further correction worth carrying.** A *prime* is a coordinate; a *prime reading* is one specific English word reading (the NSM exponent sense). *Good* the adjective in "a good knife" is the prime reading; *goods* (merchandise) and *the good* (ethics) are ordinary non-prime readings that get built like any other word. The 72-reading worklist is 72 readings, not 72 orthographic words, and alignment to the NSM chart's exponent list is what picks them.

---

## 2. Taxonomy of relations

**Notation.** Each coordinate *c* carries a candidate set *S(c)*. Initial state: unpaired *c* → {0, +1, SIL}; bipolar *c* → {−1, 0, +1, SIL}, where SIL means "silence is a legal outcome." Rules only *remove* members (monotone). Final interpretation:

- |S(c)| = 1 and the member is a value → write it;
- S(c) = {SIL} → no row (proven silence);
- |S(c)| > 1 → unresolved (goes to the typed residual or a later channel);
- S(c) = ∅ → conflict (recorded; never resolved by voting).

Every rule has a **trigger** (what must be true in some bank(s)), a **consequent** (a subset restriction on some other bank), and **guards** (§2.9). "Present" in a trigger means *resolved to a nonzero value*, not merely "nonzero is still a candidate" — see §2.8 for why.

### 2.1 Exact signed aliases (tier 0)
*Form:* name A at +1 on coordinate *c* ≡ name B at −1 on *c*; all other cells identical.
*Can force:* the full identity of the aliased reading given the other — every cell, including mask states.
*Cannot force:* anything about any other coordinate, and nothing about readings that are merely antonyms by some resource's pointer (an antonym pointer is a *candidate* for alias status, not an alias).
*Mask:* alias pairs share one row; a conflict here (one source says *A* lit, another says *B* lit, same reading) is a true conflict.
*Status:* definitional, exact, exhaustive (14 pairs). This is the "72 → 58" collapse (F076).

### 2.2 Own-slot exclusions
*Form:* *A* present → S(B) ⊆ {0, SIL}.
*Can force:* removal of ±1 from B.
*Cannot force:* the choice between written 0 and silence. That choice needs a second rule or a stated mask policy (see §2.10). It also cannot fire from *participant* evidence (a verb whose Theme is a thing does not get THING excluded or included — F042/F043 role guard).
*Example of the shape (founder hypothesis, F057):* "reading is a modifier (adjective/adverb POS, own slot) → S(THING) ⊆ {0, SIL}." Whether the result is 0 or SIL is open (§7).

### 2.3 Polar exclusions (remove the middle)
*Form:* *A* present → S(B) ⊆ {−1, +1} (and usually also removes SIL, since B is being asserted to speak).
*Can force:* that B is not neutral; it reduces a ternary choice to a binary one (F066: "words with strong emotive valence are not 0").
*Cannot force:* the sign. Sign must come from a certified source or the typed residual.
*Caution:* F066's motivating case uses emotive-valence resources (EmoLex, SentiWordNet), which record association/opinion, not definition. F057 explicitly says *dog* and *Satan* are correlated with good/bad without it being definitional. So a polar exclusion triggered by association data is an **unproved hypothesis** and must carry a source guard; it cannot be promoted on the strength of the resource's existence.

### 2.4 Dependencies (B must be spoken to)
*Form:* *A* present → S(B) ⊆ {−1, 0, +1} (SIL removed).
*Can force:* that the definition is not silent on B — a row will exist.
*Cannot force:* the value, including whether it is the middle.
*Where it matters:* this is the only rule type that converts silence into "some row." Misuse here is the main way to over-fill the lexicon (F045's "understatement and overstatement are equal distortions"). A dependency is justified only when the resource contract or the NSM explication pattern says B is *always* part of what A-readings mean.

### 2.5 Required companions
*Form:* *A* present → S(B) = {+1} (or {−1}).
*Can force:* a full value.
*Cannot force:* anything if A is only a candidate.
*Status:* strongest and rarest. From the supplied material I can justify no required companion that is a universal law; even the aliases are identities rather than companions. Candidates (e.g., "a reading lit on VERY in its own slot must also be lit on some evaluator or descriptor") are GSE adaptations of the chart's valency and need MUST-NOT testing (*very* the word itself has no such companion — its companion is supplied by grammar).

### 2.6 Combinability (permission, not force)
*Form:* *A* and *B* may both be nonzero in one reading.
*Can force:* nothing. Its function is negative-space: it is the recorded reason an exclusion was *not* written, and it licenses conjunctions (§2.8). F067's *flock* = MANY + (out-of-basis "bird") is a combinability record: substantive and quantifier coexist.
*Why it must be explicit:* without a combinability row, "no exclusion exists between A and B" is indistinguishable from "nobody checked."

### 2.7 Disjunction / coverage
*Form:* given trigger *A*, at least one of {B₁ … Bₖ} must be nonzero.
*Can force:* only the Sudoku move (F073): when k−1 of the set have had nonzero removed, the last one is forced to {−1, +1} (or {+1} if unpaired). Before that, it forces nothing on any individual cell, but it *does* forbid the joint assignment "all k are 0/SIL," which is exactly the inverse-Monty-Hall information: you know the set contains a lit cell even when you cannot say which.
*Cannot force:* a choice among ≥2 live members; that goes to the typed residual as a single *set-valued* question ("which of these k, and with what sign"), not k independent questions. This is where F067's "it's maybe 5 calls, not 20" is operationally realized: one coverage set is one call.
*Mask:* an unresolved coverage set must be stored as a *joint* unresolved record, not as k separate "unresolved" cells, or the joint constraint is lost between passes.

### 2.8 Conjunctions (joint-evidence rules)
*Form:* *A* present ∧ *B* present → consequent of any form in §2.2–2.7.
*Can force:* whatever the consequent form can, but only when **both** triggers are *resolved* nonzero.
*Cannot force:* anything from candidates. If a conjunction fired on "A might be lit and B might be lit," it could prune a cell on the strength of two guesses, and a later pass could resolve A to 0 with the pruning already done — unsound. Monotone propagation requires that conjunction triggers read only resolved values. This is also why the residual model's outputs are fed back into propagation (F069): resolving one cell can newly enable conjunctions.
*This is F073's "additive and conjunctive":* single-prime rules add constraints independently; conjunctions add constraints that neither prime alone would license.

### 2.9 Guards (source / reading / role)
Guards gate whether a rule may fire at all. They force nothing.

- **Source guard:** which resource family may supply the trigger. Example: an alias may be triggered only by the NSM hand table; a polar exclusion may not be triggered by EmoLex alone.
- **Reading guard:** evidence must be aligned to *this* reading. Synset-level and roleset-level records can satisfy an exact-reading guard; lemma-level records (USAS tags, EmoLex) satisfy only a lemma guard and need a second alignment step before they may trigger own-slot rules.
- **Role guard (F042/F043):** evidence must be about the reading's own denotatum/predicate, not about its participants, instruments, or metaphorical uses. A VerbNet role "Theme" or a FrameNet frame element says something about the *argument*, never about the target's own cell.

### 2.10 Where silence vs 0 vs unresolved matters — summary
| Situation | Correct state | Wrong state and why |
|---|---|---|
| No rule touches B, no source speaks to B, hand/omission check certifies inapplicable | SIL | 0 overstates ("the definition says neutral"); unresolved understates (it was checked) |
| Exclusion leaves {0, SIL} and a source asserts B is in-scope but middle (e.g., a reading whose definition is "neither good nor bad") | 0 | SIL understates |
| Coverage set with ≥2 live members | joint unresolved | any single 0 or SIL overstates |
| Two certified sources force disjoint subsets | conflict | voting or "pick the stronger" launders a contradiction into a fact |
| F049's "provisional closure to 0 after omission challenge" | **open** — F049 writes 0, F059 says proven silence is empty, not 0 | carry as open decision (§7) |

**No universal laws from POS or the NSM chart.** None of the above is instantiated as "adjectives never X" or "NSM says evaluators and descriptors exclude each other." The chart, as described in the prompt, gives *allowable syntax among primes in explications* ("something big," "very good," "many people," FEEL has no "about" valency). A syntactic restriction on how prime P₁ may modify P₂ is not the same as a restriction on whether a single word's explication may contain both. F067's "explicitly mutually exclusive" reading of evaluators vs descriptors is therefore **not justified from the chart as described**: "a big good thing" uses both; what the chart forbids is BIG taking GOOD as its head. The faithful GSE adaptation is a *hosting* relation (a descriptor lit in own slot needs a substantive host, which may be in the reading or supplied by grammar), not a co-occurrence exclusion.

---

## 3. Deriving and validating the rulebook

### 3.1 Three epistemic tiers (every rule carries one)
- **Research-derived law:** a statement a primary reference makes in its own terms. Examples from the supplied facts: VERY combines with GOOD/BAD and BIG/SMALL; MANY combines with substantives; FEEL lacks an "about" valency; molecules are distinct from primes; a VerbNet member must match class syntax and semantics; EmoLex records association; SentiWordNet scores a synset.
- **GSE adaptation:** a law translated into a bank relation through a stated *bridging assumption*. The bridging assumption must be written out, because it is where the error lives. Example: "if the reading's own explication would use prime P in head (own-predicate) position, then P:+1 in own slot" turns FrameNet frame-evoking (a *lexical unit evokes a frame*) into a candidate for the own-slot FEEL/MOVE positives approved in F043.
- **Unproved hypothesis:** a founder conjecture or a plausible generalization with no source backing yet. Examples: "nouns carry no definitional sentiment" (F057); "POS collapses the state space astronomically" (F015, later demoted in F017–F018 to "tiny"); "strong emotive valence means not-0" (F066); "most front-Zipf readings leave ≤5–10 banks × 1–3 candidates" (F067, explicitly a guess). These are allowed in the rulebook only with MUST-NOT examples attached and only until the sample stage tests them.

### 3.2 Field-contract sheets (one per resource)
For each resource, enumerate every field and answer four questions: *(i)* what identity scope does the field attach to (synset, roleset, class member, lexical unit, lemma+POS, bare lemma); *(ii)* what kind of claim is it (definitional, structural/syntactic, associative, opinion); *(iii)* which relation forms it may trigger (constructive: add candidate value; destructive: remove candidates); *(iv)* which guards it satisfies. This is what F056 asked for ("what semantic degrees of freedom are pinned by every typed, categorical assertion") and F057 reframed as kindergarten conditional logic. The sheet is the artifact; prose explanation is not.

### 3.3 Example ledgers
Every rule row needs at least one **positive** example (reading + native record excerpt + expected cell outcome) and at least one **MUST-NOT** example (reading where the trigger holds and the consequent must *not* obtain, or where the guard should block firing). The MUST-NOTs are where hypotheses die. For F057's noun-sentiment hypothesis, the MUST-NOT search is: find a noun reading whose definition, by an NSM-style explication, contains "bad" as a component (candidates to check, not claims: *crime*, *villain*, *disaster*). If one is certified, the rule narrows from "nouns" to something else or is dropped.

### 3.4 Practical research-to-rule workflow
1. **Chart pass.** From the NSM chart's valency/combinatorics, write one *combinability* or *hosting* row per allowed pattern and one *exclusion* row per stated restriction. Label research-derived. Do not write any exclusion the chart does not state.
2. **Bridging pass.** For each row, write the bridging assumption that turns explication syntax into a reading-level cell relation. Relabel as GSE adaptation. If no honest bridge exists, the row stays as documentation only.
3. **Resource pass.** From each field-contract sheet, write candidate constructive and destructive rows with guards. Associative fields (EmoLex, SentiWordNet opinion scores) may only produce *omission-challenge triggers* or candidate retention, never forcing, until a hypothesis test says otherwise.
4. **Founder-hypothesis pass.** Encode F057, F066, F067 conjectures as hypothesis-tier rows with explicit MUST-NOT slots.
5. **Prime closure.** Hand-define 72 readings. Run closure. Any rule that produces a conflict or an unresolved cell on a prime is either wrong or has a missing guard; fix the rule, not the prime, unless the hand definition is shown wrong.
6. **Ledger check.** Every row fires on its positives and refuses every MUST-NOT.
7. **Sample test** (§6). Promote hypothesis rows that survive; demote rows that produce conflicts on certified readings.
8. **Freeze and version.** The rulebook is data, not code; every change is a diff with the examples that motivated it.

---

## 4. End-to-end construction for one located reading

**Input:** a *located reading* = (lemma, POS, reading anchor). The anchor is whatever stable identity the source records share: a synset id, a PropBank roleset id, a VerbNet member slot, a FrameNet lexical unit. The anchor is an identity key, not an ontology; this is not WordNet-first. The output is a 58-cell vector plus mask plus provenance.

**Step 1 — Source alignment.** For each resource, retrieve the native records and tag each with an alignment grade: *exact* (same reading anchor or an explicit cross-mapping, e.g., a PropBank roleset with a VerbNet mapping), *POS-level* (lemma+POS match), *lemma-level* (bare lemma). Exact records may satisfy reading guards; POS-level may satisfy POS guards only; lemma-level may trigger nothing own-slot until a disambiguation step aligns them (a USAS tag on a lemma with three WordNet senses is not evidence for any one of them).

**Step 2 — Typed assertion extraction.** Each record is converted into typed assertions in the resource's own vocabulary (frame name, frame element, VerbNet class and predicate, thematic role, selectional restriction, roleset arg labels, USAS tag path, synset POS and pointer type, score triple, emotion-association set). No prose, no gloss (F078, F080). Assertions carry the alignment grade and the role tag (own predicate vs participant).

**Step 3 — Candidate initialization.** All 58 coordinates get their full candidate set (§2 notation).

**Step 4 — Constructive and destructive application by family.** Each family both adds and removes:

- **NSM chart / hand table.** *Constructive:* if the reading *is* a prime exponent, its cell is lit and the aliases apply (tier 0). *Destructive:* a reading that is a listed exponent is not re-derived from other resources; a reading identified as a *molecule* gets an out-of-basis marker (Step 7) and no prime cell is forced for the molecule itself.
- **FrameNet.** *Constructive:* the frame a lexical unit evokes, taken as the reading's own predicate, licenses the narrow own-slot positives of F043 when the frame's type is certifiably a feeling or a change-of-place (bridging assumption stated). *Destructive:* if the reading appears only as a frame-element filler in some other frame, that record satisfies no own-slot guard; non-core frame elements never bear on the target's cells.
- **VerbNet.** *Constructive:* class semantic predicates on the reading's own event (e.g., a motion or emotional-state predicate, if certified for the class) license the same narrow positives; the class also tells you that sign is *not* given by the class when both poles share a class (an "admire-type" class containing both positive and negative emotion verbs cannot supply GOOD/BAD sign — that becomes a one-bit residual). *Destructive:* selectional restrictions on arguments are participant facts and are role-guarded out of own-slot rules; absence of a predicate in a class is **not** evidence of silence unless the class contract is complete, which I cannot certify from the material supplied.
- **PropBank.** *Constructive:* sense-specific numbered roles with descriptive labels (experiencer, agent) support own-predicate category (feeling vs action); an explicit VerbNet mapping is the alignment bridge. *Destructive:* arg presence says nothing about the target's own THING/SOMEONE cells (role guard).
- **WordNet.** *Constructive:* reading identity and POS (used as guards); antonym pointers as *alias candidates* checked against the 14; hypernyms only through the reviewed lexical-inheritance rule of F041. *Destructive:* POS-level exclusions tagged as hypothesis tier. Per F018–F019, WordNet is an anchor and a minor channel, never the spine; lexnames are file organization, not prime assignments.
- **USAS.** *Constructive:* field tags as *candidate retention* for the matching banks (an emotion-field tag keeps FEEL's +1 candidate alive and can trigger an omission challenge). *Destructive:* a lemma with alternative tags across unrelated fields marks the reading as needing disambiguation before any USAS-triggered rule fires.
- **EmoLex.** *Constructive:* omission-challenge trigger only. *Destructive:* none permitted (association cannot prove silence or neutrality either). If the F066 polar-exclusion hypothesis is later promoted, EmoLex could gain a destructive role (remove 0) under a source guard; today it cannot.
- **SentiWordNet.** Same as EmoLex but at synset level (so it satisfies exact-reading guards). Its objectivity score is not evidence of GOOD/BAD silence or written 0; it is an opinion score.

**Correlated families (must not be counted as independent confirmation):** SentiWordNet ⊂ WordNet identity; PropBank ↔ VerbNet via explicit mappings; FrameNet and VerbNet both describe verb events and frequently agree for structural reasons; EmoLex and SentiWordNet both reflect affective opinion; USAS and WordNet lexnames both are coarse semantic fields. F017's "six independent sources giving orthogonal decomposition" is therefore an overstatement; realistic independent channels are roughly: NSM hand table; verb-event structure (FrameNet/VerbNet/PropBank as one family); sense identity/POS/pointers (WordNet); coarse field (USAS); affective opinion (EmoLex/SentiWordNet as one family). Two sources in one family agreeing is one observation.

**Step 5 — Joint propagation to fixpoint.** Apply §2 rules until no candidate set changes. Order does not matter for monotone rules; conjunctions and coverage forcing read resolved values only. Record each firing (rule id, trigger cells, consequent). This is the Sally/Sam/Jake step (F057): two facts from different channels combine into a third no channel stated.

**Step 6 — Conflict handling.** Any S(c) = ∅ is written as conflict with the two (or more) firings that emptied it. No voting, no "strongest wins." A conflicted reading is excluded from production and queued for rule review; a recurring conflict pattern is a rulebook bug.

**Step 7 — Out-of-basis content.** If a certified explication component is a molecule or world fact (*bird* in *flock*, *water*, *species* membership), the reading gets an out-of-basis marker referencing Sparse Wiki ownership. The affected prime cells remain SIL, not 0: the definition is not silent on "bird-ness," but the basis cannot express it, and writing 0 would misreport. The marker is part of the output, so downstream knows the vector is a basis projection, not the whole definition.

**Step 8 — Bounded typed residual.** Remaining unresolved cells and joint coverage sets are packaged as typed empty fields with their allowed candidate sets (F078): reading anchor, resolved cells, and for each open cell/set the legal values. No prose. The model fills fields; outputs outside the candidate set are rejected, not reinterpreted. Accepted outputs are written as resolved and Step 5 re-runs (cascade, F069). Budget is bounded per reading (F067: on the order of 2–5 selections); if the budget is exhausted, the reading stays unresolved rather than being guessed.

**Step 9 — Omission challenge (F049).** For every cell that would be closed, the model is asked bank-wise, in the same typed format, whether a value should be present; a "present" answer re-opens the cell with its candidate set and re-runs Step 5. Only then is the cell closed. Whether closure writes 0 or SIL is the open F049/F059 decision (§7); the mechanism is identical either way.

**Step 10 — Write.** Vector + mask + provenance (every cell's history: which rule, which record, which model field, or which hand certification).

**Full-lexicon worklist.** Ordered: (a) 72 prime readings, hand-defined, closed; (b) frozen random 2–10K-frequency sample; (c) Zipf top-1000; (d) full. Each item is queued with its available source families; readings with no exact-grade record anywhere are queued *last* and flagged, not skipped, because their eventual encoding is the real test of the typed residual. Alias partners are processed together.

---

## 5. Worked example (illustrative, not a data claim)

I use *hate* in its verb reading ("I hate you"), because F057 and F066 already treat it as the model case. Nothing below asserts what any resource actually contains.

**Facts that would need certification for this to be a real run:**
1. Reading anchor: which synset / roleset / VerbNet member / FrameNet lexical unit are the "I hate you" reading, and that they cross-map to each other.
2. That the verb-event family (FrameNet frame type, VerbNet class predicate, PropBank arg labels) certifies an own-predicate affective feeling for this anchor — the trigger for F043's FEEL:+1 rule.
3. Whether the VerbNet class containing this reading also contains positive-affect verbs (if yes, the class cannot supply GOOD/BAD sign).
4. SentiWordNet scores for the anchor synset and EmoLex associations for the lemma (association tier only).
5. USAS tag path for the lemma and its alternatives.
6. Whether a published NSM-style explication of *hate* exists and which primes it uses in head positions (THINK, FEEL, BAD, WANT, SOMEONE, VERY are the plausible components; I am not certifying any).
7. Which of {GOOD/BAD} is one of the 14 alias pairs (§7).

**Propagation sketch (each line labeled by tier):**

- Start: 58 open cells.
- Reading is a verb (identity, exact grade) → modifier-type own-slot exclusions do not apply; any POS-based THING exclusion (hypothesis tier) would fire if it were a noun/adjective — here it leaves THING open to guards instead. *Hypothesis tier.*
- Own-predicate affective feeling certified (fact 2) → FEEL = {+1}. *GSE adaptation of F043, approved.* Also DO's candidate set loses +1 if the verb-event family certifies an experiencer (non-agentive) own event; written 0 vs SIL open. *GSE adaptation, needs MUST-NOT testing.*
- FEEL lit → dependency "a feeling reading speaks to GOOD/BAD": removes SIL from the evaluator coordinate. *This is a hypothesis.* The chart's "feel something good/bad" shows combinability, not a dependency; I cannot justify the dependency from supplied material. If not promoted, the evaluator cell stays {−1,0,+1,SIL} and the next steps still apply to the live members.
- Polar exclusion from affective-opinion family (fact 4): remove 0 → {−1,+1}. *Hypothesis tier (F066), source-guarded.* Without it, {−1,0,+1}.
- Sign: the verb-event class contains both poles (fact 3) → no sign from structure. One typed binary field goes to the residual: evaluator ∈ {−1,+1}. Output, say, BAD:+1 (= GOOD:−1 if aliased). Accepted if in set.
- Cascade: FEEL lit ∧ BAD lit → conjunction keeps VERY's +1 candidate alive and removes SIL (the joint affect+valence pattern is the one the chart's "very bad" licenses). *GSE adaptation; forces nothing on sign/intensity by itself.* VERY remains {0,+1} → one typed field.
- Coverage (hypothesis, from the explication pattern if certified by fact 6): at least one of {THINK, WANT} must be lit for a directed-emotion verb with a SOMEONE argument. If a rule elsewhere removes +1 from one, the other is forced. Otherwise a single set-valued residual field.
- SOMEONE: the "you" argument is a participant → role guard blocks own-slot SOMEONE from being forced by the argument. Whether *hate*'s own definition includes SOMEONE as a required valency component is an open rulebook question (valency encoding is not settled in the founder record).
- Omission challenge on all remaining cells; closure.

Plausible end state: FEEL +1; evaluator −1/+1 by alias convention; VERY, THINK, WANT resolved by three typed fields; DO and THING closed; everything else proven silent. The founder's "serviceable minimum" of F066 (⟨FEEL:+1, GOOD:−1, BAD:+1⟩) is the state after the second and fifth bullets; the rest is the "wayfinder" expansion toward completeness without hallucination.

**Degrees-of-freedom count.** Before any rule: product of 58 candidate-set sizes. After the structural steps: roughly 5–8 cells open with 2–3 members each, some coupled by coverage; that is a few thousand joint assignments at most, resolved by ~3–5 typed selections because each selection cascades. The "206 trillion" number the founder rejected (F067) comes from treating open cells as independent and counting cells rather than *decisions*; the coupling is the whole point.

**Two uncertainty spaces (F087).**
- *Definitional uncertainty* = how many legal vectors remain for this reading = ∑ log₂|S(c)| minus coupling. It *shrinks* as cells get lit, because every lit cell triggers rules that prune other cells. *Hate* ends with less definitional uncertainty than *bad* had before its hand definition, even though *hate* is "harder" — F083's point that atomics are the hard part because they must be defined, not imputed.
- *Inferential richness* = how many distinct downstream chains Regenesis can run from the vector. It *grows* with the number and variety of lit cells and the relations among them. *Bad* (one lit cell) supports few chains; *hate* (FEEL, BAD, THINK, WANT, VERY, with a SOMEONE valency) supports many: chains through what the subject thinks, wants, feels, and how strongly. These are different spaces: the first is about *which vector*, the second about *what the vector licenses*. They are negatively correlated in the regime that matters, and the design must report both: definitional residual (for correctness) and lit-cell count/relation count (for Regenesis), never one as a proxy for the other.

---

## 6. Staged formal design and falsifiable acceptance checks

**Stage 0 — Schema freeze.** 58 coordinates with names and alias map; mask states; relation row schema (trigger, consequent, guards, tier, positives, MUST-NOTs, provenance). *Check:* alias map has exactly 14 rows, each mapping two names to one coordinate with opposite signs; no name appears twice.

**Stage 1 — Prime readings (72).** Hand definitions with per-bank certification (value / 0 / SIL). *Checks (falsifiable):*
- closure(v) = v for all 72; zero conflicts; zero unresolved cells;
- for every alias pair, the two readings differ only in sign on the aliased coordinate — any other difference fails;
- every rule in the book fires on at least one prime or is marked "non-prime-triggered" with justification; a rule that fires on no prime and no ledger positive is deleted.

**Stage 2 — Rulebook ledger.** *Checks:* every row has ≥1 positive and ≥1 MUST-NOT; the engine reproduces every positive and refuses every MUST-NOT; every hypothesis-tier row has a named test in Stage 3.

**Stage 3 — Frozen random sample from rank 2K–10K.** The sample is drawn and hashed *before* any rule is tuned on it, from a declared frequency list (which list is itself an open decision). Size: a couple dozen readings per F075 is enough to start; the same sample is re-run after every rulebook change. *Checks:*
- per reading: conflict count, unresolved count after propagation, typed-field count, lit-cell count, SIL/0 split, out-of-basis markers — all reported, none hidden;
- F067's prior (≤5–10 open banks, 1–3 members each, ≤~5 typed decisions) is *measured*, not assumed; a reading exceeding it is a finding about the rulebook;
- ablation: removing one source family must not change any cell that was certified by another family (independence check); if it does, the families were double-counted;
- blind adjudication: a human reviews a subset of vectors and marks each cell correct / overstated / understated / should-be-silent / should-not-be-silent; both overstatement and understatement rates are reported (F045);
- hypothesis rows that produce a certified overstatement are demoted.

**Stage 4 — Zipf top-1000.** Same checks, plus: alias-pair consistency across the whole set; conflict rate trend; model-call budget per reading; fraction of readings with out-of-basis markers.

**Stage 5 — Full lexicon.** Same checks on a rolling sample; production excludes conflicted and over-budget unresolved readings; a changelog ties every rulebook diff to the readings it changed.

**Smallest practical prototype.** A relation engine over 58 candidate sets with the four-state mask, loaded with: the 14 alias rows; the chart-derived combinability/hosting rows; the two approved F043 positives; the F057/F066/F067 rows as hypothesis tier with their MUST-NOTs; the 72 hand definitions. Demonstrate three things: (1) prime closure is a fixpoint; (2) on three to five real non-atomic readings whose native records are *transcribed from the actual resources* (not invented, not a closed toy universe — the certification list of §5 is the template), propagation produces the expected candidate-set shrinkage, at least one coverage forcing, and at least one deliberately constructed conflict that is recorded rather than resolved; (3) the typed residual contract works with a stub (a human filling the typed fields) before any model is wired in, proving the field format carries enough to decide without prose. This does not require a source-availability census: the worklist tags missing families per reading as it goes.

---

## 7. Open decisions and ambiguities the design must carry

1. **GOOD/BAD as one coordinate or two.** F067 writes ⟨GOOD:+1, BAD:−1⟩ and F066 ⟨GOOD:−1, BAD:+1⟩ as two cells; the prompt's "14 opposite-pole aliases" suggests they are one coordinate. If one, writing both is redundant and sign convention must be fixed; if two, the alias count and the 58 figure need rechecking. F083's "really 53, or 58, or however many" shows the count itself is not settled in the founder's mind.
2. **0 vs silence for excluded banks.** F057 ("adjectives cannot carry THING") does not say whether THING is written 0 or left empty; F059 demands empty for definitional silence; F049 approved "provisional closure to zero"; F088 says "zeros or empty banks." A single policy is needed per rule type.
3. **Noun/sentiment and POS-based laws.** F057 asserts nouns have no definitional value judgment while verbs may; this is a hypothesis with plausible counterexamples and conflicts with any use of SentiWordNet/EmoLex on noun readings. F014–F015 make POS a "strong constraint"; F017–F018 demote it to "tiny." Resolution adopted here: POS is a guard and a hypothesis-tier trigger, never a law — but the founder should confirm.
4. **Evaluator/descriptor "mutual exclusion."** F067 states it is explicit in NSM; the chart as described supports a modification-direction restriction, not co-occurrence exclusion. Hosting relation proposed instead; needs founder sign-off.
5. **Model-call budget.** F015 "<1% of the time"; F047 "I don't expect the lexicon to be substantially built with just symbolic rules"; F080 "99.8% without a model." These are compatible only if the model is called rarely *per cell* but on most *readings*; the target metric (per cell? per reading?) must be chosen.
6. **Residual size prior.** F066 "20–30 degrees of freedom" vs F067 "5–10 banks, 1–3 assignments, 2–3 decisions." Later supersedes, but it is a guess (F066: "my guesses tend to be pretty good") and must remain a measured quantity.
7. **Which words are "easy."** F070 wants the easy end of Zipf first; F072 and F083 say primes are hard (defined, not imputed) and the 2–10K sample is easier. Worklist order adopted here follows F075/F083; confirm.
8. **Association resources as destructive evidence.** F066 would let emotive valence remove 0; F057 says association is not definition. Carried as hypothesis-tier with source guard; founder may want it promoted or dropped.
9. **Inheritance.** F041 permits broader-class signs only via a reviewed rule; the natural source of the class relation is WordNet hypernymy, which F018–F019 distrust. What "reviewed" means and which resource supplies the class are unspecified.
10. **KIND semantics (F007).** +1 for readings that denote a category/type; NSM's KIND is relational ("kind of"). The bridging assumption from the prime to a "denotes a category" reading is unstated.
11. **Valency encoding.** F067's intensifier and F057's argument discussion imply that some readings require companions (a descriptor needs a host; a directed emotion needs a SOMEONE). Whether valency is encoded in the vector, in the mask, or left to grammar is not decided in the founder record.
12. **Typed input content (F078/F080).** The model gets fields and numbers, no prose or gloss — but it must still know *which reading* it is filling. Whether lemma + POS + resource ids suffice, and whether that is "prose," is open.
13. **Frequency list for the frozen sample and the top-1000.** Unspecified.
14. **Unavailable references.** Harmonizing, triagegeist, wayfinder, significance_weighting (F068's "feasibility scoring of conditional collapse"), constrained-hallucination, SquishOS AST contract, the cell_tracking "what an object is" thesis and its image (F060), and the "Keller et al." citation in F057 are all invoked but not supplied. Any rule that depends on them (notably feasibility scoring for competing residual assignments) cannot be justified from the supplied material and is a placeholder.
15. **Source independence (F017).** The "orthogonal decomposition" premise assumes independent channels; the supplied source facts show several are identity- or mapping-correlated (§4). The design should treat families, not resources, as channels; the founder should confirm this reframing.
16. **Unpaired range.** F040 fixes unpaired coordinates to 0/+1; F046 says "balanced ternary." F040 governs, but every rule must be checked for accidentally assuming −1 on an unpaired coordinate.

I have not claimed any empirical result; every mechanism above is specified so that a run on real records will either reproduce the predicted behavior or show which rule row is wrong.