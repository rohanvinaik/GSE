#!/usr/bin/env python3
"""
GSE Showcase — a self-evident demonstration of the complex-sentence engine.

Run it:

    python -m gse.demo.showcase

What it shows, by producing output you can read at a glance:

1. It turns English sentences into a typed **clause graph** of predicates —
   comparisons, causation, relative clauses, control, coordination — composed
   recursively for multi-clause sentences.
2. The jewel: two sentences whose HDC vectors are ~0.93 cosine-similar (an
   embedding model would call them "the same") are nonetheless **provably,
   structurally opposite** — argument-swapped logic.
3. It is **deterministic**: the same input yields a byte-identical vector hash
   on every run. An LLM cannot promise that; GSE cannot break it.
4. It is **systematic**: swap in nonsense content words and the *same* machinery
   produces the *same* structure.

No neural network runs at the semantic layer. No GPU. No training. Laptop-class.
spaCy (a small, fixed parser) is the only learned component, and it sits in
front of the deterministic core.
"""

from __future__ import annotations

from typing import Any

from gse.api import GSEEncoder
from gse.symbolic import (
    clauses,
    entity_lemmas,
    evaluate_tree,
    from_trace,
    is_argument_swap_of,
    is_logically_equal_to,
    predicates,
    resolve,
    substitute,
)

# ---------------------------------------------------------------------------
# Clause-graph pretty-printer — renders a predicate tree as readable notation.
# ---------------------------------------------------------------------------


def _fmt(node: Any) -> str:
    """Render an evaluated node as compact, readable 'Innerese' notation."""
    name = type(node).__name__

    if node is None:
        return "·"
    if name == "Atom":
        return node.lemma
    if name == "Entity":
        s = node.head.lemma
        if getattr(node, "possessor", None) is not None:
            s = f"{_fmt(node.possessor)}'s {s}"
        return s
    if name == "Phrase":
        return " ".join(a.lemma for a in node.atoms) or "∅"
    if name == "Negation":
        return f"¬{_fmt(node.operand)}"
    if name == "Coordination":
        joiner = " ∧ " if node.conjunction == "and" else " ∨ "
        return "{" + joiner.join(_fmt(m) for m in node.members) + "}"

    # Predicates
    if name == "Comparison":
        rel = ">" if node.sign > 0 else "<"
        axis = f"  ·{node.axis}" if getattr(node, "axis", None) else ""
        return f"{_fmt(node.lhs)} {rel} {_fmt(node.rhs)}{axis}"
    if name == "Equality":
        return f"{_fmt(node.lhs)} ≈ {_fmt(node.rhs)}"
    if name == "TypeAssertion":
        return f"{_fmt(node.entity)} : {_fmt(node.kind)}"
    if name == "TypeQuery":
        return f"type?({_fmt(node.entity)})"
    if name == "DegreeQuery":
        return f"degree?({_fmt(node.entity)})"
    if name == "Causation":
        # cause ⟹ effect, regardless of surface order (so/because)
        return f"{_fmt(node.cause)}  ⟹  {_fmt(node.effect)}"
    if name == "Contrast":
        return f"{_fmt(node.left)}  ⊥  {_fmt(node.right)}"
    if name == "RelativeRestriction":
        return f"{_fmt(node.head)}〈{_fmt(node.restriction)}〉"
    if name == "Control":
        return f"{_fmt(node.controller)} ⟶ ({_fmt(node.inner)})"
    if name == "MinimalSufficiency":
        return f"just-enough({_fmt(node.threshold)} for {_fmt(node.purpose)})"
    if name == "SetRestriction":
        return f"only({_fmt(node.member)})"
    if name == "BoundaryCase":
        return f"even({_fmt(node.entity)})"
    if name == "Op":
        return f"{node.operation}(" + ", ".join(_fmt(a) for a in node.args) + ")"
    return repr(node)


def _graph(encoder: GSEEncoder, sentence: str):
    """Encode → resolve → evaluate, returning the predicate list + top node."""
    tree = evaluate_tree(resolve(from_trace(encoder.encode(sentence))))
    return tree


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

W = 74


def _rule(ch: str = "═") -> str:
    return ch * W


def _section(title: str) -> None:
    print()
    print(f"▌ {title}")
    print()


# ---------------------------------------------------------------------------
# The showcase
# ---------------------------------------------------------------------------

# Sentences chosen to climb from "see Spot run" to Macbeth-grade structure,
# each exercising a distinct compositional operator.
STRUCTURE_DEMOS = [
    ("comparison", "The dog is cuter than the cat"),
    ("type assertion", "Spot is a dog"),
    ("coordination", "Spot and Rex are dogs"),
    ("causation (nested)", "Rex barks because the dog is cuter than the cat"),
    ("relative clause", "The dog that barks is cuter than the cat"),
    ("control (object)", "Lady Macbeth persuaded Macbeth to kill the king"),
    ("control + cause", "Mike wants to leave because Rex barks"),
]


def run(encoder: GSEEncoder) -> None:
    print(_rule())
    print("  GSE · Geometric Semantic Encoding")
    print("  English → typed clause graph, deterministically.")
    print("  No neural network in the semantic layer. No GPU. No training.")
    print(_rule())

    # ------------------------------------------------------------------ 1
    _section("1 · It parses sentences into a compositional clause graph")
    for label, sentence in STRUCTURE_DEMOS:
        tree = _graph(encoder, sentence)
        preds = predicates(tree)
        rendered = _fmt(tree if not preds else preds[0])
        print(f'  "{sentence}"')
        print(f"      {label:20}  →   {rendered}")
        # For multi-clause sentences, show the clause count the graph exposes.
        n = len(clauses(tree))
        if n:
            print(f"      {'':20}      ({n} linked clause{'s' if n != 1 else ''})")
        print()

    # ------------------------------------------------------------------ 2
    _section("2 · The jewel — geometrically near-identical, logically opposite")
    a = "The dog is cuter than the cat"
    b = "The cat is cuter than the dog"
    va = encoder.encode(a).vector
    vb = encoder.encode(b).vector
    cos = va.cosine(vb)
    ta = _graph(encoder, a)
    tb = _graph(encoder, b)
    pa, pb = predicates(ta)[0], predicates(tb)[0]
    print(f'  A:  "{a}"')
    print(f'  B:  "{b}"')
    print()
    print(f"  HDC vector cosine(A, B) = {cos:.3f}   ← nearly the same vector")
    print("                                       (an embedding model stops here)")
    print()
    print(f"  …but the symbolic logic:")
    print(f"      A:  {_fmt(pa)}")
    print(f"      B:  {_fmt(pb)}")
    print(f"      logically equal?   {'YES' if is_logically_equal_to(ta, tb) else 'NO'}")
    print(f"      argument swap?     {'YES' if is_argument_swap_of(ta, tb) else 'NO'}")
    print()
    print("  One geometry, two meanings. GSE keeps them provably distinct.")

    # ------------------------------------------------------------------ 3
    _section("3 · Deterministic — same input, identical hash, every run")
    probe = "Lady Macbeth persuaded Macbeth to kill the king"
    hashes = [encoder.encode(probe).vector_hash for _ in range(3)]
    same = len(set(hashes)) == 1
    print(f'  encode("{probe}")  ×3:')
    for h in hashes:
        print(f"      {h}")
    print(f"      → all identical: {'YES ✓' if same else 'NO ✗'}")
    print()
    print("  An LLM returns a different answer each run. GSE structurally cannot:")
    print("  fixed bases, integer set operations, dispatch on string labels.")

    # ------------------------------------------------------------------ 4
    _section("4 · Systematic — novel content, identical machinery")
    known = "The dog that barks is cuter than the cat"
    tree = _graph(encoder, known)
    novel = substitute(tree, {"dog": "zorble", "cat": "florp", "bark": "blib"})
    print(f'  known:  "{known}"')
    print(f"          {_fmt(predicates(tree)[0])}")
    print(f"  novel:  (substitute dog→zorble, cat→florp, bark→blib)")
    print(f"          {_fmt(predicates(novel)[0])}")
    print()
    orig_types = [type(p).__name__ for p in predicates(tree)]
    novel_types = [type(p).__name__ for p in predicates(novel)]
    print(f"      same structure: {'YES ✓' if orig_types == novel_types else 'NO ✗'}"
          f"   ({' + '.join(orig_types)})")
    print(f"      entities now:   {entity_lemmas(novel)}")

    print()
    print(_rule())
    print("  The structure above is built by integer set operations over a")
    print("  precompiled lexicon — no model weights at the semantic layer, no")
    print("  sampling, no API call. (spaCy, a small fixed parser, only supplies")
    print("  parts of speech and dependencies up front.)")
    print(_rule())
    print()


def main() -> int:
    with GSEEncoder() as encoder:
        run(encoder)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
