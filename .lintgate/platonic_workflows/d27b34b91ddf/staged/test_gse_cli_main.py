"""Tests for main."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from gse.cli.main import cmd_compare, cmd_decode, cmd_encode, cmd_interactive, cmd_verify, main


