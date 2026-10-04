"""Manual contract tests for gse.curation.llm.ollama_client."""

from __future__ import annotations

import logging
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import requests

import gse.curation.llm.ollama_client as ollama_client
from gse.curation.llm.ollama_client import (
    DEFAULT_MODEL,
    OLLAMA_URL,
    UNLOAD_TIMEOUT_SECONDS,
    GenerationConfig,
    OllamaClient,
    register_model,
    unload_model,
)

REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def _empty_model_registry():
    """Keep the module's model registry empty around every test.

    Successful generate() calls register (url, model) pairs, and the module's atexit hook would
    unload each one over real HTTP when pytest exits, so no test may leave a pair behind.
    """
    ollama_client._registered_models.clear()
    yield
    ollama_client._registered_models.clear()


def ok_response(payload=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload if payload is not None else {}
    return resp


# ---------- Constants ----------


class TestConstants:
    def test_default_model(self):
        assert DEFAULT_MODEL == "qwen3:8b"

    def test_ollama_url(self):
        assert OLLAMA_URL == "http://localhost:11434"


# ---------- GenerationConfig ----------


class TestGenerationConfig:
    def test_defaults(self):
        c = GenerationConfig()
        assert c.max_tokens == 2000
        assert c.temperature == 0.3
        assert c.top_p == 0.9

    def test_custom(self):
        c = GenerationConfig(max_tokens=500, temperature=0.7, top_p=0.5)
        assert c.max_tokens == 500
        assert c.temperature == 0.7
        assert c.top_p == 0.5


# ---------- __init__ ----------


class TestInit:
    def test_defaults(self):
        c = OllamaClient()
        assert c.model == "qwen3:8b"
        assert c.base_url == "http://localhost:11434"
        assert c._loaded is False

    def test_custom_model(self):
        c = OllamaClient(model="llama2")
        assert c.model == "llama2"

    def test_custom_url(self):
        c = OllamaClient(base_url="http://other:1234")
        assert c.base_url == "http://other:1234"


# ---------- load ----------


class TestLoad:
    def test_model_found(self):
        c = OllamaClient(model="qwen3:8b")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "qwen3:8b"}]}
        with patch("requests.get", return_value=mock_resp):
            c.load()
        assert c._loaded is True

    def test_model_not_found_triggers_pull(self):
        c = OllamaClient(model="missing")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "other"}]}
        with patch("requests.get", return_value=mock_resp):
            with patch.object(c, "_pull_model") as mock_pull:
                c.load()
                mock_pull.assert_called_once()
        assert c._loaded is True

    def test_non_200_raises(self):
        c = OllamaClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(ConnectionError):
                c.load()

    def test_connection_error_raises_with_message(self):
        c = OllamaClient()
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError):
            with pytest.raises(ConnectionError, match="ollama serve"):
                c.load()


# ---------- _pull_model ----------


class TestPullModel:
    def test_success(self):
        c = OllamaClient()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            c._pull_model()
            mock_run.assert_called_once()

    def test_failure_raises(self):
        c = OllamaClient()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error message"
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="error message"):
                c._pull_model()

    def test_exact_command_args(self):
        # Pin the exact subprocess command list
        c = OllamaClient(model="myModel")
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            c._pull_model()
            mock_run.assert_called_once_with(
                ["ollama", "pull", "myModel"],
                capture_output=True,
                text=True,
            )

    def test_error_message_format(self):
        # Pin the exact RuntimeError message prefix
        c = OllamaClient()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "boom"
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="Failed to pull model: boom"):
                c._pull_model()

    def test_zero_returncode_no_raise(self):
        # Pin the != 0 comparison
        c = OllamaClient()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            # Should not raise
            c._pull_model()


# ---------- unload ----------


class TestUnload:
    def test_posts_keep_alive_zero(self):
        c = OllamaClient(model="myModel", base_url="http://other:1234")
        with patch("requests.post", return_value=ok_response()) as mock_post:
            outcome = c.unload()
        mock_post.assert_called_once_with(
            "http://other:1234/api/generate",
            json={"model": "myModel", "keep_alive": 0},
            timeout=UNLOAD_TIMEOUT_SECONDS,
        )
        assert outcome == "unloaded"

    def test_sets_loaded_false(self):
        c = OllamaClient()
        c._loaded = True
        with patch("requests.post", return_value=ok_response()):
            c.unload()
        assert c._loaded is False

    def test_server_down_logs_and_continues(self, caplog):
        c = OllamaClient()
        c._loaded = True
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
            with caplog.at_level(logging.WARNING, logger=ollama_client.__name__):
                outcome = c.unload()
        assert outcome == "server_unreachable"
        assert c._loaded is False
        assert "server unreachable" in caplog.text

    def test_non_200_is_rejected(self):
        resp = MagicMock()
        resp.status_code = 404
        resp.text = "model 'missing' not found"
        with patch("requests.post", return_value=resp):
            assert OllamaClient(model="missing").unload() == "rejected"


# ---------- generate ----------


class TestGenerate:
    def test_basic(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": " hello "}
        with patch("requests.post", return_value=mock_resp):
            assert c.generate("hi") == "hello"

    def test_strips_response(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "  text  "}
        with patch("requests.post", return_value=mock_resp):
            assert c.generate("x") == "text"

    def test_auto_loads(self):
        c = OllamaClient()
        with patch.object(c, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(c, "_loaded", True)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"response": ""}
            with patch("requests.post", return_value=mock_resp):
                c.generate("x")
            mock_load.assert_called_once()

    def test_system_prompt_added(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            c.generate("hi", system_prompt="sys")
            payload = mock_post.call_args.kwargs["json"]
            assert payload["system"] == "sys"

    def test_no_system_prompt_not_in_payload(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            c.generate("hi")
            payload = mock_post.call_args.kwargs["json"]
            assert "system" not in payload

    def test_config_propagates(self):
        c = OllamaClient()
        c._loaded = True
        cfg = GenerationConfig(temperature=0.5, top_p=0.7, max_tokens=100)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            c.generate("hi", config=cfg)
            opts = mock_post.call_args.kwargs["json"]["options"]
            assert opts["temperature"] == 0.5
            assert opts["top_p"] == 0.7
            assert opts["num_predict"] == 100

    def test_default_config_used(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            c.generate("hi")
            opts = mock_post.call_args.kwargs["json"]["options"]
            assert opts["temperature"] == 0.3  # default

    def test_non_200_raises(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="server error"):
                c.generate("hi")

    def test_model_in_payload(self):
        c = OllamaClient(model="myModel")
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            c.generate("hi")
            assert mock_post.call_args.kwargs["json"]["model"] == "myModel"

    def test_stream_false(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            c.generate("hi")
            assert mock_post.call_args.kwargs["json"]["stream"] is False

    def test_missing_response_returns_empty(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}  # no "response" key
        with patch("requests.post", return_value=mock_resp):
            assert c.generate("hi") == ""


# ---------- decompose_word ----------


class TestDecomposeWord:
    def test_basic(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "..."}
        mock_result = MagicMock()
        mock_result.decomposition = {"GOOD": 1}
        with patch("requests.post", return_value=mock_resp):
            with patch("gse.curation.llm.response_parser.parse_llm_response", return_value=mock_result):
                with patch("gse.curation.llm.prompts.build_user_prompt", return_value="prompt"):
                    result = c.decompose_word("happy", "adj")
        assert result == {"GOOD": 1}

    def test_default_pos_unknown(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        mock_result = MagicMock()
        mock_result.decomposition = {}
        with patch("requests.post", return_value=mock_resp):
            with patch("gse.curation.llm.response_parser.parse_llm_response", return_value=mock_result):
                with patch("gse.curation.llm.prompts.build_user_prompt", return_value="x") as mock_build:
                    c.decompose_word("happy")
                    # POS defaults to "unknown"
                    call_args = mock_build.call_args
                    assert call_args.args[1] == "unknown"


# ---------- decompose_batch ----------


class TestDecomposeBatch:
    def test_empty(self):
        c = OllamaClient()
        c._loaded = True
        assert c.decompose_batch([]) == []

    def test_processes_each_word(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        mock_result = MagicMock()
        mock_result.decomposition = {"GOOD": 1}
        mock_result.confidence = 0.9
        mock_result.warnings = []
        with patch("requests.post", return_value=mock_resp):
            with patch("gse.curation.llm.response_parser.parse_llm_response", return_value=mock_result):
                with patch("gse.curation.llm.prompts.build_user_prompt", return_value="x"):
                    results = c.decompose_batch(
                        [
                            {"word": "happy", "pos": "adj"},
                            {"word": "sad", "pos": "adj"},
                        ]
                    )
        assert len(results) == 2
        assert results[0] == ({"GOOD": 1}, 0.9, [])

    def test_exception_yields_empty_decomp(self):
        from gse.curation.schema import ALL_PRIMITIVES

        c = OllamaClient()
        c._loaded = True
        with patch.object(c, "generate", side_effect=RuntimeError("network")):
            with patch("gse.curation.llm.prompts.build_user_prompt", return_value="x"):
                results = c.decompose_batch([{"word": "happy"}])
        decomp, conf, warnings = results[0]
        assert decomp == {p: 0 for p in ALL_PRIMITIVES}
        assert conf == 0.0
        assert "network" in warnings[0]

    def test_uses_simple_prompt(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        mock_result = MagicMock()
        mock_result.decomposition = {}
        mock_result.confidence = 0.0
        mock_result.warnings = []
        with patch("requests.post", return_value=mock_resp):
            with patch("gse.curation.llm.response_parser.parse_llm_response", return_value=mock_result):
                with patch("gse.curation.llm.prompts.build_user_prompt", return_value="x") as mock_build:
                    c.decompose_batch([{"word": "happy"}])
                    # simple=True kwarg
                    assert mock_build.call_args.kwargs.get("simple") is True

    def test_missing_pos_defaults_unknown(self):
        c = OllamaClient()
        c._loaded = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": ""}
        mock_result = MagicMock()
        mock_result.decomposition = {}
        mock_result.confidence = 0.0
        mock_result.warnings = []
        with patch("requests.post", return_value=mock_resp):
            with patch("gse.curation.llm.response_parser.parse_llm_response", return_value=mock_result):
                with patch("gse.curation.llm.prompts.build_user_prompt", return_value="x") as mock_build:
                    c.decompose_batch([{"word": "happy"}])
                    assert mock_build.call_args.args[1] == "unknown"


# ---------- model registry ----------


class TestModelRegistry:
    def test_successful_generate_registers_pair_once(self):
        c = OllamaClient(model="myModel", base_url="http://other:1234")
        c._loaded = True
        with patch("requests.post", return_value=ok_response({"response": "ok"})):
            c.generate("hi")
            c.generate("again")
        assert ollama_client._registered_models == {("http://other:1234", "myModel")}

    def test_failed_generate_registers_nothing(self):
        c = OllamaClient()
        c._loaded = True
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "server error"
        with patch("requests.post", return_value=resp):
            with pytest.raises(RuntimeError):
                c.generate("hi")
        assert ollama_client._registered_models == set()

    def test_register_model_defaults_to_local_server(self):
        register_model("m")
        assert ollama_client._registered_models == {(OLLAMA_URL, "m")}

    def test_successful_unload_deregisters(self):
        register_model("m")
        with patch("requests.post", return_value=ok_response()):
            assert unload_model("m") == "unloaded"
        assert ollama_client._registered_models == set()

    def test_failed_unload_stays_registered(self):
        register_model("m")
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError):
            assert unload_model("m") == "server_unreachable"
        assert ollama_client._registered_models == {(OLLAMA_URL, "m")}


# ---------- exit hook ----------


class TestExitHook:
    def test_unloads_every_registered_pair(self):
        register_model("a")
        register_model("b", url="http://other:1234")
        with patch("requests.post", return_value=ok_response()) as mock_post:
            ollama_client._unload_registered_models()
        sent = {
            (c.args[0], c.kwargs["json"]["model"], c.kwargs["json"]["keep_alive"]) for c in mock_post.call_args_list
        }
        assert sent == {
            (f"{OLLAMA_URL}/api/generate", "a", 0),
            ("http://other:1234/api/generate", "b", 0),
        }
        assert ollama_client._registered_models == set()

    def test_unreachable_server_does_not_stop_the_rest(self):
        register_model("a", url="http://down:1")
        register_model("b")

        def post(url, json, timeout):
            if url.startswith("http://down:1"):
                raise requests.exceptions.ConnectionError("refused")
            return ok_response()

        with patch("requests.post", side_effect=post):
            outcomes = ollama_client._unload_registered_models()
        assert outcomes == {
            ("http://down:1", "a"): "server_unreachable",
            (OLLAMA_URL, "b"): "unloaded",
        }

    def test_hook_registered_at_import_unloads_at_interpreter_exit(self):
        # Fresh interpreter, HTTP layer mocked (no server): one model used through generate(),
        # one registered the way the scripts do; both must be unloaded when the process exits.
        code = textwrap.dedent(
            """
            from unittest import mock

            def fake_post(url, json=None, timeout=None):
                if "keep_alive" in json:
                    print("UNLOAD", url, json["model"], json["keep_alive"], flush=True)
                return mock.Mock(status_code=200, json=lambda: {"response": "ok"})

            mock.patch("requests.post", side_effect=fake_post).start()

            from gse.curation.llm.ollama_client import OllamaClient, register_model

            client = OllamaClient(model="via-generate")
            client._loaded = True
            client.generate("hi")
            register_model("via-script", url="http://other:1234")
            """
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        assert sorted(result.stdout.splitlines()) == sorted(
            [
                f"UNLOAD {OLLAMA_URL}/api/generate via-generate 0",
                "UNLOAD http://other:1234/api/generate via-script 0",
            ]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
