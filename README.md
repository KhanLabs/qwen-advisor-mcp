# qwen-advisor-mcp

An MCP server that lets Claude Code ask another AI, Qwen (through Alibaba Cloud), for a second opinion partway through a task, instead of only checking its own work. It remembers past questions for each project, so Qwen does not start from nothing every time.

## Setup

1. Create a virtual environment and install the dependencies:

   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

2. Get a DashScope API key from the **international (Singapore)** region at
   https://modelstudio.console.alibabacloud.com/. This region has the free trial
   quota for `qwen3.8-max`.

3. Copy `.env.example` to `.env` and put your key in it. `.env` is in `.gitignore`, so
   it is never committed. You only need this for testing on your own; step 4 gives the
   key to Claude Code directly.

4. Register the server with Claude Code so it is available in every project. Replace
   `<repo>` with the full path to where you cloned this repo:

   ```
   claude mcp add --scope user qwen-advisor --env DASHSCOPE_API_KEY=<your key> -- "<repo>\.venv\Scripts\python.exe" "<repo>\qwen_advisor_mcp\server.py"
   ```

   Restart Claude Code afterwards so it picks up the new server.

The commands above are for Windows. On macOS or Linux, use `.venv/bin/pip` and
`.venv/bin/python` instead.

## How it works

- `consult_qwen(question, context, project_id)` is the only tool. Claude Code calls it
  with a short summary of what is going on and a specific question.
- Each project's history is saved in `~/.qwen-advisor/sessions/<project_id>.json`. It
  keeps only the last 12 questions and answers, so a long project does not use up your
  free token quota.
- Errors (missing key, DashScope API failures, a damaged history file) are returned as
  plain text through the tool instead of crashing the server.

## Testing it

Once `.env` has a real key, you can check it works without Claude Code:

```
.venv\Scripts\python -c "from qwen_advisor_mcp.qwen_client import ask_qwen; print(ask_qwen([{'role': 'user', 'content': 'Say hi in five words.'}]))"
```

If that prints a reply, the key and endpoint are working. The full test is registering
the server (step 4) and calling `consult_qwen` from a Claude Code session.

## Troubleshooting

**Problem:** `consult_qwen` keeps timing out after about 480 seconds (the default
240-second `QWEN_TIMEOUT_SECONDS`, tried twice because of `QWEN_MAX_RETRIES`), with
`QwenClientError: Qwen request timed out after ...`.

**Cause:** this happens with the international (Singapore) endpoint. DashScope's
dashboard shows the request finishing in about 200 seconds, but the answer never
reaches the client. It is a problem with that endpoint, not with this code. The
timeout is kept well below Claude Code's own limit for stuck tools, so a stuck request
fails with a clear error instead of hanging.

**Fix:** use the mainland endpoint, which has worked reliably with the same key:

```
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

If you registered the server with `claude mcp add` (step 4), change it there. Editing
`.env` does not affect a server that is already registered, because its settings are
saved when you register it:

```
claude mcp remove qwen-advisor -s user
claude mcp add qwen-advisor -s user -e DASHSCOPE_API_KEY=<your key> -e QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 -- "<repo>\.venv\Scripts\python.exe" "<repo>\qwen_advisor_mcp\server.py"
```

## Privacy

Everything Claude Code passes in `question` and `context` is sent to Alibaba Cloud's
DashScope API. Do not include passwords, keys or other private data in what it sends.

## License

MIT. See [LICENSE](LICENSE).
