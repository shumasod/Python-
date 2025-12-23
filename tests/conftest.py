"""Pytest configuration and fixtures."""
import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing."""
    files = [
        temp_dir / "test1.txt",
        temp_dir / "test2.txt",
        temp_dir / "file.py",
        temp_dir / "data.json",
    ]
    for file in files:
        file.write_text(f"Content of {file.name}")
    return files


@pytest.fixture
def mock_config():
    """Provide a mock configuration for tests."""
    return {
        'debug': True,
        'log_level': 'DEBUG',
        'database_url': 'sqlite:///:memory:',
    }
