import asyncio
import anthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import adispatch_custom_event

RETRY_KWARGS = dict(
    retry_if_exception_type=(anthropic.RateLimitError, anthropic.APIStatusError),
    wait_exponential_jitter=True,
    stop_after_attempt=6,
)


def make_llm(model: str, temperature: float) -> ChatAnthropic:
    return ChatAnthropic(model=model, temperature=temperature).with_retry(**RETRY_KWARGS)


class _RetryableLLM(ChatAnthropic):
    """
    ChatAnthropic subclass that retries rate limit errors at the individual LLM call level
    (so the agent continues mid-stream rather than restarting), and dispatches a custom
    event so the UI can show the waiting state.
    """
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        for attempt in range(6):
            try:
                return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except (anthropic.RateLimitError, anthropic.APIStatusError):
                if attempt == 5:
                    raise
                wait = min(4 * (2 ** attempt), 60)
                try:
                    await adispatch_custom_event("rate_limit_wait", {"wait": wait})
                except Exception:
                    pass
                await asyncio.sleep(wait)


def make_base_llm(model: str, temperature: float) -> ChatAnthropic:
    """LLM for use with create_react_agent. Retries at the LLM call level so the agent
    continues mid-stream, and dispatches events for UI rate limit feedback."""
    return _RetryableLLM(model=model, temperature=temperature)
