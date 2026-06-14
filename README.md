# Geometric Semantic Encoding (GSE)

A symbolic NLP system that encodes natural language as high-dimensional sparse ternary vectors.

## Installation

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Quick Start

1. **Generate Lexicon** (Requires Anthropic API Key for best results, or use --quick for testing):
   ```bash
   export ANTHROPIC_API_KEY="your-key"
   python scripts/generate_lexicon.py --quick
   ```

2. **Validate Lexicon**:
   ```bash
   python scripts/validate_lexicon.py
   ```

3. **Run Pipeline CLI**:
   ```bash
   # Encode a sentence
   python -m gse.cli encode --text "The dog runs in the park."

   # Check similarity
   python -m gse.cli similarity --text "The dog runs." --text2 "The cat sleeps."

   # Batch process
   python -m gse.cli batch --file sentences.txt
   ```

## Python API

```python
from gse.pipeline import load_pipeline

# Load with defaults (data/lexicon.db, data/basis.msgpack)
pipeline = load_pipeline()

# Process text
result = pipeline.process("The committee approved the proposal.")

print(f"Confidence: {result.confidence}")
print(f"Coherent: {result.coherence_passed}")
print(f"Anomalies: {result.anomalies}")

# Access vector
vector = result.vector
dense_vec = vector.to_dense()
```

## Architecture

- **Vectors**: 10,000-dimensional sparse ternary vectors ({-1, 0, +1}).
- **Composition**: Bottom-up recursive binding and bundling based on dependency parse.
- **Verification**: Merkle tree computation for integrity.
- **Coherence**: Checks for semantic anomalies (animacy, sparsity, consistency).

## Development

Run tests:
```bash
pytest tests/
```
