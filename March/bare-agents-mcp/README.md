# bare-agents-mcp

A from-scratch implementation of a raw agent loop and a bare MCP (Model Context Protocol) server in Python. No frameworks, no MCP SDK — just the protocol.

See [AGENTS_PROJECT.md](../AGENTS_PROJECT.md) for the full implementation guide.

## How It Works (End-to-End)

When you run the agent, this is what happens step by step:

```
┌──────────┐         ┌────────────┐        ┌────────────┐        ┌───────────┐
│  You     │         │  Agent     │        │ MCP Client │        │MCP Server │
│ (query)  │         │  Loop      │        │ (stdio)    │        │ + Tools   │
└────┬─────┘         └─────┬──────┘        └─────┬──────┘        └─────┬─────┘
     │  "List files in ."  │                     │                     │
     │────────────────────►│                     │                     │
     │                     │  spawn subprocess   │                     │
     │                     │────────────────────►│  stdin/stdout pipes │
     │                     │                     │────────────────────►│
     │                     │                     │  initialize (JSON-RPC)
     │                     │                     │────────────────────►│
     │                     │                     │  { capabilities }   │
     │                     │                     │◄────────────────────│
     │                     │                     │  tools/list         │
     │                     │                     │────────────────────►│
     │                     │                     │  [read_file, ...]   │
     │                     │                     │◄────────────────────│
     │                     │  convert schemas    │                     │
     │                     │  MCP → Anthropic    │                     │
     │                     │                     │                     │
     │                     │  POST /v1/messages  │                     │
     │                     │  (query + tools) ──────────────► Claude API
     │                     │                     │                     │
     │                     │  ◄── tool_use: list_directory(".")        │
     │                     │                     │                     │
     │                     │  tools/call         │                     │
     │                     │────────────────────►│  tools/call         │
     │                     │                     │────────────────────►│
     │                     │                     │  execute tool       │
     │                     │                     │  Path(".").iterdir()│
     │                     │                     │◄────────────────────│
     │                     │  ◄── result JSON    │                     │
     │                     │                     │                     │
     │                     │  POST /v1/messages  │                     │
     │                     │  (tool_result) ───────────────► Claude API
     │                     │                     │                     │
     │                     │  ◄── end_turn: "Here are the files..."   │
     │  "Here are the      │                     │                     │
     │   files: ..."       │                     │                     │
     │◄────────────────────│                     │                     │
```

### The Agent Loop (core algorithm)

```
1. Spawn MCP server as child process (stdin/stdout pipes)
2. JSON-RPC handshake: initialize → initialized
3. Discover tools: tools/list → convert to LLM's schema format
4. Send user query + tool definitions to LLM API
5. LOOP:
   a. If LLM returns end_turn → print text, done
   b. If LLM returns tool_use →
      - Execute each tool via MCP (tools/call over JSON-RPC)
      - Append tool_result to conversation
      - Call LLM again with updated conversation
      - Go to 5
6. Close MCP server subprocess
```

The loop runs until the model produces a final text answer (no more tool calls) or hits the max iteration limit (default 20).

### What Makes This "Bare Metal"

- **No MCP SDK** — the JSON-RPC 2.0 protocol is implemented by hand in `mcp_client.py` and `server.py`
- **No agent framework** — the agent loop is a plain `while` loop in `agent.py`
- **No magic** — every message between components is a JSON object you can log and inspect

## Setup

### Option A: Conda (recommended)

```bash
conda env create -f environment.yml
conda activate bare-agents-mcp
pip install -e ".[dev]"
```

### Option B: pip only

```bash
pip install -e ".[dev]"
```

Requires Python 3.12+.

## Running the Agent

### With Claude (Anthropic API)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."

# Pass query as argument
python -m src.agent "List all files in the current directory"

# Or interactive mode (prompts for input)
python -m src.agent
```

**What you'll see:** The agent logs each loop iteration and tool call to stderr, and prints the final answer to stdout.

Example session:

```
$ python -m src.agent "Create a note about Python, then list all notes"

[stderr] agent_ready              tools=['read_file', 'write_file', 'list_directory', 'create_note', 'list_notes', 'search_notes']
[stderr] loop_iteration           n=1
[stderr] api_response             stop_reason=tool_use content_types=['text', 'tool_use']
[stderr] executing_tool           tool=create_note input={'title': 'Python', 'content': 'Python is a versatile programming language...'}
[stderr] tool_result              tool=create_note result=Created note #1: Python
[stderr] loop_iteration           n=2
[stderr] api_response             stop_reason=tool_use content_types=['text', 'tool_use']
[stderr] executing_tool           tool=list_notes input={}
[stderr] tool_result              tool=list_notes result=[{"id": 1, "title": "Python", ...}]
[stderr] loop_iteration           n=3
[stderr] api_response             stop_reason=end_turn content_types=['text']

I created a note about Python and then listed all notes. Here's what's stored:

1. **Python** (Note #1): Python is a versatile programming language...
```

### With Ollama (local LLM)

```bash
# Pull a model with tool-use support
ollama pull qwen2.5

# Run
python -m src.agent_ollama "Read the file pyproject.toml"
```

The MCP server and tools are identical — only the LLM client changes.

## Testing the MCP Server in Isolation

You can pipe JSON-RPC messages directly to the server to inspect the protocol:

```bash
# Initialize handshake
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}' | python -m src.server

# You'll see the server's response on stdout:
# {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "bare-mcp", "version": "1.0.0"}}}
```

To send multiple messages, use a heredoc:

```bash
python -m src.server <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}
{"jsonrpc":"2.0","method":"initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"create_note","arguments":{"title":"Test","content":"Hello world"}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"list_notes","arguments":{}}}
EOF
```

## Running with Docker

```bash
# Interactive MCP server testing
docker-compose run mcp-server

# Run agent (pass your API key)
ANTHROPIC_API_KEY=sk-ant-... docker-compose up agent
```

Note: the agent container spawns its own MCP server subprocess internally — the `mcp-server` service is only for manual protocol testing.

## Development

```bash
# Run tests (28 tests)
pytest tests/unit -v

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check (strict mode)
mypy src/ --strict
```

## Architecture

```
agent.py / agent_ollama.py
  │
  │  Calls LLM API (Anthropic or Ollama)
  │  Detects tool_use in response
  │  Feeds tool_result back to LLM
  │
  ▼
mcp_client.py
  │
  │  Spawns server as subprocess
  │  JSON-RPC 2.0 over stdin/stdout
  │  Future-based request/response correlation
  │
  ▼
server.py
  │
  │  Reads JSON-RPC from stdin
  │  Dispatches: initialize, tools/list, tools/call
  │  Writes JSON-RPC responses to stdout
  │
  ▼
tools/__init__.py          ← @register_tool decorator + registry
├── tools/filesystem.py    ← read_file, write_file, list_directory (sandboxed)
└── tools/notes.py         ← create_note, list_notes, search_notes (in-memory)
```

### Key design: the MCP layer is LLM-agnostic

The MCP server, client, and tools know nothing about which LLM is being used. The only LLM-specific code is the schema conversion:

- `agent.py`: `inputSchema` → `input_schema` (Anthropic format)
- `agent_ollama.py`: `inputSchema` → `{ type: "function", function: { parameters } }` (OpenAI format)

Everything below the agent loop is universal.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required for `agent.py` |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Model to use with Anthropic |
| `AGENT_MAX_TOKENS` | `4096` | Max tokens per LLM response |
| `AGENT_MAX_ITERATIONS` | `20` | Max agent loop iterations |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5` | Model to use with Ollama |
| `SANDBOX_ROOT` | `.` (cwd) | Root directory for filesystem tools |
| `MAX_FILE_SIZE` | `10485760` (10 MB) | Max file size for `read_file` |

## Security

Filesystem tools are sandboxed to `SANDBOX_ROOT`. All paths are resolved and validated — attempts to read/write outside the sandbox (e.g., `../../etc/passwd`) are rejected with `PermissionError`. File reads are capped at `MAX_FILE_SIZE` to prevent memory exhaustion.
