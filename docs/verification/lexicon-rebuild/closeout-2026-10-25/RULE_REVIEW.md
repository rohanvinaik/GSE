# Rule review for admission — 2026-10-25

**Decided (F144):** Rohan approved every recommendation below. Rows 1–18 are approved as recommended, with the stated changes where given, and 3b. Row 8 is replaced by the emotion slice, and rows 19–22 and 24a are to be built, with the *pleasure* scope question. Rows 23 and 24b are withdrawn. The CAUSE decision is option B (row 26 dropped), and F057's default holds for the feeling nouns. `rule_decisions.json` records each decision. A rule writes cells once its `review_state` in the rulebook becomes `FOUNDER_APPROVED`, which for a rule with a stated change follows the change and its tests.

Rohan's policy (F129): review every rule, and admit it when we agree it fits the founder's words. This packet covers all 18 rules that can write a cell today. That includes the five laws approved earlier, because F007 and F043 were answers to framed questions. It also covers the proposed emotion rows (19–24) and two causation rows (25–26).

**How to answer:** by row number. For example: "approve 1, 4–6; approve 9 with the change; discuss 7".
- Approval sets `review_state` to `FOUNDER_APPROVED`. `rule_decisions.json` records it mechanically.
- Unified admission has landed: an unapproved rule writes no cell. Until rows are approved, the default build constructs no readings.
- A "with change" approval admits the rule after the change and its tests land.

**What you're asked.** The semantic questions in earlier drafts are answered from the published NSM literature, with quotations, in `NSM_RESOLUTIONS.md`. That covers the two contract questions and three of the four stage-3 founder questions. When sources conflict, the later NSM analysis wins (F137). The primary works you supplied (F141) are now read, and they revise rows 19–24 in five places (`NSM_RESOLUTIONS.md` §10). What's left for you:
- whether each row fits your founder words, including one proposed scope question that keeps *pleasure* out of the emotion template;
- one place where the literature conflicts with them: GOOD for the feeling nouns in row 21, all 52 of them. F057 says nouns carry no sentiment weight, with *hatred* as its example.
- **the CAUSE decision (rows 25–26), on its own, not in a batch.** NSM has no CAUSE, so the literature can't say what GSE's CAUSE is for. Option B follows design §7.3 and is recommended.

**Evidence base**
- Counts come from the frozen VerbNet audit (`symbolic-native-audit-2026-10-25/audit.json`: 1,310 frames, 3,626 member strings), re-run through the current `frame_constraints`.
- Adjective counts come from the builder's own `source_matches`, run over every USAS lemma (`evidence/source_rule_reach.json`).
- Counts are per frame or per word, not per binding.
- The join counts, the emotion population and the definition search are in `evidence/`. Each output is complete, and the README says how to re-run it.

## Summary

| # | Rule | Writes | Verdict |
|---|---|---|---|
| 1 | OWN_AFFECTIVE_FEELING | FEEL +1 | Fits |
| 2 | OWN_PHYSICAL_CHANGE_OF_PLACE | MOVE +1 | Fits, but nothing triggers it; make it the one writer of MOVE |
| 3 | MODIFIER_LACKS_INDEPENDENT_OBJECTNESS | SOMETHING 0 | Fits; extension 3b follows from the literature (adjectives qualify, they don't denote) |
| 4 | FEELING_DENOTATUM_IS_NOT_A_CATEGORY | KIND 0 | Fits |
| 5 | OWN_DEGREE_BEARING_CONTENT | INTENSITY +1 | Fits; stage 3 extends it to the atoms the chart grades with VERY |
| 6 | USAS_OWN_QUALITY_POLE | GOOD ±1 | Fits; its join certifies under the contract after row 8 |
| 7 | USAS_OWN_SIZE_POLE | BIG ±1 | Fits with change: Size only, because Dimension carries a measurement, not a pole |
| 8 | USAS_OWN_HAPPY_SAD_STATE | GOOD ±1, FEEL +1 | Replaced by the emotion slice; *mad* stays the counterexample |
| 9 | VN_EVENT_MOTION | MOVE +1 | Fits; route it through 2 |
| 10 | VN_EVENT_CONTACT | TOUCH +1 / 0 | +1 fits; the 0 branch is wrong (6 frames); keep the negation in the derivation |
| 11 | VN_AFFECTIVE_STATE | FEEL +1 | Fits with change: record who feels, and require a USAS E tag on the verb (*believe*, *value*) |
| 12 | VN_DESIRE | WANT +1 | Fits |
| 13 | VN_VITALITY | DEAD (ALIVE −1) | Fits |
| 14 | VN_EXISTENCE | EXIST +1 | Fits with change: only for a change of existence, or the existence class itself |
| 15 | VN_POSSESSION | HAVE +1 | Fits |
| 16 | VN_BEGIN | START +1 | Fits |
| 17 | VN_END | END (START −1) | Fits with change: aspectual classes only, since *hurry* fails a cancellation test |
| 18 | VN_USAS_PERCEPTION_MODE | SEE +1 / HEAR +1 | Fits |
| — | 72 atomic declarations | one cell each | Deferred to the combinatorial-profile review (F091, stage 3); the builder doesn't use them yet |
| 19–24 | First emotion slice (revised from the primary texts) | see draft | 19–22 and 24a for approval, with the *pleasure* scope question; 23 and 24b withdrawn (`EMOTION_SLICE_DRAFT.md`) |
| 25–26 | The CAUSE decision (new) | B: CAUSE +1 for VerbNet `cause`; A: BECAUSE +1, and CAUSE empty everywhere | Your decision, on its own; B recommended (design §7.3) |

## Rows

**1. OWN_AFFECTIVE_FEELING** (law, currently approved)
- **Writes:** FEEL +1.
- **Fires when:** a reading asserts `own_denotatum = affective_feeling`. Only rule 8 asserts that today.
- **Basis:** F043, which approved the proposal "the target reading's own explicit affective-feeling denotatum warrant FEEL:+1."
- **Verdict:** fits.
- **Note:** rule 8 also writes FEEL +1 directly, as a "companion". One writer per consequence is cleaner, so drop the companion when 8 is revised.
- **Witnesses:** *delighted* (adjective) is the positive case. The must-not case is "a person associated with love"; no rule asserts the guard for person nouns.

**2. OWN_PHYSICAL_CHANGE_OF_PLACE** (law, currently approved)
- **Writes:** MOVE +1.
- **Fires when:** a reading asserts `own_predicate = physical_change_of_place`. Nothing asserts this, so it never fires, and rule 9 writes MOVE on its own.
- **Basis:** F043, approving "its own explicit physical-change-of-place predicate warrant MOVE:+1."
- **Verdict:** fits, but unused.
- **Change:** rule 9 asserts this guard instead of writing MOVE, which makes this law the single writer of MOVE.

**3. MODIFIER_LACKS_INDEPENDENT_OBJECTNESS** (law, currently approved)
- **Writes:** SOMETHING 0.
- **Fires when:** `own_role = modifier_property_only`. Rules 6–8 assert this for their own adjective reading.
- **Basis:**
  - F057: "Can an adjective or adverb carry a 'THING: +1' score? Of course not."
  - F088: the box/big sub-atomic relation.
  - F118: 0 is explicit absence.
- **Verdict:** fits.
- **Witnesses:** *big* (adjective) is the positive case. NOUN records never trigger an adjective rule, so a noun reading such as "the poor" isn't touched.
- **3b, proposed extension (separate approval):** write 0 for the other substantives too: I, YOU, SOMEONE, PEOPLE, BODY, KIND and PART.
  - **F057's test** ("if I yelled 'BIG'… 'a big WHAT??'") is about the adjective having no referent of its own. That covers every substantive, not only THING.
  - **The literature settles the contract question this waited on.** Frames hold "core argument structure" (G12 p.16), so a participant in a word's content is a role, not a cell.
  - **Adjectives qualify; they don't denote.** GW2014 p.56, restating GW07: "heavy things or hard things are not conceived of as 'kinds of things' at all. While categorization is based on the concept kind, 'qualification' is based on the conceptual prime like." And p.59: "If I say that the soup on the table in front of me is salty, I do not mean that it belongs to a category of salty soups."
  - **So the extension holds**, and KIND and PART, NSM's relational substantives, belong in it. SAME/OTHER are determiners in NSM and stay out (*same*, *other*).
  - *lonely*'s and *sympathetic*'s "other people" are roles. See `NSM_RESOLUTIONS.md` §2.

**4. FEELING_DENOTATUM_IS_NOT_A_CATEGORY** (law, currently approved)
- **Writes:** KIND 0 when FEEL is +1.
- **Fires when:** under rule 1's guard. Rule 1 also forces FEEL there, so in practice this writes one cell.
- **Basis:** F007, which approved KIND +1 only when "the sense denotes a category or type itself… a feeling such as 'love' gets zero."
- **Verdict:** fits.
- **Witnesses:** *happy* → KIND 0 is the positive case. *emotion* (noun; FrameNet Feeling) names the category of feelings, so it should get KIND +1. No rule covers it yet.

**5. OWN_DEGREE_BEARING_CONTENT** (law, currently approved)
- **Writes:** INTENSITY +1.
- **Fires when:** `own_degree_domain = graded_property`. Rules 6–8 assert this.
- **Basis:** F125–F126: "intensity encodes that there is a measure of intensity that is relevant. 'Number' encodes what the intensity *is*."
- **Verdict:** fits.
- **Stage 3, recommended from the chart:** the GOOD and BIG atoms carry no INTENSITY today (turn-1 review), while the built *good* gets +1.
  - CH's VERY box grades these, and also FAR/NEAR, LONG_TIME/SHORT_TIME and WANT: "very big, very small, very good, very bad, very far, very near, a very short time, a very long time / I want it very much (=very)".
  - Record that in all of these atoms' combinatorial profiles (design §2), then write INTENSITY +1 on them through this law, so each atom and its built word agree.
  - QUANTITY waits for the quantifier scale family (F096). Nothing in this pass depends on it. See `NSM_RESOLUTIONS.md` §6.
- **Witnesses:** *tiny* is the positive case. Affect ratings such as VAD arousal never trigger it.

**6. USAS_OWN_QUALITY_POLE** (source rule, unreviewed)
- **Writes:** GOOD ±1, with the sign taken from the USAS + or −. It also asserts `modifier_property_only` and `graded_property` for its reading, which triggers 3 and 5.
- **Fires when:** a USAS adjective tag A5.1± (no slash) appears, and the same spelling has a FrameNet adjective LU in Desirability. 38 words. That makes 39 matches, because *magnificent* has two USAS records; the earlier "39 words" counted matches.
- **Basis:**
  - F066: "<FEEL:+1, GOOD:-1, BAD:+1> is a servicable minimum."
  - F076: good and bad are one signed coordinate.
  - F067: evaluators.
- **Verdict:** fits.
- **Witnesses:**
  - *excellent* (A5.1+++) and *terrible* are positive cases.
  - Secondary senses are handled correctly: *poor*'s first tag is money (I1.1−), yet its quality reading gets GOOD −1.
  - *small* has A5.1− but no Desirability LU, so it gets no quality reading.
- **Join:** A5.1 with Desirability is a same-field pair, so it certifies under the contract after row 8.

**7. USAS_OWN_SIZE_POLE** (source rule, unreviewed)
- **Writes:** BIG ±1, plus the same two asserted facts as rule 6.
- **Fires when:** a USAS adjective tag N3.2± appears with a FrameNet adjective LU in Dimension or Size. 28 words.
- **Basis:** F067 (descriptors) and F076.
- **Verdict:** fits with change. The sources answer the earlier question; the change takes effect when you approve the row.
- **Change:** join with Size only.
  - FrameNet's Dimension frame says its adjectives "must appear with a measurement expression like 5 cm" (*tall*.a: "used with a number"). Its *long* and *thick* are therefore measurement senses with no pole: "2 cm long" isn't big.
  - Size, by its own definition, concerns three-dimensional space, "not primarily to its weight, density, or length".
  - This drops *long* and *thick*; 26 words remain.
  - Whether a length pole (USAS N3.7, "length & height") should ever write BIG would be a separate rule. I'm not proposing one.
- **Witnesses:** *enormous* and *tiny* are positive cases. *medium* has an unsigned N3.2, so it gets no pole.

**8. USAS_OWN_HAPPY_SAD_STATE** (source rule, unreviewed)
- **Writes:** GOOD ±1 and FEEL +1. It also asserts `affective_feeling` (triggering 1 and 4), plus the degree and modifier facts.
- **Fires when:** a USAS adjective tag E4.1± appears with a FrameNet adjective LU in Emotion_directed. 35 words.
- **Basis:** F043 and F066.
- **Verdict:** revise into the emotion template (`EMOTION_SLICE_DRAFT.md`). Per F129 it lacks the thinking part, and it covers only E4.1.
- **Counterexample: *mad*.** USAS lists *mad* as B2−/X1, S1.2.6−, X5.2+ and E4.1+. FrameNet's *mad*.a is Emotion_directed, defined "FN: slightly angry". Joining them by spelling makes "mad = a happy feeling".

**The join for rows 6–8 and 19–21.** This replaces the first-tag proposal; per F124 it is a rule, not a word override.
- **Why not the first tag.** The USAS guide arranges the tags "in approximate rank frequency order, most likely tag first, to assist in manual post editing". That is frequency, not sense identity, so a first tag can't certify that a FrameNet unit is the same reading.
- **Contract table.** A pair certifies only when both sources' own definitions name the same field:

| USAS category (guide) | FrameNet frame (definition) | Join | Reach |
|---|---|---|---|
| A5.1, "evaluative terms depicting quality" | Desirability: "an Evaluee being judged for its quality" | certified | row 6: 38 |
| N3.2, "terms of measurement relating to size" | Size: "three-dimensional space … not primarily to its weight, density, or length" | certified | row 7: 26 |
| N3.2 | Dimension: its adjectives "must appear with a measurement expression like 5 cm" | none: a measurement carries no pole | *long*, *thick* |
| E5−, E6− | Fear (inherits Emotions_by_possibility) | certified | 9 slice readings |
| E2±, E3−, E4.1±, E4.2±, E5−, E6− | Emotion_directed, Experiencer_focus, Emotions_by_stimulus: "a particular emotional response", including *bewildered* and *astonished* | typed discriminator | row 8: 35; slice: 150 |

- **Discriminator.** One typed question per pair, answered MATCH, DIFFERENT_READING or UNRESOLVED.
  - It is given the USAS alternative, the word's other alternatives and the FrameNet frame. Rank goes in as evidence only, and only MATCH joins.
  - Controls: *mad*, *rue*.v and *misery*.n must come back DIFFERENT_READING (see the emotion draft); *happy* must come back MATCH.
- **No cheaper certification.** "One emotion alternative on each side" would certify *mad* wrongly: USAS and FrameNet each list exactly one emotion reading for it, and they differ.
- **Source contract.** The adapter reads FrameNet's `luIndex.xml`, which omits the 59 units FrameNet marks Problem. In these frames that drops *annoyed*, *irritated* and *shocked* from row 19 and *enjoyment* from row 21. No count above changes.

**9. VN_EVENT_MOTION** (VerbNet rule, unreviewed)
- **Writes:** MOVE +1.
- **Fires when:** a frame has a positive `motion(...)` for any participant at any phase. 171 frames, 733 words.
- **Basis:** F043.
- **Verdict:** fits.
- **Change:** assert rule 2's guard instead of writing MOVE directly.
- **Witnesses:** *walk* and *throw* (the thrown thing moves). I found no counterexample in the data.

**10. VN_EVENT_CONTACT** (VerbNet rule, unreviewed)
- **Writes:** TOUCH +1 for `contact(...)`. It writes TOUCH 0 if the frame only negates contact.
- **Reach:** 94 frames, 231 words.
- **Basis:** no specific ruling. It rests on F059's mandate: "a rigorous symbolic map of warranted meaning from what the sources encode."
- **Verdict:** the +1 branch fits; the 0 branch is wrong.
- **Counterexample:** TOUCH 0 is written for 6 frames, and it is wrong in both cases:
  - Four are the "hit at" and "swat at" frames of hit-18.1 and swat-18.2 (*bang, beat, bump, punch, peck…*). Those senses assert contact in their other frames.
  - Two are pelt-17.2 (*pelt, stone, bombard*). There the negation covers only the thrower and the thrown things during the flight; the stones' arrival is recorded as a location, not as contact.
  - In neither case does the source say the word's definition lacks contact, which is what F118's 0 claims.
- **Proposed change** (shared by every VerbNet rule): a frame that only negates an unpaired predicate writes nothing; it never writes 0. These 6 frames are the only place in VerbNet where that 0 branch fires. HAVE 0 and EXIST 0 never occur.
- **Derivation:** the negated predicate still stays in the reading's derivation, so a later rule can use it.

**11. VN_AFFECTIVE_STATE** (VerbNet rule, unreviewed)
- **Writes:** FEEL +1 for `emotional_state(...)`, whoever the experiencer is.
- **Reach:** 38 frames, 346 words.
- **Basis:** F043.
- **Verdict:** fits with change.
- **Change:** keep FEEL, and record which participant feels as a typed fact on the reading.
  - The subject feels in admire-31.2 and marvel-31.3 (*love, hate, marvel*).
  - Someone other than the subject feels in amuse-31.1 and appeal-31.4 (*amuse, frighten*; "it appeals *to me*").
  - The emotion template needs that role (design §3).
- **Must-not (new):** VerbNet's admire-31.2 also lists *believe, affirm, trust, support, value, respect* and *tolerate*, so this rule gives them FEEL.
  - Over the gate words the rule reaches 20 verbs; 8 carry no USAS emotion tag on the verb (`evidence/row11_reach.json`).
  - *believe, matter, respect, support* and *value* are attitude verbs. Their own FrameNet frames include Certainty, Judgment, Funding and Assessing.
  - *interest, throw* and *try* are amuse-31.1's emotion senses, as in "the question threw me".
- **Proposed guard:** write FEEL only when the same verb also has a USAS E tag; otherwise record the reading as unaligned.
  - This removes the five attitude verbs, *matter* included; if you approve it, it also settles the earlier matter-91 question.
  - It loses *interest, throw* and *try* as known omissions.
  - *trust* passes only through its E6+ ("confident") tag.

**12. VN_DESIRE** (VerbNet rule, unreviewed)
- **Writes:** WANT +1 for `desire(...)`.
- **Reach:** 21 frames, 32 words (want-32.1, wish-62, long-32.2).
- **Basis:** no specific ruling. The predicate maps one-to-one onto the WANT prime (F059).
- **Verdict:** fits.
- **Witnesses:** *want*, *wish*, *long for*. *think* in wish-62 ("thought to go") gets WANT. That's right for that sense, and it shows *think* still has no THINK.

**13. VN_VITALITY** (VerbNet rule, unreviewed)
- **Writes:** ALIVE −1 (DEAD), only when a participant is alive at the start and not alive at the end.
- **Reach:** 3 frames, 12 words (murder-42.1).
- **Basis:** F059, plus the design's transition rule.
- **Verdict:** fits.
- **Witnesses:** *kill* and *murder*.
- **Gap:** *die* is in VerbNet's "disappear" class and gets nothing. Its USAS L1− tag would need its own rule.

**14. VN_EXISTENCE** (VerbNet rule, unreviewed)
- **Writes:** EXIST +1 for `exist(...)`.
- **Reach:** 72 frames, 296 words.
- **Basis:** F059.
- **Verdict:** fits with change.
- **Keep:** 41 frames assert a change of existence, either creation (*build, create, grow*) or consumption (*consume, spend*).
- **Drop:** 31 frames say only that a participant exists during the event (*abut, adjoin, border, meet, intersect, echo, resound, swarm, billow*). That's a presupposition, not the verb's content.
- **Proposed change:** project EXIST only for a change of existence, or inside exist-47.1 itself. VerbNet's existence class (*exist, coexist, endure, survive, dwell, flourish*) means existing, so there the static form is the verb's content, not a presupposition. Without that exemption those verbs would lose EXIST until the prime route arrives in stage 3.

**15. VN_POSSESSION** (VerbNet rule, unreviewed)
- **Writes:** HAVE +1 for `has_possession(...)`, keeping both transfer endpoints.
- **Reach:** 52 frames, 209 words.
- **Basis:** F059, and design §7.1: the giver losing possession doesn't erase HAVE.
- **Verdict:** fits.
- **Witnesses:** *give, get, steal, exchange*. The negated-only branch (HAVE 0) never fires; see row 10.

**16. VN_BEGIN** (VerbNet rule, unreviewed)
- **Writes:** START +1 for an explicit `begin(...)` predicate, not merely the start(E) phase.
- **Reach:** 8 frames, 9 words (begin-55.1).
- **Basis:** F059.
- **Verdict:** fits.
- **Witnesses:** *begin, start, commence*.

**17. VN_END** (VerbNet rule, unreviewed)
- **Writes:** START −1 (END) for an explicit `end(...)` predicate.
- **Reach:** 10 frames, 14 words (stop-55.4, complete-55.2, rush-53.2).
- **Basis:** F059.
- **Verdict:** fits with change.
- **Change:** restrict this rule to the aspectual classes (55.x).
  - rush-53.2 (*hasten, hurry, rush*) reaches END through "the task ends".
  - "She hurried but didn't finish the report" is not a contradiction, so finishing is not part of *hurry*. That is a cancellation test, the standard check for an entailment.
  - The 55.x verbs fail it: "She completed the task, but the task didn't end" contradicts itself.

**18. VN_USAS_PERCEPTION_MODE** (VerbNet + USAS rule, unreviewed)
- **Writes:** SEE +1 or HEAR +1.
- **Fires when:** a frame has `perceive(...)` and the word's USAS verb tags say sight (X3.4) or sound (X3.2). If they don't settle it, the model makes a typed choice: HEARING, VISION, OTHER or UNRESOLVED. OTHER writes nothing.
- **Basis:**
  - F078: typed empty fields, not prose questions.
  - F112 and F119: "the messy/hard tail is what the small model is FOR."
- **Verdict:** fits.
- **Witnesses:** *overhear* → HEAR and *glimpse* → SEE. The class name alone (sight-30.2) never decides it, because *overhear* sits in that class.

**25–26. The CAUSE decision** (new; yours, on its own)

This is the founder question "Should VerbNet's `cause` map to CAUSE or BECAUSE?". An earlier draft of this packet treated it as settled by the literature. It isn't.

**What the literature settles: NSM's side only.**
- No NSM inventory has a CAUSE prime (CH; G12 Table 1; G15 Table 1; W1992). The chart excludes "make" as a "complex English-specific word".
- NSM writes causation as BECAUSE with DO or HAPPEN. CH's BECAUSE box: "it happened because this someone did something before".

**Why it's yours.** GSE's basis has CAUSE as well as BECAUSE. Design §7.3 expects "Native causation and explanatory BECAUSE likewise need their distinct source-to-coordinate contracts." No founder line rules on CAUSE.

**Option B, recommended: two contracts, as §7.3 expects.**
- **CAUSE:** the word's own causative event, where a causer's DO or HAPPEN brings about a change in another participant.
- **BECAUSE:** a reason or thought-to-feeling link inside the meaning.
- **Row 25 writes** CAUSE +1 for a frame's `cause(...)`, with DO +1 for an agent causer and HAPPEN +1 for an event causer. Row 26 is dropped.
- **Witnesses:**
  - *kill*: CAUSE.
  - *frighten*: CAUSE for stimulus → experiencer, and BECAUSE for thought → feeling.
  - *afraid*: BECAUSE only; its CAUSE stays a field until a law writes it.
- **Cost:** the gold needs a projection rule that sorts each NSM "because" by that test.

**Option A: NSM-literal.**
- **Row 25 writes** BECAUSE +1 with DO or HAPPEN.
- **Row 26 leaves** CAUSE empty in every reading under basis `GSE_LEXICAL_72_SIGNED_58_V1`.
- **What it costs.** Causatives and emotion words share one mark, and GSE gives up a coordinate it built.
- **What it gains.** One fewer open field per word.

**Either way**
- Both options need stage 1b, since verb readings can't assert facts yet.
- **Reach:** to be measured on the frozen audit. The turn-1 review counted `cause` as VerbNet's most common predicate (620 of 3,153), and unmapped.
- **Caution (design §5.3):** amuse-31.1 gives 242 members the same inherited `cause`. Count it once at its origin.
- **The fear target:** moves between 40 open fields (A) and 41 (B) (`evidence/template_fields.json`).

## Also needing your eyes

- ***pity* contradicts itself.** Wierzbicka 1999's explication (p.101) leaves its feeling's quality open, while the text says the feeling is "bad". Its USAS pole gives −1, which agrees with the text. Its gold records the conflict (`NSM_RESOLUTIONS.md` §1).
- **`delighted` test.** `tests/test_lexicon_builder_workflow.py:243–244` asserts that *delighted* has no THINK and no WANT. That now contradicts F129. It will flip in the same change that admits the emotion rules, not before.
- **Overlapping writers.** FEEL has three writers today (rules 1, 8 and 11) and MOVE has two (2 and 9). The proposed changes leave each consequence with one owner.
