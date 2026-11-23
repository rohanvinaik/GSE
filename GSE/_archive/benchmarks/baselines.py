"""
Baseline Models for Benchmark Comparison

Wraps popular embedding models for comparison with GSE:
- Word2Vec (Google News 300d)
- GloVe (840B 300d)
- FastText (crawl 300d)
- BERT (bert-base-uncased)
- SimCSE (supervised)
- Sentence-BERT (all-MiniLM)

Key observation: These distributional models typically give POSITIVE
similarity for antonyms because antonyms appear in similar contexts.
GSE should be the only model with substantial negative antonym similarity.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, List
import numpy as np
import logging

logger = logging.getLogger(__name__)


class BaselineModel(ABC):
    """Abstract base class for baseline models."""

    name: str
    parameters: int

    @abstractmethod
    def similarity(self, word1: str, word2: str) -> float:
        """Compute similarity between two words."""
        pass

    @abstractmethod
    def encode(self, word: str) -> Optional[np.ndarray]:
        """Get embedding for a word."""
        pass

    def batch_similarity(
        self,
        pairs: List[Tuple[str, str]]
    ) -> List[float]:
        """Compute similarity for multiple pairs."""
        return [self.similarity(w1, w2) for w1, w2 in pairs]

    def coverage(self, words: List[str]) -> float:
        """Fraction of words that can be encoded."""
        covered = sum(1 for w in words if self.encode(w) is not None)
        return covered / len(words) if words else 0.0


class Word2VecBaseline(BaselineModel):
    """Word2Vec baseline using gensim."""

    name = "Word2Vec"
    parameters = 90_000_000  # ~300M vectors × 300d = ~90M params

    def __init__(self, model_name: str = "word2vec-google-news-300"):
        """
        Initialize Word2Vec model.

        Args:
            model_name: Gensim model identifier
        """
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                import gensim.downloader as api
                logger.info(f"Loading Word2Vec model: {self.model_name}")
                self._model = api.load(self.model_name)
                logger.info(f"Loaded {len(self._model)} word vectors")
            except Exception as e:
                logger.error(f"Failed to load Word2Vec: {e}")
                self._model = {}

    def encode(self, word: str) -> Optional[np.ndarray]:
        """Get Word2Vec embedding."""
        self._load_model()
        try:
            return self._model[word.lower()]
        except KeyError:
            return None

    def similarity(self, word1: str, word2: str) -> float:
        """Compute Word2Vec cosine similarity."""
        self._load_model()
        try:
            return float(self._model.similarity(word1.lower(), word2.lower()))
        except KeyError:
            return np.nan


class GloVeBaseline(BaselineModel):
    """GloVe baseline using gensim."""

    name = "GloVe"
    parameters = 90_000_000

    def __init__(self, model_name: str = "glove-wiki-gigaword-300"):
        """
        Initialize GloVe model.

        Args:
            model_name: Gensim model identifier
        """
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                import gensim.downloader as api
                logger.info(f"Loading GloVe model: {self.model_name}")
                self._model = api.load(self.model_name)
                logger.info(f"Loaded {len(self._model)} word vectors")
            except Exception as e:
                logger.error(f"Failed to load GloVe: {e}")
                self._model = {}

    def encode(self, word: str) -> Optional[np.ndarray]:
        """Get GloVe embedding."""
        self._load_model()
        try:
            return self._model[word.lower()]
        except KeyError:
            return None

    def similarity(self, word1: str, word2: str) -> float:
        """Compute GloVe cosine similarity."""
        self._load_model()
        try:
            return float(self._model.similarity(word1.lower(), word2.lower()))
        except KeyError:
            return np.nan


class FastTextBaseline(BaselineModel):
    """FastText baseline using gensim."""

    name = "FastText"
    parameters = 90_000_000

    def __init__(self, model_name: str = "fasttext-wiki-news-subwords-300"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                import gensim.downloader as api
                logger.info(f"Loading FastText model: {self.model_name}")
                self._model = api.load(self.model_name)
            except Exception as e:
                logger.error(f"Failed to load FastText: {e}")
                self._model = {}

    def encode(self, word: str) -> Optional[np.ndarray]:
        self._load_model()
        try:
            return self._model[word.lower()]
        except KeyError:
            return None

    def similarity(self, word1: str, word2: str) -> float:
        self._load_model()
        try:
            return float(self._model.similarity(word1.lower(), word2.lower()))
        except KeyError:
            return np.nan


class BERTBaseline(BaselineModel):
    """BERT baseline using transformers."""

    name = "BERT"
    parameters = 110_000_000

    def __init__(self, model_name: str = "bert-base-uncased"):
        """
        Initialize BERT model.

        Args:
            model_name: HuggingFace model identifier
        """
        self.model_name = model_name
        self._tokenizer = None
        self._model = None

    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from transformers import AutoTokenizer, AutoModel
                import torch

                logger.info(f"Loading BERT model: {self.model_name}")
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self._model = AutoModel.from_pretrained(self.model_name)
                self._model.eval()

                # Use GPU if available
                if torch.cuda.is_available():
                    self._model = self._model.cuda()

            except Exception as e:
                logger.error(f"Failed to load BERT: {e}")
                self._tokenizer = None
                self._model = None

    def encode(self, word: str) -> Optional[np.ndarray]:
        """Get BERT CLS embedding for a word."""
        self._load_model()
        if self._model is None:
            return None

        try:
            import torch

            inputs = self._tokenizer(
                word,
                return_tensors="pt",
                padding=True,
                truncation=True,
            )

            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)
                # Use CLS token embedding
                cls_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()

            return cls_embedding.squeeze()

        except Exception as e:
            logger.warning(f"BERT encoding failed for '{word}': {e}")
            return None

    def similarity(self, word1: str, word2: str) -> float:
        """Compute BERT cosine similarity between word embeddings."""
        v1 = self.encode(word1)
        v2 = self.encode(word2)

        if v1 is None or v2 is None:
            return np.nan

        # Cosine similarity
        cos_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return float(cos_sim)


class SimCSEBaseline(BaselineModel):
    """SimCSE baseline for sentence similarity."""

    name = "SimCSE"
    parameters = 110_000_000

    def __init__(self, model_name: str = "princeton-nlp/sup-simcse-bert-base-uncased"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading SimCSE model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.error(f"Failed to load SimCSE: {e}")
                self._model = None

    def encode(self, text: str) -> Optional[np.ndarray]:
        self._load_model()
        if self._model is None:
            return None

        try:
            return self._model.encode(text, convert_to_numpy=True)
        except Exception as e:
            logger.warning(f"SimCSE encoding failed: {e}")
            return None

    def similarity(self, text1: str, text2: str) -> float:
        v1 = self.encode(text1)
        v2 = self.encode(text2)

        if v1 is None or v2 is None:
            return np.nan

        cos_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return float(cos_sim)


class SentenceBERTBaseline(BaselineModel):
    """Sentence-BERT baseline using sentence-transformers."""

    name = "Sentence-BERT"
    parameters = 22_000_000  # all-MiniLM-L6

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading Sentence-BERT model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.error(f"Failed to load Sentence-BERT: {e}")
                self._model = None

    def encode(self, text: str) -> Optional[np.ndarray]:
        self._load_model()
        if self._model is None:
            return None

        try:
            return self._model.encode(text, convert_to_numpy=True)
        except Exception as e:
            logger.warning(f"Sentence-BERT encoding failed: {e}")
            return None

    def similarity(self, text1: str, text2: str) -> float:
        v1 = self.encode(text1)
        v2 = self.encode(text2)

        if v1 is None or v2 is None:
            return np.nan

        cos_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return float(cos_sim)


class GSEBaseline(BaselineModel):
    """
    GSE as a baseline for comparison.

    This wraps the GSE pipeline to have the same interface as other baselines.
    """

    name = "GSE"
    parameters = 2_272  # As claimed in the paper

    def __init__(self, gse_pipeline=None):
        """
        Initialize GSE baseline.

        Args:
            gse_pipeline: Optional GSE pipeline instance. If None, creates new one.
        """
        self._pipeline = gse_pipeline

    def _load_pipeline(self):
        if self._pipeline is None:
            try:
                from gse.pipeline import GSEPipeline
                logger.info("Loading GSE pipeline")
                self._pipeline = GSEPipeline()
            except Exception as e:
                logger.error(f"Failed to load GSE: {e}")

    def encode(self, text: str) -> Optional[np.ndarray]:
        """Get GSE sparse vector as dense array."""
        self._load_pipeline()
        if self._pipeline is None:
            return None

        try:
            result = self._pipeline.process(text)
            # Convert sparse vector to dense
            return result.vector.to_dense() if hasattr(result.vector, 'to_dense') else np.array(result.vector)
        except Exception as e:
            logger.warning(f"GSE encoding failed for '{text}': {e}")
            return None

    def similarity(self, text1: str, text2: str) -> float:
        """Compute GSE cosine similarity."""
        self._load_pipeline()
        if self._pipeline is None:
            return np.nan

        try:
            return self._pipeline.similarity(text1, text2)
        except Exception as e:
            logger.warning(f"GSE similarity failed: {e}")
            return np.nan


def get_all_baselines() -> dict:
    """
    Get dictionary of all available baseline models.

    Returns:
        Dict of model_name -> BaselineModel
    """
    baselines = {}

    # Word-level embeddings
    try:
        baselines['word2vec'] = Word2VecBaseline()
    except Exception as e:
        logger.warning(f"Word2Vec not available: {e}")

    try:
        baselines['glove'] = GloVeBaseline()
    except Exception as e:
        logger.warning(f"GloVe not available: {e}")

    try:
        baselines['fasttext'] = FastTextBaseline()
    except Exception as e:
        logger.warning(f"FastText not available: {e}")

    # Contextual embeddings
    try:
        baselines['bert'] = BERTBaseline()
    except Exception as e:
        logger.warning(f"BERT not available: {e}")

    try:
        baselines['simcse'] = SimCSEBaseline()
    except Exception as e:
        logger.warning(f"SimCSE not available: {e}")

    try:
        baselines['sbert'] = SentenceBERTBaseline()
    except Exception as e:
        logger.warning(f"Sentence-BERT not available: {e}")

    # GSE
    try:
        baselines['gse'] = GSEBaseline()
    except Exception as e:
        logger.warning(f"GSE not available: {e}")

    return baselines


def get_baseline(name: str) -> Optional[BaselineModel]:
    """
    Get a specific baseline by name.

    Args:
        name: Baseline name (word2vec, glove, bert, simcse, sbert, gse)

    Returns:
        BaselineModel instance or None
    """
    name = name.lower()

    if name == 'word2vec':
        return Word2VecBaseline()
    elif name == 'glove':
        return GloVeBaseline()
    elif name == 'fasttext':
        return FastTextBaseline()
    elif name == 'bert':
        return BERTBaseline()
    elif name == 'simcse':
        return SimCSEBaseline()
    elif name in ('sbert', 'sentence-bert'):
        return SentenceBERTBaseline()
    elif name == 'gse':
        return GSEBaseline()
    else:
        logger.warning(f"Unknown baseline: {name}")
        return None
