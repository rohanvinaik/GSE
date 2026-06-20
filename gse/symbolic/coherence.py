"""Coherence gate — the generalized parse-degradation verifier.

The shipped repair (``gse.api.parse_repair``) fixes ONE spaCy failure mode (the
verb-POS mistag) at parse time. This module is the complement: after the
pipeline has run, it *verifies* that every clause cohered, and flags the ones
that did not — including failure modes no repair handler covers. A flagged
clause is surfaced to Genesis so it can **abstain** (not learn a rule from a
silently-wrong structure) rather than ingest the collapse.

Mirrors ``gse.symbolic.variables`` exactly: a wrapper around the *unchanged*
pipeline (``encode → from_trace → evaluate_tree → resolve → emit``) with ZERO
core edits. The ``coherence`` key is added only when something is degraded, so a
fully-coherent emit is byte-identical to plain ``emit_contract``.

v1 signal — **collapse detection**: a clause that resolved to a bare nominal
(``Atom``/``Phrase``/``Entity``) despite containing a verb-sense token AND a
distinct entity-like token (a would-be subject) "should have been" a
predication and was not. A verbless noun phrase ("the big red ball" — verb-sense
head ``ball`` but no distinct subject) is correctly left alone. Pre-tokenization
mangles (placeholder collapse "xx betray yy" → one token) are an honest miss —
the verb sense is already lost. The richer *selectional* check (partial
degradations like instrument-lumped-into-object) is a deliberate later increment.
"""

from __future__ import annotations

from typing import Any, List, Optional

from gse.api.parse_repair import _has_adjective_sense, _has_verb_sense
from gse.symbolic.expression import Atom, Negation, Phrase
from gse.symbolic.predicates import (
    Causation,
    ClauseCoordination,
    Conditional,
    Contrast,
)
from gse.symbolic.resolution import Coordination, Entity

_NOMINAL_POS = {"PROPN", "NOUN", "PRON"}
# Nodes that are bare nominals — a clause that resolves to one of these (rather
# than a predicate) is a candidate collapse.
_BARE = (Atom, Phrase, Entity, Coordination)


def _entity_like(tok) -> bool:
    """A referential nominal in a TokenTrace — including a proper noun the mistag
    demoted to ADJ (title-case content word that is not actually an adjective)."""
    if tok.pos in _NOMINAL_POS:
        return True
    return (
        tok.pos in {"ADJ", "X"}
        and tok.token.isalpha()
        and tok.token.istitle()
        and not _has_adjective_sense(tok.lemma)
    )


def _atoms(node: Any) -> List[Atom]:
    """Collect the Atoms under a bare nominal node."""
    if isinstance(node, Atom):
        return [node]
    if isinstance(node, Phrase):
        return list(node.atoms)
    if isinstance(node, Entity):
        out = [node.head] if isinstance(node.head, Atom) else []
        if isinstance(node.modifier, Atom):
            out.append(node.modifier)
        if isinstance(node.possessor, Entity):
            out.extend(_atoms(node.possessor))
        return out
    if isinstance(node, Coordination):
        out: List[Atom] = []
        for m in node.members:
            out.extend(_atoms(m))
        return out
    return []


def _is_collapsed_clause(node: Any, trace) -> bool:
    """True if a bare node looks like a clause that failed to predicate: it holds
    a verb-sense token AND a *distinct* entity-like token (a would-be subject)."""
    atoms = _atoms(node)
    toks = [trace.tokens[a.position] for a in atoms
            if 0 <= a.position < len(trace.tokens)]
    verb_positions = {t.position for t in toks if _has_verb_sense(t.lemma)}
    if not verb_positions:
        return False
    return any(_entity_like(t) for t in toks if t.position not in verb_positions)


def coherence_report(tree: Any, trace) -> List[dict]:
    """Walk an evaluated predicate tree; return one record per degraded clause.

    Recurses into the clause-arguments of clause-linking predicates (Causation,
    Contrast) and through Negation; stops at any other predicate (coherent). Only
    bare nominal nodes at a clause position are tested for collapse.
    """
    degraded: List[dict] = []

    def visit(node: Any) -> None:
        if isinstance(node, Causation):
            visit(node.cause)
            visit(node.effect)
        elif isinstance(node, (Contrast, ClauseCoordination)):
            visit(node.left)
            visit(node.right)
        elif isinstance(node, Conditional):
            visit(node.antecedent)
            visit(node.consequent)
        elif isinstance(node, Negation):
            visit(node.operand)
        elif isinstance(node, _BARE):
            if _is_collapsed_clause(node, trace):
                atoms = _atoms(node)
                positions = sorted(
                    a.position for a in atoms
                    if 0 <= a.position < len(trace.tokens)
                )
                surface = " ".join(trace.tokens[p].token for p in positions)
                degraded.append({
                    "clause": surface,
                    "positions": positions,
                    "reason": "collapse",
                })
        # any other predicate node → coherent; stop.

    visit(tree)
    return degraded


def emit_contract_with_coherence(encoder, text: str) -> Any:
    """Coherence-gated emit: run the unchanged GSE pipeline, then attach a
    ``coherence`` report of degraded clauses. Byte-identical to plain
    ``emit_contract`` when nothing is degraded. ``encoder`` is a live
    ``gse.api.GSEEncoder``."""
    from gse.symbolic import (
        GenealogyStore,
        evaluate_tree,
        from_trace,
        resolve,
        resolve_references,
    )
    from gse.symbolic.emit import emit_contract

    trace = encoder.encode(text)
    tree = evaluate_tree(resolve(from_trace(trace)))
    resolved = resolve_references(tree, GenealogyStore())
    contract = emit_contract(resolved)

    report = coherence_report(tree, trace)
    if report:
        contract = {**contract, "coherence": {"degraded": report}}
    return contract


def emit_contract_with_variables_and_coherence(
    encoder, text: str, variables: Optional[dict] = None
) -> Any:
    """Compose the two extensions: typed-variable substitution AND the
    degraded-clause report, over the one unchanged pipeline pass. Sentinel
    surfaces in the report are restored to ``$var`` names."""
    from gse.symbolic import (
        GenealogyStore,
        evaluate_tree,
        from_trace,
        resolve,
        resolve_references,
    )
    from gse.symbolic.emit import emit_contract
    from gse.symbolic.variables import restore, substitute

    sub_text, sentinel_map = substitute(text, variables)
    trace = encoder.encode(sub_text)
    tree = evaluate_tree(resolve(from_trace(trace)))
    resolved = resolve_references(tree, GenealogyStore())
    contract = emit_contract(resolved)

    report = coherence_report(tree, trace)
    if report:
        for d in report:
            for sent, (name, _vtype) in sentinel_map.items():
                d["clause"] = d["clause"].replace(sent, f"${name}")
        contract = {**contract, "coherence": {"degraded": report}}
    return restore(contract, sentinel_map)
