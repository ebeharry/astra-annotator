"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest

from core.database import DatabaseManager
from core.managers.annotation import AnnotationManager
from core.managers.experiment import ExperimentManager
from core.managers.prompt import PromptManager


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = DatabaseManager(tmp.name)
        yield db
        # Cleanup
        Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def prompt_manager(temp_db):
    """Create a PromptManager with temporary database."""
    return PromptManager(temp_db)


@pytest.fixture
def experiment_manager(temp_db):
    """Create an ExperimentManager with temporary database."""
    return ExperimentManager(temp_db)


@pytest.fixture
def annotation_manager(temp_db):
    """Create an AnnotationManager with temporary database."""
    return AnnotationManager(temp_db)


@pytest.fixture
def sample_condition(temp_db):
    """Create a sample condition for testing."""
    condition_id = temp_db.create_condition("Test Condition", "A test condition")
    return condition_id


@pytest.fixture
def sample_prompt_grid():
    """Return a sample 3x3 prompt grid."""
    return {
        "implicit": {
            "low": "Implicit low severity prompt",
            "moderate": "Implicit moderate severity prompt",
            "high": "Implicit high severity prompt",
        },
        "neutral": {
            "low": "Neutral low severity prompt",
            "moderate": "Neutral moderate severity prompt",
            "high": "Neutral high severity prompt",
        },
        "explicit": {
            "low": "Explicit low severity prompt",
            "moderate": "Explicit moderate severity prompt",
            "high": "Explicit high severity prompt",
        },
    }
