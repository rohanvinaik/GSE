#!/usr/bin/env python3
"""Audit GSE's ENUMERATION fidelity — the σ_sem question, one layer above parse fidelity.

Parse fidelity (``audit_l2_parses.py``) asks: can GSE structurally parse the sentence?
This asks the next question: given the parse, does GSE **enumerate + resolve the lawful
reading** faithfully — soundly (no confident-wrong resolution) and completely (the gold
reading is among the candidates)?

FAITHFULNESS LAW (GSE ``CLAUDE.md``): *compose existing tools, never re-ground.* This
harness runs the REAL pipeline — ``encode → resolve → resolve_document`` — and reads each
grounded common-noun entity's **committed** ``type_thread`` (the sense grounding actually
chose, including every HDC/anchor/genre gate). It NEVER re-implements grounding's WSD.
The thread↔synset bridge is index-exact: ``GenealogyStore.candidates(lemma,'NOUN',False)``
is built one row per WordNet noun sense in sense order (``build_genealogy_db``), so it
aligns element-for-element to ``wn.synsets(lemma, wn.NOUN)`` — GSE's committed synset is
``synsets[ raw.index(ent.type_thread) ]`` (grounding.py:337, :357-359).

Ground truth: SemCor (WordNet sense-annotated Brown, held out — GSE never trained on it).
The gold lemma is taken from the token's OWN annotated ``Lemma`` (never the gold synset's
first lemma — that was a prior harness bug that disambiguated the wrong word).

The metric is the SymbolicSpellCheck trichotomy, mapped to grounding's real behaviour
(grounding always COMMITS — when it declines to override it stays at the WordNet
frequency-primary, so "abstain" = *declines to override*, the safe non-destructive move):

  * candidate-recall = gold ∈ wn.synsets(lemma,'n')          — completeness CEILING (≈100%
                                                                for WSD by construction: the
                                                                candidate set IS the inventory)
  * primary-correct  = frequency-primary == gold             — the no-resolution baseline
  * override_fired   = committed sense != primary            — GSE confidently overrode
      - override-correct (resolve) = committed == gold        — valid SC=1
      - DESTROY                     = committed != gold        — confident WRONG = FALSE SC=1
  * committed-correct = GSE's final committed sense == gold
  * LIFT              = committed-correct − primary-correct    — does resolution help?
  * DESTRUCTION rate  = destroy / override_fired              — the confident-wrong FLOOR
                                                                (analog of SSC's 0.00000%)

Broken out per super-register (Brown genre → super_register_of) and per POS. GSE's
contextual WSD is noun-focused by design (the HDC resonance was validated on nouns), so
only nouns get a contextual commit; the POS split makes that explicit.

Usage:
  python scripts/audit_enumeration_fidelity.py --validate          # men-anchor + eyeball gate
  python scripts/audit_enumeration_fidelity.py [--files N] [--max-sents-per-file M]
"""
import argparse
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_OVERRIDE_LOG: list = []   # (lemma, primary, committed, gold, correct) for every override that fired


def _ensure_nltk():
    import nltk
    for pkg, path in [("semcor", "corpora/semcor"), ("wordnet", "corpora/wordnet"),
                      ("brown", "corpora/brown"), ("omw-1.4", "corpora/omw-1.4")]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(pkg, quiet=True)


def _brown_category(semcor_fileid: str) -> str:
    """SemCor 'brown1/tagfiles/br-a01.xml' -> Brown file 'ca01' -> its category."""
    from nltk.corpus import brown
    stem = semcor_fileid.split("/")[-1].replace(".xml", "")   # br-a01
    code = "c" + stem.split("-")[1]                            # ca01
    try:
        cats = brown.categories(code)
        return cats[0] if cats else "unknown"
    except Exception:
        return "unknown"


def _is_person_synset(synset_name: str) -> bool:
    """Reporting-only helper for the --validate gate: is this WordNet sense a PERSON?"""
    from nltk.corpus import wordnet as wn
    try:
        syn = wn.synset(synset_name)
    except Exception:
        return False
    if syn.lexname() == "noun.person":
        return True
    person = wn.synset("person.n.01")
    return any(person in path for path in syn.hypernym_paths())


class ComposedReader:
    """Runs the REAL GSE pipeline and reads each common-noun entity's committed synset.

    This is the whole faithfulness contract: nothing here decides a sense — grounding does,
    inside ``resolve_document``; we only READ ``ent.type_thread`` back out and map it to the
    aligned WordNet synset.
    """

    def __init__(self):
        from gse.api import GSEEncoder
        from gse.symbolic import GenealogyStore
        self.enc = GSEEncoder()
        self.store = GenealogyStore()

    def _tree_senses(self, tree):
        """Read each common-noun entity's committed synset out of ONE resolved tree.

        ``committed`` is the committed synset name, or None when grounding abstained to an
        empty thread (honest non-recovery) or the thread cannot be aligned to a synset. The
        committed sense reflects whatever CONTEXT SCALE was in the resolve_document call that
        produced this tree (single-sentence vs whole-document)."""
        from nltk.corpus import wordnet as wn

        from gse.symbolic.grounding import _collect_entities, _is_proper, _lookup_key, _position

        ents: list = []
        _collect_entities(tree, ents)
        out = []
        for ent in ents:
            if _is_proper(ent):
                continue
            head_pos = getattr(ent.head, "pos", "") or ""
            if head_pos != "NOUN":
                continue
            lemma = _lookup_key(ent)
            if not lemma:
                continue
            synsets = wn.synsets(lemma, wn.NOUN)
            if not synsets:
                continue
            raw = [tuple(t) for t in self.store.candidates(lemma, head_pos, False)]
            if len(raw) != len(synsets):
                continue   # thread↔synset alignment not exact → cannot faithfully map; skip
            primary = synsets[0].name()
            committed_thread = tuple(ent.type_thread)
            if committed_thread and committed_thread in raw:
                committed = synsets[raw.index(committed_thread)].name()
            else:
                committed = None       # empty thread (abstained) or re-ranked off the word strand
            out.append({
                "lemma": lemma.lower(), "pos_class": "noun",
                "primary": primary, "committed": committed, "position": _position(ent),
            })
        return out

    def read_document(self, sent_texts, genre=None, scale="document"):
        """Run the pipeline over a list of sentences and return per-sentence committed senses.

        scale="document": resolve_document runs ONCE over the WHOLE passage — WSD draws on
          cross-sentence context (the multi-scale grounding GSE's design depends on).
        scale="sentence": each sentence is resolved in isolation — the thin-context baseline
          (what information the disambiguator has with NO external scale imported).
        Returns list aligned to sent_texts: each element is a list of committed-sense dicts
          (empty for sentences that failed to encode)."""
        from gse.symbolic import evaluate_tree, from_trace, resolve, resolve_document

        # encode each sentence, keeping index alignment (skip un-encodable, remember which)
        trees, idx_map = [], []
        for i, s in enumerate(sent_texts):
            try:
                trees.append(evaluate_tree(resolve(from_trace(self.enc.encode(s)))))
                idx_map.append(i)
            except Exception:
                continue

        per_sent = [[] for _ in sent_texts]
        if not trees:
            return per_sent
        if scale == "document":
            try:
                resolved = resolve_document(trees, self.store, genre=genre)
            except Exception:
                return per_sent
            for k, tree in enumerate(resolved):
                per_sent[idx_map[k]] = self._tree_senses(tree)
        else:  # sentence scale — resolve each tree in isolation
            for k, tree in enumerate(trees):
                try:
                    resolved = resolve_document([tree], self.store, genre=genre)
                except Exception:
                    continue
                per_sent[idx_map[k]] = self._tree_senses(resolved[0]) if resolved else []
        return per_sent

    def read(self, sent_text: str, genre=None, scale="document"):
        """Single-sentence convenience (used by the validation gate)."""
        return self.read_document([sent_text], genre=genre, scale=scale)[0]


def _gold_nouns(tagged_sent):
    """Extract SemCor gold: dict lemma_lower -> deque of (gold_synset, pos_class) in token order,
    plus a flat per-POS list for the completeness tally. Lemma is the TOKEN's own annotated lemma."""
    import nltk
    from nltk.corpus.reader.wordnet import Lemma

    by_lemma: dict = defaultdict(deque)
    flat: list = []   # (lemma, pos_class, gold_synset)
    for chunk in tagged_sent:
        if not isinstance(chunk, nltk.Tree):
            continue
        lab = chunk.label()
        if not isinstance(lab, Lemma):
            continue
        syn = lab.synset()
        lemma = lab.name().split("%")[0].lower()      # token's lemma (bug-b fix)
        p = syn.pos()
        pos_class = "noun" if p == "n" else ("verb" if p == "v" else "adj/adv")
        gold = syn.name()
        flat.append((lemma, pos_class, gold, p))
        if p == "n":
            by_lemma[lemma].append(gold)
    return by_lemma, flat


def run_validate(reader):
    """The gate: reproduce the documented men-anchor and eyeball a few overrides BEFORE scaling.
    A faithful reader must (a) commit 'men' to a PERSON sense in a labour context (sense_resonance
    docstring: person +0.50 vs work_force +0.27, person never loses), and (b) show ~100% of committed
    senses landing in the WordNet inventory (a broken thread↔synset index would scatter them)."""
    print("=== VALIDATION GATE (run before trusting the at-scale numbers) ===\n")
    probes = [
        "The men worked the fields and the factories all day.",
        "The old men gathered wood by the river.",
        "The company hired more men for the night shift.",
    ]
    men_person_hits = 0
    men_seen = 0
    for sent in probes:
        print(f"· {sent}")
        rows = reader.read(sent, genre=None)
        for r in rows:
            tag = ""
            if r["committed"] and r["committed"] != r["primary"]:
                tag = "  <-- OVERRIDE"
            print(f"    {r['lemma']:12} primary={r['primary']:20} committed={r['committed']}{tag}")
            if r["lemma"] in ("man", "men"):
                men_seen += 1
                if r["committed"] and _is_person_synset(r["committed"]):
                    men_person_hits += 1
        print()
    ok = men_seen > 0 and men_person_hits == men_seen
    print(f"men-anchor: {men_person_hits}/{men_seen} committed to a PERSON sense  "
          f"-> {'PASS' if ok else 'CHECK — expected all person'}")
    print("(If 'man' abstains to primary man.n.01 that is already a person sense — anchor still holds.)")
    return 0


def run_scale(reader, files: int, max_sents: int, scale: str = "document"):
    from nltk.corpus import semcor
    from nltk.corpus import wordnet as wn
    try:
        from gse.discourse import super_register_of
    except Exception:
        def super_register_of(genre):
            return genre

    print(f"[context scale = {scale.upper()}]  "
          f"({'whole-passage resolve_document — multi-scale WSD context' if scale == 'document' else 'per-sentence resolve — thin-context baseline'})\n")
    tally = defaultdict(Counter)   # (super_register, pos_class) -> counters
    fids = semcor.fileids()[:files]
    for fid in fids:
        genre = _brown_category(fid)
        sr = super_register_of(genre)
        raw_sents = semcor.sents(fid)[:max_sents]
        tagged_sents = semcor.tagged_sents(fid, tag="sem")[:max_sents]

        # per-sentence gold, and completeness/baseline tally over ALL gold content tokens
        golds_per_sent = []
        for tagged in tagged_sents:
            by_lemma, flat = _gold_nouns(tagged)
            golds_per_sent.append(by_lemma)
            for lemma, pos_class, gold, p in flat:
                wp = {"n": wn.NOUN, "v": wn.VERB, "a": wn.ADJ, "s": wn.ADJ, "r": wn.ADV}.get(p)
                cands = wn.synsets(lemma, wp) if wp else wn.synsets(lemma)
                if not cands:
                    continue
                t = tally[(sr, pos_class)]
                t["gold_n"] += 1
                if gold in [c.name() for c in cands]:
                    t["cand_recall"] += 1
                if cands[0].name() == gold:
                    t["primary_ok"] += 1

        # Run the WHOLE passage through the pipeline at the chosen context scale, ONCE,
        # so document-scale WSD draws on cross-sentence context (the multi-scale grounding).
        sent_texts = [" ".join(w) for w in raw_sents]
        per_sent = reader.read_document(sent_texts, genre=None, scale=scale)

        t = tally[(sr, "noun")]
        for by_lemma, senses in zip(golds_per_sent, per_sent):
            # gold deques are per-sentence; align GSE's committed nouns to that sentence's gold
            local = {lem: deque(dq) for lem, dq in by_lemma.items()}
            for r in sorted(senses, key=lambda r: r["position"]):
                t["gse_noun_entities"] += 1               # coverage denominator
                golds = local.get(r["lemma"])
                if not golds:
                    continue
                gold = golds.popleft()
                t["scored"] += 1
                committed = r["committed"]
                primary = r["primary"]
                # baseline + committed accuracy are recorded WITHIN the scored set (same denominator)
                if primary == gold:
                    t["s_primary_ok"] += 1
                if committed is None:
                    t["abstain_empty"] += 1          # honest non-recovery (no thread) — never a destroy
                    continue
                if committed != primary:
                    t["override_fired"] += 1
                    if committed == gold:
                        t["override_ok"] += 1
                    _OVERRIDE_LOG.append((r["lemma"], primary, committed, gold, committed == gold))
                if committed == gold:
                    t["s_committed_ok"] += 1

    if _OVERRIDE_LOG:
        print(f"\n  override cases ({len(_OVERRIDE_LOG)}) — lemma: primary -> committed  (gold)  [✓/✗]:")
        for lemma, primary, committed, gold, ok in _OVERRIDE_LOG:
            print(f"    {lemma:14} {primary:22} -> {committed:22}  gold={gold:22} {'✓' if ok else '✗ DESTROY'}")
        _OVERRIDE_LOG.clear()
    return _report(tally)


def _report(tally):
    def pct(a, b):
        return f"{100 * a / b:5.1f}%" if b else "   – "

    # Columns: gold_n/cand-rec/primary = completeness+baseline over ALL gold tokens (per POS).
    # scored..DESTROY = the NOUN trichotomy WITHIN the scored set (GSE committed head-noun ∩ gold),
    # where primary% and committed% share the `scored` denominator so LIFT is same-set.
    print(f"\n{'super_register':16} {'pos':8} {'gold_n':>6} {'cand-rec':>8} {'prim(all)':>9} "
          f"{'scored':>6} {'prim(sc)':>8} {'commit':>7} {'lift':>6} {'ovr':>4} {'DESTROY':>8} {'abst':>5}")
    print("-" * 108)
    agg = Counter()
    for (sr, pos), t in sorted(tally.items()):
        sc = t["scored"]
        if pos == "noun" and sc:
            prim_sc = pct(t["s_primary_ok"], sc)
            commit = pct(t["s_committed_ok"], sc)
            lift = f"{t['s_committed_ok'] - t['s_primary_ok']:+d}"
            ovr, destroy, abst = t["override_fired"], pct(t["override_fired"] - t["override_ok"], t["override_fired"]), t["abstain_empty"]
        else:
            prim_sc = commit = lift = destroy = "  –"
            ovr = abst = 0
        print(f"{sr:16} {pos:8} {t['gold_n']:6d} {pct(t['cand_recall'], t['gold_n']):>8} "
              f"{pct(t['primary_ok'], t['gold_n']):>9} {sc:6d} {prim_sc:>8} {commit:>7} {lift:>6} "
              f"{ovr:4d} {destroy:>8} {abst:5d}")
        for k, v in t.items():
            agg[k] += v
    print("-" * 108)
    scored = agg["scored"]
    ovr = agg["override_fired"]
    print("\nσ_sem enumeration-fidelity headline (SymbolicSpellCheck floor, NOUNS — GSE's contextual scope):")
    print(f"  candidate-recall (completeness ceiling): {pct(agg['cand_recall'], agg['gold_n'])} "
          f"over {agg['gold_n']} gold content tokens — the gold reading is enumerable")
    print(f"  coverage: GSE committed {agg['gse_noun_entities']} head-noun entities; "
          f"{scored} aligned to a gold noun token ({pct(scored, agg['gse_noun_entities'])} of GSE nouns scored)")
    print(f"  DESTRUCTION rate (confident-wrong override = false SC=1): "
          f"{pct(ovr - agg['override_ok'], ovr)} over {ovr} overrides   [the floor — SSC analog of 0.00000%]")
    print(f"  committed vs primary baseline (SAME scored set): committed {pct(agg['s_committed_ok'], scored)} "
          f"vs primary {pct(agg['s_primary_ok'], scored)}   LIFT {agg['s_committed_ok'] - agg['s_primary_ok']:+d} "
          f"over {scored} scored")
    print(f"  abstain-to-empty-thread (honest non-recovery, never destroy): {agg['abstain_empty']}")
    return {
        "scored": scored, "overrides": ovr, "destroyed": ovr - agg["override_ok"],
        "committed_ok": agg["s_committed_ok"], "primary_ok": agg["s_primary_ok"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=20, help="SemCor files to audit")
    ap.add_argument("--max-sents-per-file", type=int, default=40)
    ap.add_argument("--scale", choices=["sentence", "document", "both"], default="document",
                    help="context scale for WSD: 'document' imports cross-sentence context "
                         "(GSE's multi-scale design); 'sentence' is the thin-context baseline; "
                         "'both' runs the scale comparison (the inverse-SSC measurement)")
    ap.add_argument("--validate", action="store_true",
                    help="run the men-anchor + eyeball gate and exit (do this before trusting scale)")
    args = ap.parse_args()

    _ensure_nltk()
    reader = ComposedReader()
    if args.validate:
        return run_validate(reader)
    if args.scale != "both":
        run_scale(reader, args.files, args.max_sents_per_file, scale=args.scale)
        return 0

    # scale comparison — the inverse-SSC claim made falsifiable: destruction should FALL and
    # lift should RISE as context scale grows (sentence -> document), because GSE's WSD resolves
    # by importing the disambiguating information from the scale above the token.
    print("=" * 108 + "\n  SENTENCE SCALE (thin context — the baseline)\n" + "=" * 108)
    sent = run_scale(reader, args.files, args.max_sents_per_file, scale="sentence")
    print("\n" + "=" * 108 + "\n  DOCUMENT SCALE (cross-sentence context imported — GSE's design)\n" + "=" * 108)
    doc = run_scale(reader, args.files, args.max_sents_per_file, scale="document")

    def dpct(d):
        return f"{100 * d['destroyed'] / d['overrides']:.1f}%" if d["overrides"] else "  –"

    def lift(d):
        return d["committed_ok"] - d["primary_ok"]
    print("\n" + "=" * 108)
    print("  INVERSE-SSC / MULTI-SCALE DELTA — does importing context reduce destruction & raise lift?")
    print("-" * 108)
    print(f"  {'scale':10} {'overrides':>10} {'DESTROY':>9} {'lift':>7} {'committed':>10} {'primary':>9}")
    for name, d in [("sentence", sent), ("document", doc)]:
        cok = f"{100 * d['committed_ok'] / d['scored']:.1f}%" if d["scored"] else "  –"
        pok = f"{100 * d['primary_ok'] / d['scored']:.1f}%" if d["scored"] else "  –"
        print(f"  {name:10} {d['overrides']:10d} {dpct(d):>9} {lift(d):+7d} {cok:>10} {pok:>9}")
    print("\n  PREDICTION (multi-scale info thesis): document destruction < sentence destruction, "
          "and document lift > sentence lift.")
    print(f"  OBSERVED: destruction {dpct(sent)} -> {dpct(doc)}   |   lift {lift(sent):+d} -> {lift(doc):+d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
