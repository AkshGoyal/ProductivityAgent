"""The one wrapper every LLM call goes through.

Three things are handled here so no caller has to think about them:

1. **Structured output.** The caller passes a Pydantic model; it goes to Gemini
   as ``response_schema`` and comes back parsed and validated. Nothing in this
   project parses model output with a regex or a bare ``json.loads``.
2. **Retries.** google-genai makes exactly one attempt per call by default and
   raises straight away on a 429 or a transient 503. ``HttpRetryOptions`` turns
   on the SDK's own backoff, so overload doesn't surface as a hard failure.
3. **Prompts as files.** Templates live in ``app/prompts/*.md`` rather than as
   f-strings scattered through the routes.

Swapping providers means changing this file and ``config.py``; nothing else
imports the SDK.
"""

import logging
from functools import lru_cache
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app import config

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

_client: genai.Client | None = None


class LLMError(RuntimeError):
    """Raised when a call fails or comes back unusable."""


def get_client() -> genai.Client:
    """Lazily build the shared client (reads GEMINI_API_KEY from the env).

    Without explicit retry_options the SDK makes a single attempt and raises
    immediately, so a transient "model is overloaded" 503 would surface to the
    user as a hard error. HttpRetryOptions() with no arguments uses the
    library's own defaults: a handful of attempts with exponential backoff and
    jitter over 408/429/500/502/503/504 and connection errors.
    """
    global _client
    if _client is None:
        if not config.api_key_present():
            raise LLMError(
                f"{config.API_KEY_ENV_VAR} is not set — copy .env.example, add "
                'your key from https://aistudio.google.com/apikey, and export it.'
            )
        _client = genai.Client(
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions())
        )
    return _client


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Read a prompt template from app/prompts/<name>.md."""
    path = config.PROMPTS_DIR / f'{name}.md'
    if not path.exists():
        raise LLMError(f'prompt template not found: {path}')
    return path.read_text(encoding='utf-8')


def call(
    prompt_name: str,
    response_model: type[T],
    *,
    client: genai.Client | None = None,
    **variables: object,
) -> T:
    """Render a prompt, call Gemini, and return a validated model instance.

    `client` is injectable so tests can pass a double — the suite never makes a
    live API call.
    """
    template = load_prompt(prompt_name)
    try:
        prompt = template.format(**variables)
    except KeyError as exc:
        raise LLMError(f'prompt {prompt_name} is missing variable {exc}') from exc

    active = client or get_client()

    try:
        response = active.models.generate_content(
            model=config.MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=response_model,
                max_output_tokens=config.MAX_OUTPUT_TOKENS,
            ),
        )
    except Exception as exc:  # SDK errors vary; the caller only needs one type.
        raise LLMError(f'{prompt_name} call failed: {exc}') from exc

    usage = getattr(response, 'usage_metadata', None)
    if usage is not None:
        logger.info(
            '%s: %s prompt + %s output tokens',
            prompt_name,
            getattr(usage, 'prompt_token_count', '?'),
            getattr(usage, 'candidates_token_count', '?'),
        )

    parsed = getattr(response, 'parsed', None)
    if isinstance(parsed, response_model):
        return parsed

    # The SDK usually parses for us; fall back to validating the raw text so a
    # schema-shaped reply still succeeds instead of failing on a detail of the
    # client version.
    text = getattr(response, 'text', None)
    if not text:
        raise LLMError(f'{prompt_name} returned an empty response')
    try:
        return response_model.model_validate_json(text)
    except ValidationError as exc:
        raise LLMError(f'{prompt_name} returned output that failed validation: {exc}') from exc
