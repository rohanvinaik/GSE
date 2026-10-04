"""
Ollama Client for Qwen3-8B

Uses Ollama for fast local inference on Mac.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434"


@dataclass
class GenerationConfig:
    """Configuration for text generation."""

    max_tokens: int = 2000
    temperature: float = 0.3
    top_p: float = 0.9


class OllamaClient:
    """
    Client for Ollama-hosted models.

    Much faster than transformers on Mac due to Metal optimization.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = OLLAMA_URL,
    ):
        """
        Initialize the Ollama client.

        Args:
            model: Ollama model name (e.g., "qwen3:8b")
            base_url: Ollama server URL
        """
        self.model = model
        self.base_url = base_url
        self._loaded = False

    def load(self):
        """Check if Ollama is running and model is available."""
        try:
            # Check if Ollama is running
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                raise ConnectionError("Ollama server not responding")

            # Check if model is available
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]

            if not any(self.model in name for name in model_names):
                logger.warning(f"Model {self.model} not found. Available: {model_names}")
                logger.info(f"Pulling model {self.model}...")
                self._pull_model()

            self._loaded = True
            logger.info(f"Ollama client ready with model: {self.model}")

        except requests.exceptions.ConnectionError:
            raise ConnectionError("Ollama is not running. Start it with: ollama serve")

    def _pull_model(self):
        """Pull the model if not available."""
        import subprocess

        result = subprocess.run(["ollama", "pull", self.model], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to pull model: {result.stderr}")

    def unload(self):
        """No-op for Ollama (server manages models)."""
        self._loaded = False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> str:
        """
        Generate a response for a prompt.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            config: Generation configuration

        Returns:
            The generated response text
        """
        if not self._loaded:
            self.load()

        config = config or GenerationConfig()

        # Build request
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "top_p": config.top_p,
                "num_predict": config.max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        # Make request
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=None,  # No timeout
        )

        if response.status_code != 200:
            raise RuntimeError(f"Ollama error: {response.text}")

        result = response.json()
        return result.get("response", "").strip()

    def decompose_word(
        self,
        word: str,
        pos: str = "unknown",
        gloss: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> Dict[str, int]:
        """
        Decompose a single word into primitives.

        Args:
            word: The word to decompose
            pos: Part of speech
            gloss: Optional definition
            config: Generation configuration

        Returns:
            Dict mapping primitive names to values (-1, 0, +1)
        """
        from gse.curation.llm.prompts import SYSTEM_PROMPT, build_user_prompt
        from gse.curation.llm.response_parser import parse_llm_response

        prompt = build_user_prompt(word, pos, gloss)
        response = self.generate(prompt, system_prompt=SYSTEM_PROMPT, config=config)

        result = parse_llm_response(response)
        return result.decomposition

    def decompose_batch(
        self,
        words: List[Dict[str, str]],
        config: Optional[GenerationConfig] = None,
    ) -> List[Tuple[Dict[str, int], float, List[str]]]:
        """
        Decompose a batch of words.

        Args:
            words: List of dicts with 'word', 'pos', and optionally 'gloss'
            config: Generation configuration

        Returns:
            List of (decomposition, confidence, warnings) tuples
        """
        from gse.curation.llm.prompts import SYSTEM_PROMPT, build_user_prompt
        from gse.curation.llm.response_parser import parse_llm_response

        results = []

        for word_data in words:
            word = word_data["word"]
            pos = word_data.get("pos", "unknown")
            gloss = word_data.get("gloss")

            try:
                prompt = build_user_prompt(word, pos, gloss, simple=True)
                response = self.generate(prompt, system_prompt=SYSTEM_PROMPT, config=config)

                result = parse_llm_response(response)
                results.append((result.decomposition, result.confidence, result.warnings))

            except Exception as e:
                logger.error(f"Failed to decompose '{word}': {e}")
                from gse.curation.schema import ALL_PRIMITIVES

                empty_decomp = {p: 0 for p in ALL_PRIMITIVES}
                results.append((empty_decomp, 0.0, [str(e)]))

        return results


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    client = OllamaClient()
    client.load()

    print("Testing decomposition for 'happy'...")
    import time

    start = time.time()
    result = client.decompose_word("happy", "adj")
    elapsed = time.time() - start

    active = {k: v for k, v in result.items() if v != 0}
    print(f"Active primitives: {active}")
    print(f"Time: {elapsed:.1f}s")
