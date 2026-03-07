# Bare-Metal Agents & MCP — Implementation Guide

> **Goal:** Build a raw agent loop and a bare MCP server from scratch in Python. No frameworks, no MCP SDK — just the protocol.
>
> **Runtime:** Any terminal with Python 3.12+
> **Language:** Python
> **Estimated time:** 4–6 hours

---

## 1. What You Will Build

Two things, from scratch:

1. **A raw agent loop** that calls the Anthropic Messages API directly, sends tool definitions, receives `tool_use` blocks, executes tools locally, and feeds results back in a loop until the model produces a final text response.

2. **A bare MCP server** that implements the Model Context Protocol over stdio transport using JSON-RPC 2.0, exposing tools, resources, and prompts that your agent (or Claude Code) can discover and call at runtime.

By the end, you will have a working system where your agent discovers tools from your MCP server, the user asks a question, the model decides which tools to call, your code executes them, and the loop continues until the task is done. No frameworks, no magic — just the raw protocol.

---

## 2. Architecture Overview

The system has three layers.

### 2.1 The Agent Loop (`agent.py`)

The agent loop is the orchestrator. It is a `while`-loop that repeatedly calls the Anthropic Messages API. On each iteration it checks whether the model's response contains `tool_use` content blocks. If it does, the loop executes those tools, appends the tool results as `tool_result` content blocks in the next user message, and calls the API again. The loop exits when the model returns only text blocks (i.e., a final answer). This is the fundamental pattern behind every AI agent.

### 2.2 The MCP Server (`server.py`)

The MCP server is a separate process that speaks the Model Context Protocol. MCP is an open protocol published by Anthropic that standardizes how AI applications discover and invoke external tools, read resources, and use prompt templates. The transport layer is JSON-RPC 2.0 messages over stdio (stdin/stdout). Your server will handle the `initialize` handshake, respond to `tools/list` and `tools/call` requests, and optionally serve resources via `resources/list` and `resources/read`.

### 2.3 The Bridge (how they connect)

Your agent spawns the MCP server as a child process. On startup, it performs the MCP `initialize` handshake, then calls `tools/list` to discover available tools. It converts those MCP tool definitions into the Anthropic API's tool schema format and passes them to the Messages API. When the model returns a `tool_use` block, the agent calls `tools/call` on the MCP server via JSON-RPC over stdio, gets the result, and feeds it back into the loop.

---

## 3. Key Concepts

### 3.1 The Anthropic Messages API Tool Use Contract

When you send a request to `POST /v1/messages` with a `tools` array, the model may respond with a `stop_reason` of `"tool_use"`. The response `content` array will contain one or more blocks with `type: "tool_use"`, each having an `id`, `name`, and `input` object. Your code must execute the tool, then send a new request where the conversation includes a user message containing a content block with `type: "tool_result"`, the matching `tool_use_id`, and the result content. The model then continues reasoning with the tool output.

### 3.2 MCP Protocol Lifecycle

MCP uses JSON-RPC 2.0. Every message is a JSON object with `jsonrpc: "2.0"`. Requests have a `method` and `id` field; responses match the `id`. Notifications have a `method` but no `id`. The lifecycle is:

1. Client sends `initialize` with its `protocolVersion` and `capabilities`.
2. Server responds with its `protocolVersion`, `capabilities` (e.g., which primitives it supports), and `serverInfo`.
3. Client sends `initialized` notification (no `id`) to confirm.
4. Client can now call `tools/list`, `resources/list`, `prompts/list`, and their corresponding execution methods.

### 3.3 MCP Primitives

| Primitive | Description |
|-----------|-------------|
| **Tools** | Functions the model can call. Defined with a `name`, `description`, and JSON Schema for the input. Invoked via `tools/call`. This is the most important primitive for agents. |
| **Resources** | Read-only data the client can fetch. Think of them as files or API responses. Listed via `resources/list`, read via `resources/read`. Each has a URI. |
| **Prompts** | Reusable prompt templates with arguments. Listed via `prompts/list`, retrieved via `prompts/get`. Useful for providing structured workflows. |

---

## 4. Project Structure

```
bare-agents-mcp/
├── pyproject.toml
├── environment.yml
├── Dockerfile
├── docker-compose.yml
├── src/
│   ├── __init__.py
│   ├── agent.py          # The raw agent loop (Anthropic)
│   ├── agent_ollama.py   # The raw agent loop (local Ollama)
│   ├── mcp_client.py     # Minimal MCP client (stdio transport)
│   ├── server.py         # Your MCP server
│   └── tools/
│       ├── __init__.py   # Tool registry with @register_tool decorator
│       ├── filesystem.py # File read/write/list tools
│       └── notes.py      # In-memory notes CRUD
└── tests/
    └── unit/
        ├── test_tools_registry.py
        ├── test_server.py
        └── test_agent.py
```

---

## 5. Step-by-Step Implementation

### 5.1 Scaffold the Project

```bash
mkdir bare-agents-mcp && cd bare-agents-mcp
```

Create `pyproject.toml`:
```toml
[project]
name = "bare-agents-mcp"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["anthropic", "structlog"]

[project.optional-dependencies]
dev = ["ruff", "pytest", "mypy"]
```

Install:
```bash
pip install -e ".[dev]"
```

You are intentionally **not** installing the MCP SDK. The goal is to implement the MCP protocol by hand so you understand the JSON-RPC messages. After completing this project, you can optionally refactor to use an MCP SDK to see how it abstracts these details.

### 5.2 Build the MCP Server (`server.py`)

The server reads JSON-RPC messages from stdin (newline-delimited) and writes responses to stdout. Implement these handlers:

#### 5.2.1 Message framing

MCP over stdio uses newline-delimited JSON. Each message is one line of JSON followed by a newline. Read stdin line by line, `json.loads()` each line, and dispatch based on the `method` field.

#### 5.2.2 Initialize handshake

When you receive a request with `method: "initialize"`, respond with:

```json
{
  "jsonrpc": "2.0",
  "id": "<matching id>",
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": { "tools": {} },
    "serverInfo": { "name": "bare-mcp", "version": "1.0.0" }
  }
}
```

Then expect an `"initialized"` notification (no `id`). After this, the connection is live.

#### 5.2.3 `tools/list`

Return an array of tool definitions. Each tool has a `name` (string), `description` (string), and `inputSchema` (a JSON Schema object defining the tool's parameters). Example:

```json
{
  "name": "read_file",
  "description": "Read the contents of a file at the given path.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": { "type": "string", "description": "Absolute file path" }
    },
    "required": ["path"]
  }
}
```

#### 5.2.4 `tools/call`

Receives `{ name, arguments }` in `params`. Execute the tool logic, then return:

```json
{
  "jsonrpc": "2.0",
  "id": "<id>",
  "result": {
    "content": [
      { "type": "text", "text": "<tool output here>" }
    ]
  }
}
```

If the tool fails, return `isError: true` in the result alongside the error content.

#### 5.2.5 Suggested tools to implement

Start with these to keep the scope manageable:

| Tool | Why It's Instructive |
|------|---------------------|
| `read_file` | Simplest possible tool. One input, synchronous, returns text. |
| `write_file` | Side-effect tool. Takes path + content. Teaches error handling. |
| `list_directory` | Returns structured data (array of filenames). |
| `create_note` / `list_notes` | In-memory state. Shows that MCP servers can be stateful. |
| `search_notes` | Takes a query, filters in-memory data. Shows non-trivial logic. |

---

### 5.3 Build the MCP Client (`mcp_client.py`)

This module spawns the server as a child process and provides an async interface over stdio. Key design decisions:

- Use `asyncio.create_subprocess_exec()` to start the server (e.g., `python -m src.server`).
- Maintain a pending requests map: `dict[int, asyncio.Future]`. Assign incrementing IDs to each outgoing request.
- Read stdout line-by-line. For each parsed JSON message, check if it has an `id` (response) or `method` (notification/request from server). Route responses to the matching pending future.
- Implement methods: `initialize()`, `list_tools()`, `call_tool(name, args)`, and `close()`.

The `initialize()` method should send the `initialize` request, wait for the response, then send the `initialized` notification. After that, the client is ready.

---

### 5.4 Build the Agent Loop (`agent.py`)

This is the heart of the project. Here is the algorithm:

```
1. Spawn MCP server via McpClient
2. Call client.initialize()
3. Call client.list_tools() → mcp_tools
4. Convert mcp_tools to Anthropic tool format:
     { name, description, input_schema: tool["inputSchema"] }
5. messages = [{ "role": "user", "content": user_query }]
6. LOOP (with max iteration guard):
     response = anthropic.messages.create(
       model="claude-sonnet-4-20250514",
       max_tokens=4096,
       tools=anthropic_tools,
       messages=messages
     )
     IF response.stop_reason == "end_turn":
       print final text, break
     IF response.stop_reason == "tool_use":
       FOR each tool_use block in response.content:
         result = client.call_tool(block.name, block.input)
         collect tool_result blocks
       APPEND assistant message (full response.content)
       APPEND user message with tool_result blocks
       CONTINUE loop
```

**Critical detail:** when the model returns a mix of text and `tool_use` blocks, you must append the **entire** `response.content` array as the assistant message (not just the tool_use blocks). Then append a single user message whose content is an array of all the `tool_result` blocks. Each `tool_result` must include the `tool_use_id` from the corresponding `tool_use` block.

---

## 6. Testing & Debugging

### 6.1 Test the MCP server in isolation

Before connecting the agent, test your server by piping JSON-RPC messages directly:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}' | python -m src.server
```

You should see the initialize response on stdout.

### 6.2 Inspect the MCP traffic

Add a debug flag to your MCP client that logs every JSON-RPC message sent and received (to stderr or a log file). This is the single most valuable debugging technique. When something goes wrong, the raw messages tell you exactly where the protocol contract is broken.

### 6.3 Test the agent loop without MCP

To isolate the agent loop, temporarily hardcode tools directly in `agent.py` (bypassing MCP) and use a simple if/elif to execute them. This lets you verify the Anthropic API `tool_use`/`tool_result` loop works correctly before adding MCP transport complexity.

### 6.4 Unit tests

Run the unit test suite:

```bash
pytest tests/unit -v
```

Tests cover the tool registry, server JSON-RPC dispatch, and schema conversion — all without network calls or subprocesses.

---

## 7. Extension Ideas

Once the core system works, deepen your understanding:

- **Add resources:** Implement `resources/list` and `resources/read`. Serve a config file or a database summary. Your agent can read resources to give the model extra context before tool calling.
- **Add prompts:** Implement `prompts/list` and `prompts/get`. Create a "summarize-file" prompt template that takes a file path argument and returns a pre-structured user message.
- **Multi-server agent:** Modify your agent to spawn multiple MCP servers, merge their tool lists, and route `tools/call` requests to the correct server based on tool name.
- **SSE transport:** Replace stdio with HTTP + Server-Sent Events (Streamable HTTP transport). The MCP spec defines this as the other standard transport. This teaches you how remote MCP servers work.
- **Streaming responses:** Use the Anthropic streaming API (`stream=True`) to display the model's text output in real time while still handling `tool_use` events.
- **Guardrails:** Add a confirmation step before executing destructive tools (`write_file`, `delete_file`). This mirrors how Claude Code handles tool approval and teaches human-in-the-loop patterns. **Note:** the filesystem tools currently have no sandboxing — `read_file` and `write_file` can access any path on the system. Adding path restrictions is a good security exercise.
- **Local LLM support:** Use `agent_ollama.py` to run the same agent loop against a local Ollama instance. The MCP server and tools are identical — only the LLM client changes. See the included implementation for details.

---

## 8. What You Should Understand After This Project

- The agent loop is just a while-loop that calls an LLM API, checks for `tool_use`, executes tools, and feeds results back. There is no magic.
- MCP is JSON-RPC 2.0 over a transport. The protocol has an `initialize` handshake, then request/response pairs for listing and calling tools, resources, and prompts.
- The Anthropic tool use contract requires you to send `tool_result` blocks with matching `tool_use_id` values. Getting this wrong is the most common source of bugs.
- MCP servers are just processes that speak a protocol. They can be written in any language. The stdio transport means the server's stdin/stdout IS the protocol channel, and stderr is free for logging.
- The conversion from MCP tool schemas to Anthropic API tool schemas is nearly 1:1. MCP uses `inputSchema`; the Anthropic API uses `input_schema`. The JSON Schema content is identical.
- Claude Code itself uses this exact architecture: it spawns MCP servers, discovers tools, and feeds them to the model in an agent loop. You have now built a simplified version of the same system.

---

## Appendix A: MCP Protocol Quick Reference

| Method | Direction & Purpose |
|--------|-------------------|
| `initialize` | Client → Server. Handshake. Return protocol version + capabilities. |
| `initialized` | Client → Server. Notification (no response). Confirms handshake. |
| `tools/list` | Client → Server. Return array of tool definitions with JSON Schema. |
| `tools/call` | Client → Server. Execute a tool. Params: `{ name, arguments }`. |
| `resources/list` | Client → Server. (Extension) Return array of available resources. |
| `resources/read` | Client → Server. (Extension) Return resource content by URI. |
| `prompts/list` | Client → Server. (Extension) Return array of prompt templates. |
| `prompts/get` | Client → Server. (Extension) Return a prompt with filled arguments. |

## Appendix B: Anthropic API Tool Use Message Structure

### Sending tools to the API

```python
tools = [{
    "name": "read_file",
    "description": "Read a file.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}]
```

### Model returns `tool_use`

```python
# response.content includes a block with:
# block.type == "tool_use"
# block.id == "toolu_01A..."
# block.name == "read_file"
# block.input == {"path": "/tmp/test.txt"}
```

### You send `tool_result` back

```python
# Next user message content includes:
{
    "type": "tool_result",
    "tool_use_id": "toolu_01A...",
    "content": "File contents here...",
}
```

## Appendix C: References

- MCP Specification: https://modelcontextprotocol.io/specification
- Anthropic Messages API — Tool Use: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview
- MCP Python SDK (for later refactoring): https://github.com/modelcontextprotocol/python-sdk
