"""
Corpus Scoring Pipeline

Batch processes large corpora to compute GSE cognitive complexity scores.
Supports parallel processing and caching for efficiency.

Usage:
    scorer = CorpusScorer(gse_pipeline)
    scored_docs = scorer.score_corpus(corpus_path, output_path)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Iterator, Any
from pathlib import Path
import json
import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

import numpy as np

from .cognitive_complexity import (
    compute_cognitive_complexity,
    score_document,
    CognitiveComplexityScore,
)

logger = logging.getLogger(__name__)


@dataclass
class DocumentScore:
    """
    Scored document with metadata.

    Attributes:
        doc_id: Unique document identifier
        text: Original text content
        complexity: CognitiveComplexityScore
        perplexity: Optional perplexity score (for comparison)
        metadata: Additional document metadata
    """
    doc_id: str
    text: str
    complexity: Dict[str, Any]
    perplexity: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'doc_id': self.doc_id,
            'text': self.text,
            'complexity': self.complexity,
            'perplexity': self.perplexity,
            'metadata': self.metadata,
        }


@dataclass
class ScoringStats:
    """Statistics from corpus scoring."""
    total_documents: int
    scored_documents: int
    failed_documents: int
    processing_time_seconds: float
    avg_complexity: float
    std_complexity: float
    complexity_distribution: Dict[str, int]  # Binned counts


class CorpusScorer:
    """
    Batch corpus scoring pipeline.

    Processes documents through GSE to compute cognitive complexity scores.
    Supports parallel processing for large corpora.
    """

    def __init__(
        self,
        gse_pipeline=None,
        n_workers: int = 1,
        batch_size: int = 100,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize corpus scorer.

        Args:
            gse_pipeline: GSE pipeline instance
            n_workers: Number of parallel workers (1 = sequential)
            batch_size: Documents per batch for progress reporting
            cache_dir: Optional directory for caching results
        """
        self.gse_pipeline = gse_pipeline
        self.n_workers = n_workers
        self.batch_size = batch_size
        self.cache_dir = cache_dir

        if self.gse_pipeline is None:
            self._init_gse()

    def _init_gse(self):
        """Initialize GSE pipeline."""
        try:
            from gse.pipeline import GSEPipeline, GSEConfig
            from pathlib import Path

            # Find data directory
            gse_root = Path(__file__).parent.parent.parent
            data_dir = gse_root / 'data'

            if not data_dir.exists():
                data_dir = Path.home() / '.gse' / 'data'

            lexicon_path = data_dir / 'lexicon.db'
            basis_path = data_dir / 'basis.msgpack'

            if not lexicon_path.exists() or not basis_path.exists():
                raise FileNotFoundError(f"GSE data not found at {data_dir}")

            logger.info("Initializing GSE pipeline")
            config = GSEConfig(
                lexicon_path=str(lexicon_path),
                basis_path=str(basis_path),
            )
            self.gse_pipeline = GSEPipeline(config)
        except Exception as e:
            logger.error(f"Failed to initialize GSE: {e}")
            raise

    def score_corpus(
        self,
        corpus_path: Path,
        output_path: Optional[Path] = None,
        format: str = 'jsonl',
        text_field: str = 'text',
        id_field: str = 'id',
        max_docs: Optional[int] = None,
    ) -> List[DocumentScore]:
        """
        Score all documents in a corpus.

        Args:
            corpus_path: Path to corpus (JSONL file or directory)
            output_path: Optional path to save scored documents
            format: Input format ('jsonl', 'json', 'txt')
            text_field: Field name for text content
            id_field: Field name for document ID
            max_docs: Maximum documents to process (for testing)

        Returns:
            List of DocumentScore objects sorted by complexity
        """
        logger.info(f"Scoring corpus: {corpus_path}")
        start_time = time.time()

        # Load documents
        documents = self._load_documents(corpus_path, format, max_docs)
        logger.info(f"Loaded {len(documents)} documents")

        # Score documents
        scored = []
        failed = 0

        for i, doc in enumerate(documents):
            try:
                # Get document ID
                doc_id = doc.get(id_field, str(i))

                # Get text
                text = doc.get(text_field, '')
                if not text:
                    failed += 1
                    continue

                # Score document
                scored_doc = score_document(
                    {'text': text, **doc},
                    self.gse_pipeline,
                    text_field=text_field,
                )

                document_score = DocumentScore(
                    doc_id=doc_id,
                    text=text,
                    complexity=scored_doc['complexity'],
                    perplexity=doc.get('perplexity'),
                    metadata={k: v for k, v in doc.items()
                              if k not in [text_field, id_field, 'complexity']},
                )
                scored.append(document_score)

                # Progress logging
                if (i + 1) % self.batch_size == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed
                    logger.info(
                        f"Processed {i + 1}/{len(documents)} documents "
                        f"({rate:.1f} docs/sec)"
                    )

            except Exception as e:
                logger.warning(f"Failed to score document {i}: {e}")
                failed += 1

        # Sort by complexity (highest first)
        scored.sort(key=lambda x: x.complexity.get('composite', 0), reverse=True)

        # Compute statistics
        elapsed = time.time() - start_time
        complexities = [s.complexity.get('composite', 0) for s in scored]
        stats = ScoringStats(
            total_documents=len(documents),
            scored_documents=len(scored),
            failed_documents=failed,
            processing_time_seconds=elapsed,
            avg_complexity=float(np.mean(complexities)) if complexities else 0,
            std_complexity=float(np.std(complexities)) if complexities else 0,
            complexity_distribution=self._bin_complexities(complexities),
        )

        logger.info(f"Scoring complete in {elapsed:.1f}s")
        logger.info(f"  Scored: {stats.scored_documents}, Failed: {stats.failed_documents}")
        logger.info(f"  Avg complexity: {stats.avg_complexity:.4f} +/- {stats.std_complexity:.4f}")

        # Save results
        if output_path:
            self._save_scored(scored, output_path, stats)

        return scored

    def score_corpus_parallel(
        self,
        corpus_path: Path,
        output_path: Optional[Path] = None,
        format: str = 'jsonl',
        text_field: str = 'text',
        id_field: str = 'id',
        max_docs: Optional[int] = None,
    ) -> List[DocumentScore]:
        """
        Score corpus using parallel processing.

        Note: Requires initializing GSE in each worker process.

        Args:
            Same as score_corpus

        Returns:
            List of DocumentScore objects
        """
        if self.n_workers <= 1:
            return self.score_corpus(
                corpus_path, output_path, format, text_field, id_field, max_docs
            )

        logger.info(f"Parallel scoring with {self.n_workers} workers")
        start_time = time.time()

        # Load documents
        documents = self._load_documents(corpus_path, format, max_docs)
        logger.info(f"Loaded {len(documents)} documents")

        # Split into chunks
        chunk_size = max(1, len(documents) // self.n_workers)
        chunks = [
            documents[i:i + chunk_size]
            for i in range(0, len(documents), chunk_size)
        ]

        # Process in parallel
        scored = []
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            futures = [
                executor.submit(
                    _score_chunk,
                    chunk,
                    text_field,
                    id_field,
                    i * chunk_size,
                )
                for i, chunk in enumerate(chunks)
            ]

            for future in as_completed(futures):
                try:
                    chunk_scored = future.result()
                    scored.extend(chunk_scored)
                except Exception as e:
                    logger.error(f"Chunk processing failed: {e}")

        # Sort by complexity
        scored.sort(key=lambda x: x.complexity.get('composite', 0), reverse=True)

        elapsed = time.time() - start_time
        logger.info(f"Parallel scoring complete in {elapsed:.1f}s")

        if output_path:
            self._save_scored(scored, output_path)

        return scored

    def _load_documents(
        self,
        path: Path,
        format: str,
        max_docs: Optional[int],
    ) -> List[Dict]:
        """Load documents from file or directory."""
        path = Path(path)
        documents = []

        if path.is_file():
            if format == 'jsonl':
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            documents.append(json.loads(line))
                            if max_docs and len(documents) >= max_docs:
                                break
            elif format == 'json':
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        documents = data[:max_docs] if max_docs else data
                    else:
                        documents = [data]
            elif format == 'txt':
                with open(path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if line.strip():
                            documents.append({'text': line.strip(), 'id': str(i)})
                            if max_docs and len(documents) >= max_docs:
                                break
        elif path.is_dir():
            for file_path in path.glob('*.jsonl'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            documents.append(json.loads(line))
                            if max_docs and len(documents) >= max_docs:
                                return documents

        return documents

    def _save_scored(
        self,
        scored: List[DocumentScore],
        output_path: Path,
        stats: Optional[ScoringStats] = None,
    ):
        """Save scored documents to file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save documents
        with open(output_path, 'w', encoding='utf-8') as f:
            for doc in scored:
                f.write(json.dumps(doc.to_dict()) + '\n')

        logger.info(f"Saved {len(scored)} scored documents to {output_path}")

        # Save stats
        if stats:
            stats_path = output_path.with_suffix('.stats.json')
            with open(stats_path, 'w') as f:
                json.dump({
                    'total_documents': stats.total_documents,
                    'scored_documents': stats.scored_documents,
                    'failed_documents': stats.failed_documents,
                    'processing_time_seconds': stats.processing_time_seconds,
                    'avg_complexity': stats.avg_complexity,
                    'std_complexity': stats.std_complexity,
                    'complexity_distribution': stats.complexity_distribution,
                }, f, indent=2)

    def _bin_complexities(self, complexities: List[float]) -> Dict[str, int]:
        """Bin complexity scores into categories."""
        bins = {
            'very_low': 0,    # 0.0 - 0.2
            'low': 0,         # 0.2 - 0.4
            'medium': 0,      # 0.4 - 0.6
            'high': 0,        # 0.6 - 0.8
            'very_high': 0,   # 0.8 - 1.0
        }

        for c in complexities:
            if c < 0.2:
                bins['very_low'] += 1
            elif c < 0.4:
                bins['low'] += 1
            elif c < 0.6:
                bins['medium'] += 1
            elif c < 0.8:
                bins['high'] += 1
            else:
                bins['very_high'] += 1

        return bins


def _score_chunk(
    documents: List[Dict],
    text_field: str,
    id_field: str,
    start_idx: int,
) -> List[DocumentScore]:
    """
    Score a chunk of documents (for parallel processing).

    This function runs in a worker process with its own GSE instance.
    """
    # Initialize GSE in this worker
    try:
        from gse.pipeline import GSEPipeline
        gse = GSEPipeline()
    except Exception as e:
        logger.error(f"Worker failed to initialize GSE: {e}")
        return []

    scored = []
    for i, doc in enumerate(documents):
        try:
            doc_id = doc.get(id_field, str(start_idx + i))
            text = doc.get(text_field, '')

            if not text:
                continue

            scored_doc = score_document(
                {'text': text, **doc},
                gse,
                text_field=text_field,
            )

            scored.append(DocumentScore(
                doc_id=doc_id,
                text=text,
                complexity=scored_doc['complexity'],
                perplexity=doc.get('perplexity'),
                metadata={k: v for k, v in doc.items()
                          if k not in [text_field, id_field, 'complexity']},
            ))

        except Exception as e:
            logger.debug(f"Failed to score document: {e}")

    return scored


def load_scored_corpus(path: Path) -> List[DocumentScore]:
    """
    Load previously scored corpus from file.

    Args:
        path: Path to JSONL file with scored documents

    Returns:
        List of DocumentScore objects
    """
    scored = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                scored.append(DocumentScore(
                    doc_id=data['doc_id'],
                    text=data['text'],
                    complexity=data['complexity'],
                    perplexity=data.get('perplexity'),
                    metadata=data.get('metadata', {}),
                ))

    return scored
