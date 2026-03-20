# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Obsidian-Claude Automation Agent** - Automatically processes `@claude` requests embedded in Obsidian notes using Claude AI via direct file system access.

**Core Workflow:**
1. Scans vault for notes modified in last week containing `@claude` markers
2. Sends requests to Claude API with tool restrictions (no bash, no patch_note)
3. Creates timestamped response notes with results
4. Marks requests as `@claude-done` to prevent re-processing
5. Enforces 5 requests/hour rate limit with persistent state

**Python Version:** 3.10+ (tested on 3.9.6)

## Common Commands

```bash
# Install dependencies
python3 -m pip install -r requirements.txt
python3 -m pip install pytest pytest-cov  # For development

# Run agent
python3 -m src run                    # Process pending requests
python3 -m src run --dry-run          # Preview without executing
python3 -m src status                 # Check system status
python3 -m src reset --confirm        # Clear processed request history

# Testing
python3 -m pytest tests/ -v                              # Run all tests (79 passing)
python3 -m pytest tests/ -v --cov=src --cov-report=term-missing  # With coverage
python3 -m pytest tests/test_config.py -v                # Single test file
```

**Before First Run:**
1. Set `ANTHROPIC_API_KEY` environment variable (or create `.env` file)
2. Edit `config/default_config.yaml` and set `obsidian.vault_path` to your vault directory

## Automated Scheduling

The agent runs once per invocation. For continuous monitoring, use cron to schedule regular execution.

**Quick Setup (macOS/Linux):**

```bash
# Install crontab entry (reads check_interval from config)
./scripts/setup-cron.sh install

# Check status and view recent logs
./scripts/setup-cron.sh status

# Remove crontab entry
./scripts/setup-cron.sh uninstall

# Preview what would be installed
./scripts/setup-cron.sh show
```

**How It Works:**
- `setup-cron.sh` reads `scanning.check_interval` from `config/default_config.yaml`
- Converts interval to cron expression (e.g., 300 seconds → `*/5 * * * *`)
- Installs crontab entry that runs `scripts/run-with-env.sh`
- Wrapper script loads `.env` file and runs agent with proper environment
- Logs written to `logs/cron.log`

**Manual Crontab Setup:**

```bash
# Edit crontab
crontab -e

# Add entry (example: every 5 minutes)
*/5 * * * * /path/to/obsidian_claude/scripts/run-with-env.sh >> /path/to/obsidian_claude/logs/cron.log 2>&1
```

**Common Intervals:**
- Every 5 minutes: `*/5 * * * *`
- Every 15 minutes: `*/15 * * * *`
- Every hour: `0 * * * *`
- Every 6 hours: `0 */6 * * *`
- Daily at 9am: `0 9 * * *`

**Troubleshooting:**

**Problem:** Cron jobs not running
- Check cron is running: `ps aux | grep cron`
- View system logs: `grep CRON /var/log/syslog` (Linux) or check Console.app (macOS)
- Verify entry exists: `crontab -l`

**Problem:** ANTHROPIC_API_KEY not found
- Ensure `.env` file exists in project root
- Verify wrapper script sources it: `./scripts/run-with-env.sh` (run manually)
- Alternative: Add API key directly in crontab (less secure):
  ```
  */5 * * * * ANTHROPIC_API_KEY=your-key /path/to/run-with-env.sh
  ```

**Problem:** Python not found
- Use absolute path to Python in `run-with-env.sh`
- Find path: `which python3`

**Monitoring:**

```bash
# Watch logs in real-time
tail -f logs/cron.log

# Check recent executions
tail -20 logs/cron.log

# Check agent-specific logs
tail -f logs/agent.log
```

## Architecture Overview

**Synchronous Design:** All components use synchronous operations for reliability and debuggability. No async/await complexity.

**Request Processing Pipeline (with Image OCR):**
```
main.py (CLI entry)
  → NoteScanner.scan_for_requests()          # Find notes with @claude markers (modified in last 7 days)
  → RequestParser.extract_request()          # Extract request text + context + wikilinks + images
  → RateLimiter.can_process_request()        # Check hourly quota (5/hour)

  PHASE 1 (if images detected):
  → ImageExtractor.extract_text_from_images() # Send images to Claude Vision API, extract text
  → Build enhanced context with image text

  PHASE 2:
  → ClaudeClient.process_request()           # Send main request to Claude with enhanced context
  → ResponseWriter.append_response_to_note() # Append extracted text + response to source note
  → RateLimiter.record_request()             # Track in state/processed_requests.json
```

### Key Components

**ObsidianCLIClient (src/cli_client.py)**
- Direct file system access to vault (no MCP server required)
- Platform-specific Obsidian CLI binary detection with fallback to direct file operations
- Context manager support: `with client:` pattern auto-connects/disconnects
- Methods: `search_notes()`, `read_note()`, `create_note()`, `update_note()`, `append_to_note()`

**RequestParser (src/request_parser.py)**
- Supports multiple `@claude` formats: inline, with separators (`:` or `-`), multiline (triple-quotes)
- Ignores requests in code blocks and HTML comments
- Generates SHA256 hashes for deduplication
- Context extraction: includes full note content + resolves wikilinks + detects image wikilinks
- **NEW:** Detects image wikilinks (`![[image.jpg]]`) for OCR processing

**ImageProcessor (src/image_processor.py)**
- Resolves image paths in vault (attachment folders, same directory, vault root)
- Validates image formats (JPG, PNG, GIF, WebP) and file sizes
- Reads and base64-encodes images for Claude Vision API

**ImageExtractor (src/image_extractor.py)**
- Extracts text from images using Claude Vision API (Phase 1)
- Processes multiple images sequentially
- Builds enhanced context by combining original text with extracted image text
- Handles errors gracefully (missing images, API failures)

**RateLimiter (src/rate_limiter.py)**
- Persistent state in `state/processed_requests.json`
- Tracks: processed request IDs (note_path:hash), timestamps, response paths
- Auto-cleanup of entries older than 7 days
- Prevents re-processing across application restarts

**ClaudeClient (src/claude_client.py)**
- Tool permission enforcement via allowlist (config/vault_permissions.yaml)
- Provides Obsidian tools to Claude: `obsidian_read_note`, `obsidian_search_notes`, `obsidian_write_note`
- **NEW:** `process_vision_request()` for sending images to Claude Vision API
- **Explicitly disallowed:** `bash`, `patch_note` (security restriction)

**Config (src/config.py)**
- YAML-based: `config/default_config.yaml` (main), `config/vault_permissions.yaml` (tools)
- Property-based access to all settings
- Per-vault tool permission overrides supported

### Configuration Files

**config/default_config.yaml:**
- `obsidian.vault_path`: Path to vault directory (**must set before first run**)
- `claude.model`: "claude-sonnet-4-5-20250929" (supports vision)
- `scanning.recent_timeframe`: 7 days (only scan recently modified notes)
- `rate_limit.max_requests_per_hour`: 5
- `response.max_length`: 5000 characters (truncate long responses)
- **NEW:** `image_processing.enabled`: Enable/disable image OCR (default: true)
- **NEW:** `image_processing.max_file_size_mb`: Maximum image size (default: 10MB)
- **NEW:** `image_processing.attachment_folders`: Folders to search for images

**config/vault_permissions.yaml:**
- `default.allowed_tools`: List of tools Claude can use
- Default: `obsidian_read_note`, `obsidian_search_notes`, `obsidian_write_note`
- **Blocked for security:** `bash`, `patch_note`

## Request Syntax

Supported `@claude` formats in notes (case-sensitive lowercase only):

```markdown
@claude [request text]
@claude: [request text]
@claude - [request text]
@claude """
[multi-line request]
"""
```

**Behavior:**
- Requests in code blocks/HTML comments are ignored
- Only first unprocessed request per note is processed per run
- After processing: `@claude` → `@claude-done` with response appended to same note
- On error: `@claude` → `@claude-error` with error description

**Context Extraction:**
- Parser includes full note content as context for Claude
- Automatically resolves wikilinks and includes linked note content
- **NEW:** Automatically detects and extracts text from images in context
- This allows Claude to reference other notes and images mentioned in the request

### Image OCR Processing (NEW)

The agent now supports automatic text extraction from images using Claude's vision capabilities:

**How it works:**
1. Include images in your note using Obsidian wikilink syntax: `![[image.jpg]]`
2. Add `@claude` request anywhere below the images
3. Agent automatically extracts text from images and includes it in context
4. Claude receives both the image text and your request

**Example Usage:**

```markdown
# Meeting Notes - 2026-03-19

![[whiteboard_sketch.jpg]]
![[handwritten_notes.png]]

@claude Summarize the key points from the whiteboard and notes above, and create action items
```

**After Processing:**

```markdown
# Meeting Notes - 2026-03-19

![[whiteboard_sketch.jpg]]
![[handwritten_notes.png]]

@claude-done Summarize the key points from the whiteboard and notes above, and create action items

---
**Extracted Image Text (2026-03-19 14:32):**

**From whiteboard_sketch.jpg:**
[Extracted text from whiteboard image]

**From handwritten_notes.png:**
[Extracted text from handwritten notes]

---
**Response (2026-03-19 14:32):**
[Claude's response using the extracted text as context]
---
```

**Image Processing Features:**
- **Supported formats:** JPG, JPEG, PNG, GIF, WebP
- **Two-phase processing:** Phase 1 extracts image text, Phase 2 processes main request with enhanced context
- **Auto-detect:** No special syntax needed, just include images above `@claude` marker
- **Path resolution:** Searches in same directory, attachment folders, and vault root
- **Error handling:** Gracefully handles missing images or unsupported formats
- **Rate limiting:** Image OCR requests count toward hourly API quota

**Configuration:**
```yaml
image_processing:
  enabled: true
  max_file_size_mb: 10
  attachment_folders: ["_attachments", "assets", "images"]
  ocr_extraction:
    max_images_per_request: 5
```

## Response Format

**NEW Behavior (with image OCR):**
Responses are now appended directly to the source note after the `@claude-done` marker, containing:
- Extracted image text (if images were processed)
- Timestamp
- Claude's response
- Separators for readability

**Legacy Behavior (without images):**
For requests without images, the system can still create separate response notes if configured.
**Generated filename:** `<source_note>_response_<timestamp>.md`
Example: `weekly_planning_response_20260227_153045.md`

## Important Implementation Details

**State Persistence:**
- `state/processed_requests.json` tracks all processed requests
- Survives application restarts for proper rate limiting
- Auto-cleanup of entries older than 7 days
- Request ID format: `note_path:sha256_hash` for deduplication

**Error Handling:**
- Exit codes: 0=success, 1=general error, 2=config error, 3=connection failed, 4=Claude API error
- Errors are written to source notes as `@claude-error` markers
- Logs stored in `logs/agent.log` with rotation (10MB max, 5 backups)

**Tool Restrictions:**
- Claude receives allowlist of tools from `vault_permissions.yaml`
- Attempts to use disallowed tools (bash, patch_note) are blocked
- This prevents code execution and destructive note modifications

## Development Notes

**Code Structure:**
- Type hints required for all function signatures
- Docstrings with Args/Returns/Raises sections
- All components synchronous (no async/await) for simplicity
- 79/79 unit tests passing, ~63% coverage

**Future Enhancements:**
- Multi-vault support (currently single vault)
- Retry logic for failed API calls
- Conversation threading (related requests)
- Web UI for monitoring
