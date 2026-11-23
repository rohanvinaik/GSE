# GSE build program — start here

For the issue/OpenSpec/receipt workflow, read [EXECUTION_WORKFLOW.md](EXECUTION_WORKFLOW.md). `ISSUE_MAP.json` maps stable IDs to the cross-repository board.

The [gap ledger](BUILD_GAPS.md) maps observed seams and dated reports to the work packages. Read it with the glossary, specification, assurance contract and source manifest before implementing.

This is GSE's part of a three-repository program. Read this file, [GLOSSARY.md](GLOSSARY.md), [BUILD_SPEC.md](BUILD_SPEC.md), and [ASSURANCE.md](ASSURANCE.md) before taking a work package. `REFERENCE_MANIFEST.json` pins the exact reference texts used to draft this program; `WORK_INDEX.json` carries stable IDs and cross-repository dependencies. Run `python3 scripts/check_program.py` to check the references and work graph. The checker reports missing sibling repositories explicitly.

## Founder intent, recorded 2026-10-23

Rohan: “GSE handles the question ‘how do we make English computable?’, Regenesis handles ‘How do we perform reasoning on this subjective/semantic domain?’” His later ownership instruction is decisive: “Sparse-Wiki should be substantially redone to hold ALL the world-grounding implementation, GSE all the work to encode language into computable artifacts, Regenesis for all inference and reasoning on this substrate.” The Anglican three-legged-stool reference means **independent supporting channels**. GSE's linguistic account, Sparse Wiki's world evidence, and Regenesis's derivations retain separate warrants and provenance. A computed world value derived from GSE data declares that lineage; it is not independent corroboration.

GSE owns lexical definition over the fixed NSM basis, grammar, typed roles and operators, traceable sentence/document artifacts, conservative input repair, and bounded genre/register/style observations. Its learned genre profiler is a permitted, bounded tail over deterministic GSE measurements. Regenesis owns the semantic and story conclusions drawn from those artifacts. Sparse Wiki owns world data, candidate referents, traversal, and its derivation record. GSE imports that world channel through its existing resolution/provider path; the world data build and world resolver move out of GSE.

For GSE-01, read [Rohan's founder words](LEXICON_FOUNDER_WORDS_2026-10-24.md) and the single active [lexicon construction design](LEXICON_CONSTRUCTION_DESIGN.md). Rohan's 2026-10-24 corrections are decisive: **bank relations are the basic construction laws**; hand-defined primes are the smallest stable lexical contents, each identified by its intended sense and basic combinatorial profile; native source facts restrict the legal combinations for a located reading. The 72 lexical primes reduce through 14 opposite-pole pairs to 58 signed coordinates. `NUMBER` is his separate sign- and mask-preserving scale operation, **not** a 73rd lexical prime or bank. POS is one small constraint. Neither WordNet nor a gloss is the organizing source of truth. The old all-prime, gloss/clause, source-voting, and WordNet-first routes are retired. Design §§5.3 and 7.1 now locate the saved coherence candidates, rulebook, dependency audit, and new executable constructor prototype. Its initial simple-word candidates are not a completed lexical rulebook or an audited production lexicon.

## Authority and re-grounding

1. Rohan's current words govern intent. This page records them; if he corrects it, update the record and affected packages.
2. Code and a real entry-point run establish current behavior. A dated paper, proof packet, README, or plan establishes what its author claimed at that time. `docs/THEORY.md` is known invalid and is excluded.
3. Check reference hashes. A mismatch means the cited source changed; read the **whole changed document or coherent section**, decide whether the claim still holds, and revise the manifest and affected packages together. A missing source is `UNAVAILABLE_REFERENCE`, not agreement.
4. Read the complete enclosing definition and its producer/consumer path. Before altering a symbol, trace production references and any second implementation of the same job. A defined or tested component may have no live consumer.
5. Record a work-package restatement in the implementing change: authored input → computation → emitted artifact → consuming decision → abstention. Mark each premise `USER_INTENT`, `CODE_OBSERVED`, `DATED_REPORT`, `INFERENCE`, or `UNRESOLVED`. Resolve material conflicts from primary sources; ask Rohan when those are silent.
6. Run the package's positive and MUST-NOT witnesses through the real entry point. Attach the commands, fixture/data versions, outcome classes, and receipts. Update package status only from that evidence.

The [ARC_AGI_3 glossary](../../../ARC_AGI_3/docs/GLOSSARY.md), [gap ledger](../../../ARC_AGI_3/docs/BUILD_GAPS.md), [reference manifest](../../../ARC_AGI_3/docs/REFERENCE_MANIFEST.yaml), and [dependency contract](../../../ARC_AGI_3/docs/DEPENDENCY_CONTRACT.md) supplied the re-grounding pattern. ARC's historical ownership table places world data in GSE; Rohan's current instruction above supersedes that ownership for this program.

## Cross-repository handoff

| Owner | Supplies | Receives |
|---|---|---|
| [Sparse Wiki](../../../sparse-wiki-grounding/docs/program/START_HERE.md) | Versioned referent candidates and signed, banked world-path evidence | Mention/context request and independently derived data lineage |
| **GSE** | Versioned linguistic/document record, role bindings, repair ledger, profile observations, world result references | Text and Sparse Wiki world results |
| [Regenesis](../../../Regenesis/docs/program/START_HERE.md) | Provenanced story inferences, revisions, predictions, questions, refusals | GSE records plus cited world premises |

The cross-repository integration lock belongs to the Regenesis real-entry-point harness once it has verified exact commits and data digests. A HEAD hash from an unverified or dirty checkout is not a compatibility pin. The existing ARC `stack.lock` is a historical verified combination, not this program's completion receipt.

## Work-package discipline

Take one `GSE-*` ID from `WORK_INDEX.json` and its full section in `BUILD_SPEC.md`. Check its dependency IDs, source hashes, current code, and actual consumer. Use a small OpenSpec change for implementation and link the stable program ID in the proposal. The program spec holds enduring intent; OpenSpec holds the engineering delta; an issue or board card points to the ID and implementation change. No board field can silently rewrite this contract.

The [three-repository GitHub Project](https://github.com/users/rohanvinaik/projects/5) is the execution board. The existing [GSE overhaul Project](https://github.com/users/rohanvinaik/projects/4) retains its GSE-specific history and work; reconcile related cards explicitly rather than duplicating or silently replacing them.

Results are recorded by class: identified, abstained, wrong, unavailable, and partial. A single score does not substitute for that ledger. The quality, mutation, performance, and CI rules are in [ASSURANCE.md](ASSURANCE.md).
