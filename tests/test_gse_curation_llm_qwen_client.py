"""Manual contract tests for gse.curation.llm.qwen_client."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.llm.qwen_client import (
    DEFAULT_MODEL_PATH,
    HUGGINGFACE_MODEL_ID,
    LOCAL_MODEL_PATH,
    GenerationConfig,
    MockQwenClient,
    QwenClient,
)

# ---------- Constants ----------


class TestConstants:
    def test_huggingface_id(self):
        assert HUGGINGFACE_MODEL_ID == "Qwen/Qwen3-8B"

    def test_local_path(self):
        assert "Qwen3-8B-Drama-Thinking" in LOCAL_MODEL_PATH

    def test_default_is_local(self):
        assert DEFAULT_MODEL_PATH == LOCAL_MODEL_PATH


# ---------- GenerationConfig ----------


class TestGenerationConfig:
    def test_defaults(self):
        c = GenerationConfig()
        assert c.max_new_tokens == 2000
        assert c.temperature == 0.3
        assert c.top_p == 0.9
        assert c.do_sample is True
        assert c.repetition_penalty == 1.1


# ---------- QwenClient.__init__ ----------


class TestQwenInit:
    def test_default_model_path(self):
        with patch.object(QwenClient, "_detect_device", return_value="cpu"):
            c = QwenClient()
            assert str(c.model_path) == DEFAULT_MODEL_PATH

    def test_custom_path(self):
        with patch.object(QwenClient, "_detect_device", return_value="cpu"):
            c = QwenClient(model_path="/tmp/x")
            assert str(c.model_path) == "/tmp/x"

    def test_custom_device(self):
        c = QwenClient(device="cuda")
        assert c.device == "cuda"

    def test_load_in_8bit_default_false(self):
        with patch.object(QwenClient, "_detect_device", return_value="cpu"):
            assert QwenClient().load_in_8bit is False

    def test_initial_unloaded(self):
        with patch.object(QwenClient, "_detect_device", return_value="cpu"):
            c = QwenClient()
            assert c.model is None
            assert c.tokenizer is None
            assert c._loaded is False


# ---------- _detect_device ----------


class TestDetectDevice:
    def test_mps_when_available(self):
        pytest.importorskip("torch")  # torch is not a project dependency (torch-free runtime)
        with patch("torch.backends.mps.is_available", return_value=True):
            c = QwenClient(device="cpu")  # Set device explicitly to skip detection at init
            assert c._detect_device() == "mps"

    def test_cuda_when_mps_unavailable(self):
        pytest.importorskip("torch")  # torch is not a project dependency (torch-free runtime)
        with patch("torch.backends.mps.is_available", return_value=False):
            with patch("torch.cuda.is_available", return_value=True):
                c = QwenClient(device="cpu")
                assert c._detect_device() == "cuda"

    def test_cpu_fallback(self):
        pytest.importorskip("torch")  # torch is not a project dependency (torch-free runtime)
        with patch("torch.backends.mps.is_available", return_value=False):
            with patch("torch.cuda.is_available", return_value=False):
                c = QwenClient(device="cpu")
                assert c._detect_device() == "cpu"

    def test_no_torch_returns_cpu(self):
        import builtins

        original_import = builtins.__import__

        def faux_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("not installed")
            return original_import(name, *args, **kwargs)

        c = QwenClient(device="cpu")
        with patch("builtins.__import__", side_effect=faux_import):
            assert c._detect_device() == "cpu"


# ---------- unload ----------


class TestUnload:
    def test_clears_model_and_tokenizer(self):
        c = QwenClient(device="cpu")
        c.model = MagicMock()
        c.tokenizer = MagicMock()
        c._loaded = True
        c.unload()
        assert c.model is None
        assert c.tokenizer is None
        assert c._loaded is False

    def test_safe_when_already_none(self):
        c = QwenClient(device="cpu")
        # Should not raise
        c.unload()


# ---------- MockQwenClient ----------


class TestMockQwenClient:
    def test_init_loaded(self):
        c = MockQwenClient()
        assert c._loaded is True

    def test_load_noop(self):
        c = MockQwenClient()
        c.load()  # no-op

    def test_unload_noop(self):
        c = MockQwenClient()
        c.unload()  # no-op

    def test_happy_prompt(self):
        c = MockQwenClient()
        result = c.generate("Tell me about happy")
        data = json.loads(result)
        assert data["GOOD"] == 1
        assert data["FEEL"] == 1

    def test_sad_prompt(self):
        c = MockQwenClient()
        result = c.generate("decompose sad")
        data = json.loads(result)
        assert data["GOOD"] == -1
        assert data["FEEL"] == 1

    def test_walk_prompt(self):
        c = MockQwenClient()
        result = c.generate("walk")
        data = json.loads(result)
        assert data["MOVE"] == 1
        assert data["DO"] == 1
        assert data["BODY"] == 1

    def test_unknown_prompt_all_zeros(self):
        c = MockQwenClient()
        result = c.generate("nonsense xyz")
        data = json.loads(result)
        # No keyword match → all zeros
        assert all(v == 0 for v in data.values())

    def test_case_insensitive(self):
        c = MockQwenClient()
        result = c.generate("HAPPY")
        data = json.loads(result)
        assert data["GOOD"] == 1

    def test_decompose_word(self):
        c = MockQwenClient()
        result = c.decompose_word("happy")
        assert result["GOOD"] == 1

    def test_decompose_batch_returns_tuples(self):
        c = MockQwenClient()
        results = c.decompose_batch([{"word": "happy"}, {"word": "sad"}])
        assert len(results) == 2
        # Each is (decomp, confidence, warnings)
        assert len(results[0]) == 3
        assert results[0][1] == 0.8  # confidence
        assert results[0][2] == []  # warnings

    def test_decompose_batch_default_pos_unknown(self):
        c = MockQwenClient()
        results = c.decompose_batch([{"word": "happy"}])
        # No exception → pos defaulted
        assert len(results) == 1


# ---------- QwenClient.generate (mocked) ----------


class TestQwenGenerate:
    def _make_client(self):
        c = QwenClient(device="cpu")
        c._loaded = True
        c.tokenizer = MagicMock()
        c.tokenizer.apply_chat_template.return_value = "TEMPLATED"
        # tokenizer call returns dict-like with input_ids
        mock_inputs = {"input_ids": MagicMock()}
        mock_inputs["input_ids"].shape = [1, 5]
        c.tokenizer.return_value = mock_inputs
        c.tokenizer.pad_token_id = 0
        c.tokenizer.eos_token_id = 1
        c.tokenizer.decode.return_value = "  hello  "
        c.model = MagicMock()
        c.model.device = "cpu"
        # generate returns a tensor-like; we just need outputs[0][5:] to work
        mock_out = MagicMock()
        mock_out.__getitem__.return_value = MagicMock()
        c.model.generate.return_value = mock_out
        # Override the slice path
        c.tokenizer.decode = MagicMock(return_value="  hello  ")
        return c

    def test_decompose_word_uses_full_prompt(self):
        c = QwenClient(device="cpu")
        c._loaded = True
        c.generate = MagicMock(return_value="{}")
        with patch("gse.curation.llm.response_parser.parse_llm_response") as mock_parse:
            mock_result = MagicMock()
            mock_result.decomposition = {"GOOD": 1}
            mock_parse.return_value = mock_result
            with patch("gse.curation.llm.prompts.build_user_prompt", return_value="P") as mock_build:
                result = c.decompose_word("happy", pos="adj")
                # build_user_prompt called without simple=True
                assert (
                    "simple" not in mock_build.call_args.kwargs
                    or mock_build.call_args.kwargs.get("simple", False) is False
                )
            assert result == {"GOOD": 1}

    def test_decompose_word_default_pos_unknown(self):
        c = QwenClient(device="cpu")
        c._loaded = True
        c.generate = MagicMock(return_value="{}")
        with patch("gse.curation.llm.response_parser.parse_llm_response") as mock_parse:
            mock_result = MagicMock()
            mock_result.decomposition = {}
            mock_parse.return_value = mock_result
            with patch("gse.curation.llm.prompts.build_user_prompt", return_value="P") as mock_build:
                c.decompose_word("x")
                # 2nd positional arg defaults to "unknown"
                assert mock_build.call_args.args[1] == "unknown"

    def test_decompose_batch_iterates(self):
        c = QwenClient(device="cpu")
        c._loaded = True
        c.generate = MagicMock(return_value="{}")
        with patch("gse.curation.llm.response_parser.parse_llm_response") as mock_parse:
            mock_result = MagicMock()
            mock_result.decomposition = {"GOOD": 1}
            mock_result.confidence = 0.9
            mock_result.warnings = []
            mock_parse.return_value = mock_result
            with patch("gse.curation.llm.prompts.build_user_prompt", return_value="P"):
                results = c.decompose_batch(
                    [
                        {"word": "happy"},
                        {"word": "sad"},
                    ]
                )
        assert len(results) == 2
        assert results[0][1] == 0.9

    def test_decompose_batch_uses_simple_prompt(self):
        c = QwenClient(device="cpu")
        c._loaded = True
        c.generate = MagicMock(return_value="{}")
        with patch("gse.curation.llm.response_parser.parse_llm_response") as mock_parse:
            mock_result = MagicMock()
            mock_result.decomposition = {}
            mock_result.confidence = 0.0
            mock_result.warnings = []
            mock_parse.return_value = mock_result
            with patch("gse.curation.llm.prompts.build_user_prompt", return_value="P") as mock_build:
                c.decompose_batch([{"word": "x"}])
                # simple=True kwarg passed
                assert mock_build.call_args.kwargs.get("simple") is True

    def test_decompose_batch_exception_fallback(self):
        from gse.curation.schema import ALL_PRIMITIVES

        c = QwenClient(device="cpu")
        c._loaded = True
        c.generate = MagicMock(side_effect=RuntimeError("fail"))
        with patch("gse.curation.llm.prompts.build_user_prompt", return_value="P"):
            results = c.decompose_batch([{"word": "happy"}])
        decomp, conf, warnings = results[0]
        assert decomp == {p: 0 for p in ALL_PRIMITIVES}
        assert conf == 0.0
        assert "fail" in warnings[0]

    def test_strips_response(self):
        pytest.importorskip("torch")  # torch is not a project dependency (torch-free runtime)
        c = self._make_client()
        # Mock everything to return predictable strings
        with patch("torch.no_grad"):
            mock_v = MagicMock()
            mock_v.to.return_value = mock_v
            c.tokenizer.return_value = {"input_ids": mock_v}
            c.tokenizer.return_value["input_ids"].shape = [1, 5]
            mock_out = [MagicMock()]
            c.model.generate.return_value = mock_out
            with patch.dict(c.tokenizer.return_value, {}):
                # The result.strip() is the value we care about
                # Just test that it strips
                result = c.generate("hi")
                assert result == "hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
