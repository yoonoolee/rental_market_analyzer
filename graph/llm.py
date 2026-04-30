import asyncio
import json
import os

from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

try:
    import groq
except Exception:  # pragma: no cover
    groq = None

try:
    import openai as _openai_mod
except Exception:  # pragma: no cover
    _openai_mod = None


ROLE_DEFAULTS = {
    "intent_router_classify": {"provider": "groq", "model": "llama-3.1-8b-instant", "temperature": 0.0},
    "intent_router_chat": {"provider": "groq", "model": "llama-3.3-70b-versatile", "temperature": 0.4},
    "elicitation_extract": {"provider": "groq", "model": "llama-3.1-8b-instant", "temperature": 0.1},
    "elicitation_chat": {"provider": "groq", "model": "llama-3.3-70b-versatile", "temperature": 0.4},
    "planner": {"provider": "groq", "model": "llama-3.3-70b-versatile", "temperature": 0.2},
    "listing_agent": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.1},
    "reducer": {"provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.3},
    "analyzer": {"provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.3},
    "photo_vision": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2},
}

_OVERRIDE_ENV = "RENTAL_MODELS"
# Fallback model map when provider is forced to openai but default was groq/anthropic
_OPENAI_ROLE_MODELS = {
    "intent_router_classify": "gpt-4o-mini",
    "intent_router_chat": "gpt-4o",
    "elicitation_extract": "gpt-4o-mini",
    "elicitation_chat": "gpt-4o",
    "planner": "gpt-4o-mini",
    "listing_agent": "gpt-4o-mini",
    "reducer": "gpt-4o-mini",
    "analyzer": "gpt-4o-mini",
    "photo_vision": "gpt-4o-mini",
}


def _valid_key(name: str) -> bool:
    key = (os.getenv(name) or "").strip()
    if not key:
        return False
    lowered = key.lower()
    invalid_markers = ("your_", "placeholder", "changeme", "replace")
    return not any(marker in lowered for marker in invalid_markers)


def _is_rate_limit_error(exc: Exception) -> bool:
    if groq is not None and isinstance(exc, groq.RateLimitError):
        return True
    if _openai_mod is not None and isinstance(exc, _openai_mod.RateLimitError):
        return True
    status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status_code == 429:
        return True
    message = str(exc).lower()
    return "rate limit" in message or "too many requests" in message


def _load_role_overrides() -> dict:
    raw = os.getenv(_OVERRIDE_ENV, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve_role_config(role: str) -> dict:
    base = dict(ROLE_DEFAULTS.get(role, {}))
    if not base:
        raise KeyError(f"Unknown LLM role: {role}")

    # photo_vision and listing_agent are pinned to openai (need vision / specific model)
    if role not in ("photo_vision", "listing_agent"):
        base["provider"] = os.getenv("LLM_PROVIDER", base["provider"]).strip().lower()

    overrides = _load_role_overrides().get(role)
    if isinstance(overrides, str):
        base["model"] = overrides
    elif isinstance(overrides, dict):
        base.update(overrides)

    # Roles that skip Groq in the fallback chain (anthropic -> openai directly)
    _ANTHROPIC_OPENAI_ONLY = {"reducer", "analyzer"}

    if base["provider"] == "anthropic" and not _valid_key("ANTHROPIC_API_KEY"):
        base["provider"] = "openai" if role in _ANTHROPIC_OPENAI_ONLY else "groq"
    if base["provider"] == "openai" and not _valid_key("OPENAI_API_KEY") and role not in _ANTHROPIC_OPENAI_ONLY:
        base["provider"] = "groq"
    if base["provider"] == "groq" and not _valid_key("GROQ_API_KEY"):
        base["provider"] = "openai"

    # If provider doesn't match the model family, swap to the right model
    model = str(base.get("model", ""))
    if base["provider"] == "openai" and (model.startswith("llama") or model.startswith("claude")):
        base["model"] = _OPENAI_ROLE_MODELS[role]
    if base["provider"] == "groq" and model.startswith("claude"):
        base["model"] = "llama-3.3-70b-versatile"

    return base


def _create_model(provider: str, model: str, temperature: float):
    provider = provider.lower()
    if provider == "anthropic":
        if not _valid_key("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY is missing or invalid.")
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
    if provider == "openai":
        if not _valid_key("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is missing or invalid.")
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    if provider == "groq":
        if not _valid_key("GROQ_API_KEY"):
            raise ValueError("GROQ_API_KEY is missing or invalid.")
        return ChatGroq(
            model=model,
            temperature=temperature,
            api_key=os.getenv("GROQ_API_KEY"),
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")


def make_llm(role: str):
    cfg = _resolve_role_config(role)
    return _create_model(cfg["provider"], cfg["model"], cfg["temperature"]).with_retry(
        retry_if_exception_type=(Exception,),
        wait_exponential_jitter=True,
        stop_after_attempt=6,
    )


class _RetryableMixin:
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        for attempt in range(6):
            try:
                return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except Exception as e:
                is_rate_limit = _is_rate_limit_error(e)
                if not is_rate_limit or attempt == 5:
                    try:
                        if run_manager:
                            await run_manager.on_custom_event("error_log", {
                                "node": "llm",
                                "error": f"{type(e).__name__} (attempt {attempt + 1}/6): {str(e)[:300]}",
                                "level": "error",
                            })
                    except Exception:
                        pass
                    raise
                wait = min(4 * (2 ** attempt), 60)
                try:
                    if run_manager:
                        await run_manager.on_custom_event("rate_limit_wait", {"wait": wait})
                        await run_manager.on_custom_event("error_log", {
                            "node": "llm",
                            "error": f"Rate limit (attempt {attempt + 1}/6) — retrying in {wait}s: {str(e)[:200]}",
                            "level": "warn",
                        })
                except Exception:
                    pass
                await asyncio.sleep(wait)


class _RetryableAnthropicLLM(_RetryableMixin, ChatAnthropic):
    pass


class _RetryableOpenAILLM(_RetryableMixin, ChatOpenAI):
    pass


class _RetryableGroqLLM(_RetryableMixin, ChatGroq):
    pass


def make_base_llm(role: str):
    cfg = _resolve_role_config(role)
    if cfg["provider"] == "anthropic":
        if not _valid_key("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY is missing or invalid.")
        return _RetryableAnthropicLLM(
            model=cfg["model"],
            temperature=cfg["temperature"],
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
    if cfg["provider"] == "openai":
        if not _valid_key("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is missing or invalid.")
        return _RetryableOpenAILLM(
            model=cfg["model"],
            temperature=cfg["temperature"],
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    if cfg["provider"] == "groq":
        if not _valid_key("GROQ_API_KEY"):
            raise ValueError("GROQ_API_KEY is missing or invalid.")
        return _RetryableGroqLLM(
            model=cfg["model"],
            temperature=cfg["temperature"],
            api_key=os.getenv("GROQ_API_KEY"),
        )
    raise ValueError(f"Unsupported LLM provider for base model: {cfg['provider']}")
