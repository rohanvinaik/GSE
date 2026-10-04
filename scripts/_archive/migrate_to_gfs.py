"""
Migrate GSE to GFS

This script performs the following steps:
1. Validates the existence of the Lexicon database (lexicon.db).
2. Initializes and learns the Primitive Pattern Network (Cooccurrence Matrix + K-Lines).
3. Builds the Semantic Graph.
4. Saves the learned models to `data/gfs_models/`.
"""

import os
import sys
import logging

# Ensure gse is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gse.primitives import PRIMITIVES
from gse.patterns.pattern_network import PrimitivePatternNetwork
from gse.graph.builder import GraphBuilder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate(lexicon_path: str, output_dir: str):
    if not os.path.exists(lexicon_path):
        logging.error(f"Lexicon database not found at {lexicon_path}")
        return

    logging.info(f"Starting migration using lexicon: {lexicon_path}")
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Learn Pattern Network
    logging.info("Step 1: Learning Primitive Pattern Network...")
    network = PrimitivePatternNetwork(PRIMITIVES)
    network.learn(lexicon_path)
    network.save(os.path.join(output_dir, "patterns"))
    logging.info("Pattern Network saved.")
    
    # 2. Build Semantic Graph
    logging.info("Step 2: Building Semantic Graph...")
    builder = GraphBuilder(PRIMITIVES)
    graph = builder.build(lexicon_path, pattern_network=network)
    graph.save(os.path.join(output_dir, "graph.json"))
    logging.info("Semantic Graph saved.")
    
    logging.info("Migration complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate GSE to GFS")
    parser.add_argument("--lexicon", default="lexicon.db", help="Path to lexicon.db")
    parser.add_argument("--output", default="data/gfs_models", help="Output directory for GFS models")
    
    args = parser.parse_args()
    migrate(args.lexicon, args.output)
