# First emotion slice — rows 19–24, revised from the NSM literature

**Decided (F144):** Rohan approved this draft's recommendations. Rows 19–22 and 24a are to be built, with the *pleasure* scope question, and rows 23 and 24b are withdrawn. GOOD for the feeling nouns follows the default, the felt valence. The CAUSE decision is option B, so CAUSE stays a field for these readings until a law writes it.

For approval under F129. The draft's two contract questions are answered from the published NSM literature: quotations and locations are in `NSM_RESOLUTIONS.md`. Where sources conflict, the later NSM analysis wins (F137). Two points are yours:
- **GOOD for the feeling nouns in row 21.** The literature conflicts with F057, which says nouns carry no sentiment weight, with *hatred* as its example.
- **The CAUSE decision (rows 25–26).** It sets one cell here.

**What changed in this revision.** Rohan supplied the primary works (F141), and this revision reads them. The previous revision rested on quotations of Wierzbicka 1999 in other papers; every gold explication is now primary, and checked against the printed page.
- **BECAUSE is narrowed (row 22).** It stays fixed for Fear readings, E5/E6 readings outside Fear, other nouns and verbs. It becomes a field for the other adjectives: Wierzbicka 1999's *sad* drops the link between thought and feeling on purpose.
- **GOOD's typed field extends from E5− to E6−.** A reading whose slice tags are all E5− or E6−, with no Fear unit of its part of speech, gets the field. *concern* is the witness: both Wierzbicka analyses leave its feeling open.
- **24a's reason is corrected.** CAN holds in all eight sourced Fear readings, but in *nervous* and *dread* only as the experiencer's ability. *nervous* uses MAYBE, so MAYBE is not silent for Fear readings.
- ***pleasure* is a new MUST-NOT.** The guards admit it, but Wierzbicka 1999 says it has no cognitive scenario at all. A typed scope question is proposed (below).

Unchanged from the previous revision:
- GOOD records the felt valence, and the substantive cells record the word's own head (3b holds; nouns and verbs follow the same contract).
- FEEL, THINK and LIKE are in every published wording, and WHEN in every adjective and noun wording.
- The candidate silence groups and the draft's two field relations stay withdrawn.

The evidence is in `evidence/`; its README says how to re-run it.

## Scope (rows 19–21), unchanged

A reading needs a signed USAS emotion tag (table below, no slash) plus an experiencer frame:
- **adjectives:** FrameNet Emotion_directed, Fear or Emotions_by_stimulus;
- **nouns:** Experiencer_focus, Emotion_directed or Fear;
- **verbs:** VerbNet admire-31.2.

**Population.**
- Over the whole USAS lexicon that is 77 adjectives, 30 verbs and 52 nouns.
- FrameNet's own index, which the adapter reads, omits the 59 units FrameNet marks Problem. Reading them would add *annoyed*, *irritated*, *shocked* and *enjoyment*.

| USAS tag | Scale, per the USAS guide | In slice |
|---|---|---|
| E4.1± happy/sad, E4.2± contentment | a felt state | yes |
| E2± liking | "fondness/affection/partiality/attachment, or the lack of" | yes |
| E3− | "serenity/composure/anger/violence"; enters only with an experiencer frame | yes |
| E5− | "trepidation/courage/surprise"; the minus side includes surprise | yes; outside Fear, GOOD is a field |
| E6− | "apprehension/confidence"; USAS tags *concerned* and *concern* E6− | yes; outside Fear, GOOD is a field |
| E3+, E5+, E6+, E1 | not a felt valence, or unsigned | no |

**The join** follows the contract table in `RULE_REVIEW.md`, shared with rows 6–8.
- **9 readings certify,** because their FrameNet unit is in Fear: *afraid, frightened, nervous, scared, terrified; apprehension, dread, fear, terror*.
- **The other 150 go to the typed discriminator** (MATCH, DIFFERENT_READING or UNRESOLVED). Emotion_directed, Experiencer_focus, Emotions_by_stimulus and VerbNet's admire-31.2 accept any emotional response.
- **Discriminator controls.**
  - These must come back DIFFERENT_READING: *mad* (FrameNet: "slightly angry"; USAS's only emotion tag for it is E4.1+), *rue*.v (FrameNet: "to feel compassion for; pity"; USAS: E4.2− regret) and *misery*.n (FrameNet's unit is a situation).
  - *happy* must come back MATCH.

**E5 and E6 outside Fear.** A reading whose slice tags are all E5− or E6−, and which has no Fear unit of its own part of speech, gets GOOD as a typed field: +1, −1 or empty. These 22 readings are (`evidence/template_fields.json`, `class_membership`):
- adjectives: *alarmed, anguished, anxious, concerned, dismayed, flabbergasted, flustered, horrified, perturbed, petrified, stressed, stunned, unsettled, worried*;
- nouns: *anguish, concern, desperation, dismay, horror, stupefaction*;
- verbs, since Fear has no verb units: *dread*.v, *fear*.v.

The field's controls:
- **From the population:**
  - *concerned* and *concern* → empty (W1990b p.373; W1999 p.86);
  - *worried* → −1 (W1990b p.372; W1999 p.85), and *alarmed* → −1 (W1999 p.81);
  - *anguish* → −1 (W1990b p.371);
  - *horrified* and *petrified* → −1 (W1999 pp.77, 79).
- **As fixtures:** Goddard 2015's *amazed* (+1), *shocked* (−1), *surprised* and *astonished* (empty). None of the four passes the slice's guards.

**MUST-NOT witnesses.**
- **The guards keep these out:** *lonely, nostalgic, jealous, proud, ashamed, guilty, homesick, relieved*.
- **They need their own template and wait for a later slice:** causers (*amuse*) and stimulus adjectives (*amusing*). Their explications use "someone can think ... can feel" and have no BECAUSE (G15 [I], [J]).
- ***pleasure*.n is admitted today and must not be.**
  - **The conflict.** F129 rules that emotion words include the thinking part, and Wierzbicka 1999 p.56 says *pleasure* "doesn't imply any cognitive scenario at all, not even a prototypical one".
  - **Proposed:** a typed scope question per reading, "does this reading's meaning include a thought, actual or prototypical?", answered THOUGHT_PART, NO_THOUGHT_PART or UNRESOLVED. Only THOUGHT_PART gets the template.
  - **Controls:** *pleasure* → NO_THOUGHT_PART; *sad* and *afraid* → THOUGHT_PART.

## Cells fixed by law, template and contract

| Cell | Adjectives (19) | Verbs (20) | Nouns (21) | Basis |
|---|---|---|---|---|
| FEEL | +1 | +1 | +1 | row 1 (F043) |
| THINK | +1 | +1 | +1 | F129; every sourced explication of a slice word has THINK, at least in its typicality line |
| BECAUSE | +1 for Fear and E5/E6 readings; a field for the rest | +1 | +1 | row 22: written only where every published wording of the class links thought and feeling (W1999's *sad* does not) |
| LIKE | +1 | +1 | +1 | row 22: every typicality wording, and "think like this" |
| WHEN | +1 | field | +1 | row 22: every adjective and noun wording; English verbs are explicated only in the noun format, and the one verb-specific template (*vihata*) has none |
| GOOD | from the pole; −1 in Fear; field for E5/E6 outside Fear | from the pole; field for E5/E6 | per the F057 ruling: default −1 in Fear, from the pole, field for E5/E6 outside Fear; or empty for all | Q1, felt valence |
| KIND | 0 | 0 | 0 | row 4 (F007) |
| INTENSITY | +1 | +1 | +1 | row 5 (F125–F126) |
| SOMETHING | 0 (row 3) | 0 | +1: the "something" X felt | Q2 |
| I, YOU, SOMEONE, PEOPLE, BODY, PART | 0 (3b) | 0 | 0 | Q2 |
| CAN, HAPPEN | +1 in Fear (24a) | fields | +1 in Fear (24a) | row 24a |
| CAUSE | per the CAUSE decision | per the CAUSE decision | per the CAUSE decision | option A: empty (row 26); option B: a field, until a law writes it |

## The thinking part: fields (row 22)

**What is open.** Every coordinate not fixed above is a typed field. With 3b, and with CAUSE fixed (option A):
- 40 for the Fear adjectives and Fear nouns;
- 42 for the other nouns;
- 43 for the other adjectives, for E5/E6 adjectives and nouns outside Fear, and for verbs;
- 44 for the E5/E6 verbs (*dread*, *fear*).

Under option B, CAUSE is one more field, so every count rises by one (41 for the Fear adjectives). Without 3b and its noun and verb counterparts, the Fear adjectives have 46 under A.

**What a field offers.** The coordinate's legal states other than written 0: +1 (±1 on a bipolar coordinate) or empty.
- Explicit absence needs its own warrant (F118).
- A negated thought is NOT +1, with the negated predicate kept in the derivation.

**Relations among the fields.** None is sourced yet; the draft's two are withdrawn.

**Gold.** Published explications are evaluation gold, never construction input (design §7.3). Thirteen are projected in `evidence/template_fields.json`:
- the 8 sourced Fear readings: Wierzbicka 1999's *afraid*, *fear*, *nervous*, *terrified*, *apprehension* and *dread*, and Wierzbicka 1990b's *scared* and *frightened*;
- *sad*, *concerned*, *sadness*, *pity* and *sorrow*.

What the gold shows:
- *afraid* has content in 7 of its 40 fields: DO, IF, KNOW, NOT, QUANTITY, NOW (THEN −1) and WANT. The other 33 are empty in the explication.
- Every fixed cell agrees with its explication, with two exceptions:
  - *frightened*'s THINK: its only explication prints "feels" for "thinks", almost certainly a misprint;
  - *pity*'s GOOD: the source contradicts itself.
- **Not a held-out test.** The fixed cells were drawn from these same explications, so their agreement with the gold shows only that the rows don't contradict their sources.
- **The gold depends on GSE's projection.** These are GSE choices, not Wierzbicka's (listed in `evidence/template_fields.json`); "7 of 40" and any field-fill score depend on them:
  - a prime is written whatever its scope, except GOOD, which is read from the feeling line only;
  - "know if" is written as IF, though the chart's IF box shows only conditionals;
  - "now", inside the thought, becomes the word's THEN −1;
  - "sometimes" becomes QUANTITY and WHEN;
  - "will" and the past tense write nothing;
  - "think like this" counts as LIKE;
  - "very" writes INTENSITY;
  - "have to" writes NOT and CAN (the chart's "can't not");
  - "these" has no coordinate (THIS).

## Silence (row 23, withdrawn)

- An explication that contains a prime falsifies silence for its bank:
  - *happy* (MANY, NOW, DO, CAN);
  - *afraid* (NOW, DO, IF, KNOW, WANT);
  - *nervous* (MAYBE);
  - *sorrow* (LONG_TIME);
  - *shocked* (BEFORE).
- One that lacks a prime proves nothing, because the chart shows only "some of their combinatorial possibilities".
- The FrameNet falsifications stand: *mourning* (a death), *petrified* ("paralysed with fear"), *regret*.v ("feel or express").

So no silence group can be admitted from the literature. Silence comes from your F101 method instead:
1. Measure, across the shared English population, which banks stay empty when an emotion reading is present.
2. Check each candidate against the published explications, now 13 of them.
3. Admit it as a scoped law.

## Fear (row 24a)

**The law.** A reading certified through FrameNet's Fear frame gets CAN +1 and HAPPEN +1. FrameNet's Fear inherits Emotions_by_possibility.
- **HAPPEN** occurs in all 8 sourced Fear explications.
- **CAN occurs in all 8 too, but only because the projection ignores scope.**
  - In 6 it is the possibility of the bad event ("something bad can happen").
  - *nervous* puts that possibility in MAYBE ("maybe something bad will happen", Wierzbicka 1999 p.84), and *dread* in IF and "will" ("if this happens, something very bad will happen to me", p.80). In those two, CAN is only the experiencer's ability.
- **MAYBE** stays a field, and must come back +1 for *nervous*.
- **24b (AFTER) stays withdrawn.** No Fear explication contains AFTER. Their future is "will", which writes nothing, and several are anchored in NOW.

**Controls**
- 24a must not fire for *sad*, which is not in Fear. *sad*'s own CAN ("I know I can't do anything", Wierzbicka 1999 p.62) must come back from its field.
- *dread*.v and *fear*.v are not in Fear and must find CAN through their fields.

## First completion target

The fear adjectives (*afraid, frightened, nervous, scared, terrified*) are the first readings that can export:
- their join certifies without a model;
- 24a gives a cross-bank consequence from a typed source fact;
- each now has a published gold explication.

**For *afraid* to reach CANDIDATE_COMPLETE**, it needs:
- approval of rows 1–5 with 3b, 19, 22 and 24a, and the CAUSE decision;
- its 40 or 41 fields filled, of which the gold says 33 are empty, or F101 silences that close part of them.

**Against your priors.** 40 or 41 open fields counts cells that are unproven, not cells that are uncertain (F140).
- In the gold, 33 of *afraid*'s 40 are silent. They stay open only until a scoped silence law (F101, checked against the published explications) proves that for the class.
- That leaves 7 real choices (DO, IF, KNOW, NOT, QUANTITY, NOW, WANT), inside F067's "5-10".
- The exact number of independent choices is known only after propagation (design §7 step 5), which stage 2 measures.

**Controls for the field fill**
- *afraid* with FEEL withheld and the options shuffled must answer +1.
- The GOOD field must return the values listed above: *concerned* empty, *worried* and *alarmed* −1, and Goddard 2015's four.
- 24a must not fire outside Fear; *sad*, *dread*.v and *fear*.v must find CAN through their own fields.
- *nervous* must return MAYBE +1.
- Each fill is scored against its gold, counting additions and omissions separately.

## How stage 2 is accepted

1. **Gold.**
   - Published explications serve where they exist: the 13 above, and the four surprise words (Goddard 2015).
   - You approve printouts only for readings with no published explication.
   - A disagreement becomes a rule change, never a per-word fix (F124). Gold never feeds construction.
2. **Controls (F045):**
   - the discriminator, scope and field controls above;
   - removing the frame or the tag removes the reading;
   - the out-of-scope words, and *big*, get no emotion content.
3. **Measures:** open fields and calls per word, and accuracy by error class.
