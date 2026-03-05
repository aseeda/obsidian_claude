# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Obsidian-Claude Automation Agent** - A Python tool that automatically processes natural language requests embedded in Obsidian notes using Claude AI via the Obsidian MCP (Model Context Protocol) server.

**Key Workflow:**
1. Scans Obsidian vault for notes modified in the last week containing `@claude` requests
2. Sends requests to Claude AI with restricted tool permissions
3. Creates linked response notes with results
4. Prevents re-processing and enforces rate limits (5 requests/hour)
5. Designed to run as scheduled background task (cron/systemd/Task Scheduler)

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

**Current Test Status:** 26/26 tests passing, 63% code coverage

## Development Status

**MCP Integration: ✅ Complete**

The `MCPClient` class (src/mcp_client.py) now uses the official MCP Python SDK to communicate with the Obsidian MCP server:
- ✅ Real MCP server subprocess management via `stdio_client()`
- ✅ Async/await pattern for all MCP operations
- ✅ Tool calls use `session.call_tool()` with timeout handling
- ✅ Proper connection lifecycle with retry logic
- ✅ MCP SDK package (`mcp>=1.0.0`) added to requirements.txt

**Obsidian MCP Server:**
- Using community package: `@mauricio.wolff/mcp-obsidian@latest`
- Installed via: `claude mcp add-json obsidian --scope user '{"type":"stdio","command":"npx","args":["@mauricio.wolff/mcp-obsidian@latest","/path/to/vault"]}'`

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

### Configuration Structure

**Main Config (config/default_config.yaml):**
- `mcp.*` - Server command, args, timeout
  - `server_command`: "npx"
  - `server_args`: ["@mauricio.wolff/mcp-obsidian@latest", "/path/to/vault"]
  - `timeout`: 30 (seconds)
  - `max_retries`: 3
  - `retry_delay`: 1.0 (seconds)
- `claude.*` - API key env var, model, max_tokens, temperature
- `scanning.*` - Timeframe (days), check interval (seconds)
- `rate_limit.*` - Max requests per hour
- `response.*` - Max length, timestamp inclusion, note suffix pattern
- `notifications.*` - Desktop notification settings
- `logging.*` - Level, file path, rotation settings

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
- Docstrings with Args/Returns/Raises sections
- Modules should be < 200 lines (current modules exceed this - refactoring opportunity)
- Target: >80% test coverage (currently 63%)
- Semantic versioning: v1.0.0

## Project Structure

```
src/
├── config.py           # Configuration management (6.7KB, 210 lines)
├── exceptions.py       # Custom exception hierarchy (1.5KB, 68 lines)
├── logger.py          # Logging setup (5.2KB, needs more tests)
├── mcp_client.py      # Async MCP server wrapper using official SDK (437 lines)

config/
├── default_config.yaml      # Main configuration
├── vault_permissions.yaml   # Tool allowlist

tests/
├── test_config.py     # 15 tests, config loading and properties
├── test_mcp_client.py # 11 tests, client initialization and state

logs/         # Rotating log files
state/        # Processed request tracking (JSON)
```

**MCP Client Usage Example:**
```python
import asyncio
from src.mcp_client import MCPClient

async def main():
    client = MCPClient(
        server_command="npx",
        server_args=["@mauricio.wolff/mcp-obsidian@latest", "/path/to/vault"]
    )

    async with client:
        # Search for notes
        notes = await client.search_notes(query="@claude")

        # Read a note
        content = await client.read_note("path/to/note.md")

        # Create response note
        await client.create_note(
            path="response.md",
            content="# Response\n\nContent here"
        )

asyncio.run(main())
```

## Known Issues & TODOs

1. **Test Coverage:** Improve logger.py coverage (currently 51%)
2. **Module Size:** mcp_client.py exceeds 200-line guideline (437 lines) - consider refactoring
3. **Python Version:** Ensure deployment uses Python 3.10+ (tests run on 3.9.6)
4. **Async Tests:** Update test suite to handle async MCP client methods
5. **Missing Modules:** Need to implement:
   - `note_scanner.py` - Find and parse notes (must use async MCP client)
   - `request_parser.py` - Extract `@claude` requests (regex patterns)
   - `claude_client.py` - Claude API integration with tool restrictions
   - `response_writer.py` - Create response notes (must use async MCP client)
   - `rate_limiter.py` - Request throttling
   - `notifier.py` - Desktop notifications (platform-specific)
   - `main.py` - CLI entry point and orchestration (must use asyncio)

## CLI Interface (Planned)

```bash
obsidian-claude-agent run              # Single scan for cron/scheduler
obsidian-claude-agent run --dry-run    # Preview without execution
obsidian-claude-agent init             # Initialize configuration
obsidian-claude-agent status           # Check system status
obsidian-claude-agent logs --tail 50   # View recent logs
obsidian-claude-agent reset --confirm  # Clear processed request history
```

**Exit Codes:** 0=success, 1=general error, 2=config error, 3=MCP connection failed, 4=Claude API error, 5=rate limit exceeded

## Testing Strategy

**Unit Tests Focus:**
- Configuration loading and property access
- Request parsing (all syntax variants, ignore patterns)
- Rate limiting logic
- Request hash generation
- Error message formatting

**Integration Tests (require MCP server):**
- End-to-end request processing
- Actual note search/read/create operations
- State file persistence
- Notification delivery

**Manual Test Scenarios:**
- Single/multiple requests per note
- Requests in code blocks/comments (should be ignored)
- Multi-line triple-quote requests
- Unauthorized tool requests
- Rate limit exceeded behavior
- Very long responses (truncation)
- MCP server offline handling
