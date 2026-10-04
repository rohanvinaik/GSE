#!/usr/bin/env python3
"""
GSE Command-Line Interface.

Usage:
    python -m gse.cli encode "The dog is cuter than the cat"
    python -m gse.cli compare "sentence1" "sentence2"
    python -m gse.cli decode --trace trace.json
    python -m gse.cli verify
"""

import argparse
import json
import sys

from gse.api import GSEDecoder, GSEEncoder
from gse.verification import GSEProofSuite


def cmd_encode(args):
    """Encode a sentence and output trace."""
    encoder = GSEEncoder()

    try:
        trace = encoder.encode(args.text)

        if args.format == "json":
            print(trace.to_json(indent=2))
        elif args.format == "summary":
            print(f"Input: {trace.input_text}")
            print(f"Tokens: {len(trace.tokens)}")
            print(f"Operators: {len(trace.operators)}")
            print(f"Vector NNZ: {trace.final_nnz}")
            print(f"Sparsity: {trace.sparsity:.4f}")
            print(f"Hash: {trace.vector_hash}")
            print("\nWord primitive activations:")
            for prim, val in sorted(trace.word_primitive_activations.items(), key=lambda x: -abs(x[1]))[:10]:
                print(f"  {prim}: {val:+.4f}")
            print("\nSentence primitive activations:")
            for prim, val in sorted(trace.sent_primitive_activations.items(), key=lambda x: -abs(x[1]))[:10]:
                print(f"  {prim}: {val:+.4f}")
        else:
            print(trace.to_json())

        # Save trace to file if requested
        if args.output:
            with open(args.output, "w") as f:
                f.write(trace.to_json(indent=2))
            print(f"\nTrace saved to: {args.output}", file=sys.stderr)

    finally:
        encoder.close()


def cmd_compare(args):
    """Compare two sentences."""
    encoder = GSEEncoder()
    decoder = GSEDecoder()

    try:
        trace1 = encoder.encode(args.sentence1)
        trace2 = encoder.encode(args.sentence2)

        similarity = decoder.similarity(
            trace1.vector,
            trace2.vector,
            args.sentence1,
            args.sentence2,
        )

        if args.format == "json":
            print(similarity.to_json(indent=2))
        else:
            print(f"Sentence 1: {args.sentence1}")
            print(f"Sentence 2: {args.sentence2}")
            print()
            print(f"Cosine similarity: {similarity.cosine:+.4f}")
            print(f"Alignment: {similarity.alignment:.4f}")
            print(f"Opposition: {similarity.opposition:.4f}")
            print(f"Orthogonality: {similarity.orthogonality:.4f}")

            if similarity.shared_primitives:
                print(f"\nShared primitives: {', '.join(similarity.shared_primitives)}")
            if similarity.different_primitives:
                print(f"Different primitives: {', '.join(similarity.different_primitives)}")

    finally:
        encoder.close()
        decoder.close()


def cmd_decode(args):
    """Decode a vector from a trace file."""
    decoder = GSEDecoder()
    encoder = GSEEncoder()

    try:
        if args.trace:
            # Load trace from file
            with open(args.trace) as f:
                trace_data = json.load(f)

            # Re-encode to get the vector
            from gse.api.trace import OperationTrace

            trace = OperationTrace.from_dict(trace_data)

            # Need to re-encode to get actual vector
            full_trace = encoder.encode(trace.input_text)
            vector = full_trace.vector

        elif args.text:
            # Encode text directly
            trace = encoder.encode(args.text)
            vector = trace.vector
        else:
            print("Error: Must provide --trace or --text", file=sys.stderr)
            sys.exit(1)

        # Decode
        semantics = decoder.decode(vector)

        if args.format == "json":
            print(semantics.to_json(indent=2))
        else:
            print("=== DECODED SEMANTICS ===\n")

            print("Entities:")
            for e in semantics.entities[:5]:
                print(f"  {e.lemma} ({e.pos}): confidence={e.confidence:.3f}")
                print(f"    primitives: {e.primitives}")

            print("\nAttributes:")
            for a in semantics.attributes[:5]:
                sign = "+" if a.polarity > 0 else "-"
                print(f"  {a.attribute}: {sign}{a.intensity:.3f} ({a.source_primitive})")

            print("\nRelations:")
            for r in semantics.relations[:5]:
                print(f"  {r.relation}: confidence={r.confidence:.3f} ({r.operation})")

            print("\nNearest lexemes:")
            for lemma, score in semantics.nearest_lexemes[:10]:
                print(f"  {lemma}: {score:.3f}")

            print("\nBank activity:")
            for bank, activity in sorted(semantics.bank_activations.items(), key=lambda x: -x[1]):
                print(f"  {bank}: {activity:.3f}")

    finally:
        decoder.close()
        encoder.close()


def cmd_verify(args):
    """Run verification suite."""
    suite = GSEProofSuite(verbose=not args.quiet)

    try:
        suite.run_all()
        success = suite.print_report()
        sys.exit(0 if success else 1)
    finally:
        suite.close()


def cmd_interactive(args):
    """Interactive mode for exploring encodings."""
    encoder = GSEEncoder()
    decoder = GSEDecoder()

    print("GSE Interactive Mode")
    print("Commands: encode <text>, compare <t1> | <t2>, decode <text>, quit")
    print()

    try:
        while True:
            try:
                line = input("gse> ").strip()
            except EOFError:
                break

            if not line:
                continue

            if line.lower() in ("quit", "exit", "q"):
                break

            if line.startswith("encode "):
                text = line[7:].strip()
                trace = encoder.encode(text)
                print(f"Hash: {trace.vector_hash}")
                print(f"NNZ: {trace.final_nnz}")
                top_prims = sorted(trace.word_primitive_activations.items(), key=lambda x: -abs(x[1]))[:5]
                print(f"Top primitives: {[p[0] for p in top_prims]}")

            elif line.startswith("compare "):
                parts = line[8:].split("|")
                if len(parts) == 2:
                    s1, s2 = parts[0].strip(), parts[1].strip()
                    v1 = encoder.encode(s1).vector
                    v2 = encoder.encode(s2).vector
                    cos = v1.cosine(v2)
                    print(f"Cosine: {cos:+.4f}")
                else:
                    print("Usage: compare <sentence1> | <sentence2>")

            elif line.startswith("decode "):
                text = line[7:].strip()
                trace = encoder.encode(text)
                semantics = decoder.decode(trace.vector)
                print(f"Entities: {[e.lemma for e in semantics.entities[:5]]}")
                print(f"Attributes: {[(a.source_primitive, a.polarity) for a in semantics.attributes[:3]]}")
                print(f"Nearest: {[n[0] for n in semantics.nearest_lexemes[:5]]}")

            else:
                print("Unknown command. Try: encode, compare, decode, quit")

    finally:
        encoder.close()
        decoder.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="GSE Command-Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s encode "The dog is cuter than the cat"
  %(prog)s encode "Hello world" --format summary
  %(prog)s compare "I love you" "I hate you"
  %(prog)s decode --text "The big dog"
  %(prog)s verify
  %(prog)s interactive
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # encode
    p_encode = subparsers.add_parser("encode", help="Encode text to HDC vector")
    p_encode.add_argument("text", help="Text to encode")
    p_encode.add_argument("--format", choices=["json", "summary"], default="summary")
    p_encode.add_argument("--output", "-o", help="Save trace to file")
    p_encode.set_defaults(func=cmd_encode)

    # compare
    p_compare = subparsers.add_parser("compare", help="Compare two sentences")
    p_compare.add_argument("sentence1", help="First sentence")
    p_compare.add_argument("sentence2", help="Second sentence")
    p_compare.add_argument("--format", choices=["json", "text"], default="text")
    p_compare.set_defaults(func=cmd_compare)

    # decode
    p_decode = subparsers.add_parser("decode", help="Decode vector to semantics")
    p_decode.add_argument("--trace", help="Path to trace JSON file")
    p_decode.add_argument("--text", help="Text to encode then decode")
    p_decode.add_argument("--format", choices=["json", "text"], default="text")
    p_decode.set_defaults(func=cmd_decode)

    # verify
    p_verify = subparsers.add_parser("verify", help="Run verification suite")
    p_verify.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    p_verify.set_defaults(func=cmd_verify)

    # interactive
    p_interactive = subparsers.add_parser("interactive", help="Interactive mode")
    p_interactive.set_defaults(func=cmd_interactive)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
