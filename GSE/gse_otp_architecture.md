# GSE Vector Architecture: OTP-Based Design

## Overview

This document specifies a proper **Orthogonal Ternary Projection (OTP)** architecture for GSE's hyperdimensional computing layer. The design guarantees:

1. **Perfect orthogonality** between all primitives
2. **Perfect orthogonality** between all roles
3. **Non-trivial binding** (bind always produces non-zero results)
4. **Efficient bundling** (superposition preserves retrievability)
5. **Interpretable structure** (can identify which primitive/role from vector)

---

## The Problem with Random Sparse Vectors

The current implementation uses random sparse vectors:
```python
# Current approach
primitive_i = SparseVector.random(10000, 1000, seed=i)
role_j = SparseVector.random(10000, 1000, seed=1000+j)
```

Issues:
1. **Quasi-orthogonal only**: |cos(p_i, p_j)| ≈ 0.01-0.05, not exactly 0
2. **Probabilistic binding overlap**: Expected ~100 non-zeros, but varies
3. **No semantic structure**: Can't decode "which primitive" from vector directly
4. **Antonym handling is ad-hoc**: Special cases rather than principled design

---

## The Grid-Based OTP Architecture

### Core Idea

Conceptualize D=10,000 dimensions as a **100×100 grid**:

```
Position (r, c) in grid = dimension index 100*r + c

         c=0  c=1  c=2  ...  c=99
        ┌────┬────┬────┬────┬────┐
   r=0  │  0 │  1 │  2 │... │ 99 │
        ├────┼────┼────┼────┼────┤
   r=1  │100 │101 │102 │... │199 │
        ├────┼────┼────┼────┼────┤
   r=2  │200 │201 │202 │... │299 │
        ├────┼────┼────┼────┼────┤
   ...  │    │    │    │    │    │
        ├────┼────┼────┼────┼────┤
   r=99 │9900│9901│9902│... │9999│
        └────┴────┴────┴────┴────┘
```

**Primitives use ROWS** (horizontal bands)
**Roles use COLUMNS** (vertical bands)
**Binding = ROW ∩ COLUMN intersection**

### Primitive Encoding (63 primitives)

Each primitive uses **2 consecutive rows** (200 dimensions):
- Primitive 0: rows 0-1 → dims 0-199
- Primitive 1: rows 2-3 → dims 200-399
- Primitive 31: rows 62-63 → dims 6200-6399
- (primitives 32-62 continue)

Total rows needed: 63 × 2 = 126 rows (uses rows 0-125, leaving 74-99 for future)

Within each primitive's row band:
- **Balanced signs**: Half +1, half -1
- **Deterministic pattern**: Based on primitive index
- **Row 0 of pair**: even columns get +1, odd columns get -1
- **Row 1 of pair**: pattern continues or inverts for antonyms

```
Primitive 0 (rows 0-1):
  Row 0: [+1, -1, +1, -1, +1, -1, ...] (alternating)
  Row 1: [+1, -1, +1, -1, +1, -1, ...] (same pattern)

Primitive 1 (rows 2-3):
  Row 2: [+1, -1, +1, -1, +1, -1, ...]
  Row 3: [+1, -1, +1, -1, +1, -1, ...]
```

**Density**: 200/10000 = 2%
**Orthogonality**: PERFECT (disjoint row sets)

### Role Encoding (20 roles)

Each role uses **5 consecutive columns** (500 dimensions):
- Role 0: columns 0-4 → every row, columns 0-4
- Role 1: columns 5-9 → every row, columns 5-9
- Role 19: columns 95-99 → every row, columns 95-99

Total columns needed: 20 × 5 = 100 columns (exactly fills the grid)

Within each role's column band:
- **Balanced signs**: Half +1, half -1
- **Pattern**: alternating by row

```
Role 0 (columns 0-4):
  Row 0: [+1, -1, +1, -1, +1, 0, 0, 0, ...]
  Row 1: [-1, +1, -1, +1, -1, 0, 0, 0, ...]
  Row 2: [+1, -1, +1, -1, +1, 0, 0, 0, ...]
  ...
```

**Density**: 500/10000 = 5%
**Orthogonality**: PERFECT (disjoint column sets)

### Binding Operation

`bind(primitive_i, role_j)` = element-wise multiplication

Since primitive uses rows R_i and role uses columns C_j:
- Result has non-zeros ONLY at intersection (R_i × C_j)
- For 2 rows × 5 columns = 10 cells = 10 non-zero positions

```
bind(primitive_0, role_0):
  Non-zeros at: (row 0, cols 0-4) and (row 1, cols 0-4)
  = dims [0,1,2,3,4, 100,101,102,103,104]
  = 10 non-zero positions
  Signs = primitive_sign × role_sign at each position
```

**Key property**: bind(p_i, r_j) is PERFECTLY DISTINGUISHABLE from bind(p_k, r_l) for (i,j) ≠ (k,l) because they use different row-column intersections!

### Bundling Operation

`bundle([v1, v2, ...])` = element-wise sum with majority vote

Works correctly because:
- Each bound pair contributes votes to its unique 10 positions
- Majority vote recovers the dominant signal
- Orthogonality means minimal interference

---

## Handling Antonyms with OTP Structure

For antonym pairs like (GOOD, BAD), we want:
- High similarity in most dimensions
- **Sign flip** in specific "polarity" dimensions

### Antonym Encoding Strategy

Antonym pairs share the SAME row set but with OPPOSITE signs in designated "polarity columns":

```
Polarity columns: 0-9 (first 10 columns of each row)

GOOD (primitive i):
  Rows 2i, 2i+1
  Polarity cols (0-9): +1
  Other cols (10-99): [alternating pattern]

BAD (primitive i+32, paired with GOOD):
  Rows 2(i+32), 2(i+32)+1 = different rows
  OR share rows with GOOD but opposite polarity signs

Option 2 (shared rows):
  Both GOOD and BAD use rows 2i, 2i+1
  GOOD: polarity cols get +1, pattern X in other cols
  BAD:  polarity cols get -1, pattern X in other cols (same!)
  
  Result: dot(GOOD, BAD) = negative (anti-correlated)
```

**For GSE, Option 2 is preferable** because it directly encodes the antonym relationship in the vector structure.

---

## Comparison: Random vs OTP Architecture

| Property | Random Sparse | OTP Grid |
|----------|--------------|----------|
| Primitive orthogonality | ~0.98-0.99 | 1.00 (exact) |
| Role orthogonality | ~0.98-0.99 | 1.00 (exact) |
| Binding non-zeros | ~100 (varies) | 10 (exact) |
| Binding uniqueness | Probabilistic | Guaranteed |
| Antonym structure | Ad-hoc | Principled |
| Interpretability | None | Full decode possible |
| Density | 10% | 2-5% |

---

## Implementation

### Dimension Layout

```python
D = 10000
GRID_SIZE = 100  # 100x100 grid

def grid_to_dim(row: int, col: int) -> int:
    """Convert grid position to dimension index."""
    return row * GRID_SIZE + col

def dim_to_grid(dim: int) -> tuple[int, int]:
    """Convert dimension index to grid position."""
    return dim // GRID_SIZE, dim % GRID_SIZE
```

### Primitive Vector Generation

```python
ROWS_PER_PRIMITIVE = 2
COLS_PER_ROLE = 5

def generate_primitive_vector(primitive_idx: int, dimension: int = 10000) -> SparseVector:
    """Generate OTP-structured primitive vector."""
    grid_size = int(np.sqrt(dimension))
    
    # Determine row range for this primitive
    start_row = primitive_idx * ROWS_PER_PRIMITIVE
    end_row = start_row + ROWS_PER_PRIMITIVE
    
    positive_indices = []
    negative_indices = []
    
    for row in range(start_row, end_row):
        for col in range(grid_size):
            dim = row * grid_size + col
            # Alternating sign pattern: even cols +1, odd cols -1
            if col % 2 == 0:
                positive_indices.append(dim)
            else:
                negative_indices.append(dim)
    
    return SparseVector(
        dimension=dimension,
        positive_indices=np.array(positive_indices, dtype=np.uint16),
        negative_indices=np.array(negative_indices, dtype=np.uint16)
    )


def generate_role_vector(role_idx: int, dimension: int = 10000) -> SparseVector:
    """Generate OTP-structured role vector."""
    grid_size = int(np.sqrt(dimension))
    
    # Determine column range for this role
    start_col = role_idx * COLS_PER_ROLE
    end_col = start_col + COLS_PER_ROLE
    
    positive_indices = []
    negative_indices = []
    
    for row in range(grid_size):
        for col in range(start_col, end_col):
            dim = row * grid_size + col
            # Alternating sign pattern: even rows +1, odd rows -1
            if row % 2 == 0:
                positive_indices.append(dim)
            else:
                negative_indices.append(dim)
    
    return SparseVector(
        dimension=dimension,
        positive_indices=np.array(positive_indices, dtype=np.uint16),
        negative_indices=np.array(negative_indices, dtype=np.uint16)
    )
```

### Antonym Pair Generation

```python
POLARITY_COLS = range(0, 10)  # First 10 columns are "polarity dimensions"

def generate_antonym_pair(
    pos_idx: int, 
    neg_idx: int,
    dimension: int = 10000
) -> tuple[SparseVector, SparseVector]:
    """
    Generate antonym pair with shared structure and opposite polarity.
    
    Both vectors use the SAME rows but:
    - Positive term: +1 in polarity columns
    - Negative term: -1 in polarity columns
    - Identical in all other columns
    """
    grid_size = int(np.sqrt(dimension))
    
    # Use the positive term's row assignment
    start_row = pos_idx * ROWS_PER_PRIMITIVE
    end_row = start_row + ROWS_PER_PRIMITIVE
    
    pos_positive = []
    pos_negative = []
    neg_positive = []
    neg_negative = []
    
    for row in range(start_row, end_row):
        for col in range(grid_size):
            dim = row * grid_size + col
            
            if col in POLARITY_COLS:
                # Polarity columns: opposite signs
                pos_positive.append(dim)  # Positive term gets +1
                neg_negative.append(dim)  # Negative term gets -1
            else:
                # Non-polarity columns: same pattern for both
                if col % 2 == 0:
                    pos_positive.append(dim)
                    neg_positive.append(dim)
                else:
                    pos_negative.append(dim)
                    neg_negative.append(dim)
    
    return (
        SparseVector(dimension, np.array(pos_positive, dtype=np.uint16), 
                     np.array(pos_negative, dtype=np.uint16)),
        SparseVector(dimension, np.array(neg_positive, dtype=np.uint16),
                     np.array(neg_negative, dtype=np.uint16))
    )
```

---

## Binding and Bundling with OTP Vectors

### Binding Analysis

When we bind a primitive (using rows) with a role (using columns):

```
Primitive 0: non-zeros at rows [0, 1] × all cols = 200 positions
Role 0: non-zeros at all rows × cols [0, 1, 2, 3, 4] = 500 positions

Intersection: rows [0, 1] × cols [0, 1, 2, 3, 4] = 10 positions

bind(Primitive 0, Role 0):
  Non-zeros at dims: [0, 1, 2, 3, 4, 100, 101, 102, 103, 104]
  Signs = prim_sign[dim] × role_sign[dim]
```

The binding result is **extremely sparse** (10/10000 = 0.1%) but **uniquely determined** by the (primitive, role) pair.

### Bundling Capacity

With 10 non-zeros per bound pair, how many pairs can we bundle reliably?

**Worst case**: All pairs have non-overlapping intersections (true by OTP design!)
- Bundle of 5 pairs: 50 non-zeros, no interference
- Bundle of 10 pairs: 100 non-zeros, no interference
- Bundle of 100 pairs: 1000 non-zeros, still no interference

**The OTP structure means bundling has NO capacity limit from interference!**

The limit comes from:
1. Running out of unique (primitive, role) pairs: 63 × 20 = 1260
2. Vector becoming too dense for efficient storage

---

## Position Encoding for Sequences

For encoding word position in sentences, we need position vectors that:
1. Are dissimilar to each other
2. Don't interfere with primitive/role structure

### Strategy: Use Unused Rows

Rows 126-199 are unused by primitives (only need 126 for 63 primitives).

Position encoding uses these "spare" rows:
- Position 0: rows 130-131
- Position 1: rows 132-133
- etc.

This keeps positions orthogonal to primitives while allowing binding.

### Alternative: Permutation-Based Position

Use circular permutation of a base vector:
```python
def position_vector(pos: int, base: SparseVector) -> SparseVector:
    """Generate position vector by permuting base vector."""
    return permute(base, pos * 100)  # Shift by 100 dims per position
```

This creates quasi-orthogonal position vectors while preserving the OTP structure.

---

## Implementation Checklist

1. [ ] Replace `SparseVector.random()` with `generate_primitive_vector()`
2. [ ] Replace role generation with `generate_role_vector()`
3. [ ] Implement `generate_antonym_pair()` for GOOD/BAD, BIG/SMALL, etc.
4. [ ] Update `PrimitiveBasis.generate()` to use OTP structure
5. [ ] Add `decode_primitive()` function to identify primitive from vector
6. [ ] Add `decode_role()` function to identify role from vector
7. [ ] Update tests to verify exact orthogonality
8. [ ] Benchmark binding/bundling with new structure

---

## Theoretical Justification

From your OTP document:

> "Each symbol is 'visible' to some channels and 'transparent' to others... The zeros are not missing information—they encode orthogonality."

In the grid architecture:
- Primitive i is "visible" to rows R_i (has signal there)
- Primitive i is "transparent" to rows R_j for j ≠ i (zeros = orthogonality)
- Same logic for roles and columns

> "Information is not just bits (presence/absence) but geometry (orientation/orthogonality)."

The grid structure makes this explicit:
- Row membership = primitive identity
- Column membership = role identity
- Row × Column intersection = binding location
- Sign pattern = semantic content

This is **true geometric semantic encoding** where the structure of the vector space directly mirrors semantic structure.

---

## Summary

| Aspect | Current Implementation | OTP Grid Architecture |
|--------|----------------------|----------------------|
| Orthogonality | Probabilistic (~99%) | Exact (100%) |
| Binding | ~100 non-zeros | 10 non-zeros (exact) |
| Antonyms | Ad-hoc polarity dims | Principled shared structure |
| Decode | Impossible | Direct (row/col identification) |
| Density | 10% | 2-5% |
| Interpretability | Low | High |

The grid-based OTP architecture is a **strict improvement** over random sparse vectors for GSE's requirements.
