import sqlite3
import json
import numpy as np
from gse.vectors import SparseVector, bind, bundle, PrimitiveBasis

def main():
    # Load basis
    basis = PrimitiveBasis.load("data/basis.msgpack")
    
    # Load vectors from DB
    conn = sqlite3.connect("data/lexicon.db")
    cursor = conn.execute("SELECT lemma, vector, decomposition FROM lexicon WHERE lemma IN ('big', 'large')")
    rows = cursor.fetchall()
    conn.close()
    
    vecs = {}
    decomps = {}
    
    for r in rows:
        lemma = r[0]
        v = SparseVector.deserialize(r[1])
        vecs[lemma] = v
        decomps[lemma] = json.loads(r[2])
        print(f"Loaded {lemma}: nnz={v.nnz}, sparsity={v.sparsity}")
        print(f"  Decomposition: {decomps[lemma]}")
        
    if 'big' in vecs and 'large' in vecs:
        sim = vecs['big'].cosine(vecs['large'])
        print(f"Similarity (big vs large): {sim}")
        
        # Manual reconstruction
        print("Reconstructing 'big' manually...")
        # big: [["BIG", "attribute"], ["SOMETHING", "theme"]]
        parts = []
        for prim, role in decomps['big']:
            p = basis.primitives[prim]
            r = basis.roles[role]
            b = bind(p, r)
            parts.append(b)
            print(f"  Component {prim}-{role}: nnz={b.nnz}")
            
        reconstructed_big = bundle(parts)
        print(f"  Reconstructed big sim to DB big: {reconstructed_big.cosine(vecs['big'])}")
        
        print("Reconstructing 'large' manually...")
        parts_large = []
        for prim, role in decomps['large']:
            p = basis.primitives[prim]
            r = basis.roles[role]
            b = bind(p, r)
            parts_large.append(b)
            print(f"  Component {prim}-{role}: nnz={b.nnz}")
            
        reconstructed_large = bundle(parts_large)
        print(f"  Reconstructed large sim to DB large: {reconstructed_large.cosine(vecs['large'])}")
        
        # Check component overlap
        # big has C1, C2
        # large has C1, C2, C3
        # C1 = BIG-attribute
        # C2 = SOMETHING-theme
        # C3 = VERY-manner
        
        # Let's check similarity of C1 to C2
        c1 = parts[0]
        c2 = parts[1]
        print(f"  Sim(C1, C2) = {c1.cosine(c2)}")
        
        # Sim(Big, Large)
        # Big = bundle(C1, C2)
        # Large = bundle(C1, C2, C3)
        
        # Theoretical sim?
        # If C1, C2, C3 orthogonal:
        # Big = C1+C2
        # Large = C1+C2+C3
        # Dot = 2. NormA = sqrt(2). NormB = sqrt(3).
        # Cos = 2 / sqrt(6) = 0.816.
        
        pass

if __name__ == "__main__":
    main()
