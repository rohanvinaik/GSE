"""Manual contract tests for gse.teaching.conversation_processor."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.teaching.conversation_processor import (
    ConversationProcessor,
    ConversationTurn,
)

# ---------- ConversationTurn ----------


class TestConversationTurn:
    def test_str_truncates_long_content(self):
        t = ConversationTurn(role="user", content="x" * 200)
        s = str(t)
        # str returns first 100 chars + "..."
        assert "[user]" in s
        assert "..." in s

    def test_defaults(self):
        t = ConversationTurn(role="user", content="hi")
        assert t.conversation_id == ""
        assert t.turn_index == 0


# ---------- Fixtures ----------


@pytest.fixture
def proc():
    return ConversationProcessor()


@pytest.fixture
def short_min_proc():
    # Lower min for tests
    return ConversationProcessor(min_content_length=5, max_content_length=100)


def write_json(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return str(p)


# ---------- __init__ ----------


class TestInit:
    def test_defaults(self):
        p = ConversationProcessor()
        assert p.min_content_length == 50
        assert p.max_content_length == 10000
        assert p.skip_system is True

    def test_custom_values(self):
        p = ConversationProcessor(min_content_length=10, max_content_length=500, skip_system=False)
        assert p.min_content_length == 10
        assert p.max_content_length == 500
        assert p.skip_system is False


# ---------- process_file ----------


class TestProcessFile:
    def test_missing_file_raises(self, proc):
        with pytest.raises(FileNotFoundError):
            list(proc.process_file("/nonexistent/file.json"))

    def test_claude_filename_routes_to_claude(self, tmp_path, short_min_proc):
        # File with "claude" in name → routes through process_claude_file
        path = write_json(
            tmp_path,
            "claude_chat.json",
            [{"uuid": "x", "chat_messages": [{"sender": "human", "text": "hello world from human"}]}],
        )
        result = list(short_min_proc.process_file(path))
        assert len(result) == 1

    def test_gpt_filename_routes_to_gpt(self, tmp_path, short_min_proc):
        path = write_json(
            tmp_path,
            "gpt_chat.json",
            [
                {
                    "mapping": {
                        "n1": {
                            "message": {
                                "author": {"role": "user"},
                                "content": {"parts": ["hello world from user"]},
                            }
                        }
                    }
                }
            ],
        )
        result = list(short_min_proc.process_file(path))
        assert len(result) == 1

    def test_unknown_filename_auto_detects(self, tmp_path, short_min_proc):
        # Filename doesn't hint format — falls back to auto-detect
        path = write_json(tmp_path, "random.json", [{"chat_messages": [{"sender": "human", "text": "hello world"}]}])
        result = list(short_min_proc.process_file(path))
        assert len(result) >= 1


# ---------- process_claude_file ----------


class TestProcessClaudeFile:
    def test_list_format(self, tmp_path, short_min_proc):
        path = write_json(
            tmp_path,
            "claude.json",
            [
                {"uuid": "a", "chat_messages": [{"sender": "human", "text": "message text"}]},
                {"uuid": "b", "chat_messages": [{"sender": "assistant", "text": "response text"}]},
            ],
        )
        result = list(short_min_proc.process_claude_file(path))
        assert len(result) == 2

    def test_dict_with_chat_messages(self, tmp_path, short_min_proc):
        path = write_json(tmp_path, "claude.json", {"chat_messages": [{"sender": "human", "text": "hello world"}]})
        result = list(short_min_proc.process_claude_file(path))
        assert len(result) == 1

    def test_dict_with_conversations(self, tmp_path, short_min_proc):
        path = write_json(
            tmp_path,
            "claude.json",
            {"conversations": [{"chat_messages": [{"sender": "human", "text": "hello world"}]}]},
        )
        result = list(short_min_proc.process_claude_file(path))
        assert len(result) == 1

    def test_invalid_json_warns(self, tmp_path, short_min_proc, capsys):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{")
        result = list(short_min_proc.process_claude_file(str(path)))
        out = capsys.readouterr().out
        assert "JSON decode error" in out
        assert result == []


# ---------- _process_claude_conversation ----------


class TestProcessClaudeConversation:
    def test_skips_system_when_configured(self, short_min_proc):
        conv = {
            "uuid": "x",
            "chat_messages": [
                {"sender": "system", "text": "system message"},
                {"sender": "human", "text": "human message"},
            ],
        }
        result = list(short_min_proc._process_claude_conversation(conv))
        # System is skipped
        assert len(result) == 1

    def test_includes_system_when_not_skipping(self):
        proc = ConversationProcessor(min_content_length=5, skip_system=False)
        conv = {
            "uuid": "x",
            "chat_messages": [
                {"sender": "system", "text": "system message"},
                {"sender": "human", "text": "human message"},
            ],
        }
        result = list(proc._process_claude_conversation(conv))
        assert len(result) == 2

    def test_fallback_to_content_field(self, short_min_proc):
        conv = {"chat_messages": [{"sender": "human", "content": "fallback content here"}]}
        result = list(short_min_proc._process_claude_conversation(conv))
        assert len(result) == 1

    def test_fallback_to_message_field(self, short_min_proc):
        conv = {"chat_messages": [{"sender": "human", "message": "fallback message here"}]}
        result = list(short_min_proc._process_claude_conversation(conv))
        assert len(result) == 1

    def test_min_length_filters(self, short_min_proc):
        conv = {
            "chat_messages": [
                {"sender": "human", "text": "x"}  # 1 char, below min of 5
            ]
        }
        result = list(short_min_proc._process_claude_conversation(conv))
        assert result == []

    def test_max_length_truncates(self):
        proc = ConversationProcessor(min_content_length=1, max_content_length=10)
        long_text = "abcdefghijklmnop"  # 16 chars > max 10
        conv = {"chat_messages": [{"sender": "human", "text": long_text}]}
        result = list(proc._process_claude_conversation(conv))
        assert result == ["abcdefghij"]  # truncated to 10 chars


# ---------- process_gpt_file ----------


class TestProcessGptFile:
    def test_list_format(self, tmp_path, short_min_proc):
        path = write_json(
            tmp_path,
            "gpt.json",
            [
                {
                    "mapping": {
                        "n1": {
                            "message": {
                                "author": {"role": "user"},
                                "content": {"parts": ["hello world from user"]},
                            }
                        }
                    }
                }
            ],
        )
        result = list(short_min_proc.process_gpt_file(path))
        assert len(result) == 1

    def test_dict_with_mapping(self, tmp_path, short_min_proc):
        path = write_json(
            tmp_path,
            "gpt.json",
            {
                "mapping": {
                    "n1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["hello world"]},
                        }
                    }
                }
            },
        )
        result = list(short_min_proc.process_gpt_file(path))
        assert len(result) == 1

    def test_dict_with_conversations(self, tmp_path, short_min_proc):
        path = write_json(
            tmp_path,
            "gpt.json",
            {
                "conversations": [
                    {
                        "mapping": {
                            "n1": {
                                "message": {
                                    "author": {"role": "user"},
                                    "content": {"parts": ["hello world"]},
                                }
                            }
                        }
                    }
                ]
            },
        )
        result = list(short_min_proc.process_gpt_file(path))
        assert len(result) == 1

    def test_invalid_json_warns(self, tmp_path, short_min_proc, capsys):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        list(short_min_proc.process_gpt_file(str(path)))
        out = capsys.readouterr().out
        assert "decode" in out.lower()


# ---------- _process_gpt_conversation ----------


class TestProcessGptConversation:
    def test_skips_system(self, short_min_proc):
        conv = {
            "mapping": {
                "n1": {
                    "message": {
                        "author": {"role": "system"},
                        "content": {"parts": ["system message"]},
                    }
                },
                "n2": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["user message"]},
                    }
                },
            }
        }
        result = list(short_min_proc._process_gpt_conversation(conv))
        assert len(result) == 1

    def test_non_dict_node_skipped(self, short_min_proc):
        conv = {
            "mapping": {
                "n1": "not a dict",
                "n2": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["hello world"]},
                    }
                },
            }
        }
        result = list(short_min_proc._process_gpt_conversation(conv))
        assert len(result) == 1

    def test_missing_message_skipped(self, short_min_proc):
        conv = {
            "mapping": {
                "n1": {},  # no 'message' key
            }
        }
        result = list(short_min_proc._process_gpt_conversation(conv))
        assert result == []

    def test_non_string_part_skipped(self, short_min_proc):
        conv = {
            "mapping": {
                "n1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": [{"type": "image"}, "hello world text"]},
                    }
                },
            }
        }
        result = list(short_min_proc._process_gpt_conversation(conv))
        # Only the string part is yielded
        assert len(result) == 1

    def test_max_length_truncates(self):
        proc = ConversationProcessor(min_content_length=1, max_content_length=5)
        conv = {
            "mapping": {
                "n1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["abcdefghij"]},
                    }
                }
            }
        }
        result = list(proc._process_gpt_conversation(conv))
        assert result == ["abcde"]


# ---------- _auto_detect_and_process ----------


class TestAutoDetect:
    def test_chat_messages_signal_claude(self, tmp_path, short_min_proc):
        path = write_json(tmp_path, "x.json", [{"chat_messages": [{"sender": "human", "text": "hello world"}]}])
        result = list(short_min_proc._auto_detect_and_process(path))
        assert len(result) >= 1

    def test_mapping_signal_gpt(self, tmp_path, short_min_proc):
        path = write_json(
            tmp_path,
            "x.json",
            [
                {
                    "mapping": {
                        "n1": {
                            "message": {
                                "author": {"role": "user"},
                                "content": {"parts": ["hello world"]},
                            }
                        }
                    }
                }
            ],
        )
        result = list(short_min_proc._auto_detect_and_process(path))
        assert len(result) >= 1

    def test_unknown_defaults_to_claude(self, tmp_path, short_min_proc):
        # Empty JSON list — neither signal present, defaults to claude
        path = write_json(tmp_path, "x.json", [])
        result = list(short_min_proc._auto_detect_and_process(path))
        assert result == []

    def test_read_failure_handled(self, short_min_proc, capsys):
        result = list(short_min_proc._auto_detect_and_process("/nonexistent.json"))
        out = capsys.readouterr().out
        assert "Auto-detect failed" in out
        assert result == []


# ---------- _clean_text ----------


class TestCleanText:
    def test_removes_code_blocks(self, proc):
        result = proc._clean_text("Hello ```code here``` world")
        assert "code here" not in result

    def test_removes_inline_code(self, proc):
        result = proc._clean_text("Hello `inline` world")
        assert "inline" not in result

    def test_removes_images(self, proc):
        result = proc._clean_text("Hello ![alt](url) world")
        assert "alt" not in result
        assert "url" not in result

    def test_links_become_text(self, proc):
        result = proc._clean_text("Hello [link text](url)")
        assert "link text" in result
        assert "url" not in result

    def test_excessive_whitespace_collapsed(self, proc):
        result = proc._clean_text("Hello    world")
        assert result == "Hello world"

    def test_non_string_returns_empty(self, proc):
        assert proc._clean_text(None) == ""
        assert proc._clean_text(123) == ""

    def test_special_chars_removed(self, proc):
        result = proc._clean_text("Hello @#$ world")
        # @ # $ removed; alphanumerics + basic punct preserved
        assert "@" not in result


# ---------- get_file_stats ----------


class TestGetFileStats:
    def test_missing_file_returns_defaults(self, proc):
        stats = proc.get_file_stats("/nonexistent.json")
        assert stats["conversations"] == 0
        assert stats["format"] == "unknown"

    def test_claude_list_format(self, tmp_path, proc):
        path = write_json(
            tmp_path,
            "x.json",
            [
                {"chat_messages": [{"sender": "human", "text": "x"}, {"sender": "ai", "text": "y"}]},
                {"chat_messages": [{"sender": "human", "text": "z"}]},
            ],
        )
        stats = proc.get_file_stats(path)
        assert stats["format"] == "claude"
        assert stats["conversations"] == 2
        assert stats["messages"] == 3

    def test_gpt_list_format(self, tmp_path, proc):
        path = write_json(
            tmp_path,
            "x.json",
            [
                {"mapping": {"n1": {}, "n2": {}}},
            ],
        )
        stats = proc.get_file_stats(path)
        assert stats["format"] == "gpt"
        assert stats["messages"] == 2

    def test_claude_dict_format(self, tmp_path, proc):
        path = write_json(tmp_path, "x.json", {"chat_messages": [{"sender": "h", "text": "x"}]})
        stats = proc.get_file_stats(path)
        assert stats["format"] == "claude"
        assert stats["conversations"] == 1
        assert stats["messages"] == 1

    def test_gpt_dict_format(self, tmp_path, proc):
        path = write_json(tmp_path, "x.json", {"mapping": {"n1": {}, "n2": {}}})
        stats = proc.get_file_stats(path)
        assert stats["format"] == "gpt"
        assert stats["messages"] == 2

    def test_file_size_reported(self, tmp_path, proc):
        path = write_json(tmp_path, "x.json", {"chat_messages": []})
        stats = proc.get_file_stats(path)
        assert stats["file_size_mb"] >= 0

    def test_parse_error_recorded(self, tmp_path, proc):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        stats = proc.get_file_stats(str(path))
        assert "error" in stats


# ---------- count_turns ----------


class TestCountTurns:
    def test_counts_yields(self, tmp_path, short_min_proc):
        path = write_json(
            tmp_path,
            "claude.json",
            [
                {
                    "chat_messages": [
                        {"sender": "human", "text": "msg one here"},
                        {"sender": "assistant", "text": "msg two here"},
                    ]
                }
            ],
        )
        assert short_min_proc.count_turns(path) == 2

    def test_missing_file_returns_zero(self, short_min_proc):
        # process_file raises but count_turns catches
        assert short_min_proc.count_turns("/nonexistent.json") == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
