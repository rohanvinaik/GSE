# Independent second reading: design check

Conventions used below: **E** = what Rohan's words or the appended document literally say; **I** = my inference from those texts; **U** = what neither text settles. No code is cited as evidence; it is gone.

---

## 1. The construction principle for non-atomic words, in plain English

**E (Rohan):** The definition of a word is not stored anywhere as a value. Each source is a blind man: what it reports is correct about the part it touches, and wrong only when it is allowed to infer the whole from that part. The job is to let each source assert its part, and then let those parts talk to each other, because a correct assertion about one aspect (e.g. "this reading is an adjective") removes most of the possible joint assignments on every other aspect. That collapse is why a cheap model suffices for whatever is left, and why the symbolic layer must be measured first, with raw gloss text essentially never in the loop.

**E (document):** The object being narrowed is a joint feasible set F of complete assignments (reading, slots, obligations, realizations, all 58 signed write states, provenance), not 58 separate ternary questions. A fact filters F; because reviewed laws couple roles across banks, one fact can remove configurations in banks it never names. Propagate to a fixed point, read cells that are constant over all survivors as entailed, and leave genuinely open cells open.

**I — the two different operations Rohan distinguishes:**

- **Axiomatic definition (primes).** A prime is *stipulated*: its vector is the basis certificate itself — its own coordinate carries the prime's sign, all other canonical coordinates are silent by the definition of an atom on this basis, and the 14 opposite-pole names are not separate definitions but the negative sign of an already-counted coordinate. Nothing is inferred from sources. Rohan's "words that are axiomatic are harder, because they're meant to be defined, not imputed" means the difficulty is in *choosing and reviewing* the basis, not in computing anything.
- **Imputation (non-atomic readings).** A non-atomic reading's vector is *derived*: every source-native typed fact about that located reading is converted into a constraint on F; constraints intersect; cross-bank couplings cascade; the result is whatever is entailed across all survivors, plus a named small residual. "Relatively trivial" in Rohan's words means: once the atoms are fixed and the coupling laws are reviewed, a non-atomic word is a conjunction of atom-components selected by the surviving constraints, and the remaining uncertainty is small enough for a typed model call or a second symbolic channel.

**U:** Rohan's phrase "impute for combinations of words" could mean (a) non-atomic words as combinations of primes, or (b) multi-word expressions. The document reads it as (a). Rohan's "72 primes (really 53, or 58, or however many)" does not confirm the document's 58; the document asserts 58 and additionally reports a NUMBER drift in a runtime registry. The count is therefore not fixed by Rohan's words and must be settled explicitly before any prime proof is printed.

---

## 2. What an executable proof must print

The three things it must not be: an old synthetic Sudoku (hand-declared universe, hand-declared rule, ablation on that rule); a source-availability census ("10 lemmas have FrameNet records"); a tally of one-cell writes on a source's own candidate reading that never reach the target reading.

**For each of the 72 prime names (I, from the document's tier-0/tier-1 description):**
- The alias map: which 14 names collapse onto which 14 coordinates, so that the printed universe has 58 columns, not 72.
- The certificate per atomic prime reading: canonical coordinate, sign, and the statement that every other canonical coordinate is ∅ *by definition* (not by any source).
- A MUST-NOT companion for at least some primes: a same-spelled non-atomic English sense (the document names homographs as a hazard) that does **not** receive the atom's all-other-silent closure. Without this, the prime proof says nothing about the boundary between definition and imputation.
- Confirmation that the resultant prime vector is produced with *zero* lexical source premises consulted — if a source premise appears in a prime's derivation, the proof has violated Rohan's "defined, not imputed."

**For each reading in the frozen random sample (I):**
- Sample freeze: rank source, rank window (2,000–10,000), seed, item list digest. "Frozen" means a reader can re-draw the identical list.
- Reading identity and link proofs: lemma, POS, which source records were linked to the target reading, and whether each link is an exact key, a bounded certified choice, or an assumption. Assumed links must be labelled as such on every derivation that uses them.
- The declared universe and counting rule before any premise: every canonical cell with its initial domain (including ∅ and UNRESOLVED as members where applicable), slot/role variables, obligations, and the OTHER branch where it exists.
- Each hard premise in order: source, record ID, field value, level, rule ID, guard that was proved, and the exact domain reductions (cell, removed values, remaining values). A premise with an unproved guard must be printed as "removed nothing."
- At least one reduction per demonstrated reading that touches a cell in a bank the premise did not name — this is the cross-bank cascade Rohan is asking about. If no reading in the sample shows one, the proof must say so explicitly.
- Fixed-point state under two premise orders, shown equal.
- A conjunctive interaction witness on a **real** reading: configurations surviving each premise alone and their plain intersection, eliminated only when the guarded joint rule fires. The document is explicit that a large combined log-count gain is not this witness.
- A bottom-up entailment: at least one cell whose value was never asserted by any premise but is constant over all survivors.
- A coverage/forcing instance where a named exhaustive unit forces a realization, together with the control: remove the certificate and show the same local exclusions no longer force it. This must run on sample data, not on the old toy.
- Negative controls on real records: a missing source family, a POS-mismatched record, and an open-world zero flag each eliminate zero worlds.
- Support counts: |F| before/after each premise within the declared universe, with the gain, and with the explicit caveat that a product of local domain sizes is only a bound. Duplicate evidence paths for one assignment must not multiply the count.
- The final record: all 58 canonical cells with state ∈ {−1, 0, +1, ∅, UNRESOLVED, CONFLICT} and each state's derivation chain. If any cell is 0 or ∅ it must show a derivation; "nothing wrote it" is not a derivation. The 14 aliases are emitted from canonical states, never counted as additional writes.
- The residual, named: which cells remain open, their surviving domains, and the cross-cell constraints among them. This is the number Rohan's "tiny residual" hypothesis is tested against.

**Aggregate over the sample (I):**
- Per rule family: how many reductions reached the *target* reading versus stayed on a source's own candidate reading.
- Distribution of residual-cell counts per reading; count of CONFLICT, UNRESOLVED, abstained, unavailable, and out-of-basis cases, by configuration family and source coverage.
- A reviewed subset audited for both false additions and false omissions, with the omission challenge run against the cross-bank obligation unit.
- Separate columns for (a) sign cells written, (b) silence cells written, (c) cells merely narrowed. Mixing these — e.g. counting "modifier-silence" writes alongside sign writes — is exactly the one-cell tally the question warns against.

---

## 3. Passages that conflict with the newer instructions or contain a demonstrable defect

**(a) References to deleted code as active or as comparison material.** 

> "The active pilot in `lexical_factor_compiler.py` operates on a **FrameNet lexical unit as its own candidate reading**."

> "The runnable `lexical_factor_compiler` CLI now calls `compile_symbolic_packet`, and `lexical_symbolic_batch` runs that same path over a surface cohort after explicit form routing. … The older `compile_packet` remains an isolated historical comparison function with no production caller."

> "The present [factor compiler] is a partial prototype. Its real *hate.v* run established provisional FEEL:+1 and GOOD:−1, with BAD:+1 derived … The next builder must replace that construction path with the joint-support and coverage contract above, while keeping native source readers."

**E:** Rohan said "Literally throw away the bad code" and "I'd rather just re-do the work than risk you re-poisoning yourself AGAIN." **I:** Every sentence that describes what a compiler "now calls," what remains as a "comparison function," or what a run "established" must be retired; none of it exists and none of it was design authority anyway. The clause "while keeping native source readers" is an instruction to retain old implementation; Rohan did not carve out an exemption in the quoted words. **U:** Whether readers are "bad code" is not decided by either text. The document should not pre-decide it; the design should specify what a reader must emit (native level, field, units, version, lineage) and leave the question of reuse to Rohan.

Minor but related: "with BAD:+1 derived" is wording that treats the alias as a derivation step, which the tier-0 section itself says would double-count. Narrow to "BAD:+1 is the same state by name identity."

**(b) Receipts cited as proof.**

> "The first [executable semantic-Sudoku receipt] … proves those propagation and ablation mechanics on a declared finite universe and reads real native records for one common non-atomic reading."

**E:** Rohan asked for "the proof … from each of the 72 primes … plus the 2-10K random sample." The receipt describes a single reading with assumed source alignments and an unresolved INTENSITY cell, on a demo that is now deleted. **I:** "Proves" must be downgraded to "a dated observation of a deleted demo." It cannot be the proof Rohan asked for, and the document should stop using it as an acceptance milestone. The same applies to the paragraphs reporting "eight hand-picked lemmas … 111 eligible source-local candidates with 29 written cells" and "24 mid-frequency surfaces … 52 cells across 493 candidates, with 85 modifier-silence cells": these are source-local tallies on hand-picked or 24-item sets, and the document itself concedes they "describe rule coverage, not accuracy or completed definitions." They are the census/tally the question warns against and should be moved out of the design into history.

**(c) Staging that does not match Rohan's spec.**

> "Before a top-1,000 test, demonstrate the **symbolic-only** degree-of-freedom collapse on non-atomic readings … Word frequency orders audit depth, not build coverage."

**E:** Rohan specified the 72 primes plus a frozen random sample at rank 2,000–10,000 "for even EASIER/more robust constraint collapse." **I:** The document's staircase (hand-picked → 24 surfaces → top-1,000 → full worklist) is not Rohan's. The design should name his two cohorts as the acceptance cohorts and treat frequency-ordered audit as a later activity.

**(d) An internally contradictory registered rule — demonstrable from the document alone.**

> "Adjective `Emotions_by_stimulus` frame with Experiencer and Stimulus roles, sole USAS `E4.1+`, and NRC `joy=1, positive=1, negative=0` | GOOD:+1 for this affective adjective candidate; the FEEL/CAUSE role remains unresolved."

This conflicts with three earlier statements in the same document:

> "A bare FEEL:+1 with no role and scope is insufficient for that elimination."

> "Specify whether GOOD is the feeling's hedonic tone or an attitude toward an object. *Pity*, *admire*, guilt, and schadenfreude show why POS alone cannot supply that role. Candidate relation until each guard and consequent is registered."

> "NRC Emotion … Cannot assert alone: A zero flag as lexical negation or a positive flag for all senses."

**I:** The rule writes a GOOD sign while admitting the role it is a sign *of* is unresolved, and uses an NRC lemma-level positive flag as a necessary antecedent of a sense-level sign. By the document's own standard, GOOD without a role is not a located definitional claim. This row must be demoted to "candidate relation" or re-guarded so that the role is proved before GOOD is written. The *hate.v* conjunction row has the same structure (FEEL:+1 and GOOD:−1 with "directed-dislike" asserted by the rule author rather than proved by a field) and should be reviewed under the same question.

**(e) Gloss tokens re-entering through a typed side channel.**

> "The same Kaikki sense's typed `links` targets are exactly `very` and `small`, so a second guarded rule adds INTENSITY:+1."

> "The located *identity.n* sense whose link targets are `sameness` and `identicalness` … writes SAME:+1. … The *begin.v* reading with link targets `start`, `initiate`, `first` … writes START:+1."

**E:** Rohan: "I don't think we EVER need the raw gloss text." Document: "Cannot assert alone: … gloss-token votes … No new general clause parser on this path." **I:** A Kaikki `links` list is the set of linked tokens of the gloss. Rules that fire on "link targets are exactly {very, small}" or "at least two distinct concordant link anchors" are gloss-token votes under another field name. Whether Rohan permits typed link fields as a symbolic channel is **U** — he said nothing about them — but the document cannot simultaneously forbid gloss-token votes and license these. Either declare `links` an admitted typed channel with its own contract (what a link asserts about the reading, and that it is not evidence of exhaustiveness), or narrow these rules out. As written, the document's claim "with no gloss parsing" for the *tiny* bridge is not accurate about its own mechanism.

**(f) An unsourced appeal to authority.**

> "feeling *love.n* has KIND:0 under Rohan's rule."

**U:** No such rule appears in Rohan's quoted words. It also writes a reviewed *middle* (0) rather than silence (∅) on an unpaired coordinate, and the document never says what a "middle" means on a {0, +1} coordinate. Narrow: either cite the rule and define unpaired-0 semantics, or remove the example.

**(g) Registry entries listed without the witnesses the registry demands.**

> "WordNet `noun.person→SOMEONE`, `noun.artifact`/`noun.group→SOMETHING`, `noun.event→HAPPEN`, `verb.motion→MOVE`, and `verb.communication→SAY` … Additions to this registry require a positive and a MUST-NOT witness per rule family."

**I:** The entries are presented as admitted while the admission condition (positive + MUST-NOT witness per family) is not shown for any of them. A lexname is a classification of the whole category; the document elsewhere forbids "blanket ancestor-vector inheritance" and "applying one frame's predicate to every class member." Lexname→prime is structurally the same move one level up. **U:** Whether every member of each lexname satisfies the own-denotatum/own-predicate guard cannot be determined from the document; it must be checked per family before any of these counts toward Rohan's proof.

**(h) Residual-size prior attributed to Rohan.**

> "The 'often two or three residual model choices for common readings' claim is Rohan's empirical prior, to be measured."

**U:** Not in the quoted words. Keep as a hypothesis, drop the attribution unless sourced.

---

## 4. What can be derived from source-native typed fields alone

I am not building a catalog; I am sorting what the document already names into three bins.

**Derivable without a model or gloss (E/I, with the stated conditions):**
- **Tier-0 alias identity** and **atomic prime certificates** — no source involved.
- **Morphology routing**: Kaikki `form-of` + `form_of.word` sends an inflection to a lemma; a residual non-form reading on the same spelling is retained. Typed, reading-level, no gloss.
- **Pure-modifier slot** for a located adjective reading: remove SOMETHING:+1 as an *independent denotatum in that slot*. Requires reading-level POS (a Kaikki sense has one); lemma-level POS from USAS/NRC does not suffice, and no other slot and no substantivized reading is touched. Silence (∅) in that slot needs a separate exhaustiveness certificate, which no named field supplies.
- **Own event/denotatum class on a source's own candidate reading**: a FrameNet LU in a Size frame (own property), Motion/Self_motion frame (own change of place), Process_start/Activity_start (own START), People_by_vocation (own SOMEONE), etc. These are properties of the LU as its own reading. They *stay* on that candidate reading.
- **Argument structure (S)**: PropBank roleset + VerbNet class + FrameNet core roles constrain arity and role slots of the event candidate. These narrow S, not P directly.

**Apparent joins that need additional proof before they are legitimate (I):**
- **Any transfer from a FrameNet/WordNet/VerbNet candidate to a Kaikki target reading** needs a *same-reading* proof. The document's *tiny* bridge uses uniqueness ("sole non-form adjective sense," "unique FrameNet Size LU") as the alignment. Uniqueness in each inventory is not identity across inventories; it is a bounded choice that requires a certificate stating that when each inventory has one adjective reading they are the same reading. Without that certificate the derivation must be labelled "assumed link."
- **Size pole via Kaikki `hypernyms.word=small`**: `hypernyms` is a typed relation field, not gloss, so it is admissible evidence of the own-size pole; but "the hypernym names a property of the reading's own entity" is an own-role claim that the Size frame's Entity role is supplying — hence the join depends on the same-reading proof above.
- **MOVE from VerbNet `motion` common predicate or from `Cause_motion`**: the predicate is stated of the Theme. Transferring it to the verb's own predicate requires proof that the Theme's motion *is* the verb's own content (intransitive self-motion) rather than a caused participant's motion. The document's own boundary ("a moving participant does not transfer MOVE") applies; own-role proof needed.
- **GOOD/FEEL from Emotions_by_stimulus + USAS + NRC**: needs the FEEL-versus-CAUSE role resolved and a declaration of what GOOD is a sign of. Own-role proof needed; currently a candidate relation (§3d).
- **SentiWordNet polarity**: only after an exact synset join *and* the target's own evaluative predicate is aligned. Both are joins to be proved.
- **USAS single-tag selection**: the document uses "exactly one recorded tag for that POS" as the guard. That is a lemma/POS-level fact; it still needs a reading-level alignment to apply to one Kaikki sense among several.
- **Kaikki `links`-based INTENSITY / SAME / START**: needs a decision (§3e) on whether `links` is an admitted typed channel at all, and if so, a contract that link anchors are evidence of a component, not of coverage.
- **WordNet lexname → prime** and **VerbNet class-common predicate → prime** on their own candidates: need the per-family positive and MUST-NOT witnesses the registry requires; coverage of the whole lexname/class by the guard is unproved.

**Cannot determine from the document:**
- Any **written 0** on any coordinate. No source field is identified that yields a reviewed middle, and the semantics of 0 on an unpaired {0, +1} coordinate is not defined.
- Any **∅ (proved silence)** beyond the modifier-slot case, because no source field is given a closed-world contract; the document explicitly says "no global 'absence means false' rule exists."
- **KIND:+1** from a category-denotatum reading: no source field for "the target itself denotes a category" is named.
- **MANY/QUANTITY** on collectives: the document calls this a candidate relation pending a located member obligation.
- **Out-of-basis obligations** (e.g. bird-member restriction of *flock*): which field would locate them is not stated.
- **Any completed vector**: the document identifies no mechanism that would certify the cross-bank coverage/omission challenge from source-native fields alone, so under this document a symbolic-only run can produce entailed signs and a named residual, but not a certified complete definition for a non-atomic word. Whether Rohan's "99.8% without a model" transfers to definitions is, as the document itself says, a hypothesis the random-sample proof is meant to test.