#!/usr/bin/env python3
"""
GSE Reasoning Showcase — solve a logical-reasoning problem, deterministically.

    python -m gse.demo.reasoning

The full architecture on an LSAT-style logic problem, every line live output:

1. **It solves the logic.** Type-syllogism and linear ordering, derived by
   transitive closure over the clause graph — *with the proof chain* — refusing
   the unentailed direction. No model, no training, no GPU: integer set ops.
2. **Structure ⟂ grounding, and it is honest about which it has.** On a word in
   no lexicon, GSE derives the comparison structure *and* flags that it cannot
   ground the word. An LLM cannot separate "I solved it" from "I understand it."
3. **The full stack on real words** — ground + resolve + reason, end to end,
   with the type genealogy that grounds the conclusion.

The premises are separate English sentences, resolved across sentence boundaries
into one knowledge base, then reasoned over.
"""

from __future__ import annotations

from gse.api import GSEEncoder
from gse.symbolic import (
    KnowledgeBase,
    evaluate_tree,
    from_trace,
    grounding_flags,
    predicates,
    resolve,
    resolve_document,
    resolve_references,
)

W = 74


def _rule(ch: str = "═") -> str:
    return ch * W


def _section(title: str) -> None:
    print(f"\n▌ {title}\n")


def _doc(encoder, sentences, genealogy=None):
    trees = [evaluate_tree(resolve(from_trace(encoder.encode(s)))) for s in sentences]
    return resolve_document(trees, genealogy)


def run(encoder: GSEEncoder, genealogy=None) -> None:
    print(_rule())
    print("  GSE · Logical reasoning, deterministically")
    print("  English premises → typed clause graph → transitive closure → answer")
    print(_rule())

    # ------------------------------------------------------------------ 1
    _section("1 · Solve the logic — derived, with proof, direction respected")
    premises = [
        "All woodles are zoodles",
        "All zoodles are floops",
        "Bing is a woodle",
        "A snib is bigger than a wug",
        "A wug is bigger than a glonk",
    ]
    kb = KnowledgeBase.from_trees(_doc(encoder, premises, genealogy))
    print("  Premises — five separate sentences, resolved into one problem:")
    for p in premises:
        print(f"      {p}.")
    print("\n  Queries — each answer is a derivation with its chain:")
    for d in [
        kb.is_a("bing", "floop"),
        kb.is_a("bing", "zoodle"),
        kb.is_a("floop", "bing"),
        kb.greater("snib", "glonk"),
        kb.greater("glonk", "snib"),
    ]:
        print(f"      {d}")
    print("\n  Read off the geometry of the clause graph — a proof, not a guess.")
    print("  The words could be invented or real: the inference uses only the")
    print("  structure (the is-a and ordering edges), never the words' meanings.")

    # ------------------------------------------------------------------ 2
    _section("2 · Structure ⟂ grounding — it solves, and flags what it can't ground")
    sent = "The zorble is bigger than the florp"
    tree = resolve_references(evaluate_tree(resolve(from_trace(encoder.encode(sent)))), genealogy)
    comp = predicates(tree)[0]
    flags = grounding_flags(tree)
    print(f'  "{sent}"')
    print(
        f"      structure derived:  {type(comp).__name__}"
        f"({comp.lhs.head.lemma} {'>' if comp.sign > 0 else '<'} {comp.rhs.head.lemma})"
    )
    print(f"      grounding:          {[f'{f.kind}({f.lemma})' for f in flags]}")
    print("\n  'zorble' and 'florp' are in no lexicon and no corpus. GSE builds the")
    print("  comparison structure correctly *and* tells you it cannot ground either")
    print("  word — clean structure plus a catalogued residual. It never fabricates")
    print("  a meaning to paper over the gap. (An LLM cannot hand you that split.)")

    # ------------------------------------------------------------------ 3
    _section("3 · The full stack on real words — ground + resolve + reason")
    real = ["A poodle is a dog", "A dog is an animal"]
    rtrees = _doc(encoder, real, genealogy)
    rkb = KnowledgeBase.from_trees(rtrees)
    for p in real:
        print(f"      {p}.")
    print()
    print(f"      {rkb.is_a('poodle', 'animal')}")
    if genealogy is not None:
        from gse.symbolic import emit

        grounded = {}
        for t in rtrees:
            stack = [emit(t)]
            while stack:
                n = stack.pop()
                if isinstance(n, dict):
                    if n.get("type_thread"):
                        grounded[n["lemma"]] = " → ".join(n["type_thread"][-3:])
                    stack += list(n.values())
                elif isinstance(n, list):
                    stack += n
        if grounded:
            print("\n      grounded (WordNet type genealogy, last hops):")
            for lemma, thread in sorted(grounded.items()):
                print(f"        {lemma:8} …→ {thread}")
    print("\n  Same transitive closure — now over words the system also *grounds*.")

    print()
    print(_rule())
    print("  Reasoning is set operations over a typed clause graph: the premises")
    print("  were English sentences; the conclusions are derivations with")
    print("  provenance; the determinism is structural. (A deterministic")
    print("  GSE-native front-end supplies POS; everything from the clause")
    print("  structure down is symbolic — no statistical parser anywhere.)")
    print(_rule())
    print()


def main() -> int:
    genealogy = None
    try:
        from gse.symbolic import GenealogyStore

        genealogy = GenealogyStore()
    except Exception:
        genealogy = None
    with GSEEncoder() as encoder:
        run(encoder, genealogy)
    if genealogy is not None:
        genealogy.close()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
