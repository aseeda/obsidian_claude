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
python-dotenv>=1.0.0   # Environment variable loading
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
python3 -m pytest tests/test_cli_client.py -v
```

**Current Test Status:** 79/79 tests passing (24 CLI client, 14 config, 20 rate limiter, 19 request parser, 2 other)

## Development Status

**Phase 3: Core Implementation - ✅ Complete (v1.0)**

All major components are implemented and tested. The agent is functional and ready for production use:
- ✅ **CLI Client** (src/cli_client.py) - Direct file system vault operations
- ✅ **Request Parser** (src/request_parser.py) - Extracts @claude requests from notes
- ✅ **Rate Limiter** (src/rate_limiter.py) - Request throttling with state persistence
- ✅ **Claude Client** (src/claude_client.py) - API integration with tool restrictions
- ✅ **Note Scanner** (src/note_scanner.py) - Finds pending requests in vault
- ✅ **Response Writer** (src/response_writer.py) - Creates formatted response notes
- ✅ **Main Orchestrator** (src/main.py) - CLI entry point with full workflow
- ✅ **Configuration System** (src/config.py) - YAML-based settings management
- ✅ **Exception Hierarchy** (src/exceptions.py) - Comprehensive error handling

**Architecture Decision:** The project uses **direct file system operations** rather than MCP server integration for better reliability, performance, and reduced complexity. Obsidian CLI binary detection is supported with automatic fallback to direct file access.

**Requirements:**
- Python 3.10+ (currently tested on 3.9.6)
- Anthropic API key (set ANTHROPIC_API_KEY environment variable)
- Valid Obsidian vault directory path
- Obsidian installation optional (CLI binary detection falls back to direct file access)

## Architecture

### Core Components

**Configuration System (src/config.py)**
- Loads YAML configs: `config/default_config.yaml` (main), `config/vault_permissions.yaml` (tool allowlist)
- Provides property-based access to all settings (Obsidian, Claude, scanning, rate limits, etc.)
- Per-vault tool permission overrides

**CLI Client (src/cli_client.py)** - 454 lines
- Synchronous wrapper for Obsidian vault operations via direct file system access
- Platform-specific CLI binary detection with auto-fallback to direct file operations
- Methods: `search_notes()`, `read_note()`, `create_note()`, `update_note()`, `append_to_note()`
- Context manager support for automatic connect/disconnect (`with client:`)
- **Important:** All methods are synchronous (no async/await complexity)

**Request Parser (src/request_parser.py)** - 238 lines
- Extracts @claude requests from note content with multiple format support
- Formats: inline (`@claude text`), with separators (`@claude: text`, `@claude - text`), multiline (triple-quotes)
- Ignores requests inside code blocks and HTML comments
- Generates SHA256 hashes for request deduplication
- Methods for marking requests as processed (`@claude-done`) or errored (`@claude-error`)

**Rate Limiter (src/rate_limiter.py)** - 294 lines
- Enforces max requests per hour limit (configurable, default 5)
- Persists state to JSON file (`state/processed_requests.json`)
- Tracks processed requests, timestamps, and response note paths
- Automatic cleanup of entries older than 7 days
- Provides usage statistics and manual reset functionality

**Claude Client (src/claude_client.py)** - 255 lines
- Integrates with Anthropic Claude API
- Enforces tool permission restrictions (allowlist-based)
- Provides Obsidian tools (read_note, search_notes, write_note) to Claude
- Handles API errors and unauthorized tool usage
- **Note:** Currently uses synchronous Anthropic SDK (not async)

**Note Scanner (src/note_scanner.py)** - 208 lines
- Scans vault for notes containing `@claude` markers
- Uses CLI client for file system search operations
- Filters by modification time (configurable timeframe, default 7 days)
- Returns list of `PendingRequest` objects with note path, content, and parsed request
- **Note:** Uses async/await patterns (interfaces with future async MCP integration)

**Response Writer (src/response_writer.py)** - 215 lines
- Creates formatted response notes with metadata (source note, request text, timestamp, status)
- Generates unique filenames with timestamps: `<note>_response_YYYYMMDD_HHMMSS.md`
- Updates source notes to mark requests as processed
- Supports response truncation (configurable max length)
- **Note:** Uses async/await patterns (interfaces with future async MCP integration)

**Custom Exceptions (src/exceptions.py)**
- Hierarchy: `ObsidianClaudeError` (base) → `MCPError`, `ClaudeAPIError`, `ConfigurationError`, etc.
- Specific errors: `MCPConnectionError`, `MCPTimeoutError`, `UnauthorizedToolError`, `RateLimitExceededError`

**Logger (src/logger.py)**
- Rotating file handler with configurable size limits
- Format: timestamp, level, module, message

### Configuration Structure

**Main Config (config/default_config.yaml):**
- `obsidian.*` - Vault path and CLI settings
  - `vault_path`: "/path/to/vault" (required - **must be updated before running**)
  - `cli_path`: null (optional, auto-detects if null)
  - `timeout`: 30 (seconds)
- `claude.*` - Claude API configuration
  - `api_key_env`: "ANTHROPIC_API_KEY" (environment variable name)
  - `model`: "claude-sonnet-4-5-20250929"
  - `max_tokens`: 4000
  - `temperature`: 0.7
- `scanning.*` - Note scanning settings
  - `recent_timeframe`: 7 (days to look back for modified notes)
  - `check_interval`: 300 (seconds, for future scheduled runs)
- `rate_limit.*` - Request throttling
  - `max_requests_per_hour`: 5
- `response.*` - Response note formatting
  - `max_length`: 5000 (characters)
  - `include_timestamp`: true
  - `note_suffix`: "_response_"
- `logging.*` - Log file settings
  - `level`: "DEBUG"
  - `file`: "logs/agent.log"
  - `max_size`: 10485760 (10MB)
  - `backup_count`: 5
- `dry_run`: false (preview mode without execution)

**Permissions (config/vault_permissions.yaml):**
- `default.allowed_tools` - Default tool allowlist for all vaults
- `vaults.<path>.allowed_tools` - Per-vault overrides

**Allowed Tools (configurable):**
- `read_note`, `search_notes`, `write_note` (Obsidian MCP tools)
- `web_search`, `web_fetch` (if available via MCP)

**Explicitly Disallowed:**
- `patch_note` (modify existing notes with patches)
- `bash` (execute shell commands)

**Important Implementation Details:**

1. **Synchronous Architecture:**
   - All components are synchronous (no async/await complexity)
   - CLI Client (ObsidianCLIClient) operates directly on file system
   - Main orchestrator runs in synchronous mode for simplicity
   - This design prioritizes reliability and debuggability over async performance

2. **Request Processing Flow:**
   ```
   main.py (CLI entry)
     → NoteScanner.scan_for_requests()
     → finds notes with @claude markers
     → RequestParser.extract_request()
     → extracts request text + context + wikilinks
     → RateLimiter.can_process_request()
     → checks hourly quota
     → ClaudeClient.process_request()
     → sends to Claude API with context
     → ResponseWriter.create_response_note()
     → creates timestamped response note
     → RequestParser.mark_request_processed()
     → replaces @claude with @claude-done
     → RateLimiter.record_request()
     → tracks in state file
   ```

3. **Tool Permissions:**
   - Tool names defined in vault_permissions.yaml restrict Claude's capabilities
   - Prevents Claude from using `bash` or `patch_note` tools
   - Allowlist approach: only explicitly allowed tools are available

4. **State Persistence:**
   - Rate limiter stores state in `state/processed_requests.json`
   - Tracks: processed request IDs (note_path:hash), timestamps, response paths
   - Survives application restarts for proper rate limiting across runs
   - Auto-cleanup of entries older than 7 days

5. **Environment Variables:**
   - Supports `.env` file for local configuration (loaded via python-dotenv)
   - Required: `ANTHROPIC_API_KEY` for Claude API access
   - Example `.env.example` provided in repo

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
- API unavailable → Log error, skip run (retry next schedule)
- Rate limit exceeded → Mark pending, log next available time
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
├── __init__.py
├── __main__.py              # Package entry point (python -m src)
├── main.py                  # Main orchestrator with CLI (418 lines)
├── config.py                # Configuration management (210 lines)
├── exceptions.py            # Custom exception hierarchy (68 lines)
├── logger.py                # Logging setup with rotation
├── cli_client.py            # Synchronous vault client (454 lines)
├── request_parser.py        # @claude request extraction (238 lines)
├── rate_limiter.py          # Request throttling (294 lines)
├── claude_client.py         # Claude API integration (255 lines)
├── note_scanner.py          # Vault scanning for requests (208 lines)
└── response_writer.py       # Response note creation (215 lines)

config/
├── default_config.yaml      # Main configuration (must set vault_path!)
└── vault_permissions.yaml   # Tool allowlist

tests/
├── test_config.py           # 17 tests - config loading and properties
├── test_cli_client.py       # 24 tests - vault operations
├── test_request_parser.py   # 19 tests - request extraction patterns
├── test_rate_limiter.py     # 20 tests - throttling and state persistence
└── (test coverage: 80 tests total)

logs/         # Auto-created: rotating log files
state/        # Auto-created: processed_requests.json
```

**CLI Client Usage Example:**
```python
from src.cli_client import ObsidianCLIClient

def main():
    client = ObsidianCLIClient(
        vault_path="/path/to/vault",
        cli_path=None  # Auto-detect CLI binary
    )

    with client:
        # Search for notes (direct file system scan)
        notes = client.search_notes(query="@claude")

        # Read a note
        content = client.read_note("path/to/note.md")

        # Create response note
        client.create_note(
            path="response.md",
            content="# Response\n\nContent here"
        )

main()
```

## Known Limitations & Future Enhancements

1. **Testing Coverage:**
   - Integration tests with real Claude API not yet implemented
   - Need end-to-end tests with actual Obsidian vault
   - Target: >80% test coverage (currently 63%)

2. **Code Organization:**
   - Several modules exceed 200-line target (main.py: 440, cli_client.py: 454)
   - Consider splitting large modules into smaller components
   - Extract common patterns into utility functions

3. **User Experience:**
   - Manual vault_path configuration required in YAML
   - Interactive setup wizard (`python -m src init`) could improve onboarding
   - No web UI for monitoring processed requests

4. **Advanced Features (Future):**
   - Multi-vault support (currently single vault only)
   - Custom response templates
   - Request prioritization/scheduling
   - Retry logic for failed API calls
   - Conversation threading (multiple related requests)

## CLI Interface

**Running the agent:**

```bash
# Run as Python module (recommended)
python3 -m src run                    # Single scan and process
python3 -m src run --dry-run          # Preview without execution
python3 -m src status                 # Check system status
python3 -m src init                   # Initialize configuration
python3 -m src reset --confirm        # Clear processed request history

# Custom config file
python3 -m src run --config path/to/config.yaml

# Alternative: Direct invocation
python3 src/main.py run
```

**Before first run:**

1. Create `.env` file with API key (or export environment variable):
   ```bash
   # Copy example file
   cp .env.example .env

   # Edit .env and add your key
   echo 'ANTHROPIC_API_KEY=your-api-key-here' > .env

   # Alternative: export directly
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

2. Edit `config/default_config.yaml`:
   ```yaml
   obsidian:
     vault_path: "/path/to/your/obsidian/vault"  # Change this!
   ```

3. Test configuration:
   ```bash
   python3 -m src status
   ```

**Exit Codes:**
- 0 = success
- 1 = general error
- 2 = config error
- 3 = MCP connection failed (currently not used)
- 4 = Claude API error
- 130 = keyboard interrupt (Ctrl+C)

## Testing Strategy

**Unit Tests (79 tests, all passing):**
- ✅ Configuration loading and property access (14 tests)
- ✅ CLI client vault operations (24 tests)
- ✅ Request parsing - all syntax variants, ignore patterns (19 tests)
- ✅ Rate limiting logic and state persistence (20 tests)
- ✅ Request hash generation
- ✅ Error message formatting

**Integration Tests (TODO):**
- End-to-end request processing with real Claude API
- Actual vault operations with test vault
- State file persistence across runs
- Error handling in full workflow

**Manual Test Scenarios (TODO):**
- Single/multiple requests per note
- Requests in code blocks/comments (should be ignored)
- Multi-line triple-quote requests
- Rate limit exceeded behavior
- Very long responses (truncation at 5000 chars)
- Invalid vault paths
- Missing API key
- Concurrent runs (state file locking)
