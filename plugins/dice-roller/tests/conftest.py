"""Pytest configuration and fixtures for dice-roller plugin tests."""

import sys
from pathlib import Path

# Add plugin directory to path for local imports
PLUGIN_DIR = Path(__file__).parent.parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

import pytest
import random
from unittest.mock import AsyncMock, MagicMock

from dice import DiceParser, DiceRoller


@pytest.fixture
def parser() -> DiceParser:
    """Create a DiceParser with default limits."""
    return DiceParser()


@pytest.fixture
def strict_parser() -> DiceParser:
    """Create a DiceParser with strict limits."""
    return DiceParser(max_dice=5, max_sides=20, max_modifier=10)


@pytest.fixture
def roller() -> DiceRoller:
    """Create a DiceRoller with default settings."""
    return DiceRoller()


@pytest.fixture
def seeded_roller() -> DiceRoller:
    """Create a DiceRoller with seeded RNG for deterministic tests."""
    rng = random.Random(42)
    return DiceRoller(rng=rng)


@pytest.fixture
def mock_nats():
    """Create mock NATS client for testing."""
    nats = AsyncMock()
    nats.subscribe = AsyncMock(return_value=MagicMock())
    nats.publish = AsyncMock()
    return nats


@pytest.fixture
def plugin_config():
    """Default plugin configuration."""
    return {
        "max_dice": 20,
        "max_sides": 1000,
        "max_modifier": 100,
        "emit_events": True,
    }
