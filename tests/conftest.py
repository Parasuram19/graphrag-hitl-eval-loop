import os
import pytest

@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    """Prevent pydantic-settings from failing due to missing .env in CI."""
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "test")
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")
    monkeypatch.setenv("VECTOR_INDEX_NAME", "test_index")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "384")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake-key-for-ci")
    monkeypatch.setenv("OPENROUTER_MODEL", "test-model")