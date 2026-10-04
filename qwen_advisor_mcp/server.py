"""MCP server exposing a single `consult_qwen` tool for Claude Code.

Run directly (stdio transport, what `claude mcp add` expects):

    python qwen_advisor_mcp/server.py

Or via the MCP inspector for local testing:

    python -m mcp dev qwen_advisor_mcp/server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python path/to/qwen_advisor_mcp/server.py` to resolve absolute
# imports of its own package (the script's own dir, not its parent, is
# what Python puts on sys.path by default).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer

from qwen_advisor_mcp.qwen_client import SYSTEM_PROMPT, QwenClientError, ask_qwen
from qwen_advisor_mcp.store import append_exchange, load_history

mcp = MCPServer("qwen-advisor")


@mcp.tool()
def consult_qwen(question: str, context: str = "", project_id: str = "default") -> str:
    """Ask Qwen3.8 for a second opinion or sanity check.

    Use this when facing a genuinely uncertain design decision, before
    committing to a risky or hard-to-reverse implementation choice, or
    when the user explicitly asks to check with Qwen. `context` should be
    a concise summary of relevant recent work or decisions — Qwen only
    sees what's passed here plus its own memory of past consultations for
    this project, not the rest of the conversation. `project_id` should
    identify the current project (e.g. its folder name) so history stays
    separate per project.
    """
    history = load_history(project_id)
    user_turn = f"Context: {context}\n\nQuestion: {question}" if context else question
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_turn},
    ]

    try:
        reply = ask_qwen(messages)
    except QwenClientError as exc:
        return f"Error consulting Qwen: {exc}"

    append_exchange(project_id, user_turn, reply)
    return reply


if __name__ == "__main__":
    mcp.run()
