"""
GSE Lexicon Audit Daemon

Passively audits the lexicon database in the background.
Designed for continuous operation on resource-constrained hardware (16GB RAM).

Components:
- audit_daemon.py: Main entry point
- config.py: Configuration settings
- state_manager.py: Progress checkpointing
- throttle.py: CPU/memory throttling
- ollama_client.py: Ollama LLM fallback
- review_queue.py: Manual review queue
- audit_logger.py: Decision logging with provenance

Usage:
    python -m daemon.audit_daemon           # Run in foreground
    python -m daemon.audit_daemon --test    # Test mode (10 words)
    python -m daemon.audit_daemon --stats   # Show statistics
"""

from daemon.config import (
    DB_PATH,
    THROTTLE_CONFIG,
    OLLAMA_CONFIG,
    AUDIT_CONFIG,
    ALL_PRIMITIVES,
)
from daemon.state_manager import StateManager
from daemon.throttle import ThrottleManager
from daemon.ollama_client import OllamaClient
from daemon.review_queue import ReviewQueue
from daemon.audit_logger import AuditLogger

__all__ = [
    "DB_PATH",
    "THROTTLE_CONFIG",
    "OLLAMA_CONFIG",
    "AUDIT_CONFIG",
    "ALL_PRIMITIVES",
    "StateManager",
    "ThrottleManager",
    "OllamaClient",
    "ReviewQueue",
    "AuditLogger",
]
