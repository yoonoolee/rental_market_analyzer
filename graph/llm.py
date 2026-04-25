import anthropic
from langchain_anthropic import ChatAnthropic

RETRY_KWARGS = dict(
    retry_if_exception_type=(anthropic.RateLimitError,),
    wait_exponential_jitter=True,
    stop_after_attempt=6,
)


def make_llm(model: str, temperature: float) -> ChatAnthropic:
    return ChatAnthropic(model=model, temperature=temperature).with_retry(**RETRY_KWARGS)


def make_base_llm(model: str, temperature: float) -> ChatAnthropic:
    """Raw LLM without retry wrapping — use where bind_tools is needed (e.g. create_react_agent)."""
    return ChatAnthropic(model=model, temperature=temperature)
