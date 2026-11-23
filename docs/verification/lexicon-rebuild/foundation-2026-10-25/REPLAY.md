# Replay of the frozen gate build against d2c2e52 (2026-10-25)

F160 set the commit condition: "Run the cell-level replay, review the semantic differences, refresh the baseline with that justification, and run the full repository gate." This is the replay and the review. The review found one rule that wrote CAUSE where the approved meaning of CAUSE rules it out; that rule was corrected from the NSM sources before the numbers below were taken.

A refreshed baseline is a change detector. It records what the build does now; it does not certify that the readings are right.

## How it was run

- **Old:** commit d2c2e52 in its own worktree, built on the 1,040 gate words with the gate's flags. Checked against the recorded baseline: `frozen build: IDENTICAL` (`replay/d2c2e52_baseline_check.txt`). The word list is the same file in both trees (`replay/gate_words_sha256.txt`).
- **New:** the current tree, same words, sources and flags. The gate's verdict is CHANGED for all 1,040 records, as expected.
- **Comparison:** `replay/compare.py`, written by a sub-agent to report facts only, run on both builds. The design consultant recounted the first comparison independently and agreed. That comparison was taken before the CAUSE correction, and it is kept in `replay/before_cause_correction/`.
- **Model calls:** none in either build.

Both builds read the same source files: `native` is identical in all 1,040 records, and the source locks match. The manifests are in `replay/old_manifest.json` and `replay/new_manifest.json`.

Commands:

```sh
uv run python -m gse.lexicon_builder build --symbolic-only \
  --word-file docs/verification/lexicon-rebuild/closeout-2026-10-25/gate/gate_words.txt \
  --sources data/external --nltk ~/nltk_data/corpora --output <dir>
uv run python scripts/lexicon_frozen_build.py check <dir> docs/verification/lexicon-rebuild/closeout-2026-10-25/gate
```

## Result

- All 470 old readings are still there; none was removed. 1,614 readings are new.
- In the 470 shared readings, 4,110 cells changed. **Every change narrows an open cell to one state. No cell the old build had settled changed value.**
- 191 more cells kept their value but are now written by a different rule.

## Changed cells in the shared readings

| Cells | Readings | Rule | What it writes | Authority |
|---:|---:|---|---|---|
| 3,624 | 453 | `VERB_HEADS_NO_SUBSTANTIVE` | the eight substantive cells 0 on a verb reading | F151's proposal, agreed at F152: row 20's "verbs head no substantive" for every predicate; the head contract of NSM_RESOLUTIONS §2 (F144) |
| 238 + 230 | 238 | `NATIVE:VN_CAUSATION` | CAUSE +1, and DO +1 for an Agent causer | F144 option B, read through the NSM sources (below) |
| 8 | 8 | `EVALUATOR_EXCLUDES_SIZE` | BIG 0 on the good/bad-quality adjectives | F067, agreed at F152 |
| 8 | 8 | `SIZE_DESCRIPTOR_EXCLUDES_EVALUATION` | GOOD 0 on the size adjectives | F067, agreed at F152 |
| 2 | 1 | `FEAR_AVERSION` | WANT +1 and NOT +1 on *afraid* ("I don't want this to happen") | F151's proposal, agreed at F152; F159 keeps it conditional, with in-sample evidence |

The witnesses are WANT's SOMEONE 0 and GOOD's BIG 0 / BIG's GOOD 0 in the prime reconstruction, *afraid* through the real CLI, and the CAUSE witnesses below (`tests/test_lexicon_foundation_workflow.py`).

**Same value, different writer (191 cells).**
- MOVE +1 on 190 motion readings is now written by `OWN_PHYSICAL_CHANGE_OF_PLACE` from the motion fact, not by the VerbNet rule directly. F144 approved this as rows 2 and 9: "this law becomes the single writer of MOVE".
- *afraid*'s GOOD −1 is first narrowed to ±1 by `SIGNED_FELT_VALENCE_DOMAIN` (F066).
- `EMOTION_FEAR_ADJ:FEEL` no longer fires. FEEL +1 comes from `OWN_AFFECTIVE_FEELING`, as in the old build (F144 row 1: drop the duplicate FEEL companion).

**Other per-reading changes.** A static `exist` is now coded `PARTICIPANT_EXISTENCE_PRESUPPOSITION` (F144 row 14). *afraid* carries its `NEGATED_DESIRE` relation. One coverage-gap note was rewritten. Six *point* gesture frames carry `NO_CHANGE_TO_ANOTHER_PARTICIPANT`.

## New readings (1,614)

| Readings | Kind | What is written |
|---:|---|---|
| 1,171 | Lemma head-contract readings | ADJ 261 and VERB 203: the eight substantive cells 0 (row 3b, F144; F152). NOUN 553 and ADV 154: nothing. The noun contract is next (F160). |
| 373 | VerbNet frame readings | Built because an admitted rule now writes in them: DO+CAUSE 175, DO+EXIST+CAUSE 98, FEEL 56, FEEL+CAUSE 20, EXIST 17, CAUSE 7 |
| 63 | Prime readings | 14 complete (the examined primes' surfaces), 49 partial drafts |
| 6 | Function-word construction readings | QUANTITY or INTENSITY on their prime homes |
| 1 | *fear* as a noun | `EMOTION_FEAR_NOUN` (F144 rows 21, 22, 24a) |

The frame readings come from three rules:
- `VN_CAUSATION`, narrowed as below.
- `VN_EXISTENCE` and `VN_AFFECTIVE_STATE`, which F144 approved with a stated change, and the code implements exactly that change. Row 14 writes EXIST only for a change of existence or inside exist-47.1; row 11 writes FEEL only when the verb has a USAS E tag.
- Their writes no longer appear as withheld: VN_EXISTENCE 155 and VN_AFFECTIVE_STATE 122.

**Per record.**
- Every record gained a `structural_entries` key; it is non-empty for 26 function words.
- 193 records differ only by that key.
- *fear*'s noun alternative is now handled.
- Record codes: 689 words went from no applicable rule to constructed readings, 43 from withheld-rules-only to constructed readings, and 11 to structural entries. 193 still match no rule.

## The CAUSE correction

**What was wrong.**
- The draft wrote CAUSE +1, and DO +1 for an Agent, for every VerbNet `cause(...)`.
- VerbNet puts `cause(Agent, E)` on most agentive frames, including saying (`transfer_info` only). So CAUSE reached 861 readings, 218 of them in the communication classes (*say*, *tell*, *ask*, *talk*).
- Option B defines CAUSE as the word's own causative event: "a causer's DO or HAPPEN brings about a change in another participant" (NSM_RESOLUTIONS §6, F144). Saying changes no one.

**What the NSM sources say.** Both were read whole for this review.
- **GW16**, Goddard & Wierzbicka 2016, "Explicating the English lexicon of 'doing and happening'":
  - Verbs that affect someone or something put the change in the frame. *hit*: "someone X did something to someone else (at this time) / because of this, something happened to this someone else at the same time"; *kick* ("to something") and *kill* ("at this time") have the same shape. *cut* and *grind*: "because of this, something is happening to this something during this time as this someone wants"; *dig* has "to something in this place".
  - Verbs that move or create something state the change as the outcome. *push*: "because this someone X did this to this something, after this, this thing was not in the place where it was before"; *throw* says "this something". *make*: "when this someone does this, something happens to these things as this someone wants".
  - Locomotion links the doing to the doer's own motion: "because of this, this someone is moving in this place during this time as this someone wants".
- **GW2014 Table 1.2** gives HAPPEN's undergoer frame: "something HAPPENS to someone/something".
- **GW2014 chapter 7** covers the English speech-act verbs:
  - Template I opens "someone X said something to someone else Y at that time". Template II, for *praise*, *criticize*, *compliment* and *insult*, opens "someone X said something good/bad about someone else Y at that time". *greet* opens "someone X said some words to someone else Y at that time".
  - Every one is headed by SAY. Where an effect appears, it is "this someone wanted something to happen because of it": wanted, never asserted.
  - The one causative in the chapter is the institutional *marry*: "someone X did something at that time / because of this, something happened to two people (someone X, someone Y) as this someone wanted".

**The rule now.**
- VerbNet `cause(...)` writes CAUSE +1 only when the caused event asserts something happening to a participant other than the causer:
  - a state or relation at the event's end or result;
  - that participant's motion, transfer or emotional state during it;
  - its aspectual beginning or ending.
- A predicate the builder already refused as a wrong-sense or out-of-scope join never counts.
- DO and HAPPEN are written only with CAUSE.
- A frame that fails the test leaves CAUSE and DO unresolved, never 0, and records `NO_CHANGE_TO_ANOTHER_PARTICIPANT`.
- The code is in `native_constraints._changes_another_participant`, and the rule record (`VN_CAUSATION`) carries real witnesses.

**What it changed.** The counts are from `replay/cause/before_narrowing.txt` and `after_narrowing.txt`.

| VerbNet family | CAUSE readings before | after |
|---|---:|---:|
| 37 communication (*say*, *tell*, *ask*, *talk*) | 218 | 0 |
| 29 characterize, appoint, dub | 62 | 24 (naming: *name*, *call*, *term*; electing) |
| 31 psych | 37 | 23 (*interest*, *try* and *throw* lose it where their only change is an emotional state refused for lack of a USAS E tag, F144 row 11, and keep it where a result is stated; *matter* loses it) |
| 40 bodily gesture | 24 | 3 |
| 14 learn, 87 focus, 38 sounds, 48 appearance | 18 | 0 |
| 55 aspectual | 13 | 10 (*continue* removed) |
| 54 measure, capacity | 13 | 7 |
| 18 contact | 20 | 18 (the "hit at" frames: no contact) |
| all other families | 456 | 453 (creation, possession, change of state, putting, motion and killing keep every reading; *group*, *keep* and *rush* lose one each) |
| **All** | **861** | **538** |

- CAUSE kept: *kill*, *give*, *put*, *build*, *make*, *throw*, *hit*, *frighten*, *amuse*, *name*, *start*, *end*.
- CAUSE removed: *say*, *tell*, *ask*, *talk*, seeing or knowing someone as something, *learn*, *focus*, *continue*.
- 317 new frame readings are no longer built, because CAUSE and DO were their only writes. Verbs left with no frame reading fall back to the lemma head-contract reading, which is why that count rose from 182 to 203.

**Known limits.** These are recorded in the rule.
- **Reflexive result.** VerbNet gives "Tom ran the soles off his shoes" and "We walked ourselves into a state of exhaustion" (run-51.3.2 frames 7 and 8) the same semantics, so the reflexive result passes. That is 4 readings.
- **Own body part.** The native adapter drops VerbNet's role restrictions, so the actor's own body part also passes: "Linda winked her eye", wink-40.3.1, *point*, 3 readings. Carrying the restrictions through the adapter fixes this.
- **No outcome phase.** Some frames state no outcome phase, such as *show*'s `appear` (reflexive_appearance-48.1.2) and some psych frames; there CAUSE stays unresolved.
- **Membership.** VerbNet lists *want* in appoint-29.1 ("We elected him governor"). That is a question about the class membership, not about CAUSE.

**Witnesses.** In `test_cause_needs_something_to_happen_to_another_participant`:
- **No CAUSE or DO:** *say*, *know as*, *continue*, *hit at*, an unaligned emotion, and a lone walker.
- **CAUSE:** *frighten* (no DO), *run the horse*, *start* and *throw away* (with DO).

The revised `test_native_causation_and_presupposed_existence_have_distinct_contracts` uses *kill*'s alive→not-alive change.

## What this does not establish

- No ordinary word is complete. 553 noun and 154 adverb head readings have no decided cell.
- The rules admitted as `SOURCE_JUSTIFIED` pass admission on the presence of their fields. VERB_HEADS, EVALUATOR, SIZE, FEAR_AVERSION, FEELING_NOUN_HEAD, EMOTION_FEAR_NOUN and SIGNED_FELT_VALENCE_DOMAIN still carry placeholder witnesses. Their review belongs to the conditional-rule checkpoint (F158 §5).
- The CAUSE condition reads VerbNet's predicate structure. It inherits VerbNet's frame semantics and membership.
