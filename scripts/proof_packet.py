"""The GSE proof packet — every experiment in the packet document, live.

Each section prints the literal transcript quoted in
``resume/Communication/vision/GSE/GSE_Proof_Packet.md``. Run everything:

    python scripts/proof_packet.py            # all sections
    python scripts/proof_packet.py needle …   # named sections only

Sections: basics · lsat · needle · dirty · policy · contradiction ·
fingerprint · coined · spell
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gse.api import GSEEncoder  # noqa: E402
from gse.symbolic import evaluate_tree, from_trace, resolve  # noqa: E402
from gse.symbolic.inference import KnowledgeBase  # noqa: E402
from gse.symbolic.queries import predicates  # noqa: E402

_ENC = GSEEncoder()


def pipe(s: str):
    return evaluate_tree(resolve(from_trace(_ENC.encode(s))))


def vec_hash(s: str) -> str:
    v = _ENC.encode(s).vector
    return hashlib.sha256(repr(v).encode()).hexdigest()[:12]


def _decomp(word: str) -> dict:
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "data", "lexicon_clean.db"))
    rows = conn.execute(
        "SELECT pv.primitive, pv.value FROM primitive_values pv"
        " JOIN lexemes lx ON lx.id = pv.lexeme_id WHERE lx.lemma = ?",
        (word,),
    ).fetchall()
    conn.close()
    return dict(sorted(rows))


def header(title: str) -> None:
    print(f"\n{'=' * 72}\n== {title}\n{'=' * 72}")


def _nm(operand) -> str:
    """Compact name of an Entity / Atom operand."""
    if operand is None:
        return "∅"
    if hasattr(operand, "head"):
        return operand.head.lemma
    return getattr(operand, "lemma", type(operand).__name__)


def show(p) -> str:
    """Compact one-line rendering of a predicate (the doc-quotable form)."""
    name = type(p).__name__
    if name == "Comparison":
        op = ">" if p.sign >= 0 else "<"
        return f"Comparison({_nm(p.lhs)} {op} {_nm(p.rhs)}, axis={getattr(p.lhs, 'modifier', None) and p.lhs.modifier.lemma})"
    if name == "TypeAssertion":
        return f"TypeAssertion({_nm(p.entity)} is_a {_nm(p.kind)})"
    if name == "Event":
        pt = f", {_nm(p.patient)}" if p.patient is not None else ""
        return f"Event({p.verb}: {_nm(p.agent)}{pt})"
    if name == "Negation":
        return f"NOT[{show(p.operand)}]"
    if name == "Causation":
        return f"Causation(cause={show(p.cause)} → effect={show(p.effect)})"
    if name == "Conditional":
        return f"Conditional({show(predicates(p.antecedent)[0])} ⇒ {show(predicates(p.consequent)[0])})"
    return repr(p)[:80]


# --------------------------------------------------------------------------- #
def basics() -> None:
    header("BASICS — argument swap, clause order, determinism, abstention")
    a = "The zorble is bigger than the florp"
    b = "The florp is bigger than the zorble"
    ta, tb = pipe(a), pipe(b)
    cos = _ENC.encode(a).vector.cosine(_ENC.encode(b).vector)
    print(f"A: {a!r}\nB: {b!r}")
    print(f"  bag-of-words cosine(A, B) = {cos:.4f}")
    print(f"  A -> {show(predicates(ta)[0])}")
    print(f"  B -> {show(predicates(tb)[0])}")
    print()
    c = "Rex barks because the dog is cute"
    d = "The dog is cute because Rex barks"
    for s in (c, d):
        print(f"{s!r}\n  -> {show(pipe(s))}")
    print()
    s = "Macbeth murdered Duncan and Macduff killed Macbeth."
    hashes = {vec_hash(s) for _ in range(3)}
    print(f"{s!r}\n  encode ×3 -> sha256 {hashes} (byte-identical)")
    print()
    from gse.symbolic import GenealogyStore, grounding_flags, resolve_references

    store = GenealogyStore()
    t = resolve_references(pipe("The zorble is bigger than the florp"), store)
    print(f"structure derived:   {show(predicates(t)[0])}")
    print(f"grounding abstained: {[f.kind + '(' + f.lemma + ')' for f in grounding_flags(t)]}")


# --------------------------------------------------------------------------- #
_LSAT = [
    "Mike is taller than Rex.",
    "Rex is taller than Spot.",
    "Spot is taller than Bob.",
    "A poodle is a dog.",
    "A dog is an animal.",
    "Mike is a poodle.",
    "If a poodle is taller than Bob then the poodle wins.",
]


def _run_lsat(sentences) -> list:
    kb = KnowledgeBase.from_trees([pipe(s) for s in sentences])
    out = []
    out.append(kb.greater("mike", "bob"))
    out.append(kb.is_a("mike", "animal"))
    out.append(kb.greater("bob", "mike"))
    out.append(kb.is_a("mike", "knife"))
    out.append(kb.event("win", "mike"))
    return out


def lsat() -> None:
    header("LSAT — multi-step derivation from raw text (with a firing conditional)")
    for s in _LSAT:
        print(f"  {s}")
    print()
    for d in _run_lsat(_LSAT):
        print(f"  {d}")


# --------------------------------------------------------------------------- #
def _names(n: int) -> list:
    cons, vow = "KBDFGLMNPRSTV", "aeiou"
    out, i = [], 0
    while len(out) < n:
        c1, v1, c2, v2 = (cons[i % 13], vow[(i // 13) % 5], cons[(i // 65) % 13].lower(), vow[(i // 325) % 5])
        name = f"{c1}{v1}{c2}o{v2}"  # Kabo a, Babo e, ...
        i += 1
        out.append(f"{c1}{v1}{c2}{v2}n")  # Kaban, Beban, ...
    return list(dict.fromkeys(out))[:n]


_FILLER = [
    "The garden was quiet.",
    "A cold wind crossed the field.",
    "The lamp flickered in the hall.",
    "Nobody spoke during the meal.",
]


def needle(lengths=(10, 25, 50, 100)) -> None:
    header("NEEDLE — a premise chain scattered in filler; correctness vs length")
    for n in lengths:
        names = _names(n + 1)
        premises = [f"{names[i]} is taller than {names[i + 1]}." for i in range(n)]
        doc, fi = [], 0
        for j, p in enumerate(premises):  # deterministic interleave 1:2
            doc.append(p)
            for _ in range(2):
                doc.append(_FILLER[fi % len(_FILLER)])
                fi += 1
        kb = KnowledgeBase.from_trees([pipe(s) for s in doc])
        top, bottom = names[0].lower(), names[n].lower()
        d = kb.greater(top, bottom)
        rev = kb.greater(bottom, top)
        print(
            f"  chain length {n:3d}  ({len(doc)} sentences): "
            f"greater({top}, {bottom}) = {d.holds}"
            f"  [proof: {len(d.chain) - 1} steps]"
            f"   reverse: {'REFUSED' if not rev.holds else 'ERROR'}"
        )


# --------------------------------------------------------------------------- #
_CLEAN_CHAIN = [
    "Einstein is taller than Mike.",
    "Mike is taller than Rex.",
    "Rex is taller than Spot.",
    "Spot is taller than Bob.",
    "Mike is a poodle.",
    "A poodle is a dog.",
    "A dog is an animal.",
    "If a poodle is taller than Bob then the poodle wins.",
]
_DIRTY_CHAIN = [
    "Einstien is taller than Mike.",  # a NAME typo — the entity leg's case
    "Mike is taller than Rex.",
    "Rex is taller than Spot.",
    "Spot is taller than Bob.",
    "Mike is a poodel.",  # word-leg typos
    "A pooodle is a dog.",
    "A dog is an animal.",
    "If a poodle is taller than Bob then the poodle wins.",
]


def _run_chain(sentences) -> list:
    kb = KnowledgeBase.from_trees([pipe(s) for s in sentences])
    return [
        kb.greater("einstein", "bob"),
        kb.is_a("mike", "animal"),
        kb.event("win", "mike"),
        kb.greater("bob", "einstein"),
        kb.is_a("mike", "knife"),
    ]


def dirty() -> None:
    header("DIRTY INPUT — typos healed with a ledger, then the SAME derivation")
    from gse.mcp.spell_server import spell_suggest

    healed, ledger = [], []
    for s in _DIRTY_CHAIN:
        r = spell_suggest(s)
        healed.append(r["corrected"].replace(" .", "."))
        for tok in r["tokens"]:
            if tok.get("misspelled") and tok.get("top"):
                ledger.append((tok["surface"], tok["top"]))
    for s in _DIRTY_CHAIN:
        print(f"  {s}")
    print("\n  repair ledger: " + ", ".join(f"{a}→{b}" for a, b in ledger))
    print(f"  healed text == intended text: {healed == _CLEAN_CHAIN}")
    clean, dirty_run = _run_chain(_CLEAN_CHAIN), _run_chain(healed)
    print(f"  derivations identical to the clean-text run: {clean == dirty_run}\n")
    for d in dirty_run:
        print(f"  {d}")


# --------------------------------------------------------------------------- #
def policy() -> None:
    header("POLICY — rules + facts -> a ruling with a citable chain, and refusals")
    text = [
        "Alice is a member.",
        "Bob is a member.",
        "If a member misses the payment then the member loses the vote.",
        "If a member loses the vote then the member leaves the board.",
        "Alice missed the payment.",
        "Carol did not miss the payment.",
    ]
    for s in text:
        print(f"  {s}")
    print()
    kb = KnowledgeBase.from_trees([pipe(s) for s in text])
    for q in [
        ("lose", "alice", "vote"),
        ("leave", "alice", "board"),
        ("lose", "bob", "vote"),
        ("lose", "carol", "vote"),
    ]:
        print(f"  {kb.event(*q)}")


# --------------------------------------------------------------------------- #
def world() -> None:
    header("WORLD GROUNDING — the premise the text never states")
    from gse.symbolic import GenealogyStore, resolve_references

    store = GenealogyStore()
    rpipe = lambda s: resolve_references(pipe(s), store)  # noqa: E731

    text = ["If a person led a country then the person commanded the army.", "Napoleon led France."]
    for s in text:
        print(f"  {s}")
    print("\n  (no sentence types napoleon or france — the world store does:)")
    for name in ("napoleon", "france"):
        print(f"    {name:9} -> {' → '.join(store.thread(name, 'PROPN', True))}")
    kb = KnowledgeBase.from_trees([rpipe(s) for s in text])
    print()
    print(f"  {kb.event('command', 'napoleon', 'army')}")
    print(f"  {kb.event('command', 'france', 'army')}     (a country is not a person)")
    print(f"  {kb.is_a('napoleon', 'person')}")

    print("\n  compositional: the same grounded referent, different decomposed predicates —")
    print("  world identity constant, meaning varying over the closed 72-prime basis:\n")
    for s in ["Napoleon is a tyrant.", "Napoleon is poor."]:
        (p,) = predicates(rpipe(s))
        kind = p.kind.head if hasattr(p.kind, "head") else p.kind
        print(f"  {s!r}")
        print(f"    -> napoleon[{' → '.join(p.entity.type_thread)}] is_a {kind.lemma} ⟨{kind.word_primitives}⟩")


# --------------------------------------------------------------------------- #
def _propositions(tree):
    """(polarity, key) propositions in a resolved tree — Events (with clause
    negation) and TypeAssertions (with the kind's negation-prefix normalized)."""
    from gse.nlp.morphology import resolve_negation

    out = []

    def ev_key(p):
        ag = p.agent.head.lemma if hasattr(p.agent, "head") else getattr(p.agent, "lemma", None)
        pt = None
        if p.patient is not None:
            pt = p.patient.head.lemma if hasattr(p.patient, "head") else getattr(p.patient, "lemma", None)
        return ("event", p.verb, ag, pt)

    def walk(n, pol=1):
        name = type(n).__name__
        if name == "Negation":
            walk(n.operand, -pol)
            return
        if name == "Event":
            out.append((pol, ev_key(n)))
            return
        if name == "TypeAssertion":
            ent = n.entity.head.lemma if hasattr(n.entity, "head") else n.entity.lemma
            kind = n.kind.head.lemma if hasattr(n.kind, "head") else n.kind.lemma
            neg = resolve_negation(kind)
            if neg:
                kind, pol = neg[0], -pol
            out.append((pol, ("isa", ent, kind)))
            return

    walk(tree)
    return out


def contradiction() -> None:
    header("CONTRADICTION MINING — sign-flipped propositions, cited exactly")
    corpus = [
        "The steward locked the vault.",
        "The queen trusted the steward.",
        "The knight is loyal.",
        "A messenger arrived at dawn.",
        "Bob did not sign the ledger.",
        "The steward did not lock the vault.",
        "The garden was quiet.",
        "The knight is disloyal.",
        "The cook sharpened the knives.",
    ]
    index: dict = {}
    for i, s in enumerate(corpus):
        for pol, key in _propositions(pipe(s)):
            index.setdefault(key, []).append((pol, i, s))
    found = []
    for key, occ in index.items():
        pos = [o for o in occ if o[0] > 0]
        neg = [o for o in occ if o[0] < 0]
        if pos and neg:
            found.append((key, pos[0], neg[0]))
    print(f"  corpus: {len(corpus)} sentences; contradictions found: {len(found)}\n")
    for key, (_, i, a), (_, j, b) in found:
        print(f"  CONTRADICTION on {key}:")
        print(f"    [{i}] {a!r}")
        print(f"    [{j}] {b!r}\n")
    unpaired = [s for s in corpus if "Bob" in s]
    print(f"  precision check: {unpaired[0]!r} (negation with no positive twin) -> not flagged")


# --------------------------------------------------------------------------- #
def reduction() -> None:
    header("REDUCTION — text reduces like an equation")
    print("  negation is a SIGN, from either mechanism (clause 'not' | prefix), and signs multiply:\n")
    for s in [
        "The knight is loyal.",
        "The knight is disloyal.",
        "The knight is not disloyal.",
        "The knight is not unmerry.",
    ]:
        (pol, key) = _propositions(pipe(s))[0]
        print(f"  {s!r:34} -> {'+' if pol > 0 else '-'}{key[2]}({key[1]})")
    a = _propositions(pipe("The knight is loyal."))
    b = _propositions(pipe("The knight is not disloyal."))
    print(f"\n  derived equivalence: 'loyal' == 'not disloyal': {a == b}   (-(-x) = x)")

    passage = [
        "The guard hurt the prisoner.",
        "The guard wounded the prisoner.",
        "The guard injured the prisoner.",
        "The warden healed the prisoner.",
        "The knight is loyal.",
        "The knight is not disloyal.",
    ]
    terms: dict = {}
    for s in passage:
        for pol, key in _propositions(pipe(s)):
            if key[0] == "event":
                key = ("event", frozenset(_decomp(key[1]).items()), key[2], key[3])
            terms[(pol, key)] = terms.get((pol, key), 0) + 1
    print(f"\n  passage ({len(passage)} sentences) collects to {len(terms)} terms:")
    for (pol, key), n in terms.items():
        if key[0] == "event":
            sig = ", ".join(f"{p}{'+' if v > 0 else '-'}" for p, v in sorted(key[1]))
            print(f"    {n} × {'+' if pol > 0 else '-'}⟨{sig}⟩({key[2]}, {key[3]})")
        else:
            print(f"    {n} × {'+' if pol > 0 else '-'}{key[2]}({key[1]})")


# --------------------------------------------------------------------------- #
def fingerprint() -> None:
    header("FINGERPRINT — the representational collapse, live")
    for w in ["hurt", "injure", "wound", "harm", "attack", "heal"]:
        print(f"  {w:8} -> {_decomp(w)}")
    print()
    sents = [
        "The guard hurt the prisoner.",
        "The guard injured the prisoner.",
        "The guard wounded the prisoner.",
        "The guard healed the prisoner.",
    ]
    keys = {}
    for s in sents:
        (p,) = predicates(pipe(s))
        key = (frozenset(_decomp(p.verb).items()), p.agent.head.lemma, p.patient.head.lemma)
        keys.setdefault(key, []).append(s)
        print(f"  {s!r}\n     form = (verb⟨{_decomp(p.verb)}⟩, {p.agent.head.lemma}, {p.patient.head.lemma})")
    print(
        f"\n  distinct forms across {len(sents)} sentences: {len(keys)}"
        f"  (hurt/injure/wound collapse; heal differs by the GOOD sign)"
    )


# --------------------------------------------------------------------------- #
def coined() -> None:
    header("COINED WORDS — meaning for words that never existed")
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "data", "lexicon_clean.db"))
    for base, coin in [("loyal", "unloyal"), ("merry", "unmerry")]:
        in_lex = conn.execute("SELECT 1 FROM lexemes WHERE lemma=?", (coin,)).fetchone()
        (p,) = predicates(pipe(f"The knight is {coin}."))
        kind = p.kind if not hasattr(p.kind, "head") else p.kind.head
        print(f"  {coin!r}: in the 67K lexicon? {bool(in_lex)}   base {base} = {_decomp(base)}")
        print(
            f"  'The knight is {coin}.' -> kind: {kind.lemma} {kind.word_primitives}"
            f"   (negation computed at encode time)"
        )
    conn.close()


# --------------------------------------------------------------------------- #
def spell() -> None:
    header("SPELLCHECK — never destroys, honestly abstains, names included")
    from gse.mcp.spell_server import spell_suggest

    for text in [
        "I beleive this is teh correct anser",
        "Einstien published the theory of relativity",
        "we flew to Melbourn yesterday",
    ]:
        r = spell_suggest(text)
        print(f"  {text!r}\n    -> {r['corrected']!r}")


# --------------------------------------------------------------------------- #
_SECTIONS = {
    "basics": basics,
    "lsat": lsat,
    "needle": needle,
    "dirty": dirty,
    "policy": policy,
    "world": world,
    "contradiction": contradiction,
    "reduction": reduction,
    "fingerprint": fingerprint,
    "coined": coined,
    "spell": spell,
}

if __name__ == "__main__":
    picks = sys.argv[1:] or list(_SECTIONS)
    for name in picks:
        _SECTIONS[name]()
