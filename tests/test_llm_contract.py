"""The LLM wrapper's contract: schema in, validated model out, retries on."""

import pytest
from pydantic import BaseModel

from app import config, llm, models
from tests.conftest import FakeLLMClient


def test_call_passes_the_pydantic_model_as_the_response_schema():
    """Structured output is the whole defence against malformed replies."""
    client = FakeLLMClient(models.BreakdownResult(tasks=[]))

    llm.call(
        'breakdown_goal',
        models.BreakdownResult,
        client=client,
        profile='',
        title='t',
        description='d',
        target_date='none',
        existing_tasks='None.',
    )

    sent = client.calls[0]['config']
    assert sent.response_schema is models.BreakdownResult
    assert sent.response_mime_type == 'application/json'


def test_call_returns_the_parsed_model(monkeypatch):
    expected = models.BreakdownResult(
        tasks=[models.SuggestedTask(title='Write the outline', estimated_minutes=45)]
    )
    client = FakeLLMClient(expected)

    result = llm.call(
        'breakdown_goal',
        models.BreakdownResult,
        client=client,
        profile='',
        title='t',
        description='d',
        target_date='none',
        existing_tasks='None.',
    )

    assert result.tasks[0].title == 'Write the outline'


def test_missing_prompt_variable_is_reported_clearly():
    client = FakeLLMClient(models.BreakdownResult(tasks=[]))
    with pytest.raises(llm.LLMError, match='missing variable'):
        llm.call('breakdown_goal', models.BreakdownResult, client=client, title='only one')


def test_unknown_prompt_name_raises():
    with pytest.raises(llm.LLMError, match='prompt template not found'):
        llm.load_prompt('does_not_exist')


def test_sdk_failures_surface_as_llm_error():
    class Exploding:
        class models:  # noqa: D106 - test double
            @staticmethod
            def generate_content(**_kwargs):
                raise RuntimeError('503 UNAVAILABLE')

    with pytest.raises(llm.LLMError, match='503'):
        llm.call(
            'breakdown_goal',
            models.BreakdownResult,
            client=Exploding(),
            profile='',
            title='t',
            description='d',
            target_date='none',
            existing_tasks='None.',
        )


def test_client_is_built_with_retry_options(monkeypatch):
    """google-genai makes a single attempt by default; a 503 would be fatal
    without this, so assert it can't regress silently."""
    monkeypatch.setenv(config.API_KEY_ENV_VAR, 'test-key-not-real')
    monkeypatch.setattr(llm, '_client', None)

    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm.genai, 'Client', FakeClient)
    llm.get_client()

    assert captured['http_options'].retry_options is not None
    monkeypatch.setattr(llm, '_client', None)


def test_missing_api_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv(config.API_KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(llm, '_client', None)

    with pytest.raises(llm.LLMError, match=config.API_KEY_ENV_VAR):
        llm.get_client()
