"""Manual contract tests for gse.cli.main."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.cli.main import (
    cmd_compare,
    cmd_decode,
    cmd_encode,
    cmd_interactive,
    cmd_verify,
    main,
)


def make_trace(**overrides):
    """Build a mock OperationTrace-like object."""
    defaults = {
        "input_text": "hello",
        "tokens": [object()],
        "operators": [],
        "final_nnz": 5,
        "sparsity": 0.999,
        "vector_hash": "sha256:abc",
        "word_primitive_activations": {"GOOD": 0.5, "BIG": 0.3},
        "sent_primitive_activations": {"SYN_SUBJ": 0.7},
        "vector": object(),
        "to_json": lambda indent=None: json.dumps({"trace": "data"}, indent=indent),
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def make_similarity():
    obj = MagicMock()
    obj.cosine = 0.85
    obj.alignment = 0.6
    obj.opposition = 0.1
    obj.orthogonality = 0.3
    obj.shared_primitives = ["GOOD"]
    obj.different_primitives = ["BIG"]
    obj.to_json = lambda indent=None: json.dumps({"sim": 0.85}, indent=indent)
    return obj


def make_semantics():
    obj = MagicMock()
    entity = MagicMock()
    entity.lemma = "dog"
    entity.pos = "n"
    entity.confidence = 0.9
    entity.primitives = ["ALIVE"]
    obj.entities = [entity]

    attr = MagicMock()
    attr.attribute = "size"
    attr.polarity = 1
    attr.intensity = 0.5
    attr.source_primitive = "BIG"
    obj.attributes = [attr]

    rel = MagicMock()
    rel.relation = "COMP_THAN"
    rel.confidence = 0.7
    rel.operation = "SET_DIFF"
    obj.relations = [rel]

    obj.nearest_lexemes = [("dog", 0.9), ("cat", 0.5)]
    obj.bank_activations = {"Evaluators": 0.5, "Actions": 0.3}
    obj.to_json = lambda indent=None: json.dumps({"sem": "x"}, indent=indent)
    return obj


# ---------- cmd_encode ----------

class TestCmdEncode:
    def _args(self, **kw):
        defaults = dict(text="hello", format="summary", output=None)
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_summary_format_prints_human_lines(self, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst):
            cmd_encode(self._args(format="summary"))
        out = capsys.readouterr().out
        assert "Tokens:" in out
        assert "Vector NNZ:" in out
        assert "Hash:" in out
        encoder_inst.close.assert_called_once()

    def test_json_format_prints_json(self, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst):
            cmd_encode(self._args(format="json"))
        out = capsys.readouterr().out
        # to_json(indent=2) output should be present
        assert "trace" in out

    def test_unknown_format_falls_back_to_json(self, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst):
            cmd_encode(self._args(format="weird"))
        out = capsys.readouterr().out
        # Falls through to else branch (no-indent to_json)
        assert "trace" in out

    def test_output_writes_file(self, tmp_path, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        out_path = tmp_path / "trace.json"
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst):
            cmd_encode(self._args(format="summary", output=str(out_path)))
        assert out_path.exists()
        assert "trace" in out_path.read_text()

    def test_close_called_even_on_exception(self):
        encoder_inst = MagicMock()
        encoder_inst.encode.side_effect = RuntimeError("boom")
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst):
            with pytest.raises(RuntimeError):
                cmd_encode(self._args())
        encoder_inst.close.assert_called_once()


# ---------- cmd_compare ----------

class TestCmdCompare:
    def _args(self, **kw):
        defaults = dict(sentence1="A", sentence2="B", format="text")
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_text_format_prints_sections(self, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        decoder_inst = MagicMock()
        decoder_inst.similarity.return_value = make_similarity()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst):
            cmd_compare(self._args())
        out = capsys.readouterr().out
        assert "Sentence 1: A" in out
        assert "Sentence 2: B" in out
        assert "Cosine similarity" in out

    def test_json_format_prints_json(self, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        decoder_inst = MagicMock()
        decoder_inst.similarity.return_value = make_similarity()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst):
            cmd_compare(self._args(format="json"))
        out = capsys.readouterr().out
        assert "sim" in out

    def test_closes_both(self):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        decoder_inst = MagicMock()
        decoder_inst.similarity.return_value = make_similarity()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst):
            cmd_compare(self._args())
        encoder_inst.close.assert_called_once()
        decoder_inst.close.assert_called_once()


# ---------- cmd_decode ----------

class TestCmdDecode:
    def _args(self, **kw):
        defaults = dict(trace=None, text="hello", format="text")
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_text_mode_encodes_and_decodes(self, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        decoder_inst = MagicMock()
        decoder_inst.decode.return_value = make_semantics()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst):
            cmd_decode(self._args(text="hello", trace=None))
        out = capsys.readouterr().out
        assert "DECODED SEMANTICS" in out
        assert "Entities:" in out

    def test_trace_mode_loads_file(self, tmp_path):
        trace_file = tmp_path / "t.json"
        trace_file.write_text(json.dumps({
            "input_text": "hi", "tokens": [], "operators": [],
            "final_nnz": 0, "sparsity": 1.0,
            "word_primitive_activations": {}, "sent_primitive_activations": {},
            "vector_hash": "sha256:0",
        }))

        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        decoder_inst = MagicMock()
        decoder_inst.decode.return_value = make_semantics()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst):
            cmd_decode(self._args(text=None, trace=str(trace_file)))
        # encoder.encode was called with the trace.input_text
        encoder_inst.encode.assert_called()

    def test_no_input_exits(self, capsys):
        encoder_inst = MagicMock()
        decoder_inst = MagicMock()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst):
            with pytest.raises(SystemExit) as exc_info:
                cmd_decode(self._args(text=None, trace=None))
        assert exc_info.value.code == 1

    def test_json_format(self, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        decoder_inst = MagicMock()
        decoder_inst.decode.return_value = make_semantics()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst):
            cmd_decode(self._args(text="hi", format="json"))
        out = capsys.readouterr().out
        assert "sem" in out


# ---------- cmd_verify ----------

class TestCmdVerify:
    def test_success_exits_zero(self):
        suite_inst = MagicMock()
        suite_inst.print_report.return_value = True
        with patch("gse.cli.main.GSEProofSuite", return_value=suite_inst):
            with pytest.raises(SystemExit) as exc:
                cmd_verify(argparse.Namespace(quiet=False))
        assert exc.value.code == 0
        suite_inst.run_all.assert_called_once()
        suite_inst.close.assert_called_once()

    def test_failure_exits_one(self):
        suite_inst = MagicMock()
        suite_inst.print_report.return_value = False
        with patch("gse.cli.main.GSEProofSuite", return_value=suite_inst):
            with pytest.raises(SystemExit) as exc:
                cmd_verify(argparse.Namespace(quiet=True))
        assert exc.value.code == 1

    def test_quiet_flag_passed_to_suite(self):
        suite_inst = MagicMock()
        suite_inst.print_report.return_value = True
        with patch("gse.cli.main.GSEProofSuite", return_value=suite_inst) as klass:
            with pytest.raises(SystemExit):
                cmd_verify(argparse.Namespace(quiet=True))
        # GSEProofSuite called with verbose=False (not quiet)
        klass.assert_called_once_with(verbose=False)


# ---------- cmd_interactive ----------

class TestCmdInteractive:
    def test_quit_exits_loop(self, capsys):
        encoder_inst = MagicMock()
        decoder_inst = MagicMock()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst), \
             patch("builtins.input", side_effect=["quit"]):
            cmd_interactive(argparse.Namespace())
        encoder_inst.close.assert_called_once()
        decoder_inst.close.assert_called_once()

    def test_eof_exits_loop(self):
        encoder_inst = MagicMock()
        decoder_inst = MagicMock()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst), \
             patch("builtins.input", side_effect=EOFError):
            cmd_interactive(argparse.Namespace())
        encoder_inst.close.assert_called_once()

    def test_empty_line_continues(self, capsys):
        encoder_inst = MagicMock()
        decoder_inst = MagicMock()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst), \
             patch("builtins.input", side_effect=["", "quit"]):
            cmd_interactive(argparse.Namespace())

    def test_encode_command(self, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        decoder_inst = MagicMock()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst), \
             patch("builtins.input", side_effect=["encode hello world", "quit"]):
            cmd_interactive(argparse.Namespace())
        out = capsys.readouterr().out
        assert "Hash:" in out

    def test_compare_command_valid(self, capsys):
        encoder_inst = MagicMock()
        vec = MagicMock()
        vec.cosine.return_value = 0.42
        trace_obj = make_trace(vector=vec)
        encoder_inst.encode.return_value = trace_obj
        decoder_inst = MagicMock()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst), \
             patch("builtins.input", side_effect=["compare a | b", "quit"]):
            cmd_interactive(argparse.Namespace())
        out = capsys.readouterr().out
        assert "Cosine:" in out

    def test_compare_command_malformed(self, capsys):
        encoder_inst = MagicMock()
        decoder_inst = MagicMock()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst), \
             patch("builtins.input", side_effect=["compare nosplit", "quit"]):
            cmd_interactive(argparse.Namespace())
        out = capsys.readouterr().out
        assert "Usage:" in out

    def test_decode_command(self, capsys):
        encoder_inst = MagicMock()
        encoder_inst.encode.return_value = make_trace()
        decoder_inst = MagicMock()
        decoder_inst.decode.return_value = make_semantics()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst), \
             patch("builtins.input", side_effect=["decode hello", "quit"]):
            cmd_interactive(argparse.Namespace())
        out = capsys.readouterr().out
        assert "Entities:" in out

    def test_unknown_command_prints_help(self, capsys):
        encoder_inst = MagicMock()
        decoder_inst = MagicMock()
        with patch("gse.cli.main.GSEEncoder", return_value=encoder_inst), \
             patch("gse.cli.main.GSEDecoder", return_value=decoder_inst), \
             patch("builtins.input", side_effect=["foobar", "quit"]):
            cmd_interactive(argparse.Namespace())
        out = capsys.readouterr().out
        assert "Unknown command" in out


# ---------- main ----------

class TestMain:
    def test_no_command_prints_help_and_exits(self, capsys):
        with patch("sys.argv", ["gse"]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1
        # argparse help was printed
        out = capsys.readouterr().out
        assert "Examples:" in out or "usage:" in out

    def test_encode_dispatched(self):
        called = []
        def fake_cmd_encode(args):
            called.append(args.text)
        with patch("sys.argv", ["gse", "encode", "hello world"]), \
             patch("gse.cli.main.cmd_encode", fake_cmd_encode):
            main()
        assert called == ["hello world"]

    def test_compare_dispatched(self):
        called = []
        def fake(args):
            called.append((args.sentence1, args.sentence2))
        with patch("sys.argv", ["gse", "compare", "a", "b"]), \
             patch("gse.cli.main.cmd_compare", fake):
            main()
        assert called == [("a", "b")]

    def test_verify_dispatched(self):
        called = []
        def fake(args):
            called.append(args.quiet)
        with patch("sys.argv", ["gse", "verify", "--quiet"]), \
             patch("gse.cli.main.cmd_verify", fake):
            main()
        assert called == [True]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
