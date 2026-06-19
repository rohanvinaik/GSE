# GSE Extension Map — Variables & Case-Roles (for Genesis KB authoring)

> Reference map for two extensions that let GSE serve as Genesis's rule-authoring front-end:
> **(A) typed pattern variables** (declared, surviving the parse) and **(B) case-role separation**
> (instrument/co-agent instead of lumping prepositional phrases into the object). Produced by a
> codebase-mapping pass 2026-06-19; verify file:line against the source before editing.
>
> **STATUS (2026-06-19):**
> - **(A) typed variables — BUILT, VERIFIED, AND CONSUMED END-TO-END.** GSE side: `gse/symbolic/variables.py`
>   (`emit_contract_with_variables`) substitutes declared vars → nonce sentinels → unchanged pipeline →
>   restores typed variable-refs (`lemma="$X"`, `var_type`, distinct entity_ids). Both formats
>   (`X is a person.` / inline `${x:person}`) verified; ZERO core edits; symbolic suite green (3922).
>   Bridge side (Genesis repo, `--fire-typed`): rule clauses route through a variable-aware transport
>   (`gse_emit_rules.py` / server `R` tag), the walker builds each var as a plain `new Entity("variable")`,
>   and the declared type is enforced the ENGINE's way — a `be(var, type)` antecedent in the rule plus a
>   synthesized `be`-fact on each story entity. **Verified live (RuleTypeProbe + end-to-end fire):** a
>   `person`-guarded retaliation rule fires on `soldier harms king` and is correctly silent on
>   `soldier harms table`. NOTE — the type does NOT ride on the variable entity: the StoryProcessor fire
>   matcher only recognizes `"variable"`-typed slots as bindable and IGNORES any type on them (a `"?"`-typed
>   slot is treated as a literal and never matches); it also will not read type from a thread at match time.
>   So the be-antecedent + synthesized be-fact is the working mechanism, not `addType` on the variable.
> - **(B) case-roles — DEFERRED (scoped, not built).** Genuinely invasive (encoder arg-collection +
>   predicate dataclasses + emit + resolution) for a refinement; SVO + typed vars cover the bulk of
>   commonsense rules. The touch points below are ready when it's wanted; do it as a focused pass.

## Pipeline
```
spaCy (front-end, only non-deterministic component)
 → gse/api/encoder.py        tokenize, dynamic role assignment, clause segmentation → OperationTrace
 → gse/symbolic/from_trace   → Expression AST
 → gse/symbolic/operators.py → predicates.py  (Comparison/TypeAssertion/Causation/Control/Event/…)
 → gse/symbolic/grounding.py + genealogy_store.py  (entity ids + two-strand type threads)
 → gse/symbolic/emit.py      → Genesis contract {op, args[], features{}}
```
Three-stage resolution per `docs/RESOLVED_STRUCTURE_DESIGN.md` (predicate tree → entity identity → context).

## Verified behaviour (raw `emit_contract`)
- `a person betrays a king` → `EVENT(betray,[person,king])` with **full WordNet threads** (person→living_thing→…; king→…→king). **The type machinery already works.**
- `Macbeth kills Duncan with a knife` → `e1.lemma="duncan knife"` — **instrument lumped into the object at the GSE level** (not the walker). Extension B.
- `XX betrays YY` → one collapsed entity `lemma="xx betray yy"` — **spaCy mangles placeholder tokens before the symbolic core** (the vision doc's named soft spot). Extension A.

## Extension A — typed variables (dual format)
A variable is a **named, typed** placeholder. Two syntaxes, one mechanism:
- **Winston (primary, human):** `X is a person.` declarations + `If X harms Y then Y harms X.`
- **Ugly (scripts):** inline `${x:person}` — name+type together, no declaration block.
Mechanism: **preprocess before spaCy** — substitute each variable occurrence (keyed by name) with a
distinct clean sentinel noun spaCy parses cleanly; carry `is_variable` + `declared_type`; after emit,
map sentinels back to variable refs and set `type_thread` from the declared type. Same name → same
sentinel → GSE corefs → one variable; distinct names → distinct variables (two-same-type works).
- Touch points: `encoder.py:375` `_extract_dynamic_primitives`; `trace.py` `TokenTrace` (+`is_variable`,`declared_type`); `resolution.py:114` preserve VAR; a variable genealogy provider; `emit.py:56` `_leaf_str`.

## Extension B — case-role separation
Collapse origin: `encoder.py:37` `DEP_TO_SYNTACTIC` maps `pobj`/`prep`/`obl` → `SYN_OBJ`, erasing role
before resolve. Chain to fix: expand DEP map (`obl:agent`,`obl:instrument`,`case`) → new `CaseRole`
node in `resolution.py` → optional `roles` field on `Event`/`Causation`/… in `predicates.py` →
serialize in `emit.py` (`features.roles`) → recurse in `grounding.py:113` `_map_entities`.
**Backward-compat:** `roles` defaults empty → byte-identical traces when unused (`RESOLVED_STRUCTURE_DESIGN.md §7`).

## Risks / open questions
- `with` = instrument vs co-agent: needs the coherence-scored sense selector to rank role senses.
- PP-attachment ambiguity ("king of Scotland with a knife"): spaCy decides, can be wrong.
- Variable scope is sentence-local today (`grounding.py:85`); cross-sentence is Stage-3 work.
