# GSE proof packet — reproduction against current code (2026-11-24)

Packet: `/Users/rohanvinaik/resume/Communication/vision/GSE/GSE_Proof_Packet.md (dated 2026-07-01)`

## Setup

- **tree**: /tmp/gse-proof/tree (git archive of GSE HEAD 5792ca35563e1234c0c3a557ce04ef163c4458c6, 2026-11-24)
- **data**: /tmp/gse-proof/tree/data -> symlink to /Users/rohanvinaik/Projects/GSE/data
- **python**: CPython 3.14.7 via uv venv --managed-python --python 3.14; uv sync --locked
- **active_lexicon**: data/lexicon_active.json -> lexicon_builder/2026-11-12/sparse-release-021.db (versioned definition DB; the code falls back to data/lexicon_clean.db only when the pointer is absent: GSE/lexicon_resource.py)
- **rename**: The packet's code and commands use `gse.`; every run used `GSE.` (package renamed in GSE commit 668ab76, 2026-11-23). The dated script was taken from GSE commit bb297e5 (2026-07-01) and only `gse.` -> `GSE.` was changed (perl s/\bgse\./GSE./g, 9 lines).
- **no_writes**: I edited nothing in /Users/rohanvinaik/Projects/GSE. Before any run I snapshotted data/ to depth 2; a re-check midway found no changes. The final check was `find data -newer <snapshot>` with no depth limit. It found one entry: the directory data/lexicon_builder/2026-11-12/ssl-explicit-genera/ssl-api-checkpoint, with mtime 2026-11-24 16:27:31. No file inside it is newer than the snapshot. Nothing I ran references that path (rg over GSE/, the scripts and the probes). Lexicons are opened through read-only sqlite URIs, and there are no -wal, -shm or -journal files under data/. The other session working in that checkout could account for it; I did not confirm this. scripts/adversarial_destruction.py was run from /tmp/gse-proof/scratch, so its sqlite3.connect('data/frequency.db') could not create a file in the real data/.
- **classification_rule**: Primary class = today's reproduce path (current scripts/proof_packet.py, or the smallest faithful reproduction through public entry points where the script has no section). Section class = worst sub-claim, ordered BROKEN > CHANGED > UNVERIFIABLE > REPRODUCED. The dated script's result is reported beside it, not substituted for it.
- **missing resources**: data/genealogy.db (GenealogyStore, world/word type threads, resolve_references with a store); data/spell_entities.db (spell-checker entity leg; built from genealogy.db by GSE/curation/build_spell_entities.py); data/frequency.db (frequency weighting in scripts/adversarial_destruction.py)
- **script `current`**: scripts/proof_packet.py at HEAD (the packet's own reproduce command, today's version; already uses GSE.)
- **script `dated`**: scripts/proof_packet_dated_bb297e5.py = git show bb297e5:scripts/proof_packet.py with gse.->GSE. (the code that produced the packet)
- **script `archived_lexicon_diagnostic`**: /tmp/gse-proof/probes/run_archived_lexicon.py: current script with GSE.lexicon_resource.ACTIVE_POINTER redirected in-process to a nonexistent path, so the code's own fallback selects data/lexicon_clean.db. NON-DEFAULT configuration, used only to attribute differences; never used for a classification.

## Counts

- REPRODUCED: 4
- CHANGED: 1
- UNVERIFIABLE: 6
- BROKEN: 4

## Table

| § | Title | Class | Today's `scripts/proof_packet.py` | Dated 2026-07-01 script (gse→GSE only) |
|---|---|---|---|---|
| 1 | The null axis — identical vectors, opposite truths | **REPRODUCED** | REPRODUCED (identical lines; the section later stops at GenealogyStore(), see §2) | REPRODUCED (identical lines) |
| 2 | Structure is the meaning — clause order, determinism, honest abstention | **UNVERIFIABLE** | Prints (a) and (b), then errors at GenealogyStore() (missing data/genealogy.db) | Same as current |
| 3 | The LSAT problem — multi-step derivation, conditionals firing | **REPRODUCED** | REPRODUCED (identical; the packet wraps the last line for page width) | REPRODUCED (output identical to current) |
| 4 | The unlosable needle — correctness that does not decay with distance | **REPRODUCED** | REPRODUCED (identical) | REPRODUCED (output identical to current) |
| 5 | The dirty-input theorem — typos healed with a ledger, then the same proof | **UNVERIFIABLE** | Runs (exit 0); the printed transcript differs (no Einstien repair, both equality checks False) | Identical to current |
| 6 | The policy ruling — rules + facts -> verdict with citable chain | **REPRODUCED** | REPRODUCED (identical; the packet elides the head of the second chain with …) | REPRODUCED (output identical to current) |
| 7 | World grounding — the premise the text never states | **CHANGED** | Errors at GenealogyStore(): sqlite3.OperationalError (data/genealogy.db missing), a missing resource | Same error |
| 8 | Contradiction mining — the null axis weaponized | **BROKEN** | BROKEN: LookupError: relation_evidence_error:LookupError | REPRODUCED exactly. Its keys are surface lemmas plus GSE.nlp.morphology.resolve_negation and need no lexicon decomposition. |
| 9 | Reduction — natural language reduces like an equation | **BROKEN** | Partial output, then BROKEN: LookupError: relation_evidence_error:LookupError | REPRODUCED exactly, but its verb signatures come from the script's own _decomp, which opens data/lexicon_clean.db directly. The encoder no longer reads that file (see §10). |
| 10 | The fingerprint — the representational collapse, live | **BROKEN** | BROKEN: LookupError: unread lexical evidence: AMBIGUOUS | Prints the packet's bytes, but it reads data/lexicon_clean.db directly. The encoder's lexicon is data/lexicon_builder/2026-11-12/sparse-release-021.db (per data/lexicon_active.json). lexicon_clean.db is now the archived fallback (GSE/lexicon_resource.py). |
| 11 | Coined words — meaning for words that never existed | **BROKEN** | BROKEN: LookupError: unread lexical evidence: AMBIGUOUS | CHANGED: encode-time result is {} for both coined words (packet: {'GOOD': -1} and {'FEEL': 1, 'GOOD': -1, 'SOMETHING': 1}). The base values it prints come from data/lexicon_clean.db. |
| 12 | The spell-checker — the substrate as a shipped product | **UNVERIFIABLE** | Runs (exit 0); line 2 differs (Einstien unhealed) | Identical to current |
| 13 | Robustness on prose it was never built for | **UNVERIFIABLE** | no section | no section |
| 14 | It finds what the author missed — the discovery channel | **UNVERIFIABLE** | no section | no section |
| 15 | The gap is the intelligence — refusing what information theory forbids | **UNVERIFIABLE** | no section | no section |

## Per-section notes

### §1. The null axis — identical vectors, opposite truths — REPRODUCED

**Packet claim.** 'The zorble is bigger than the florp' vs 'The florp is bigger than the zorble': cosine(A,B)=1.0000; A -> Comparison(zorble > florp, axis=big); B -> Comparison(florp > zorble, axis=big).

**Reproduction.** `cd /tmp/gse-proof/tree && .venv/bin/python scripts/proof_packet.py basics   (also the dated script, same section)`

**Today.**

```
bag-of-words cosine(A, B) = 1.0000
A -> Comparison(zorble > florp, axis=big)
B -> Comparison(florp > zorble, axis=big)
```

**Notes.** Output identical in both scripts. Probe /tmp/gse-proof/probes/p_cosine.py: today the same encoder cosine is also 1.0000 between A and 'The blick is bigger than the wug' and between A and 'The dog is bigger than the cat'. Under the archived-lexicon diagnostic, A vs the blick/wug sentence is 1.0000 and A vs the dog/cat sentence is 0.9023.

**Observation (claim vs evidence).** The number is GSE's own encoder-vector cosine (_ENC.encode(a).vector.cosine(...)), and no independent co-occurrence or embedding model is tested. The probe shows the two invented words add nothing to that vector: any pair of invented nouns gives 1.0000, and today so does dog/cat. So the 1.0000 shows the invented words are empty in GSE's vector. It does not show that a distributional representation of them is identical.

### §2. Structure is the meaning — clause order, determinism, honest abstention — UNVERIFIABLE

**Packet claim.** (a) 'Rex barks because the dog is cute' / 'The dog is cute because Rex barks' give opposite Causation graphs; (b) 'Macbeth murdered Duncan and Macduff killed Macbeth.' encoded x3 -> sha256 {'b1aacd8a02f3'} (byte-identical); (c) structure derived Comparison(zorble > florp) while grounding abstained ['ungrounded(zorble)', 'ungrounded(florp)'].

**Reproduction.** `.venv/bin/python scripts/proof_packet.py basics; dated script basics; /tmp/gse-proof/probes/p_ground.py (store-less grounding with a real-word control, the configuration GSE.demo.reasoning falls back to)`

**Today.**

```
(a) -> Causation(cause=TypeAssertion(dog is_a cute) → effect=Event(bark: rex))
(a) -> Causation(cause=Event(bark: rex) → effect=TypeAssertion(dog is_a cute))
(b) encode ×3 -> sha256 {'e71d8c892724'} (byte-identical)   [same digest in separate processes and in both scripts]
(c) GenealogyStore() -> sqlite3.OperationalError: unable to open database file   [data/genealogy.db absent]
(c, store=None) 'The zorble is bigger than the florp': flags=['ungrounded(zorble)', 'ungrounded(florp)']
(c, store=None, control) 'The dog is bigger than the cat': flags=['ungrounded(dog)', 'ungrounded(cat)']
```

**Sub-claims.**

- (a) causation direction: REPRODUCED (identical)
- (b) determinism x3: REPRODUCED as a verdict (3 identical digests); the digest value differs from the packet: b1aacd8a02f3 -> e71d8c892724
- (c) grounding abstention: UNVERIFIABLE: needs data/genealogy.db

**Notes.** Archived-lexicon diagnostic: the current code prints sha256 {'b1aacd8a02f3'}, the packet's digest, so the changed digest follows the active-lexicon switch. Without a store (genealogy=None, as GSE.demo.reasoning falls back to), the zorble/florp flags appear, but so do ungrounded(dog) and ungrounded(cat) under the active lexicon. With the archived lexicon, dog/cat are not flagged. So in today's store-less configuration the flag line does not tell real words from invented ones.

**Observation (claim vs evidence).** The packet's preface says the script reproduces the evidence 'deterministically (same bytes every run)'. Within a run and across processes that still holds. Across code/lexicon versions the printed digest is not the packet's.

### §3. The LSAT problem — multi-step derivation, conditionals firing — REPRODUCED

**Packet claim.** Seven sentences -> greater(mike,bob)=TRUE ⊢ mike→rex→spot→bob; is_a(mike,animal)=TRUE ⊢ mike→poodle→dog→animal; greater(bob,mike)=not entailed; is_a(mike,knife)=not entailed; event(mike, mike win)=TRUE ⊢ mike → rex → spot → bob → mike → poodle → rule: poodle > bob ⇒ poodle win → ∴ mike win.

**Reproduction.** `.venv/bin/python scripts/proof_packet.py lsat (KnowledgeBase.from_trees over evaluate_tree(resolve(from_trace(GSEEncoder().encode(s)))))`

**Today.**

```
greater(mike, bob)  =  TRUE     ⊢  mike → rex → spot → bob
is_a(mike, animal)  =  TRUE     ⊢  mike → poodle → dog → animal
greater(bob, mike)  =  not entailed
is_a(mike, knife)  =  not entailed
event(mike, mike win)  =  TRUE     ⊢  mike → rex → spot → bob → mike → poodle → rule: poodle > bob ⇒ poodle win → ∴ mike win
```

### §4. The unlosable needle — correctness that does not decay with distance — REPRODUCED

**Packet claim.** Chains of 10/25/50/100 invented names in 3x filler: greater(top,bottom)=True with proof length = chain length; reverse REFUSED at every length.

**Reproduction.** `.venv/bin/python scripts/proof_packet.py needle`

**Today.**

```
chain length  10  (30 sentences): greater(kakan, sakan) = True  [proof: 10 steps]   reverse: REFUSED
chain length  25  (75 sentences): greater(kakan, vekan) = True  [proof: 25 steps]   reverse: REFUSED
chain length  50  (150 sentences): greater(kakan, tokan) = True  [proof: 50 steps]   reverse: REFUSED
chain length 100  (300 sentences): greater(kakan, riban) = True  [proof: 100 steps]   reverse: REFUSED
```

**Notes.** Run time about 39 s.

**Observation (claim vs evidence).** The filler is four fixed sentences with no comparatives, so there are no distractor premises. The LLM decay contrast is asserted, not measured here. Honest boundaries already says the corpus is synthetic.

### §5. The dirty-input theorem — typos healed with a ledger, then the same proof — UNVERIFIABLE

**Packet claim.** repair ledger: Einstien→Einstein, poodel→poodle, pooodle→poodle; healed text == intended text: True; derivations identical to the clean-text run: True; greater(einstein,bob)=TRUE ⊢ einstein → mike → rex → spot → bob.

**Reproduction.** `.venv/bin/python scripts/proof_packet.py dirty (GSE.mcp.spell_server.spell_suggest per line); dated script dirty; /tmp/gse-proof/probes/p_spell.py and p_logic.py (entity-leg availability, per-line comparison)`

**Today.**

```
repair ledger: poodel→poodle, pooodle→poodle
healed text == intended text: False
derivations identical to the clean-text run: False
greater(einstein, bob)  =  not entailed
is_a(mike, animal) TRUE; event(mike, mike win) TRUE (same chain as packet); greater(bob, einstein) not entailed; is_a(mike, knife) not entailed
Einstien token: decision 'offered', ambiguous true, suggestions [{'word': 'einstein', 'score': 2.55}], not committed
GSE.nlp.spellcheck_entity._DEFAULT_ENTITIES.available == False (data/spell_entities.db absent)
lines 2-8 healed == intended: True each; 4 of 5 queries identical clean vs healed
clean-text run: greater(einstein, bob) = TRUE ⊢ einstein → mike → rex → spot → bob
```

**Sub-claims.**

- word-leg repairs poodel/pooodle: REPRODUCED
- entity-leg repair Einstien→Einstein and everything that depends on it: UNVERIFIABLE: data/spell_entities.db (derived from data/genealogy.db) absent, so the entity leg is a no-op
- derivation through the clean name: REPRODUCED (clean-text run)
- 0.00000% destruction rate: see §12

**Notes.** Today's transcript does not match the packet on this machine. The difference traces to the missing entity dictionary. The word leg offers 'einstein' as a ranked option but does not commit to it.

**Observation (claim vs evidence).** The packet states 'measured frequency-weighted destruction rate: 0.00000%' but shows no measurement, and scripts/proof_packet.py does not compute it. The repo's scripts/adversarial_destruction.py does compute it, and it needs data/frequency.db, which is absent here (see §12).

### §6. The policy ruling — rules + facts -> verdict with citable chain — REPRODUCED

**Packet claim.** alice lose vote TRUE (chain via rule 1); alice leave board TRUE (rule 1 chained into rule 2); bob lose vote not entailed; carol lose vote not entailed (negated fact fires nothing).

**Reproduction.** `.venv/bin/python scripts/proof_packet.py policy; control probe /tmp/gse-proof/probes/p_logic.py`

**Today.**

```
event(alice, alice lose vote)  =  TRUE  ⊢  fact: alice miss payment → alice → member → rule: member miss payment ⇒ member lose vote → ∴ alice lose vote
event(alice, alice leave board)  =  TRUE  ⊢  fact: alice miss payment → alice → member → rule: member miss payment ⇒ member lose vote → ∴ alice lose vote → alice → member → rule: member lose vote ⇒ member leave board → ∴ alice leave board
event(bob, bob lose vote)  =  not entailed
event(carol, carol lose vote)  =  not entailed
control: + 'Carol is a member.' + 'Carol did not miss the payment.' -> not entailed
control: + 'Carol is a member.' + 'Carol missed the payment.' -> TRUE ⊢ fact: carol miss payment → carol → member → rule … ∴ carol lose vote
```

**Observation (claim vs evidence).** In the packet's premises Carol is never stated to be a member, so her 'not entailed' does not by itself show the negation doing the blocking. The added control (Carol a member) supports the claim: negated fact gives not entailed, positive fact gives TRUE.

### §7. World grounding — the premise the text never states — CHANGED

**Packet claim.** napoleon -> Thing → Agent → Person → Royalty; france -> Thing → Place → PopulatedPlace → Country; event(napoleon, command army)=TRUE via world types; event(france, command army)=not entailed; is_a(napoleon, person)=TRUE; 'Napoleon is a tyrant.' -> tyrant ⟨ALIVE+1, GOOD−1, SOMEONE+1, SOMETHING+1⟩; 'Napoleon is poor.' -> poor ⟨GOOD−1, PEOPLE+1, SOMETHING+1⟩.

**Reproduction.** `.venv/bin/python scripts/proof_packet.py world; dated script world; /tmp/gse-proof/probes/p_world_word.py (the section's rpipe with resolve_references(tree, None), i.e. without the world store)`

**Today.**

```
store = GenealogyStore() -> sqlite3.OperationalError: unable to open database file (both scripts)
store-less word half: 'Napoleon is a tyrant.' -> napoleon[] is_a tyrant ⟨{}⟩
store-less word half: 'Napoleon is poor.' -> napoleon[] is_a poor ⟨{}⟩
active lexicon: lookup_lexeme('tyrant') and ('poor') -> state unread, reason AMBIGUOUS (12 and 21 candidate definitions)
```

**Sub-claims.**

- world type threads, world-grounded rule firing, typed refusal: UNVERIFIABLE: data/genealogy.db absent
- decomposed predicates for tyrant / poor: CHANGED: word_primitives are {} today (packet: ALIVE+1 GOOD−1 SOMEONE+1 SOMETHING+1 / GOOD−1 PEOPLE+1 SOMETHING+1)

**Notes.** Archived-lexicon diagnostic of the same store-less probe prints the packet's exact primitive sets for tyrant and poor, so the empty sets follow the active-lexicon switch. The word half was reproduced without the store; resolve_references with a real store could not be run.

**Observation (claim vs evidence).** §7 says 'the rule's generic subject and generic object both bind' through type lineages. Honest boundaries names the fragment as 'single-antecedent modus ponens with one generic subject bound through the is-a hierarchy'. The section's wording goes beyond the named fragment.

### §8. Contradiction mining — the null axis weaponized — BROKEN

**Packet claim.** 9-sentence corpus -> 2 contradictions: ('event','lock','steward','vault') [0]/[5]; ('isa','knight','loyal') [2]/[7] via dis- prefix; 'Bob did not sign the ledger.' not flagged.

**Reproduction.** `.venv/bin/python scripts/proof_packet.py contradiction; dated script contradiction`

**Today.**

```
current: LookupError: relation_evidence_error:LookupError (raised in _propositions; claim_key -> _decomp('lock') -> GSE.lexical_evidence.lookup_lexeme state 'unread', reason AMBIGUOUS: 44 candidate definitions for 'lock')
dated (rename only): corpus: 9 sentences; contradictions found: 2 — CONTRADICTION on ('event', 'lock', 'steward', 'vault') [0]/[5]; CONTRADICTION on ('isa', 'knight', 'loyal') [2]/[7]; precision check … not flagged   (identical to packet)
```

**Notes.** Archived-lexicon diagnostic of the current script: runs, but finds 1 contradiction (knight loyal/disloyal). All five Event propositions, including the steward/vault pair, are 'WITHHELD Event: unsupported (generic_relation)'. So the current claim authority does not recover the packet's event contradiction even with the old lexicon.

**Observation (claim vs evidence).** The precision-check line is a hard-coded print in both script versions, not a computed test. It is consistent with the dated run, where neither contradiction involves Bob. 'No rule anywhere ... nothing was authored' refers to antonym pairs. The negation prefixes themselves are a fixed list (_NEG_PREFIXES, GSE/nlp/morphology.py:47).

### §9. Reduction — natural language reduces like an equation — BROKEN

**Packet claim.** +loyal(knight), -loyal(knight), not disloyal -> +loyal, not unmerry -> +merry; 'loyal' == 'not disloyal': True; 6-sentence passage collects to 3 terms: 3 × +⟨FEEL+, GOOD-, SOMETHING+⟩(guard, prisoner), 1 × +⟨BODY+, DO+, GOOD+, SOMETHING+⟩(warden, prisoner), 2 × +loyal(knight).

**Reproduction.** `.venv/bin/python scripts/proof_packet.py reduction; dated script reduction`

**Today.**

```
current: 'The knight is loyal.' -> [(1, ('GSE.claim/1', ('type', 'loyal'), …))]; disloyal -> (-1, … 'loyal' …); not disloyal -> (1, … 'loyal' …); not unmerry -> (1, … 'merry' …)
current: supported projection: 'loyal' == 'not disloyal': True
current: passage -> LookupError: relation_evidence_error:LookupError (same cause as §8: verb lookups AMBIGUOUS)
dated: identical to packet, including '3 × +⟨FEEL+, GOOD-, SOMETHING+⟩(guard, prisoner)' … '2 × +loyal(knight)'
```

**Sub-claims.**

- sign composition (clause not × prefix): REPRODUCED as a verdict (new key format)
- passage collects to 3 terms: BROKEN in current script (LookupError)

**Notes.** Archived-lexicon diagnostic of the current script: passage collects to 3 supported terms with the packet's signatures.

### §10. The fingerprint — the representational collapse, live — BROKEN

**Packet claim.** hurt/injure/wound -> {'FEEL': 1, 'GOOD': -1, 'SOMETHING': 1}; harm -> {'GOOD': -1, 'SOMETHING': 1}; attack -> {'DO': 1, 'GOOD': -1, 'SOMETHING': 1}; heal -> {'BODY': 1, 'DO': 1, 'GOOD': 1, 'SOMETHING': 1}; 4 sentences -> 2 distinct forms.

**Reproduction.** `.venv/bin/python scripts/proof_packet.py fingerprint; dated script fingerprint; /tmp/gse-proof/probe_lex.py, probe_enc.py`

**Today.**

```
current: _decomp('hurt') -> LookupError: unread lexical evidence: AMBIGUOUS
active lexicon candidate definitions: hurt 28, injure 6, wound 20, harm 9, attack 41, heal 11; none selected (state unread, reason AMBIGUOUS)
encoder today: Event objects for hurt/injure/wound/heal carry no primitive signature; TypeAssertion kinds carry word_primitives={}
dated: identical to packet (6 signatures, 2 distinct forms), read from data/lexicon_clean.db by the script's own SQL
```

**Notes.** Archived-lexicon diagnostic: the current script reproduces the six signatures and 2 distinct forms.

**Observation (claim vs evidence).** 'A rule written once on the GOOD−1 form covers the whole harm cluster': in the packet's own transcript, harm and attack have signatures that differ from hurt/injure/wound. Exact form equality joins only those three, and matching on a sub-signature is not demonstrated.

### §11. Coined words — meaning for words that never existed — BROKEN

**Packet claim.** 'unloyal' not in 67K lexicon, base loyal={'GOOD': 1} -> kind unloyal {'GOOD': -1}; 'unmerry' not in lexicon, base merry={'FEEL': 1, 'GOOD': 1, 'SOMETHING': 1} -> kind unmerry {'FEEL': 1, 'GOOD': -1, 'SOMETHING': 1}.

**Reproduction.** `.venv/bin/python scripts/proof_packet.py coined; dated script coined; probe_enc.py`

**Today.**

```
current: _decomp('loyal') -> LookupError: unread lexical evidence: AMBIGUOUS
dated: 'unloyal': in the 67K lexicon? False   base loyal = {'GOOD': 1}
dated: 'The knight is unloyal.' -> kind: unloyal {}
dated: 'unmerry': in the 67K lexicon? False   base merry = {'FEEL': 1, 'GOOD': 1, 'SOMETHING': 1}
dated: 'The knight is unmerry.' -> kind: unmerry {}
active lexicon: unloyal/unmerry state no_row (not present); loyal 9 / merry 13 candidate definitions, AMBIGUOUS
```

**Notes.** GSE.nlp.morphology.negation_admission returns code 'lexical_unread' (preserve, no primitives) when the base lookup is unread. Archived-lexicon diagnostic: the current script prints the packet's output exactly.

### §12. The spell-checker — the substrate as a shipped product — UNVERIFIABLE

**Packet claim.** 'I beleive this is teh correct anser' -> 'I believe this is the correct anser'; 'Einstien published …' -> 'Einstein published …'; 'we flew to Melbourn yesterday' unchanged (Melbourn 'is a real village'); frequency-weighted destruction 0.00000%.

**Reproduction.** `.venv/bin/python scripts/proof_packet.py spell; /tmp/gse-proof/probes/p_spell.py; scripts/adversarial_destruction.py run from /tmp/gse-proof/scratch (cwd chosen so its sqlite3.connect('data/frequency.db') cannot create a file in the real data dir)`

**Today.**

```
'I beleive this is teh correct anser' -> 'I believe this is the correct anser'
'Einstien published the theory of relativity' -> 'Einstien published the theory of relativity'
'we flew to Melbourn yesterday' -> 'we flew to Melbourn yesterday'
Melbourn token: decision 'kept', reason 'rarity_unread' (no entity-dictionary recognition; entity leg unavailable)
Einstien token: decision 'offered', suggestion 'einstein' (score 2.55), not committed
```

**Sub-claims.**

- beleive/teh healed, anser kept: REPRODUCED (anser: reason 'valid_word')
- Einstien -> Einstein: UNVERIFIABLE: data/spell_entities.db absent
- Melbourn kept: REPRODUCED in output. The stated reason ('a real village') is not what the token record shows today ('rarity_unread').
- 0.00000% frequency-weighted destruction: UNVERIFIABLE: the frequency weighting needs data/frequency.db, which is absent. The repo's scripts/adversarial_destruction.py was stopped after about 13 minutes, before its 46,783-word unweighted edit-1 scan finished, so no count was obtained (partial output: /tmp/gse-proof/runs/adversarial_destruction.txt).

### §13. Robustness on prose it was never built for — UNVERIFIABLE

**Packet claim.** On a dense mathematical paper, GSE drops un-walkable skeleton edges by name ('could not walk skeleton edge … java.lang.NullPointerException', 'skipped an un-stringifiable skeleton edge') and continues; the document graph still forms and Genesis recovers the load-bearing concepts.

**Reproduction.** `None possible from the packet: no input document, command or script is given; scripts/proof_packet.py has no such section. Searched the GSE tree and git history and ~/Genesis for the log strings.`

**Today.**

```
log strings absent from the GSE tree and GSE history
they were System.err lines in ~/Genesis gsebridge/Understand.java (present at Genesis commit 99b21c4, 2026-07-27, lines 1122/1129); absent from Genesis HEAD f7699c3 (Understand.java still exists)
```

**Notes.** Missing: the input paper, the command, and the emitting code (now gone from Genesis HEAD). The behaviour is Genesis's Java bridge, not a GSE entry point.

**Observation (claim vs evidence).** The claims 'the document graph still forms' and 'Genesis still recovers the load-bearing concepts' rest on two quoted log lines only. The preface says every transcript is output of scripts/proof_packet.py, but this one is not.

### §14. It finds what the author missed — the discovery channel — UNVERIFIABLE

**Packet claim.** Over a 698-document corpus, GSE mention-grounding produced 591 concept-anchors; re-derives 383/550 hand-authored anchors (70%); 208 never tagged, every one CONCEPT-category, each grounded in >=1 literal mention.

**Reproduction.** `None possible: no command, script or corpus location is given in this packet or the Genesis packet (§2.13/§2.15). No code computing these counts was found in GSE or ~/Genesis.`

**Today.**

```
not run
```

**Notes.** Missing: the 698-document corpus, the 550 hand-authored anchors, and the grounding command.

**Observation (claim vs evidence).** 'every one CONCEPT-category, each grounded in ≥1 literal mention' and 'structure his own curation missed' are stated without a listing or adjudication. Genesis packet §2.13, on the related run, says 'Nobody adjudicated the match'. §14 cites Genesis §2.13 for recovery ('it does; see the Genesis packet §2.13'), but §2.13 reports 2,654/2,869 (93%) for the author's hand-written anchors, while §14 reports 383/550 (70%). Neither packet says how the two figures relate.

### §15. The gap is the intelligence — refusing what information theory forbids — UNVERIFIABLE

**Packet claim.** Over the 698-document corpus, the world-grounding filter resolves 297 generic concepts and 32 aliases by form; 31 world-absent concepts and 9 dangling acronyms (COEC, ELLMO, NCEMS, PVUI) are abstained and routed to review with reasons.

**Reproduction.** `None possible: no command or script given; the world-grounding filter needs data/genealogy.db.`

**Today.**

```
not run
```

**Notes.** Missing: corpus, command, and data/genealogy.db.

**Observation (claim vs evidence).** 'exactly the set whose meaning is the author's free definition' is asserted without the list or an adjudication.

## Footer demos named by the packet (not among the 15)

- `GSE.verification.symbolic_proof_suite (packet: '(13/13)')`: Total: 12 PASSED, 0 FAILED, 1 ABSTAINED (exit 2). bipolar_distinct_from_relational ABSTAINED: LEXICAL_SELECTION_UNAVAILABLE ('big' ambiguous in the active lexicon).
- `GSE.demo.reasoning`: exit 0; transitive is-a and ordering proofs print; section 2 prints ungrounded(zorble), ungrounded(florp) with genealogy=None (see §2 control); section 3 prints no WordNet genealogy (no store).
- `GSE.demo.showcase`: exit 0; cosine(A,B)=1.000 with dog>cat / cat>dog distinct; encode x3 sha256:182880d23dec32f2 identical; word_primitives={} on every Atom shown.
- `Test suite '4,000 passed'`: not run (not one of the 15 demonstrations)

## Packet-wide observations

- The preface says every transcript is literal output of one run of scripts/proof_packet.py. That script has sections for §1–§12 only. §13's log lines come from Genesis's Java bridge, and §14–§15 have no script. The 'Bottom line' says 'Twelve sections, one script', but the packet has fifteen.
- Lexicon-pointer dependency, which changes no classification: data/lexicon_active.json is untracked and gitignored (written 2026-11-19). It selects the 20 GB versioned lexicon sparse-release-021.db. A fresh clone has no pointer and falls back to the tracked data/lexicon_clean.db. The archived-lexicon diagnostic runs the current code in that fallback. There, §9, §10 and §11 reproduce, the §2 digest is b1aacd8a02f3 as in the packet, and the §7 word half matches. §8 still finds only 1 of 2 contradictions, because the steward/vault Event is withheld as generic_relation. Results on this machine therefore depend on local, unversioned state.

Raw outputs: `/tmp/gse-proof/runs/`; probes: `/tmp/gse-proof/probes/`, `/tmp/gse-proof/probe_lex.py`, `/tmp/gse-proof/probe_enc.py`.
