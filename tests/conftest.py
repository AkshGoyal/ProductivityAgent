"""Shared fixtures. The LLM client is always a double — no live API calls."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app import api, db
from app.main import app


class FakeResponse:
    """Mimics the shape of a google-genai response."""

    def __init__(self, parsed: BaseModel):
        self.parsed = parsed
        self.text = parsed.model_dump_json()
        self.usage_metadata = None


class FakeModels:
    def __init__(self, responses: list[BaseModel]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError('FakeLLMClient ran out of queued responses')
        return FakeResponse(self._responses.pop(0))


class FakeLLMClient:
    """Stands in for genai.Client; queue one response per expected call."""

    def __init__(self, *responses: BaseModel):
        self.models = FakeModels(list(responses))

    @property
    def calls(self) -> list[dict]:
        return self.models.calls


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    connection = db.connect(tmp_path / 'test.db')
    db.migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def client(conn: sqlite3.Connection) -> TestClient:
    """A TestClient wired to the temp database instead of the real one."""
    api.set_conn(conn)
    with TestClient(app) as test_client:
        yield test_client
    api.set_conn(None)
