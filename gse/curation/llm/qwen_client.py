"""
Qwen3-8B Model Client

Loads and runs Qwen3-8B for semantic decomposition.

Supports:
- Official Huggingface model: Qwen/Qwen3-8B
- Local model path (e.g., Qwen3-8B-Drama-Thinking)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Model options
HUGGINGFACE_MODEL_ID = "Qwen/Qwen3-8B"
LOCAL_MODEL_PATH = "/Users/rohanvinaik/relational-ai/experimental_data/models/Qwen3-8B-Drama-Thinking"
DEFAULT_MODEL_PATH = LOCAL_MODEL_PATH  # Use local model (faster loading)


@dataclass
class GenerationConfig:
    """Configuration for text generation."""
    max_new_tokens: int = 2000
    temperature: float = 0.3
    top_p: float = 0.9
    do_sample: bool = True
    repetition_penalty: float = 1.1


class QwenClient:
    """
    Client for local Qwen3-8B-Drama-Thinking model.

    Uses the transformers library to load and run the model locally.
    Optimized for Apple Silicon (MPS) or CUDA where available.
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        device: Optional[str] = None,
        load_in_8bit: bool = False,
    ):
        """
        Initialize the Qwen client.

        Args:
            model_path: Path to the model directory
            device: Device to use ('mps', 'cuda', 'cpu', or None for auto)
            load_in_8bit: Whether to load in 8-bit precision (requires bitsandbytes)
        """
        self.model_path = Path(model_path)
        self.device = device or self._detect_device()
        self.load_in_8bit = load_in_8bit

        self.model = None
        self.tokenizer = None
        self._loaded = False

    def _detect_device(self) -> str:
        """Detect the best available device."""
        try:
            import torch
            if torch.backends.mps.is_available():
                return "mps"
            elif torch.cuda.is_available():
                return "cuda"
            else:
                return "cpu"
        except ImportError:
            return "cpu"

    def load(self):
        """Load the model and tokenizer."""
        if self._loaded:
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "transformers>=4.51.0 and torch are required. "
                "Install with: pip install 'transformers>=4.51.0' torch"
            ) from e

        # Check if using HuggingFace model ID or local path
        model_id = str(self.model_path)
        is_hf_model = not Path(model_id).exists() or model_id.startswith("Qwen/")

        logger.info(f"Loading Qwen model: {model_id}")
        logger.info(f"Source: {'HuggingFace' if is_hf_model else 'Local'}")
        logger.info(f"Using device: {self.device}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            trust_remote_code=True,
        )

        # Determine dtype based on device
        if self.device == "mps":
            dtype = torch.float16  # MPS works best with float16
        elif self.device == "cuda":
            dtype = torch.bfloat16
        else:
            dtype = torch.float32

        # Load model - use direct loading for MPS (faster than device_map="auto")
        load_kwargs = {
            "torch_dtype": dtype,
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,  # Load shards one at a time
        }

        if self.load_in_8bit:
            load_kwargs["load_in_8bit"] = True

        logger.info(f"Loading model with dtype={dtype}...")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            **load_kwargs
        )

        # Move to device after loading (faster than device_map for MPS)
        if self.device != "cpu":
            logger.info(f"Moving model to {self.device}...")
            self.model = self.model.to(self.device)

        self._loaded = True
        logger.info("Model loaded successfully")

    def unload(self):
        """Unload the model to free memory."""
        if self.model is not None:
            del self.model
            self.model = None
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        self._loaded = False

        # Clear CUDA cache if available
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

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

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Apply chat template
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        # Tokenize
        inputs = self.tokenizer(text, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        # Generate
        import torch
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=config.max_new_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                do_sample=config.do_sample,
                repetition_penalty=config.repetition_penalty,
                pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
            )

        # Decode
        response = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )

        return response.strip()

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


class MockQwenClient:
    """
    Mock client for testing without loading the actual model.

    Useful for unit tests and development without GPU resources.
    """

    def __init__(self):
        self._loaded = True

    def load(self):
        pass

    def unload(self):
        pass

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> str:
        """Return a mock JSON response."""
        import json

        from gse.curation.schema import ALL_PRIMITIVES

        # Generate a simple mock response
        mock_decomp = {p: 0 for p in ALL_PRIMITIVES}

        # Set some basic values based on common patterns
        if "happy" in prompt.lower():
            mock_decomp["GOOD"] = 1
            mock_decomp["FEEL"] = 1
            mock_decomp["SOMEONE"] = 1
        elif "sad" in prompt.lower():
            mock_decomp["GOOD"] = -1
            mock_decomp["FEEL"] = 1
            mock_decomp["SOMEONE"] = 1
        elif "walk" in prompt.lower():
            mock_decomp["MOVE"] = 1
            mock_decomp["DO"] = 1
            mock_decomp["BODY"] = 1
            mock_decomp["SOMEONE"] = 1

        return json.dumps(mock_decomp)

    def decompose_word(
        self,
        word: str,
        pos: str = "unknown",
        gloss: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> Dict[str, int]:
        from gse.curation.llm.response_parser import parse_llm_response

        response = self.generate(f"Decompose: {word}")
        result = parse_llm_response(response)
        return result.decomposition

    def decompose_batch(
        self,
        words: List[Dict[str, str]],
        config: Optional[GenerationConfig] = None,
    ) -> List[Tuple[Dict[str, int], float, List[str]]]:
        results = []
        for word_data in words:
            decomp = self.decompose_word(word_data["word"], word_data.get("pos", "unknown"))
            results.append((decomp, 0.8, []))
        return results
