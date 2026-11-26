import sqlite3, json, random, collections, sys
from GSE.nlp.native import NativeNLP
from GSE.lexicon.senses import read_senses
DB = 'data/lexicon_builder/2026-11-12/sparse-release-022-verbnet-do.db'
c = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
nlp = NativeNLP()
IDENT = {"SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART", "WORDS", "WHEN", "WHERE", "ALIVE"}
NEG = {"not", "without", "lacking", "no", "never", "non"}
CLOSED = {"several", "any", "many", "much", "some", "each", "every", "all", "both", "few", "other", "another", "such", "certain", "various", "one", "more", "most", "less", "very", "also", "especially", "usually", "often", "being", "having", "used", "make", "made", "do", "be", "have"}
UD = {"NOUN": "NOUN", "PROPN": None, "VERB": "VERB", "ADJ": "ADJ", "ADV": "ADV"}
cache = {}
def reading(lemma, pos):
    key = (lemma, pos)
    if key not in cache:
        r = read_senses(c, lemma, pos) if pos else None
        cache[key] = {b: v for b, v in (r or {}).get('assignments', {}).items() if v} if r else {}
    return cache[key]
def compose(gloss, noun_def):
    toks = list(nlp(gloss)); out = collections.defaultdict(dict); genus_done = False; negate = False
    for t in toks:
        lw = t.lemma_.lower()
        if lw in NEG: negate = True; continue
        pos = UD.get(t.pos_)
        if not pos: 
            if t.pos_ in {"PUNCT", "CCONJ", "SCONJ"}: negate = False
            continue
        if lw in CLOSED: continue
        vals = reading(lw, pos)
        is_genus = (noun_def and not genus_done and pos == "NOUN")
        if noun_def and not is_genus:  # a noun's banks are its own denotatum: only its genus contributes
            continue
        for b, v in vals.items():
            if b in IDENT and not is_genus: continue
            out[b][(-v if negate else v)] = lw
        if is_genus: genus_done = True
    return {b: (next(iter(s)) if len(s) == 1 else sorted(s), s) for b, s in out.items()}
rows = c.execute("select d.entry_id, l.gloss, d.domains, l.pos from definition_states d join lexemes l on d.lexeme_id=l.id where l.gloss is not null").fetchall()
random.Random(7).shuffle(rows); rows = rows[:3000]
before = after = added_total = 0; ex = []
for e, g, dom, lpos in rows:
    d = json.loads(dom); stored = {b: v[0] for b, v in d.items() if len(v) == 1 and v[0]}
    comp = compose(g, lpos == "noun"); new = {b: v for b, (v, s) in comp.items() if isinstance(v, int) and b not in stored and len(d.get(b, [])) > 1 and v in d.get(b, [])}
    before += len(stored); after += len(stored) + len(new); added_total += len(new)
    if new and len(ex) < 12: ex.append((e.split(':')[1][:22], g[:60], {b: f"{v:+d} via {comp[b][1][v]}" for b, v in list(new.items())[:4]}))
print(f'sample 3000: nonzero banks/def {before/3000:.2f} -> {after/3000:.2f}  (+{added_total})  word readings cached {len(cache)}')
for x in ex: print(' ', x)
