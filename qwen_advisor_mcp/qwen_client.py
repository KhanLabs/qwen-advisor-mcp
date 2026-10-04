"""Thin wrapper around Qwen's DashScope OpenAI-compatible endpoint."""

from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from openai import APITimeoutError, OpenAI, OpenAIError

load_dotenv()

logger = logging.getLogger("qwen_advisor_mcp")
if not logger.handlers:
    # stderr only -- stdout is the MCP JSON-RPC channel, writing there would
    # corrupt the protocol stream.
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[qwen-advisor] %(asctime)s %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

_DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "qwen3.8-max"

# The openai SDK's own defaults are a 600s read timeout with 2 automatic
# retries -- worst case ~1800s of total silence on the wire before it gives
# up, which is exactly the idle-timeout window Claude Code's MCP harness
# uses to decide a tool has hung and abort it with no useful error surfaced.
# Observed failure mode against the intl/Singapore endpoint: DashScope's own
# dashboard shows the request completing server-side in ~200s, but the
# response never arrives back at this client -- the read just stalls. Keep
# our own ceiling comfortably under that 1800s harness timeout so a stuck
# request fails fast with a real, catchable error instead of hanging until
# something external kills it.
_DEFAULT_TIMEOUT_SECONDS = 240.0
_DEFAULT_MAX_RETRIES = 1

SYSTEM_PROMPT = (
    "You are Qwen, acting as an advisor to Claude Code (an autonomous coding "
    "agent) and the developer it's working with. You will receive a summary "
    "of what they're currently doing plus a specific question. You are not "
    "executing anything yourself — give direct, concise, practical advice. "
    "Flag risks, tradeoffs, or better approaches when relevant. If the "
    "context is insufficient to answer well, say what's missing instead of "
    "guessing."
)


class QwenClientError(RuntimeError):
    """Raised when the Qwen client can't produce an advisory reply."""


def ask_qwen(messages: list[dict[str, str]]) -> str:
    """Send the full message list (system + history + new turn) to Qwen.

    Returns the assistant reply text. Raises QwenClientError with a clear,
    user-facing message on any failure (missing key, API error, empty
    response) so the caller can surface it as tool output instead of crashing.
    """
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise QwenClientError(
            "DASHSCOPE_API_KEY is not set. Add it to .env or to this MCP "
            "server's registered environment."
        )

    base_url = os.environ.get("QWEN_BASE_URL", _DEFAULT_BASE_URL)
    model = os.environ.get("QWEN_MODEL", _DEFAULT_MODEL)
    timeout = float(os.environ.get("QWEN_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS))
    max_retries = int(os.environ.get("QWEN_MAX_RETRIES", _DEFAULT_MAX_RETRIES))

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
    )

    started = time.monotonic()
    logger.info(
        "requesting model=%s timeout=%ss max_retries=%s messages=%d",
        model, timeout, max_retries, len(messages),
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
    except APITimeoutError as exc:
        elapsed = time.monotonic() - started
        logger.warning("timed out after %.1fs (budget was ~%.0fs across retries)", elapsed, timeout * (max_retries + 1))
        raise QwenClientError(
            f"Qwen request timed out after {elapsed:.0f}s. The API/network path "
            "may be degraded right now -- safe to retry."
        ) from exc
    except OpenAIError as exc:
        elapsed = time.monotonic() - started
        logger.warning("failed after %.1fs: %s", elapsed, exc)
        raise QwenClientError(f"Qwen API error: {exc}") from exc

    elapsed = time.monotonic() - started
    logger.info("responded in %.1fs", elapsed)

    choice = response.choices[0] if response.choices else None
    content = choice.message.content if choice and choice.message else None
    if not content:
        raise QwenClientError("Qwen returned an empty response.")

    return content


__all__ = ["QwenClientError", "SYSTEM_PROMPT", "ask_qwen"]
