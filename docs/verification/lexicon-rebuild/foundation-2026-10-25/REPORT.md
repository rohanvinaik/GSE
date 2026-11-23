# Checkpoint 1: the prime foundation (2026-10-25), revision 3

For the design consultant's foundation checkpoint (F158), revised after the consultant's review (F159). **Accepted at F160** as a design checkpoint: twelve examined profiles, sixty drafts, ordinary lexical construction still incomplete.

**Revision 3 (the F160 commit condition).**
- **Replay done.** The cell-level replay against d2c2e52 is done and reviewed ([REPLAY.md](REPLAY.md)): every change narrows an open cell, and no settled value changed.
- **CAUSE corrected.** The review found that the draft's CAUSE rule wrote CAUSE +1 and DO +1 on every VerbNet `cause(...)`, including saying. Read through GW16 and GW2014 ch. 7, option B now requires something to happen to another participant: 861 CAUSE readings became 538, with none left in the communication classes.
- **Research filed.** The noun and NSM-prime research packets are filed in [research-2026-10-25](../research-2026-10-25/README.md).

**Recorded boundary (F160).** `decision_check` proves local forcing given the other final values, not a derivation rooted in independent premises. Two separate decisions can still credit one relation between their cells (A = B) through each other's values. The strict expected-failure witness `test_two_decisions_cannot_root_each_other_through_one_relation` pins this; general conditional-chain provenance must root each derivation before relying on the check. The twelve definitions are not reopened.
- **Authority:** F148 (primes "*perfect* recapitulations" of NSM); F151–F152 (an unexamined cell stays unresolved; the NSM literature and the consultant settle the open questions); F157–F158 (handoff plan); F159 (review).
- **Sources of the numbers:** `prime_proof.json`, written by `python -m gse.lexicon_builder prime-proof`; `summary.json` and `gate/build_breakdown.json`, computed by `evidence/summarize.py`; `gate/gate.log`, from `scripts/lexicon_gate.sh`.
- **State:** uncommitted in the `lexicon-builder` worktree, on top of d2c2e52.

## The F159 corrections

| Correction | What changed | Witness |
|---|---|---|
| 1. One-hot scope | `SUBSTANTIVE_HEAD_IS_ONE_HOT` now guards on `own_role = substantive` **and** `lexical_unit_kind = PRIME`. A prime's identity claim asserts the second fact; no ordinary reading can. | An ordinary substantive reading does not fire it, and the same reading with the prime fact does. In the 1,040-word build it fired on 10 prime readings and no other reading (`gate/build_breakdown.json`). |
| 2. Provenance | `decision_check` now credits a cited law only if it fired, covers the decision's coordinates and, given its other final states, allows nothing but the decided value. Codes: `CITED_LAW_UNKNOWN`, `CITED_LAW_INACTIVE`, `CITED_LAW_DOES_NOT_COVER`, `CITED_LAW_DOES_NOT_FORCE`. Every cited law must qualify. Premises list only the claims actually compiled, and the record's `ablated` field names what was withheld. | An active law permitting every INTENSITY state, credited for GOOD's degree, is `CITED_LAW_DOES_NOT_FORCE`, even though another law supplies +1. Two genuinely forcing laws are both credited. Ablation removes withheld claims from the premises. |
| 3. Silence wording | Each boundary is an *authored* decision. Its warrant now says the chart shows only some combinations, so the judged lines are consistent with the boundary without proving it, and reconstruction checks consistency, not completeness. Design §2 says the same. | Text change; the boundary-ablation and contradiction witnesses are unchanged and pass. |
| 4. Validator types | `definition_status` type-checks every field before using it. | List-valued `decision_id`, mapping-valued `state`, non-string coordinates, authority, `derived_by`, line or judgment, a null location, and a non-dict decision each return a named code. |

Two further fixes inside corrections 2 and 4, found on a second review:
- **No circular credit.** The forcing check now filters a law's rows only by the law's coordinates *outside* the decision, and requires every surviving row to carry the decided state on all coordinates inside it. A decision's own cells never vouch for each other. Witness: a law allowing {(0,0), (+1,+1)}, credited for a decision covering both cells at 0, is `CITED_LAW_DOES_NOT_FORCE`; the same law forcing one cell from an outside fact is credited.
- **No type errors.** `examination_status` returns `MALFORMED_CLAIM` for a claim whose kind is not a string, and `decision_check` returns `COORDINATE_NOT_RECONSTRUCTED` instead of raising on a missing coordinate.

All twelve still reconstruct under both fixes.

Also done under F159's condition on I (its complete lexical-unit profile, including first-person reference and combinatorial behavior, must be justified):
- **Typed chart lines.** Every judged chart line in all twelve profiles (49 lines: 43 combinations, 5 degree domains, 1 prohibition) is now typed by a claim of its kind: one `PERMITS_COMBINATION` claim per combination line, plus the existing degree and prohibition claims. `examination_status` refuses an untyped or mistyped line.
- **Reference binding.** I, NOW and HERE carry a `BINDS_REFERENCE` claim (`FIRST_PERSON_SPEAKER`, `UTTERANCE_TIME`, `SPEAKER_PLACE`) in place of the speaker/time/place argument slots. A binding writes no cell, so I has no SAY and NOW and HERE have no WHEN or WHERE.
- **Argument slots.** BAD and SMALL gained the slots their antonyms have.

Settled by F159:
- No SAY in I.
- The head-record zeros stand as a stated GSE convention, and they do not by themselves satisfy F148's V/U/W test.
- CAUSE stays silent on BECAUSE (design §9).
- Time/place zeros stand, and are never inferred from nounhood (in the law's warrant and must-not list).
- Unexamined cells stay unresolved.
- `FEAR_AVERSION`'s attribution to F152 stands, with its conditional status and in-sample boundary explicit.

## The twelve examined primes

Each decision set was written from the prime's chart box before reconstruction. All twelve reconstruct as `CANDIDATE_COMPLETE`, and every decision is `RECONSTRUCTED` under the forcing check. The cells match the earlier mechanical draft apart from the head-record cells; examination added the warrants, the judged and typed chart lines, and the reference bindings.

| Prime | Written cells (deciding law) | Silent | Chart lines judged |
|---|---|---|---|
| I | I +1; the other 7 substantive cells 0 (one-hot) | 50 | 5 combinations |
| SOMEONE | SOMEONE +1; the other 7 substantive cells 0 (one-hot) | 50 | 3 combinations |
| SOMETHING | SOMETHING +1; the other 7 substantive cells 0 (one-hot) | 50 | 3 combinations |
| GOOD | GOOD +1; INTENSITY +1 (degree); SOMETHING 0 (row 3); the other 7 substantive cells 0 (3b); BIG 0 (F067) | 47 | 6 combinations, 1 degree domain |
| BAD | GOOD −1; otherwise as GOOD | 47 | 6 combinations, 1 degree domain |
| BIG | BIG +1; INTENSITY +1; SOMETHING 0; the other 7 substantive cells 0; GOOD 0 (F067) | 47 | 2 combinations, 1 degree domain |
| SMALL | BIG −1; otherwise as BIG | 47 | 2 combinations, 1 degree domain |
| WANT | WANT +1; INTENSITY +1 ("I want it very much"); 8 substantive cells 0 (predicate head) | 48 | 6 combinations, 1 degree domain |
| FEEL | FEEL +1; 8 substantive cells 0 (predicate head) | 49 | 3 combinations, 1 prohibition (no ABOUT) |
| NOW | THEN −1; 8 substantive cells 0 (time head) | 49 | 2 combinations |
| HERE | HERE +1; 8 substantive cells 0 (place head) | 49 | 2 combinations |
| BECAUSE | BECAUSE +1; 8 substantive cells 0 (operator head) | 49 | 3 combinations |

Two recorded judgments:
- **DON'T WANT.** NSM's DON'T WANT has no GSE coordinate. GSE writes it as WANT +1 with NOT +1 in the reading that contains it, as `FEAR_AVERSION` does.
- **FEEL has no valence of its own.** The chart grades its complement ("feel something very good"), not FEEL.

## Witnesses

Authored, in `tests/test_lexicon_atomic_and_tail.py` and `tests/test_lexicon_foundation_workflow.py`:

- **Reconstruction:** every examined prime reconstructs fully.
- **Drafts:** no draft writes silence or fires a boundary law.
- **Ablation:**
  - removing GOOD's degree claim reopens only INTENSITY, the degree law stops firing, and the claim leaves the premises;
  - removing GOOD's boundary reopens exactly its 47 cells;
  - a duplicated warrant survives;
  - removing permissions, argument slots, bindings and prohibitions from six primes leaves their vectors unchanged.
- **Conflicts:** a boundary contradicting the degree law, and an admitted law contradicting FEEL's boundary, are each a `FOUNDATION_CONFLICT`.
- **Provenance:** the four `CITED_LAW_*` codes, including the permissive-law witness and the circular joint-credit witness, plus redundant credit. A strict expected-failure witness pins the F160 boundary: two decisions crediting one A = B relation through each other's values.
- **One-hot scope:** an ordinary substantive reading does not fire the one-hot law.
- **Deixis:** a binding writes no cell.
- **Typed lines:** every judged line is typed, and untyped, mistyped or malformed-claim lines are refused.
- **Homographs:** the ordinary "good" reading fires no boundary law.
- **Opposite poles:** sign and coordinate identity holds on all 14 pairs, and full equality where both poles are examined.
- **Loader fences:** eight structural refusals and nine adversarial-type refusals.

## Gate

`scripts/lexicon_gate.sh`; the whole log is in `gate/gate.log`.

| Check | Result |
|---|---|
| Pinned Ruff check and format | Pass |
| Lexicon and Detective lexicon tests | 148 passed in the gate run; 149 after the second-review fixes (direct run) |
| ty (advisory) | Pass |
| Frozen symbolic build | **CHANGED** for all 1,040 records (`gate/frozen_report.json`), so the gate exits 1 |

The frozen-build change is deliberate, and the baseline was **not** refreshed (F159 agrees). It changed for three reasons:
- the draft added a `structural_entries` field to every record;
- the draft added head-contract readings for nouns and adverbs, plus prime and function-word readings;
- this pass changed the prime readings.

The cell-level comparison F159 asked for is now [REPLAY.md](REPLAY.md). Its numbers are taken after the CAUSE correction, so they supersede this section's build counts:
- PARTIAL is 2,070, not 2,366;
- 538 readings carry CAUSE, not 861.

The build before the correction, from `gate/build_breakdown.json`:
- 14 complete readings, all examined-prime surfaces (i, me, someone, something, thing, good, bad, big, small, want, feel, now, here, because);
- 49 partial prime-profile readings (drafts);
- 1,150 partial head-contract readings;
- 1,143 partial VerbNet frame readings;
- 18 partial source-rule projections;
- 6 partial function-word readings;
- 26 words with a structural home;
- no complete reading for an ordinary word.

## Open

1. **A noun head contract, early.**
   - **Measured** in the gate build: all 553 noun head readings carry no decided cell, and SOMETHING +1 is written only by the SOMETHING prime (through "something" and "thing") and one Fear noun.
   - **Already approved, not yet built:** the NSM resolution approved at F144 (§6) gives *box* and *dog* SOMETHING +1 and KIND 0 (F007), but no rule writes it.
   - **Needed:** a contract naming which source fields warrant a noun's own head (SOMETHING, SOMEONE, PEOPLE, BODY, PART), including whether part and body nouns (hand, wheel, handle) carry PART alongside BODY or SOMETHING.
   - **Why early:** without it, the 40–50K sweep leaves nouns blank. The one-hot law stays guarded to primes until then.
2. **The remaining 60 primes.**
   - **Next step:** examine them, including the GSE-only coordinates, which need written GSE definitions first (INFER, HIER±, CERTAINTY, START/END, THEN, OUTSIDE, TOWARD/AWAY, WITH/WITHOUT, CAUSE, MUST's construction scope).
   - **YOU** needs its own second-person binding.
   - **The drafts' `unexamined_boundary_proposal` lists are stale** against the head laws (YOU's list says SOMEONE is silent; the one-hot law writes 0), so recompute each at examination time.
3. **Before the checkpoint commit (F160):** refresh the frozen baseline with [REPLAY.md](REPLAY.md) as its justification, then run the full repository gate (`scripts/ci_local.sh`) on the exact tree. The gate passed on the tree before the CAUSE correction; it must pass again.
4. **Before any readiness claim (F159):**
   - Detective pins for `definition_status`, `examination_status` and `decision_check`;
   - revalidating the six Detective-generated lexicon tests through Detective's protocol (they run and pass, but `tail_task_status` and `certificates.json` changed in the draft);
   - carrying VerbNet's role restrictions and FrameNet's semantic types and incorporated elements through the native adapter (`sources.py`). The noun contract needs them, and so does the CAUSE rule's own-body-part limit.
