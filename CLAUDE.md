# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Obsidian-Claude Automation Agent** - A Python tool that automatically processes natural language requests embedded in Obsidian notes using Claude AI via the Obsidian MCP (Model Context Protocol) server.

**Key Workflow:**
1. Scans Obsidian vault for notes containing `@claude` requests (via MCP search)
2. Reads note content and parses first unprocessed request
3. Checks if request was already processed (deduplication)
4. Enforces rate limits (configurable requests per hour)
5. Sends request to Claude AI with restricted tool permissions
6. Creates timestamped response note with Claude's reply
7. Updates source note: `@claude` → `@claude-done` with wikilink to response
8. Records processed request in state file
9. Sends desktop notification with results
10. Designed to run as scheduled background task (cron/systemd/Task Scheduler)

**Python Version:** 3.10+ required (project may run on 3.9.6 but not officially supported)

## Dependencies

**Core Requirements (requirements.txt):**
```
anthropic>=0.18.0      # Claude API client
pyyaml>=6.0            # Configuration file parsing
python-dateutil>=2.8.2 # Date/time utilities
plyer>=2.1.0           # Desktop notifications
mcp>=1.0.0             # MCP Python SDK for server communication
```

**Development Requirements:**
```
pytest>=7.0.0          # Testing framework
pytest-cov>=4.0.0      # Code coverage reporting
```

**Installation:**
```bash
python3 -m pip install -r requirements.txt
python3 -m pip install pytest pytest-cov  # For development
```

## Testing Commands

```bash
# Install dependencies
python3 -m pip install -q pytest pytest-cov

# Run all tests
python3 -m pytest tests/ -v

# Run with coverage
python3 -m pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test file
python3 -m pytest tests/test_config.py -v
python3 -m pytest tests/test_mcp_client.py -v
```

**Current Test Status:** 67 tests across 4 test files - some tests failing due to async/MCP integration changes

## Development Status

**Phase 3: ✅ Core Automation Complete**

All core modules have been implemented:
- ✅ MCP Client with official Python SDK integration
- ✅ Claude Client with tool restrictions and API integration
- ✅ Note Scanner for finding @claude requests
- ✅ Request Parser supporting all syntax formats
- ✅ Response Writer for creating formatted notes
- ✅ Rate Limiter with persistent state tracking
- ✅ Notifier for desktop notifications
- ✅ Main CLI orchestrator with async/await pattern

**Obsidian MCP Server:**
- Using community package: `@mauricio.wolff/mcp-obsidian@latest`
- Installed via: `npx @mauricio.wolff/mcp-obsidian@latest <vault_path>`
- MCP SDK: The project uses `mcp` Python package from PyPI (installed via requirements.txt)
- **Important:** The MCP client uses stdio transport to communicate with the Node.js-based Obsidian server

## Architecture

### Core Components

**Configuration System (src/config.py)**
- Loads YAML configs: `config/default_config.yaml` (main), `config/vault_permissions.yaml` (tool allowlist)
- Provides property-based access to all settings (MCP, Claude, scanning, rate limits, etc.)
- Per-vault tool permission overrides

**MCP Client (src/mcp_client.py)**
- Async wrapper for Obsidian MCP server communication using official MCP Python SDK
- Retry logic with configurable attempts (default 3) and delays
- Async methods: `search_notes()`, `read_note()`, `create_note()`, `update_note()`, `append_to_note()`
- Async context manager support for automatic connect/disconnect (`async with client:`)
- **Important:** All methods are async and must be awaited in async context

**Custom Exceptions (src/exceptions.py)**
- Hierarchy: `ObsidianClaudeError` (base) → `MCPError`, `ClaudeAPIError`, `ConfigurationError`, etc.
- Specific errors: `MCPConnectionError`, `MCPTimeoutError`, `UnauthorizedToolError`, `RateLimitExceededError`

**Logger (src/logger.py)**
- Rotating file handler with configurable size limits
- Format: timestamp, level, module, message

**Request Parser (src/request_parser.py)**
- Regex-based parsing for all @claude request formats
- Ignores requests in code blocks and HTML comments
- Generates request hashes for deduplication
- Methods to mark requests as processed (@claude-done) or failed (@claude-error)

**Claude Client (src/claude_client.py)**
- Anthropic API integration with tool restrictions
- Async request processing with MCP tool integration
- Tool permission enforcement (validates allowed tools)
- Response text extraction and error handling

**Note Scanner (src/note_scanner.py)**
- Scans vault for notes containing @claude markers
- Filters by modification timeframe (configurable days)
- Async MCP operations for vault search and reading
- Returns PendingRequest objects for processing

**Response Writer (src/response_writer.py)**
- Creates formatted response notes with metadata
- Generates timestamped filenames (e.g., note_response_20260305_143045.md)
- Updates source notes with wikilinks to responses
- Async MCP operations for note creation/updates

**Rate Limiter (src/rate_limiter.py)**
- Persistent state tracking via JSON file (state/processed_requests.json)
- Enforces requests per hour limit
- Deduplication using note path + request hash
- Automatic cleanup of entries older than N days

**Notifier (src/notifier.py)**
- Desktop notifications via plyer library
- Success, error, and rate limit notifications
- Cross-platform support (macOS, Linux, Windows)
- Can be disabled in configuration

**Main Orchestrator (src/main.py)**
- CLI entry point with argparse (run, status, init, reset commands)
- Async workflow orchestration using asyncio
- Component initialization and lifecycle management
- Error handling with specific exit codes

### Configuration Structure

**Main Config (config/default_config.yaml):**
- `mcp.*` - Server command, args, timeout
  - `server_command`: "npx"
  - `server_args`: ["@mauricio.wolff/mcp-obsidian@latest", "/path/to/vault"]
  - `timeout`: 30 (seconds)
  - `max_retries`: 3
  - `retry_delay`: 1.0 (seconds)
- `claude.*` - API key env var, model, max_tokens, temperature
  - `api_key_env`: Environment variable name (default: "ANTHROPIC_API_KEY")
  - `model`: Claude model ID (e.g., "claude-sonnet-4-5-20250929")
- `scanning.*` - Timeframe and check interval
  - `recent_timeframe`: Days to look back for modified notes (default: 7)
  - `check_interval`: Seconds between scans (default: 300)
- `rate_limit.*` - Max requests per hour
  - `max_requests_per_hour`: Rate limit threshold (default: 5)
- `response.*` - Max length, timestamp inclusion, note suffix pattern
  - `max_length`: Maximum response characters (default: 5000)
  - `include_timestamp`: Add timestamp to responses (default: true)
  - `note_suffix`: Pattern for response note names (default: "_response_")
- `notifications.*` - Desktop notification settings
  - `enabled`: Enable/disable notifications (default: true)
  - `on_success`: Notify on successful processing
  - `on_error`: Notify on errors
- `logging.*` - Level, file path, rotation settings
  - `level`: Log level (DEBUG, INFO, WARNING, ERROR)
  - `file`: Path to log file (default: "logs/agent.log")
  - `max_size`: Max log file size in bytes (default: 10485760 = 10MB)
  - `backup_count`: Number of backup log files to keep (default: 5)
- `dry_run` - Preview mode without execution (default: false)

**Permissions (config/vault_permissions.yaml):**
- `default.allowed_tools` - Default tool allowlist for all vaults
- `vaults.<path>.allowed_tools` - Per-vault overrides

**Allowed Tools (configurable):**
- `read_note`, `search_notes`, `write_note` (Obsidian MCP tools)
- `web_search`, `web_fetch` (if available via MCP)

**Explicitly Disallowed:**
- `patch_note` (modify existing notes with patches)
- `bash` (execute shell commands)

**Note:** Tool names correspond to MCP server tools. The Obsidian MCP server uses simplified names like `read_note` rather than `obsidian_read_note`.

## Request Syntax

The tool recognizes these `@claude` request formats in notes:

```markdown
@claude [request text]
@claude: [request text]
@claude - [request text]
@claude """
[multi-line request]
"""
```

**Parsing Rules:**
- Case-sensitive: only lowercase `@claude`
- Ignored inside markdown code blocks (triple backticks) and HTML comments
- Only first unprocessed request per note is processed per run
- After processing, `@claude` is replaced with `@claude-done` and response link is added

## Response Note Format

**Filename:** `<source_note>_response_<timestamp>.md` (e.g., `weekly_planning_response_20260227_153045.md`)

**Structure:**
```markdown
# Claude Response

**Source Note:** [[weekly_planning]]
**Request:** [Original request text]
**Timestamp:** 2026-02-27 15:30:45
**Status:** Success

---

## Response

[Claude's full response here]

---

*Generated by Obsidian-Claude Agent*
```

## Error Handling Patterns

**Error Scenarios:**
- Unauthorized tool requested → Write `@claude-error` with explanation to note
- API unavailable → Log, notify, skip run (retry next schedule)
- Rate limit exceeded → Mark pending, notify with next available time
- Malformed request → Write parse error to note, mark done
- Connection failure → Exit with code 3

**Error Messages in Notes:**
```markdown
@claude-error [original request]
**Error:** [Error description]
[Timestamp/additional context]
```

## State Management

**File:** `state/processed_requests.json`

Tracks:
- Processed requests (note path + request hash)
- Rate limit counters (requests per hour window)
- Response note paths
- Cleanup of entries older than 7 days

## Code Quality Standards

- Type hints required for all function signatures
- Docstrings with Args/Returns/Raises sections (Google style)
- Modules should be < 200 lines (current modules exceed this - refactoring opportunity)
- Target: >80% test coverage
- Semantic versioning: v1.0.0

## Important Implementation Details

### Async/Await Pattern

**Critical:** The entire codebase uses async/await patterns. All MCP operations and the main workflow are asynchronous.

- All MCP client methods (`search_notes`, `read_note`, `create_note`, `update_note`) are async
- Claude client's `process_request` method is async
- Note scanner's `scan_for_requests` method is async
- Response writer's note creation/update methods are async
- Main orchestrator runs via `asyncio.run()` in src/main.py

**When adding new code:**
- Use `async def` for any function that calls async methods
- Always `await` async function calls
- Use `async with` for MCP client context manager
- Run the main entry point with `asyncio.run(async_main(args))`

### Tool Permission Security

The Claude client enforces strict tool permissions:
- Only tools in `allowed_tools` list can be used
- Tool definitions are filtered before sending to Claude API
- If Claude attempts unauthorized tool, `UnauthorizedToolError` is raised
- Default allowed tools: `read_note`, `search_notes`, `write_note`
- Explicitly disallowed: `patch_note`, `bash`

### State Persistence

The rate limiter maintains state in `state/processed_requests.json`:
- **processed_requests**: Set of `note_path:request_hash` entries
- **request_timestamps**: List of ISO-format timestamps for rate limiting
- **response_map**: Mapping of request IDs to response note paths
- **Automatic cleanup**: Entries older than 7 days are removed on load

### Request Deduplication

Requests are uniquely identified by:
1. Note path (full path to the note)
2. Request hash (SHA256 of request text, first 16 chars)

Combined format: `note_path:request_hash`

This prevents re-processing the same request multiple times, even if the @claude marker hasn't been replaced yet.

## Project Structure

```
src/
├── __init__.py         # Package initialization
├── __main__.py        # Direct module execution (python -m src)
├── config.py          # Configuration management
├── exceptions.py      # Custom exception hierarchy
├── logger.py          # Logging setup with rotation
├── mcp_client.py      # Async MCP server wrapper (437 lines)
├── claude_client.py   # Claude API integration with tool restrictions
├── note_scanner.py    # Vault scanner for @claude requests
├── request_parser.py  # Request parsing and marking
├── response_writer.py # Response note creation
├── rate_limiter.py    # Rate limiting and state persistence
├── notifier.py        # Desktop notifications
└── main.py            # CLI orchestrator and entry point

config/
├── default_config.yaml      # Main configuration
└── vault_permissions.yaml   # Tool allowlist

tests/
├── test_config.py          # Config loading and properties
├── test_mcp_client.py      # MCP client initialization
├── test_request_parser.py  # Request parsing logic
└── test_rate_limiter.py    # Rate limiting and state

logs/         # Rotating log files
state/        # Processed request tracking (JSON)
```

**Component Integration Example:**
```python
import asyncio
from src.config import Config
from src.mcp_client import MCPClient
from src.claude_client import ClaudeClient
from src.note_scanner import NoteScanner
from src.request_parser import RequestParser

async def main():
    # Load configuration
    config = Config()

    # Initialize MCP client
    mcp_client = MCPClient(
        server_command=config.mcp_server_command,
        server_args=config.mcp_server_args
    )

    # Initialize Claude client with tool restrictions
    claude_client = ClaudeClient(
        model=config.claude_model,
        allowed_tools=config.default_allowed_tools,
        mcp_client=mcp_client
    )

    # Initialize scanner with parser
    scanner = NoteScanner(
        mcp_client=mcp_client,
        request_parser=RequestParser()
    )

    async with mcp_client:
        # Scan for requests
        pending = await scanner.scan_for_requests()

        # Process first request
        if pending:
            request = pending[0]
            response = await claude_client.process_request(
                request_text=request.request.request_text
            )
            print(f"Response: {response}")

asyncio.run(main())
```

## Known Issues & TODOs

1. **Test Failures:** Some async tests are failing after MCP integration changes - need to update test mocks
2. **Test Coverage:** Add integration tests for full end-to-end workflow with live MCP server
3. **Module Size:** main.py (419 lines) exceeds 200-line guideline - consider refactoring
4. **Python Version:** Project requires Python 3.10+ for proper async support (currently tested on 3.9.6)
5. **Configuration Validation:** Add schema validation for YAML configs using pydantic or similar
6. **Error Recovery:** Improve retry logic for transient MCP connection failures
7. **State File Location:** State file path should be configurable in config YAML (currently hardcoded)

## CLI Interface

The agent provides these commands:

```bash
# Run a single scan cycle (for cron/scheduler)
python -m src run

# Preview without executing
python -m src run --dry-run

# Check system status and connectivity
python -m src status

# Initialize configuration (placeholder - currently just confirms initialization)
python -m src init

# Clear processed request history
python -m src reset --confirm

# Use custom config file (permissions file not yet configurable via CLI)
python -m src run --config custom_config.yaml

# Direct Python execution (alternative to python -m src)
python src/main.py run
```

**Note:** The `--permissions` flag exists but is not yet implemented in the config loading logic.

**Exit Codes:**
- 0 = Success
- 1 = General error
- 2 = Configuration error
- 3 = MCP connection failed
- 4 = Claude API error
- 130 = Interrupted by user (Ctrl+C)

## Testing Strategy

**Implemented Unit Tests:**
- `test_config.py` - Configuration loading, property access, YAML parsing
- `test_mcp_client.py` - MCP client initialization, connection state
- `test_request_parser.py` - Request parsing for all syntax variants, ignore patterns
- `test_rate_limiter.py` - Rate limiting logic, state persistence, deduplication

**Integration Tests (TODO - require live MCP server):**
- End-to-end request processing workflow
- Real vault search/read/create operations
- State file persistence across runs
- Notification delivery on different platforms

**Manual Test Scenarios:**
- Multiple @claude requests in single note (only first is processed)
- Requests inside code blocks/HTML comments (should be ignored)
- Multi-line triple-quote requests
- Unauthorized tool requests (should fail gracefully)
- Rate limit exceeded (should notify and stop)
- Very long responses (should truncate if configured)
- MCP server offline (should exit with code 3)
- Invalid configuration files (should exit with code 2)
