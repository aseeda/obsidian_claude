"""
Main CLI Entry Point

Orchestrates the Obsidian-Claude automation agent.
"""

import asyncio
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

from .config import Config
from .mcp_client import MCPClient
from .claude_client import ClaudeClient
from .note_scanner import NoteScanner
from .response_writer import ResponseWriter
from .request_parser import RequestParser
from .rate_limiter import RateLimiter
from .notifier import Notifier
from .logger import setup_logging
from .exceptions import (
    ObsidianClaudeError,
    MCPConnectionError,
    ClaudeAPIError,
    RateLimitExceededError,
    ConfigurationError
)

logger = logging.getLogger(__name__)


class ObsidianClaudeAgent:
    """Main orchestrator for the Obsidian-Claude automation agent."""

    def __init__(self, config: Config):
        """
        Initialize the agent with configuration.

        Args:
            config: Configuration object
        """
        self.config = config
        self.mcp_client = None
        self.claude_client = None
        self.note_scanner = None
        self.response_writer = None
        self.request_parser = None
        self.rate_limiter = None
        self.notifier = None

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing Obsidian-Claude Agent...")

        # Initialize MCP client
        self.mcp_client = MCPClient(
            server_command=self.config.mcp_server_command,
            server_args=self.config.mcp_server_args,
            timeout=self.config.mcp_timeout,
            max_retries=self.config.mcp_max_retries,
            retry_delay=self.config.mcp_retry_delay
        )

        # Initialize Claude client
        self.claude_client = ClaudeClient(
            model=self.config.claude_model,
            max_tokens=self.config.claude_max_tokens,
            temperature=self.config.claude_temperature,
            allowed_tools=self.config.default_allowed_tools,
            mcp_client=self.mcp_client
        )

        # Initialize request parser
        self.request_parser = RequestParser()

        # Initialize note scanner
        self.note_scanner = NoteScanner(
            mcp_client=self.mcp_client,
            request_parser=self.request_parser,
            timeframe_days=self.config.scanning_timeframe_days
        )

        # Initialize response writer
        self.response_writer = ResponseWriter(
            mcp_client=self.mcp_client,
            response_suffix=self.config.response_suffix,
            include_timestamp=self.config.response_include_timestamp,
            max_response_length=self.config.response_max_length
        )

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            state_file=self.config.state_file,
            max_requests_per_hour=self.config.rate_limit_max_per_hour
        )

        # Initialize notifier
        self.notifier = Notifier(
            enabled=self.config.notifications_enabled
        )

        logger.info("All components initialized")

    async def run(self, dry_run: bool = False) -> int:
        """
        Run a single scan and process requests.

        Args:
            dry_run: If True, don't actually process requests

        Returns:
            Exit code (0=success, >0=error)
        """
        try:
            await self.initialize()

            # Connect to MCP server
            logger.info("Connecting to Obsidian MCP server...")
            await self.mcp_client.connect()

            # Scan for pending requests
            pending_requests = await self.note_scanner.scan_for_requests()

            if not pending_requests:
                logger.info("No pending requests found")
                self.notifier.notify_processed(0)
                return 0

            logger.info(f"Found {len(pending_requests)} pending request(s)")

            if dry_run:
                logger.info("DRY RUN: Would process the following requests:")
                for req in pending_requests:
                    logger.info(f"  - {req.note_path}: {req.request.request_text[:50]}...")
                return 0

            # Process each request
            processed_count = 0
            for pending in pending_requests:
                try:
                    await self._process_single_request(pending)
                    processed_count += 1

                except RateLimitExceededError as e:
                    logger.warning(f"Rate limit exceeded: {e}")
                    next_time = self.rate_limiter.get_next_available_time()
                    if next_time:
                        self.notifier.notify_rate_limit(
                            next_time.strftime("%Y-%m-%d %H:%M:%S")
                        )
                    break  # Stop processing more requests

                except Exception as e:
                    logger.error(f"Failed to process request from {pending.note_path}: {e}")
                    # Mark as error in note
                    await self._mark_request_error(pending, str(e))
                    continue

            # Notify about results
            self.notifier.notify_processed(processed_count)

            logger.info(f"Processing complete: {processed_count} request(s) processed")
            return 0

        except MCPConnectionError as e:
            logger.critical(f"MCP connection failed: {e}")
            self.notifier.notify_error("MCP Connection Failed", str(e))
            return 3

        except ClaudeAPIError as e:
            logger.critical(f"Claude API error: {e}")
            self.notifier.notify_error("Claude API Error", str(e))
            return 4

        except Exception as e:
            logger.critical(f"Unexpected error: {e}", exc_info=True)
            self.notifier.notify_error("Agent Error", str(e))
            return 1

        finally:
            # Disconnect MCP client
            if self.mcp_client:
                await self.mcp_client.disconnect()
                logger.info("Disconnected from MCP server")

    async def _process_single_request(self, pending) -> None:
        """
        Process a single pending request.

        Args:
            pending: PendingRequest object
        """
        note_path = pending.note_path
        request = pending.request

        # Check if already processed
        if self.rate_limiter.is_processed(note_path, request.request_hash):
            logger.debug(f"Request already processed: {note_path}")
            return

        # Check rate limit
        if not self.rate_limiter.can_process_request():
            raise RateLimitExceededError("Rate limit exceeded")

        logger.info(f"Processing request from {note_path}")

        # Send to Claude
        response_text = await self.claude_client.process_request(
            request_text=request.request_text
        )

        # Create response note
        response_path = await self.response_writer.create_response_note(
            source_note_path=note_path,
            request_text=request.request_text,
            response_text=response_text,
            status="Success"
        )

        # Update source note to mark as processed
        response_name = Path(response_path).stem
        updated_content = self.request_parser.mark_request_processed(
            content=pending.note_content,
            request=request,
            response_link=response_name
        )

        await self.response_writer.update_source_note(
            note_path=note_path,
            updated_content=updated_content
        )

        # Record in rate limiter
        self.rate_limiter.record_request(
            note_path=note_path,
            request_hash=request.request_hash,
            response_path=response_path
        )

        logger.info(f"Successfully processed request from {note_path}")

    async def _mark_request_error(self, pending, error_message: str) -> None:
        """
        Mark a request as failed in the source note.

        Args:
            pending: PendingRequest object
            error_message: Error description
        """
        try:
            updated_content = self.request_parser.mark_request_error(
                content=pending.note_content,
                request=pending.request,
                error_message=error_message
            )

            await self.response_writer.update_source_note(
                note_path=pending.note_path,
                updated_content=updated_content
            )

            logger.info(f"Marked request as error in {pending.note_path}")

        except Exception as e:
            logger.error(f"Failed to mark error in note: {e}")

    async def status(self) -> int:
        """
        Check and display system status.

        Returns:
            Exit code
        """
        try:
            await self.initialize()

            print("Obsidian-Claude Agent Status")
            print("=" * 40)

            # Check MCP connection
            print("\n[MCP Server]")
            try:
                await self.mcp_client.connect()
                print("  Status: ✓ Connected")
                await self.mcp_client.disconnect()
            except Exception as e:
                print(f"  Status: ✗ Connection failed: {e}")

            # Check rate limiter
            print("\n[Rate Limiter]")
            usage = self.rate_limiter.get_current_usage()
            print(f"  Requests this hour: {usage['current_hour_requests']}/{usage['max_requests_per_hour']}")
            print(f"  Remaining: {usage['remaining_requests']}")
            print(f"  Total processed: {usage['total_processed']}")

            # Check Claude API
            print("\n[Claude API]")
            print(f"  Model: {self.config.claude_model}")
            print(f"  Allowed tools: {', '.join(self.config.default_allowed_tools)}")

            print("\n" + "=" * 40)
            return 0

        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return 1


async def async_main(args) -> int:
    """
    Async main function.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code
    """
    # Load configuration
    try:
        config = Config(config_path=args.config)
    except ConfigurationError as e:
        logger.critical(f"Configuration error: {e}")
        return 2

    # Setup logging
    setup_logging(
        log_file=config.logging_file,
        level=config.logging_level,
        max_size=config.logging_max_size,
        backup_count=config.logging_backup_count
    )

    # Create agent
    agent = ObsidianClaudeAgent(config)

    # Execute command
    if args.command == 'run':
        return await agent.run(dry_run=args.dry_run)
    elif args.command == 'status':
        return await agent.status()
    elif args.command == 'init':
        print("Configuration initialized successfully")
        return 0
    elif args.command == 'reset':
        if args.confirm:
            agent.rate_limiter = RateLimiter(state_file=config.state_file)
            count = agent.rate_limiter.reset_processed()
            print(f"Reset {count} processed requests")
            return 0
        else:
            print("Use --confirm to reset processed request history")
            return 1
    else:
        print(f"Unknown command: {args.command}")
        return 1


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Obsidian-Claude Automation Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'command',
        choices=['run', 'status', 'init', 'reset'],
        help='Command to execute'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without executing (run command only)'
    )

    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Confirm destructive operations (reset command only)'
    )

    parser.add_argument(
        '--config',
        default='config/default_config.yaml',
        help='Path to configuration file'
    )

    parser.add_argument(
        '--permissions',
        default='config/vault_permissions.yaml',
        help='Path to permissions file'
    )

    args = parser.parse_args()

    # Run async main
    try:
        exit_code = asyncio.run(async_main(args))
        return exit_code
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
