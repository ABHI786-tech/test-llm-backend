"""LLM access through LiteLLM.

LiteLLM gives one `acompletion` call for every provider. The model is chosen with a
`provider/model` prefix (`anthropic/...`, `gemini/...`, `gpt-...`), and each provider's
API key is read from its usual environment variable, so no per-provider SDK is needed.
"""

import json
import os
from typing import Any

import litellm
from  core.exceptions import LLMNotConfiguredError, LLMServiceError
from  schemas.schemas import (
    FieldSuggestion,
    MediaOutletAnswer,
    MediaOutletRecord,
    OutletSuggestions,
)

# LiteLLM is chatty; we surface our own errors instead.
litellm.suppress_debug_info = True
# Drop parameters a provider does not support (e.g. response_format on some models)
# rather than failing the request.
litellm.drop_params = True

# Column id -> LiteLLM model id. Override any of these from .env.
MODEL_REGISTRY: dict[str, str] = {
    "claude": os.getenv("LITELLM_MODEL_CLAUDE", "anthropic/claude-sonnet-4-5"),
    "gemini": os.getenv("LITELLM_MODEL_GEMINI", "gemini/gemini-2.5-flash"),
    "gpt": os.getenv("LITELLM_MODEL_GPT", "gpt-4o-mini"),
}

# Model used by the single-question /ask route.
DEFAULT_MODEL = os.getenv("LITELLM_MODEL", MODEL_REGISTRY["gpt"])

# Environment variable that must be present for a given model id.
_KEY_ENV = {
    "gpt-": "OPENAI_API_KEY",
    "o1": "OPENAI_API_KEY",
    "o3": "OPENAI_API_KEY",
    "azure/": "AZURE_API_KEY",
    "anthropic/": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini/": "GEMINI_API_KEY",
    "vertex_ai/": "VERTEXAI_API_KEY",
}

ANSWER_SYSTEM_PROMPT = """You answer questions about a media outlet and the people who work there.

Rules:
1. Use ONLY the values present in the record. Never guess, infer, or add outside knowledge.
2. Identify which key field the question maps to and put that field's exact name in
   `matched_field`. For a nested person use a dotted path such as `personnel.title`.
3. Copy the value into `value` exactly as it appears in the record.
4. If the question is about a specific person, also set `matched_personnel_id` to that
   person's `id`. Otherwise leave it null.
5. If no field matches, or the matched field is empty, set `matched_field` and `value`
   to null and say so in `answer`.
6. `confidence` is your certainty that `value` answers the question: 1.0 when the field
   matches unambiguously, lower when the question is vague.
7. `answer` must be at most two sentences."""

SUGGEST_SYSTEM_PROMPT = """You review a media outlet record and suggest improved values for its fields.

Rules:
1. Return one entry per field in `suggestions`, using the exact `key` from the allowed list.
2. `value` must have the same type as the current record value: a string for text fields,
   and a list of strings for list fields. Use null when you have nothing to add.
3. You may normalise, tidy or expand values (for example splitting a comma separated
   string into a list, fixing capitalisation, shortening an over-long slogan) but you must
   NOT invent facts that contradict the record.
4. If a field is already correct, return it unchanged with `confidence` 1.0.
5. `confidence` is how sure you are that the suggestion is an improvement: 1.0 when you are
   certain, below 0.5 when you are guessing. Never exceed 0.8 without strong evidence.
6. `note` is a short reason, at most 12 words."""


def required_key_env(model: str) -> str | None:
    """Which env var holds the API key for this model id, if any is required."""
    lowered = model.lower()
    for prefix, env in _KEY_ENV.items():
        if lowered.startswith(prefix):
            return env
    return None


def missing_keys(models: list[str]) -> list[str]:
    """Env var names that are unset for the given models (unknown providers pass)."""
    missing = []
    for model in models:
        env = required_key_env(model)
        if env and not os.getenv(env):
            missing.append(env)
    return sorted(set(missing))


def record_to_json(record: MediaOutletRecord) -> str:
    """Serialize the record to pure JSON for the prompt."""
    return json.dumps(record.model_dump(mode="json"), ensure_ascii=False)


def _parse_structured(response: Any, model_cls: type) -> Any:
    """Read the JSON payload out of a LiteLLM response and validate it.

    LiteLLM returns the structured result as a JSON string in `message.content`
    (unlike the OpenAI SDK, which hands back a pre-parsed object), so this parses
    and validates in one step.
    """
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, KeyError) as exc:
        raise LLMServiceError("The model returned an unexpected response shape") from exc

    content = getattr(message, "content", None)
    if content is None or content == "":
        raise LLMServiceError("The model returned an empty response")

    if isinstance(content, dict):
        return model_cls.model_validate(content)

    try:
        return model_cls.model_validate_json(content)
    except Exception as exc:  # noqa: BLE001 - translated into a domain error
        raise LLMServiceError(f"The model did not return valid JSON: {exc}") from exc


async def _acompletion(model: str, messages: list[dict], schema: type) -> Any:
    """One LiteLLM call with structured output, with errors mapped to AppErrors."""
    env = required_key_env(model)
    if env and not os.getenv(env):
        raise LLMNotConfiguredError(f"{env} is not set on the server")

    try:
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=0,
            response_format=schema,
            timeout=60,
        )
    except LLMNotConfiguredError:
        raise
    except Exception as exc:  # noqa: BLE001 - translated into a domain error
        raise LLMServiceError(f"LLM request to {model} failed: {exc}") from exc

    return _parse_structured(response, schema)


async def answer_about_media_outlet(
    record: MediaOutletRecord, question: str, model: str = DEFAULT_MODEL
) -> MediaOutletAnswer:
    """Send the media outlet record as JSON to the LLM and get a structured answer back.

    The record is the only source of truth; the model is instructed to answer strictly
    from the key fields it contains.
    """
    payload = record_to_json(record)
    return await _acompletion(
        model,
        [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Media outlet record (JSON):\n```json\n{payload}\n```\n\nQuestion: {question}"
                ),
            },
        ],
        MediaOutletAnswer,
    )


async def suggest_fields(record: MediaOutletRecord, allowed_keys: list[str], model: str) -> OutletSuggestions:
    """Ask one model to suggest improved values for every field of the record."""
    return await _acompletion(
        model,
        [
            {"role": "system", "content": SUGGEST_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Media outlet record (JSON):\n```json\n{record_to_json(record)}\n```\n\n"
                    f"Allowed keys, one per entry: {json.dumps(allowed_keys)}"
                ),
            },
        ],
        OutletSuggestions,
    )


__all__ = [
    "DEFAULT_MODEL",
    "FieldSuggestion",
    "MODEL_REGISTRY",
    "OutletSuggestions",
    "answer_about_media_outlet",
    "missing_keys",
    "record_to_json",
    "required_key_env",
    "suggest_fields",
]