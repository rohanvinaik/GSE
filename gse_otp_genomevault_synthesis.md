# GSE Orthogonal Ternary Projection Architecture

## Core Insight from GenomeVault

The key insight from GenomeVault's HDC system is **intentional blindness as information**:

```
Hydrophobic Bank: A=+1, T=-1, G,C=0 (transparent)
MajorGroove Bank: G=+1, C=-1, A,T=0 (transparent)
```

The zeros are NOT missing data—they're **active assertions of non-membership**. When the hydrophobic bank returns 0, it's saying "this is definitively NOT an AT-type nucleotide."

For GSE, we can apply the same principle: **semantic banks where primitives are either visible (±1) or transparent (0)**.

---

## Architecture: Semantic Bank OTP

### Dimension Allocation

```
D = 8,192 total dimensions (2^13, good for Hadamard)
8 semantic banks × 1,024 dims each
```

### Bank Definitions

Each bank is a **semantic lens** that sees only its primitives:

| Bank | Semantic Category | Primitives | Antonym Pairs |
|------|-------------------|------------|---------------|
| 0 | **Substantives** | I, YOU, SOMEONE, SOMETHING, PEOPLE, BODY, KIND, PART | — |
| 1 | **Determiners** | THIS, SAME, OTHER, ONE, TWO, SOME, ALL | MUCH/LITTLE |
| 2 | **Evaluators** | VERY, MORE, LIKE | GOOD/BAD, BIG/SMALL |
| 3 | **Mental** | THINK, KNOW, WANT, FEEL, SEE, HEAR | — |
| 4 | **Action** | SAY, DO, HAPPEN, MOVE, TRUE, WORDS | BE/HAVE, LIVE/DIE, EXIST |
| 5 | **Temporal** | WHEN, NOW, MOMENT | BEFORE/AFTER, LONG_TIME/SHORT_TIME |
| 6 | **Spatial** | WHERE, HERE, INSIDE, SIDE, TOUCH | ABOVE/BELOW, FAR/NEAR |
| 7 | **Logical** | NOT, MAYBE, CAN, BECAUSE, IF | — |

### Primitive Encoding

Within each bank, primitives use **Hadamard-like patterns**:

```python
# Bank 2 (Evaluators) example:
# dim_range = [2048, 3071]  (1024 dims)

GOOD = hadamard_row(0, 1024)   # [+1, +1, +1, +1, -1, -1, -1, -1, ...]
BAD  = -hadamard_row(0, 1024)  # [-1, -1, -1, -1, +1, +1, +1, +1, ...]  # Antonym!

BIG   = hadamard_row(1, 1024)  # [+1, +1, -1, -1, +1, +1, -1, -1, ...]
SMALL = -hadamard_row(1, 1024) # Antonym with exact negation

VERY = hadamard_row(2, 1024)   # Orthogonal to GOOD, BIG
MORE = hadamard_row(3, 1024)   # Orthogonal to all above
LIKE = hadamard_row(4, 1024)
```

**Key Properties:**
- Within bank: Primitives are orthogonal via Hadamard structure
- Across banks: Perfect orthogonality (disjoint dimension sets)
- Antonyms: Exact negation (cosine = -1.0)

### Role Encoding

Roles are **cross-bank columns** that span all semantic banks:

```python
# 20 roles, each gets 1024/20 = 51 dimensions per bank
# Total per role: 51 × 8 = 408 dimensions

role_dims_per_bank = 51

def generate_role_vector(role_idx):
    """Role spans ALL banks, same relative position in each."""
    vec = np.zeros(D, dtype=np.int8)
    
    for bank in range(8):
        bank_start = bank * 1024
        role_start = bank_start + role_idx * role_dims_per_bank
        role_end = role_start + role_dims_per_bank
        
        # Hadamard pattern within role slice (varies by bank for uniqueness)
        pattern = hadamard_row(bank, role_dims_per_bank)
        vec[role_start:role_end] = pattern
    
    return vec
```

### Binding = Bank × Role Intersection

When we bind a primitive with a role:

```
bind(GOOD, agent):
  GOOD is in Bank 2, uses dims [2048, 3071]
  agent uses dims [2048+0*51 : 2048+1*51] in Bank 2 = [2048, 2099]
  
  Result: 51 non-zeros at intersection
  Signs = GOOD_sign[0:51] × agent_sign[0:51]
```

**Properties:**
- Binding ALWAYS produces ~51 non-zeros (role_dims_per_bank)
- Different (primitive, role) pairs → different dimension sets
- Binding is in primitive's bank (inherits semantic category)

---

## The Accumulation + Sign Paradigm

### Encoding (Composition)

```python
def compose(role_filler_pairs):
    """Compose multiple (primitive, role) bindings."""
    accumulator = np.zeros(D, dtype=np.int32)
    
    for primitive_vec, role_vec in role_filler_pairs:
        bound = bind(primitive_vec, role_vec)  # 51 non-zeros
        accumulator[bound.positive_indices] += 1
        accumulator[bound.negative_indices] -= 1
    
    # Quantize to ternary
    return np.sign(accumulator).astype(np.int8)
```

### Decoding (Query)

```python
def decode_bank_similarity(composed_vec, bank_idx):
    """Get similarity to all primitives in a bank."""
    bank_start = bank_idx * 1024
    bank_end = bank_start + 1024
    
    bank_slice = composed_vec[bank_start:bank_end]
    
    # Project onto each primitive's Hadamard pattern
    similarities = {}
    for prim_name, prim_idx in primitives_in_bank[bank_idx]:
        pattern = hadamard_row(prim_idx, 1024)
        sim = np.dot(bank_slice, pattern)
        similarities[prim_name] = sim
    
    return similarities
```

### The Magnitude Recovery

Just like GenomeVault:
- At encode: We store direction (sign)
- At decode: We recover magnitude (similarity strength)

```python
# Encode time:
accumulator = [+3, -7, 0, +12, -1, +45, ...]
encoded     = [+1, -1,  0,  +1, -1,  +1, ...]  # Magnitude "lost"

# Decode time:
sim = sum(encoded[dims] * signs)
    = (+1)(+1) + (-1)(-1) + (+1)(+1) + ...
    = 4  # MAGNITUDE RECOVERED as similarity strength!
```

---

## The Two-Level Decode Strategy

Like GenomeVault's hydrophobic vs. major-groove decision:

```python
def decode_primitive(composed_vec):
    """Decode dominant primitive from composed vector."""
    
    # Step 1: Find dominant bank
    bank_magnitudes = []
    for bank in range(8):
        bank_start = bank * 1024
        bank_end = bank_start + 1024
        magnitude = np.abs(composed_vec[bank_start:bank_end]).sum()
        bank_magnitudes.append((bank, magnitude))
    
    dominant_bank = max(bank_magnitudes, key=lambda x: x[1])[0]
    
    # Step 2: Find dominant primitive within bank
    bank_sims = decode_bank_similarity(composed_vec, dominant_bank)
    dominant_prim = max(bank_sims, key=lambda k: abs(bank_sims[k]))
    
    # Step 3: Sign determines polarity (for antonyms)
    sign = np.sign(bank_sims[dominant_prim])
    
    return dominant_prim, sign, dominant_bank
```

---

## Storage Format: 3D Tensor

Following GenomeVault's HDF5 structure:

```python
# Shape: (n_concepts, n_banks, dims_per_bank)
# For lexicon of 20,000 words:
#   (20000, 8, 1024) as int8 = 160 MB

# With gzip compression (90% zeros): ~16 MB
```

The 3D structure enables:
1. **Bank-wise processing**: Query only relevant semantic banks
2. **Column-major compression**: Same dimension across concepts correlates
3. **Efficient retrieval**: Load only needed banks for query

---

## Comparison with Previous Approaches

| Aspect | Random Sparse | Grid OTP | GenomeVault-Inspired |
|--------|---------------|----------|----------------------|
| Orthogonality | ~99% | 100% (exact) | 100% (Hadamard) |
| Antonyms | Ad-hoc | Sign flip | Exact negation |
| Binding nnz | ~100 (varies) | 10 (exact) | 51 (exact) |
| Semantic structure | None | Row = primitive | Bank = category |
| Storage | Flat | 2D grid | 3D (concept, bank, dim) |
| Decode | Impossible | Row decode | Bank → primitive decode |
| Theory | Probabilistic | Geometric | Information-theoretic |

---

## Implementation Sketch

```python
import numpy as np
from scipy.linalg import hadamard

D = 8192
N_BANKS = 8
DIMS_PER_BANK = D // N_BANKS  # 1024
N_ROLES = 20
ROLE_DIMS_PER_BANK = DIMS_PER_BANK // N_ROLES  # 51

class OTPBasis:
    def __init__(self):
        # Generate Hadamard matrix for sign patterns
        self.H = hadamard(DIMS_PER_BANK)
        
        self.primitives = {}
        self.roles = {}
        self.primitive_to_bank = {}
        self.bank_to_primitives = {i: [] for i in range(N_BANKS)}
    
    def generate_primitive(self, name, bank, idx_in_bank, is_antonym_neg=False):
        """Generate primitive vector in specified bank."""
        vec = np.zeros(D, dtype=np.int8)
        
        bank_start = bank * DIMS_PER_BANK
        pattern = self.H[idx_in_bank % DIMS_PER_BANK, :]
        
        if is_antonym_neg:
            pattern = -pattern
        
        vec[bank_start:bank_start + DIMS_PER_BANK] = np.sign(pattern)
        
        self.primitives[name] = vec
        self.primitive_to_bank[name] = bank
        self.bank_to_primitives[bank].append(name)
        
        return vec
    
    def generate_role(self, name, role_idx):
        """Generate role vector spanning all banks."""
        vec = np.zeros(D, dtype=np.int8)
        
        for bank in range(N_BANKS):
            bank_start = bank * DIMS_PER_BANK
            role_start = bank_start + role_idx * ROLE_DIMS_PER_BANK
            role_end = role_start + ROLE_DIMS_PER_BANK
            
            # Use different Hadamard row per bank for variety
            pattern = self.H[bank, :ROLE_DIMS_PER_BANK]
            vec[role_start:role_end] = np.sign(pattern)
        
        self.roles[name] = vec
        return vec
    
    def bind(self, prim_vec, role_vec):
        """Element-wise multiplication (binding)."""
        return (prim_vec * role_vec).astype(np.int8)
    
    def bundle(self, vectors):
        """Element-wise sum with sign quantization."""
        acc = np.zeros(D, dtype=np.int32)
        for v in vectors:
            acc += v
        return np.sign(acc).astype(np.int8)
    
    def get_bank_similarity(self, vec, bank):
        """Get similarities to all primitives in bank."""
        bank_start = bank * DIMS_PER_BANK
        bank_slice = vec[bank_start:bank_start + DIMS_PER_BANK]
        
        sims = {}
        for name in self.bank_to_primitives[bank]:
            prim_slice = self.primitives[name][bank_start:bank_start + DIMS_PER_BANK]
            sims[name] = np.dot(bank_slice, prim_slice.astype(np.float32))
        
        return sims
```

---

## Summary

The GenomeVault-inspired OTP architecture for GSE provides:

1. **Principled orthogonality** via Hadamard matrices (not random)
2. **Semantic banks** that mirror NSM categories
3. **Perfect antonymy** through exact negation
4. **Guaranteed binding** via cross-bank role structure
5. **Two-level decode** (bank → primitive) for interpretability
6. **Efficient 3D storage** with column-major compression

This is a clean synthesis of:
- Your OTP theory (informational zeros, geometric encoding)
- GenomeVault's practical HDC architecture (banks, Hadamard, 3D storage)
- GSE's semantic requirements (primitives, roles, composition)
