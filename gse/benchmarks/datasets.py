"""
Benchmark Dataset Loaders

Loads standard NLP evaluation datasets:
- SimLex-999: Word similarity (structural semantics focus)
- WordSim-353: Word relatedness
- STS Benchmark: Sentence-level similarity
- Custom antonym set: Built from GSE primitives
"""

import csv
import logging
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default cache directory
CACHE_DIR = Path.home() / ".cache" / "gse_benchmarks"


@dataclass
class WordPair:
    """A word pair with human similarity score."""
    word1: str
    word2: str
    score: float  # Typically 0-10 or 0-1 depending on dataset
    pos: Optional[str] = None  # Part of speech if available
    relation: Optional[str] = None  # e.g., 'synonym', 'antonym', 'hypernym'


@dataclass
class SentencePair:
    """A sentence pair with human similarity score."""
    sentence1: str
    sentence2: str
    score: float  # Typically 0-5


class BenchmarkDataset:
    """Container for benchmark datasets with metadata."""

    def __init__(
        self,
        name: str,
        pairs: List,  # WordPair or SentencePair
        description: str = "",
        citation: str = "",
    ):
        self.name = name
        self.pairs = pairs
        self.description = description
        self.citation = citation

    def __len__(self):
        return len(self.pairs)

    def __iter__(self):
        return iter(self.pairs)

    def get_words(self) -> Tuple[List[str], List[str]]:
        """Get word lists for word-level datasets."""
        words1 = [p.word1 for p in self.pairs]
        words2 = [p.word2 for p in self.pairs]
        return words1, words2

    def get_scores(self) -> List[float]:
        """Get human similarity scores."""
        return [p.score for p in self.pairs]


def _download_file(url: str, output_path: Path) -> None:
    """Download a file with progress indication."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading {url} to {output_path}")
    urllib.request.urlretrieve(url, output_path)


def _ensure_simlex999(cache_dir: Path = CACHE_DIR) -> Path:
    """Download SimLex-999 if not cached."""
    simlex_path = cache_dir / "SimLex-999.txt"

    if simlex_path.exists():
        return simlex_path

    # Download from official source
    url = "https://fh295.github.io/SimLex-999.zip"
    zip_path = cache_dir / "SimLex-999.zip"

    _download_file(url, zip_path)

    # Extract
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(cache_dir)

    # Find the text file
    extracted_path = cache_dir / "SimLex-999" / "SimLex-999.txt"
    if extracted_path.exists():
        extracted_path.rename(simlex_path)

    return simlex_path


def load_simlex999(cache_dir: Path = CACHE_DIR) -> BenchmarkDataset:
    """
    Load SimLex-999 dataset.

    SimLex-999 measures similarity (not relatedness), making it ideal
    for testing structural semantic representations like GSE.

    Key distinction: 'hot' and 'cold' should have LOW similarity
    (they are antonyms, not similar concepts).

    Returns:
        BenchmarkDataset with 999 word pairs
    """
    simlex_path = _ensure_simlex999(cache_dir)

    pairs = []
    with open(simlex_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            pair = WordPair(
                word1=row['word1'].lower(),
                word2=row['word2'].lower(),
                score=float(row['SimLex999']),
                pos=row.get('POS'),
            )
            pairs.append(pair)

    return BenchmarkDataset(
        name="SimLex-999",
        pairs=pairs,
        description="Word similarity (not relatedness) judgments from Hill et al. 2015",
        citation="Hill, F., Reichart, R., & Korhonen, A. (2015). SimLex-999",
    )


def _ensure_wordsim353(cache_dir: Path = CACHE_DIR) -> Path:
    """Get WordSim-353 from local data directory or cache."""
    # First check local project data
    local_paths = [
        Path(__file__).parent.parent.parent / "data" / "benchmarks" / "wordsim353.csv",
        Path("data/benchmarks/wordsim353.csv"),
    ]

    for local_path in local_paths:
        if local_path.exists():
            return local_path

    # Fall back to cache
    wordsim_path = cache_dir / "wordsim353.csv"
    if wordsim_path.exists():
        return wordsim_path

    # Create empty file as fallback (download URLs are unreliable)
    logger.warning("WordSim-353 not found locally. Please download to data/benchmarks/wordsim353.csv")
    wordsim_path.parent.mkdir(parents=True, exist_ok=True)
    wordsim_path.touch()

    return wordsim_path


def load_wordsim353(cache_dir: Path = CACHE_DIR) -> BenchmarkDataset:
    """
    Load WordSim-353 dataset.

    WordSim-353 measures relatedness (not strict similarity).
    'hot' and 'cold' may get HIGH scores (they are related concepts).

    This is a comparison benchmark - GSE may perform differently here
    since it captures structural semantics rather than distributional patterns.

    Returns:
        BenchmarkDataset with 353 word pairs
    """
    wordsim_path = _ensure_wordsim353(cache_dir)

    pairs = []

    if wordsim_path.stat().st_size == 0:
        logger.warning("WordSim-353 not available, returning empty dataset")
        return BenchmarkDataset(
            name="WordSim-353",
            pairs=[],
            description="Word relatedness judgments",
        )

    with open(wordsim_path, 'r', encoding='utf-8') as f:
        # Try to detect delimiter (tab or comma)
        first_line = f.readline()
        f.seek(0)
        delimiter = '\t' if '\t' in first_line else ','

        reader = csv.reader(f, delimiter=delimiter)
        next(reader, None)  # Skip header
        for row in reader:
            if len(row) >= 3:
                try:
                    pair = WordPair(
                        word1=row[0].lower().strip(),
                        word2=row[1].lower().strip(),
                        score=float(row[2]),
                    )
                    pairs.append(pair)
                except (ValueError, IndexError):
                    continue

    return BenchmarkDataset(
        name="WordSim-353",
        pairs=pairs,
        description="Word relatedness judgments from Finkelstein et al. 2001",
        citation="Finkelstein, L., et al. (2001). Placing Search in Context",
    )


def _ensure_sts_benchmark(cache_dir: Path = CACHE_DIR) -> Path:
    """Download STS Benchmark if not cached."""
    sts_dir = cache_dir / "stsbenchmark"
    sts_test = sts_dir / "sts-test.csv"

    if sts_test.exists():
        return sts_dir

    # Download from STS wiki
    url = "http://ixa2.si.ehu.eus/stswiki/images/4/48/Stsbenchmark.tar.gz"
    tar_path = cache_dir / "Stsbenchmark.tar.gz"

    try:
        _download_file(url, tar_path)

        with tarfile.open(tar_path, 'r:gz') as tar:
            tar.extractall(cache_dir)
    except Exception as e:
        logger.warning(f"Could not download STS Benchmark: {e}")
        sts_dir.mkdir(parents=True, exist_ok=True)

    return sts_dir


def load_sts_benchmark(
    split: str = "test",
    cache_dir: Path = CACHE_DIR
) -> BenchmarkDataset:
    """
    Load STS Benchmark dataset.

    Args:
        split: One of 'train', 'dev', 'test'
        cache_dir: Cache directory

    Returns:
        BenchmarkDataset with sentence pairs
    """
    sts_dir = _ensure_sts_benchmark(cache_dir)
    sts_file = sts_dir / f"sts-{split}.csv"

    pairs = []

    if not sts_file.exists():
        logger.warning(f"STS Benchmark {split} not available")
        return BenchmarkDataset(
            name=f"STS-Benchmark-{split}",
            pairs=[],
            description="Sentence similarity benchmark",
        )

    with open(sts_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if len(row) >= 7:
                try:
                    score = float(row[4])
                    pair = SentencePair(
                        sentence1=row[5],
                        sentence2=row[6],
                        score=score,
                    )
                    pairs.append(pair)
                except (ValueError, IndexError):
                    continue

    return BenchmarkDataset(
        name=f"STS-Benchmark-{split}",
        pairs=pairs,
        description="Sentence similarity from SemEval STS tasks",
        citation="Cer, D., et al. (2017). SemEval-2017 Task 1",
    )


# Antonym pairs derived from GSE primitives and common antonyms
PRIMITIVE_ANTONYM_PAIRS = [
    # From POLARITY_SCOPE - these trigger bank infection
    ("good", "bad"),
    ("big", "small"),
    ("live", "die"),
    ("above", "below"),
    ("before", "after"),

    # Extended antonyms aligned with GSE primitives
    ("love", "hate"),
    ("happy", "sad"),
    ("fast", "slow"),
    ("hot", "cold"),
    ("light", "dark"),
    ("old", "young"),
    ("rich", "poor"),
    ("strong", "weak"),
    ("high", "low"),
    ("long", "short"),
    ("deep", "shallow"),
    ("wide", "narrow"),
    ("thick", "thin"),
    ("heavy", "light"),
    ("hard", "soft"),
    ("dry", "wet"),
    ("clean", "dirty"),
    ("safe", "dangerous"),
    ("easy", "difficult"),
    ("true", "false"),

    # Mental/emotional antonyms (MENTAL bank)
    ("like", "dislike"),
    ("want", "reject"),
    ("know", "ignore"),
    ("remember", "forget"),
    ("accept", "refuse"),
    ("agree", "disagree"),
    ("trust", "distrust"),
    ("hope", "despair"),
    ("calm", "anxious"),
    ("confident", "doubtful"),

    # Action antonyms (ACTION bank)
    ("start", "stop"),
    ("begin", "end"),
    ("create", "destroy"),
    ("build", "demolish"),
    ("open", "close"),
    ("enter", "exit"),
    ("arrive", "leave"),
    ("give", "take"),
    ("buy", "sell"),
    ("win", "lose"),

    # Temporal antonyms (TEMPORAL bank)
    ("early", "late"),
    ("always", "never"),
    ("often", "rarely"),
    ("past", "future"),

    # Spatial antonyms (SPATIAL bank)
    ("near", "far"),
    ("inside", "outside"),
    ("up", "down"),
    ("front", "back"),
    ("left", "right"),

    # Quantity antonyms (DETERMINERS bank)
    ("all", "none"),
    ("many", "few"),
    ("more", "less"),
    ("full", "empty"),

    # Gradable adjectives
    ("beautiful", "ugly"),
    ("smart", "stupid"),
    ("brave", "cowardly"),
    ("kind", "cruel"),
    ("honest", "dishonest"),
    ("polite", "rude"),
    ("patient", "impatient"),
    ("generous", "selfish"),
    ("careful", "careless"),
    ("possible", "impossible"),
]

# Synonym pairs for discrimination test
SYNONYM_PAIRS = [
    ("happy", "joyful"),
    ("big", "large"),
    ("small", "tiny"),
    ("fast", "quick"),
    ("smart", "intelligent"),
    ("beautiful", "pretty"),
    ("begin", "start"),
    ("end", "finish"),
    ("help", "assist"),
    ("answer", "reply"),
    ("choose", "select"),
    ("difficult", "hard"),
    ("easy", "simple"),
    ("important", "significant"),
    ("famous", "renowned"),
    ("old", "ancient"),
    ("new", "novel"),
    ("strange", "weird"),
    ("quiet", "silent"),
    ("loud", "noisy"),
]


def load_custom_antonyms() -> BenchmarkDataset:
    """
    Load custom antonym pairs for testing emergent antonymy.

    This dataset is designed to test GSE's core claim:
    Antonyms should receive NEGATIVE cosine similarity through
    polarity propagation, unlike distributional approaches which
    give positive similarity (antonyms appear in similar contexts).

    Returns:
        BenchmarkDataset with antonym pairs (expected similarity < 0)
    """
    pairs = [
        WordPair(
            word1=w1,
            word2=w2,
            score=-1.0,  # Expected: negative similarity for GSE
            relation="antonym",
        )
        for w1, w2 in PRIMITIVE_ANTONYM_PAIRS
    ]

    return BenchmarkDataset(
        name="GSE-Antonyms",
        pairs=pairs,
        description="Custom antonym set based on GSE primitives and POLARITY_SCOPE",
        citation="GSE Paper (2025)",
    )


def load_custom_synonyms() -> BenchmarkDataset:
    """
    Load custom synonym pairs for discrimination test.

    Synonyms should have POSITIVE similarity in both GSE and
    distributional approaches.

    Returns:
        BenchmarkDataset with synonym pairs (expected similarity > 0)
    """
    pairs = [
        WordPair(
            word1=w1,
            word2=w2,
            score=1.0,  # Expected: positive similarity
            relation="synonym",
        )
        for w1, w2 in SYNONYM_PAIRS
    ]

    return BenchmarkDataset(
        name="GSE-Synonyms",
        pairs=pairs,
        description="Custom synonym set for antonym/synonym discrimination",
        citation="GSE Paper (2025)",
    )


def extract_negation_subset(
    sts_dataset: BenchmarkDataset
) -> BenchmarkDataset:
    """
    Extract sentence pairs containing negation.

    GSE should outperform distributional approaches on negation-heavy
    subsets because polarity propagation explicitly handles negation.

    Args:
        sts_dataset: STS Benchmark dataset

    Returns:
        Filtered dataset with negation-containing pairs
    """
    negation_markers = [
        "not", "n't", "no", "never", "neither", "nobody",
        "nothing", "nowhere", "none", "nor", "cannot", "without",
    ]

    negation_pairs = []
    for pair in sts_dataset.pairs:
        s1_lower = pair.sentence1.lower()
        s2_lower = pair.sentence2.lower()

        has_negation = any(
            marker in s1_lower or marker in s2_lower
            for marker in negation_markers
        )

        if has_negation:
            negation_pairs.append(pair)

    return BenchmarkDataset(
        name=f"{sts_dataset.name}-Negation",
        pairs=negation_pairs,
        description=f"Negation subset of {sts_dataset.name}",
    )


def get_all_datasets(cache_dir: Path = CACHE_DIR) -> Dict[str, BenchmarkDataset]:
    """
    Load all available benchmark datasets.

    Returns:
        Dictionary of dataset name -> BenchmarkDataset
    """
    datasets = {}

    # Word-level
    try:
        datasets['simlex999'] = load_simlex999(cache_dir)
        logger.info(f"Loaded SimLex-999: {len(datasets['simlex999'])} pairs")
    except Exception as e:
        logger.warning(f"Could not load SimLex-999: {e}")

    try:
        datasets['wordsim353'] = load_wordsim353(cache_dir)
        logger.info(f"Loaded WordSim-353: {len(datasets['wordsim353'])} pairs")
    except Exception as e:
        logger.warning(f"Could not load WordSim-353: {e}")

    # Sentence-level
    try:
        datasets['sts_test'] = load_sts_benchmark('test', cache_dir)
        logger.info(f"Loaded STS-Test: {len(datasets['sts_test'])} pairs")

        # Add negation subset
        datasets['sts_negation'] = extract_negation_subset(datasets['sts_test'])
        logger.info(f"Extracted STS-Negation: {len(datasets['sts_negation'])} pairs")
    except Exception as e:
        logger.warning(f"Could not load STS Benchmark: {e}")

    # Custom sets
    datasets['antonyms'] = load_custom_antonyms()
    logger.info(f"Loaded antonyms: {len(datasets['antonyms'])} pairs")

    datasets['synonyms'] = load_custom_synonyms()
    logger.info(f"Loaded synonyms: {len(datasets['synonyms'])} pairs")

    return datasets
