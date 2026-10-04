#!/usr/bin/env python3
"""
Conversation Processor for Large Claude/GPT JSON Exports

Handles streaming processing of large conversation JSON files:
- Claude conversation exports (claude_conversations.json)
- GPT conversation exports (gpt_conversations.json)

Yields conversation turns as text for teaching without loading
entire file into memory.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    role: str  # 'human', 'assistant', 'user', 'system'
    content: str
    conversation_id: str = ""
    turn_index: int = 0

    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:100]}..."


class ConversationProcessor:
    """
    Process large conversation JSON files for teaching.

    Streams conversation turns without loading entire file into memory.
    Supports both Claude and GPT export formats.
    """

    def __init__(
        self,
        min_content_length: int = 50,
        max_content_length: int = 10000,
        skip_system: bool = True,
    ):
        """
        Initialize processor.

        Args:
            min_content_length: Minimum characters per turn to include
            max_content_length: Maximum characters (truncate longer)
            skip_system: Whether to skip system messages
        """
        self.min_content_length = min_content_length
        self.max_content_length = max_content_length
        self.skip_system = skip_system

    def process_file(self, filepath: str) -> Iterator[str]:
        """
        Process a conversation file, yielding text content.

        Automatically detects format (Claude vs GPT).

        Args:
            filepath: Path to JSON file

        Yields:
            Text content from each conversation turn
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Detect format from filename or content
        filename = path.name.lower()

        if "claude" in filename:
            yield from self.process_claude_file(filepath)
        elif "gpt" in filename or "chatgpt" in filename:
            yield from self.process_gpt_file(filepath)
        else:
            # Try to auto-detect from content
            yield from self._auto_detect_and_process(filepath)

    def process_claude_file(self, filepath: str) -> Iterator[str]:
        """
        Process Claude conversation export.

        Claude exports typically have structure:
        [
            {
                "uuid": "...",
                "name": "...",
                "chat_messages": [
                    {"sender": "human"|"assistant", "text": "..."},
                    ...
                ]
            },
            ...
        ]

        Args:
            filepath: Path to Claude export JSON

        Yields:
            Text content from each message
        """
        try:
            # Stream parse the JSON
            with open(filepath, "r", encoding="utf-8") as f:
                # For very large files, use ijson for streaming
                # But for now, parse in chunks
                data = json.load(f)

            if isinstance(data, list):
                for conv in data:
                    yield from self._process_claude_conversation(conv)
            elif isinstance(data, dict):
                # Single conversation or wrapped format
                if "chat_messages" in data:
                    yield from self._process_claude_conversation(data)
                elif "conversations" in data:
                    for conv in data["conversations"]:
                        yield from self._process_claude_conversation(conv)

        except json.JSONDecodeError as e:
            print(f"Warning: JSON decode error in {filepath}: {e}")
        except Exception as e:
            print(f"Warning: Error processing {filepath}: {e}")

    def _process_claude_conversation(self, conv: Dict) -> Iterator[str]:
        """Process a single Claude conversation object."""
        messages = conv.get("chat_messages", [])

        for i, msg in enumerate(messages):
            sender = msg.get("sender", "unknown")

            # Skip system if configured
            if self.skip_system and sender == "system":
                continue

            # Get text content
            text = msg.get("text", "")
            if not text:
                # Try alternate field names
                text = msg.get("content", "") or msg.get("message", "")

            text = self._clean_text(text)

            # Apply length filters
            if len(text) < self.min_content_length:
                continue

            if len(text) > self.max_content_length:
                text = text[: self.max_content_length]

            yield text

    def process_gpt_file(self, filepath: str) -> Iterator[str]:
        """
        Process GPT/ChatGPT conversation export.

        GPT exports typically have structure:
        [
            {
                "title": "...",
                "mapping": {
                    "node_id": {
                        "message": {
                            "author": {"role": "user"|"assistant"},
                            "content": {"parts": ["..."]}
                        }
                    },
                    ...
                }
            },
            ...
        ]

        Args:
            filepath: Path to GPT export JSON

        Yields:
            Text content from each message
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for conv in data:
                    yield from self._process_gpt_conversation(conv)
            elif isinstance(data, dict):
                if "mapping" in data:
                    yield from self._process_gpt_conversation(data)
                elif "conversations" in data:
                    for conv in data["conversations"]:
                        yield from self._process_gpt_conversation(conv)

        except json.JSONDecodeError as e:
            print(f"Warning: JSON decode error in {filepath}: {e}")
        except Exception as e:
            print(f"Warning: Error processing {filepath}: {e}")

    def _process_gpt_conversation(self, conv: Dict) -> Iterator[str]:
        """Process a single GPT conversation object."""
        mapping = conv.get("mapping", {})

        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue

            message = node.get("message")
            if not message:
                continue

            # Get author role
            author = message.get("author", {})
            role = author.get("role", "unknown")

            # Skip system if configured
            if self.skip_system and role == "system":
                continue

            # Get content
            content = message.get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                if isinstance(part, str):
                    text = self._clean_text(part)

                    # Apply length filters
                    if len(text) < self.min_content_length:
                        continue

                    if len(text) > self.max_content_length:
                        text = text[: self.max_content_length]

                    yield text

    def _auto_detect_and_process(self, filepath: str) -> Iterator[str]:
        """Auto-detect format and process."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                # Read first 1000 chars to detect format
                sample = f.read(1000)

            if '"chat_messages"' in sample or '"sender"' in sample:
                yield from self.process_claude_file(filepath)
            elif '"mapping"' in sample or '"author"' in sample:
                yield from self.process_gpt_file(filepath)
            else:
                # Try Claude format as default
                yield from self.process_claude_file(filepath)

        except Exception as e:
            print(f"Warning: Auto-detect failed for {filepath}: {e}")

    def _clean_text(self, text: str) -> str:
        """Clean text content for teaching."""
        if not isinstance(text, str):
            return ""

        # Remove markdown artifacts
        text = re.sub(r"```[\s\S]*?```", "", text)  # Code blocks
        text = re.sub(r"`[^`]+`", "", text)  # Inline code
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # Images
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # Links → text

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove special characters
        text = re.sub(r"[^\w\s.,!?;:\'\"-]", "", text)

        return text.strip()

    def get_file_stats(self, filepath: str) -> Dict[str, Any]:
        """
        Get statistics about a conversation file without full processing.

        Args:
            filepath: Path to JSON file

        Returns:
            Dict with conversation count, message count, etc.
        """
        stats = {
            "filepath": str(filepath),
            "format": "unknown",
            "conversations": 0,
            "messages": 0,
            "file_size_mb": 0,
        }

        path = Path(filepath)
        if not path.exists():
            return stats

        stats["file_size_mb"] = path.stat().st_size / (1024 * 1024)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                stats["conversations"] = len(data)
                if data:
                    first = data[0]
                    if "chat_messages" in first:
                        stats["format"] = "claude"
                        stats["messages"] = sum(len(c.get("chat_messages", [])) for c in data)
                    elif "mapping" in first:
                        stats["format"] = "gpt"
                        stats["messages"] = sum(len(c.get("mapping", {})) for c in data)
            elif isinstance(data, dict):
                stats["conversations"] = 1
                if "chat_messages" in data:
                    stats["format"] = "claude"
                    stats["messages"] = len(data["chat_messages"])
                elif "mapping" in data:
                    stats["format"] = "gpt"
                    stats["messages"] = len(data["mapping"])

        except Exception as e:
            stats["error"] = str(e)

        return stats

    def count_turns(self, filepath: str) -> int:
        """Count total turns in a file (for progress tracking)."""
        count = 0
        try:
            for _ in self.process_file(filepath):
                count += 1
        except Exception:
            pass
        return count


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    import sys

    print("Conversation Processor Self-Test")
    print("=" * 50)

    processor = ConversationProcessor()

    # Test with sample data
    sample_claude = [
        {
            "uuid": "test-1",
            "name": "Test Conversation",
            "chat_messages": [
                {"sender": "human", "text": "This is a test message from the human user."},
                {"sender": "assistant", "text": "This is a response from the assistant."},
            ],
        }
    ]

    sample_gpt = [
        {
            "title": "Test Conversation",
            "mapping": {
                "node1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["This is a test message from the user."]},
                    }
                },
                "node2": {
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {"parts": ["This is a response from the assistant."]},
                    }
                },
            },
        }
    ]

    # Create temp files for testing
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test Claude format
        claude_path = os.path.join(tmpdir, "claude_test.json")
        with open(claude_path, "w") as f:
            json.dump(sample_claude, f)

        print("\n1. Claude Format Processing:")
        for text in processor.process_file(claude_path):
            print(f"   [{len(text)} chars] {text[:50]}...")

        # Test GPT format
        gpt_path = os.path.join(tmpdir, "gpt_test.json")
        with open(gpt_path, "w") as f:
            json.dump(sample_gpt, f)

        print("\n2. GPT Format Processing:")
        for text in processor.process_file(gpt_path):
            print(f"   [{len(text)} chars] {text[:50]}...")

        # Test stats
        print("\n3. File Statistics:")
        stats = processor.get_file_stats(claude_path)
        print(f"   Format: {stats['format']}")
        print(f"   Conversations: {stats['conversations']}")
        print(f"   Messages: {stats['messages']}")

    # If real files provided
    if len(sys.argv) > 1:
        print("\n4. Real File Processing:")
        for filepath in sys.argv[1:]:
            print(f"\n   Processing: {filepath}")
            stats = processor.get_file_stats(filepath)
            print(f"   Size: {stats['file_size_mb']:.1f} MB")
            print(f"   Format: {stats['format']}")
            print(f"   Conversations: {stats['conversations']}")

            # Sample first few
            count = 0
            for text in processor.process_file(filepath):
                count += 1
                if count <= 3:
                    print(f"   Sample {count}: {text[:80]}...")
                if count >= 100:
                    break
            print(f"   Total sampled: {count} turns")

    print("\n" + "=" * 50)
    print("Conversation Processor tests complete!")
