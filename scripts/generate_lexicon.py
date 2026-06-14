import argparse
import json
import os

from gse.lexicon_generator import LexiconGenerator
from gse.lexicon_validator import VALIDATION_PAIRS
from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import PrimitiveBasis


def main():
    parser = argparse.ArgumentParser(description="Generate GSE Lexicon")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY"), help="Anthropic API Key")
    parser.add_argument("--output", default="data/lexicon.db", help="Output SQLite database path")
    parser.add_argument("--basis", default="data/basis.msgpack", help="Path to primitive basis")
    parser.add_argument("--input-file", help="Input JSON file with word list")
    parser.add_argument("--quick", action="store_true", help="Generate only validation words for testing")

    args = parser.parse_args()

    # Ensure data directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(os.path.dirname(args.basis), exist_ok=True)

    # Load or generate basis
    if os.path.exists(args.basis):
        print(f"Loading basis from {args.basis}...")
        basis = PrimitiveBasis.load(args.basis)
    else:
        print(f"Generating new basis at {args.basis}...")
        basis = PrimitiveBasis()
        basis.generate(PRIMITIVES, ROLES)
        basis.save(args.basis)

    # Initialize generator
    generator = LexiconGenerator(basis, api_key=args.api_key)

    words_to_process = []

    if args.quick:
        print("Quick mode: preparing validation words...")
        # Collect unique words from validation pairs
        unique_words = set()
        for category in VALIDATION_PAIRS.values():
            for w1, w2 in category:
                unique_words.add(w1)
                unique_words.add(w2)

        # Add a few common ones for sentences
        unique_words.update(["the", "a", "dog", "cat", "run", "sleep", "chase", "John", "Mary", "love", "give", "book", "quickly", "in", "to"])

        for w in unique_words:
            # We need to guess POS or add entries for multiple POS
            # For simplicity in quick mode, we'll try to guess or add generic entries
            # A better way is to have a manual dictionary for quick mode
            pass

            # Simple heuristic or just add duplicates for likely POS
            words_to_process.append({"word": w, "pos": "NOUN", "definition": f"A quantity of {w}"})
            words_to_process.append({"word": w, "pos": "VERB", "definition": f"To {w}"})
            words_to_process.append({"word": w, "pos": "ADJ", "definition": f"Being {w}"})

    elif args.input_file:
        print(f"Loading words from {args.input_file}...")
        with open(args.input_file, 'r') as f:
            words_to_process = json.load(f)
    else:
        print("No input provided. Use --quick or --input-file.")
        return

    print(f"Queued up {len(words_to_process)} entries for generation.")

    if not args.api_key:
        print("\nWARNING: No API key provided.")
        print("Generation will attempt to run but will fail if it tries to call LLM.")
        print("For 'quick' mode without API key, we could inject manual fallback/mock data if implemented.")
        # We could implement a fallback here if we want the tests to pass without key

    generator.generate_batch(words_to_process, args.output)
    print(f"Done. Lexicon saved to {args.output}")

if __name__ == "__main__":
    main()
