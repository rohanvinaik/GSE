"""
GSE Command Line Interface (v2)

Uses the new GSEPipeline from pipeline_v2.py
"""

import argparse
import json
import sys

from gse.pipeline_v2 import GSEPipeline


def main():
    parser = argparse.ArgumentParser(description="GSE Semantic Encoding v2")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Encode command
    encode_parser = subparsers.add_parser("encode", help="Encode text to vector")
    encode_parser.add_argument("--text", "-t", required=True, help="Input text")
    encode_parser.add_argument("--lexicon", "-l", default="data/lexicon_clean.db")

    # Similarity command
    sim_parser = subparsers.add_parser("similarity", help="Compare two texts")
    sim_parser.add_argument("--text1", "-t1", required=True, help="First text")
    sim_parser.add_argument("--text2", "-t2", required=True, help="Second text")
    sim_parser.add_argument("--lexicon", "-l", default="data/lexicon.db")

    # Decompose command
    decomp_parser = subparsers.add_parser("decompose", help="Decompose unknown word")
    decomp_parser.add_argument("--word", "-w", required=True, help="Word to decompose")
    decomp_parser.add_argument("--pos", "-p", default="NOUN", help="Part of speech")
    decomp_parser.add_argument("--lexicon", "-l", default="data/lexicon.db")

    # Search command
    search_parser = subparsers.add_parser("search", help="Find similar words")
    search_parser.add_argument("--word", "-w", required=True, help="Query word")
    search_parser.add_argument("--top", "-n", type=int, default=5, help="Number of results")
    search_parser.add_argument("--lexicon", "-l", default="data/lexicon.db")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show lexicon statistics")
    stats_parser.add_argument("--lexicon", "-l", default="data/lexicon.db")

    # Integrity command
    integrity_parser = subparsers.add_parser("integrity", help="Verify lexicon integrity")
    integrity_parser.add_argument("--lexicon", "-l", default="data/lexicon.db")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize pipeline
    pipeline = GSEPipeline()

    # Load lexicon if specified
    lexicon_path = getattr(args, 'lexicon', 'data/lexicon_clean.db')
    try:
        import os
        if os.path.exists(lexicon_path):
            pipeline.load_lexicon(lexicon_path)
    except Exception as e:
        print(f"Warning: Could not load lexicon: {e}", file=sys.stderr)

    if args.command == "encode":
        result = pipeline.encode_sentence(args.text)
        print(json.dumps({
            "text": args.text,
            "word_count": result.word_count,
            "dims_per_word": result.dims_per_word,
            "norm": result.norm,
            "nnz": result.nnz,
        }, indent=2))

    elif args.command == "similarity":
        result = pipeline.compute_similarity(args.text1, args.text2)
        print(json.dumps({
            "text1": args.text1,
            "text2": args.text2,
            "cosine": result.cosine,
            "euclidean": result.euclidean,
            "bank_similarities": result.bank_similarities,
        }, indent=2))

    elif args.command == "decompose":
        result = pipeline.decompose_word(args.word, args.pos)
        print(json.dumps({
            "word": args.word,
            "pos": args.pos,
            "decomposition": [(p, r, v) for p, r, v in result.decomposition],
            "confidence": result.confidence,
            "method": result.method,
            "source_patterns": result.source_patterns,
        }, indent=2))

    elif args.command == "search":
        results = pipeline.find_similar(args.word, k=args.top)
        print(json.dumps({
            "query": args.word,
            "results": [
                {"lemma": r.lemma, "pos": r.pos, "similarity": r.similarity}
                for r in results
            ]
        }, indent=2))

    elif args.command == "stats":
        stats = pipeline.get_statistics()
        print(json.dumps(stats, indent=2))

    elif args.command == "integrity":
        result = pipeline.check_integrity()
        print(json.dumps({
            "valid": result["valid"],
            "root_hash": result["root_hash"],
            "issues": result.get("issues", [])
        }, indent=2))


if __name__ == "__main__":
    main()
