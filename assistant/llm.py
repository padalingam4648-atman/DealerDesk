import json
import logging
import os
import time
from dataclasses import dataclass
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[LLMToolCall]


class LLMUnavailableError(Exception):
    """Raised when the LLM provider cannot be reached or returns unrecoverable errors."""
    pass


# Global injectable adapter hook for testing and offline mocks
_custom_llm_adapter = None


def set_llm_adapter(adapter_fn):
    global _custom_llm_adapter
    _custom_llm_adapter = adapter_fn


def reset_llm_adapter():
    global _custom_llm_adapter
    _custom_llm_adapter = None


def call_llm(
    messages: list[dict],
    tool_schemas: list[dict],
    temperature: float = 0.0,
    timeout: float = 25.0,
) -> LLMResponse:
    """
    Thin, resilient provider adapter.
    Dispatches to custom adapter (if registered in tests) or the configured provider (Groq).
    Applies retries with backoff on transient 429 / 5xx errors.
    """
    global _custom_llm_adapter
    if _custom_llm_adapter is not None:
        return _custom_llm_adapter(messages, tool_schemas, temperature=temperature)

    api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise LLMUnavailableError("No LLM provider API key configured (GROQ_API_KEY is empty).")

    try:
        from groq import Groq, APIConnectionError, RateLimitError, InternalServerError
    except ImportError:
        raise LLMUnavailableError("The 'groq' package is not installed.")

    client = Groq(api_key=api_key, timeout=timeout)
    model = (
        getattr(settings, "ASSISTANT_MODEL", "")
        or os.environ.get("ASSISTANT_MODEL", "")
        or "openai/gpt-oss-120b"
    )

    max_attempts = 3
    last_err = None

    for attempt in range(max_attempts):
        try:
            # Build API call parameters
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if tool_schemas:
                kwargs["tools"] = tool_schemas
                kwargs["tool_choice"] = "auto"

            res = client.chat.completions.create(**kwargs)
            choice = res.choices[0].message

            parsed_tool_calls = []
            if getattr(choice, "tool_calls", None):
                for tc in choice.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        fn_args = {}
                    parsed_tool_calls.append(LLMToolCall(
                        id=tc.id,
                        name=fn_name,
                        arguments=fn_args,
                    ))

            return LLMResponse(
                content=choice.content,
                tool_calls=parsed_tool_calls,
            )

        except (RateLimitError, InternalServerError, APIConnectionError) as e:
            last_err = e
            if attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 1.5
                logger.warning(f"Transient Groq error (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Groq API failed after {max_attempts} attempts: {e}")
                raise LLMUnavailableError(f"LLM provider failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected Groq API exception: {e}")
            raise LLMUnavailableError(f"LLM API error: {e}")

    raise LLMUnavailableError(f"LLM provider call timed out or failed: {last_err}")
