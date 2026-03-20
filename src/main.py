"""
Main CLI Entry Point

Orchestrates the Obsidian-Claude automation agent.
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from .config import Config
from .cli_client import ObsidianCLIClient
from .claude_client import ClaudeClient
from .note_scanner import NoteScanner
from .response_writer import ResponseWriter
from .request_parser import RequestParser
from .rate_limiter import RateLimiter
from .image_processor import ImageProcessor
from .image_extractor import ImageExtractor
from .logger import setup_logging
from .exceptions import (
    ObsidianClaudeError,
    MCPConnectionError,
    MCPError,
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
        self.cli_client = None
        self.claude_client = None
        self.note_scanner = None
        self.response_writer = None
        self.request_parser = None
        self.rate_limiter = None
        self.image_processor = None
        self.image_extractor = None

    def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing Obsidian-Claude Agent...")

        # Initialize CLI client
        self.cli_client = ObsidianCLIClient(
            vault_path=self.config.obsidian_vault_path,
            cli_path=self.config.obsidian_cli_path,
            timeout=self.config.obsidian_timeout
        )

        # Initialize Claude client
        self.claude_client = ClaudeClient(
            model=self.config.claude_model,
            max_tokens=self.config.claude_max_tokens,
            temperature=self.config.claude_temperature,
            allowed_tools=self.config.default_allowed_tools
        )

        # Initialize request parser
        self.request_parser = RequestParser()

        # Initialize note scanner
        self.note_scanner = NoteScanner(
            cli_client=self.cli_client,
            request_parser=self.request_parser,
            timeframe_days=self.config.scanning_timeframe_days
        )

        # Initialize response writer
        self.response_writer = ResponseWriter(
            cli_client=self.cli_client,
            response_suffix=self.config.response_suffix,
            include_timestamp=self.config.response_include_timestamp,
            max_response_length=self.config.response_max_length
        )

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            state_file=self.config.state_file,
            max_requests_per_hour=self.config.rate_limit_max_per_hour
        )

        # Initialize image processor
        self.image_processor = ImageProcessor(
            vault_path=self.config.obsidian_vault_path,
            attachment_folders=self.config.get('image_processing.attachment_folders', ['_attachments', 'assets', 'images']),
            max_file_size_mb=self.config.get('image_processing.max_file_size_mb', 10)
        )

        # Initialize image extractor
        self.image_extractor = ImageExtractor(
            image_processor=self.image_processor,
            claude_client=self.claude_client,
            ocr_prompt=self.config.get('image_processing.ocr_extraction.prompt'),
            max_images_per_request=self.config.get('image_processing.ocr_extraction.max_images_per_request', 5)
        )

        logger.info("All components initialized")

    def run(self, dry_run: bool = False) -> int:
        """
        Run a single scan and process requests.

        Args:
            dry_run: If True, don't actually process requests

        Returns:
            Exit code (0=success, >0=error)
        """
        try:
            self.initialize()

            # Connect to vault
            logger.info("Connecting to Obsidian vault...")
            self.cli_client.connect()

            # Scan for pending requests
            logger.info("Scanning vault for @claude requests...")
            pending_requests = self.note_scanner.scan_for_requests()

            if not pending_requests:
                logger.info("No pending requests found")
                return 0

            logger.info(f"Found {len(pending_requests)} pending request(s)")

            if dry_run:
                print("\n" + "=" * 60)
                print("DRY RUN: Would process the following requests:")
                print("=" * 60)
                logger.info("DRY RUN: Would process the following requests:")
                for req in pending_requests:
                    preview = req.request.request_text[:50] + "..." if len(req.request.request_text) > 50 else req.request.request_text
                    print(f"\n  [{req.note_path}]")
                    print(f"    Request: {preview}")
                    if req.request.context:
                        context_preview = req.request.context[:100] + "..." if len(req.request.context) > 100 else req.request.context
                        print(f"    Context: {len(req.request.context)} chars")
                        print(f"    Preview: {context_preview}")
                    if req.request.wikilinks:
                        print(f"    Wikilinks: {', '.join(req.request.wikilinks)}")
                    logger.info(f"  - {req.note_path}: {preview}")
                print("\n" + "=" * 60 + "\n")
                return 0

            # Process each request
            processed_count = 0
            for pending in pending_requests:
                try:
                    self._process_single_request(pending)
                    processed_count += 1

                except RateLimitExceededError as e:
                    logger.warning(f"Rate limit exceeded: {e}")
                    next_time = self.rate_limiter.get_next_available_time()
                    if next_time:
                        logger.info(f"Next request available at: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    break  # Stop processing more requests

                except Exception as e:
                    logger.error(f"Failed to process request from {pending.note_path}: {e}")
                    # Mark as error in note
                    self._mark_request_error(pending, str(e))
                    continue

            logger.info(f"Processing complete: {processed_count} request(s) processed")
            return 0

        except MCPConnectionError as e:
            logger.critical(f"MCP connection failed: {e}")
            return 3

        except ClaudeAPIError as e:
            logger.critical(f"Claude API error: {e}")
            return 4

        except Exception as e:
            logger.critical(f"Unexpected error: {e}", exc_info=True)
            return 1

        finally:
            # Disconnect CLI client
            if self.cli_client:
                self.cli_client.disconnect()
                logger.info("Disconnected from vault")

    def _process_single_request(self, pending) -> None:
        """
        Process a single pending request with two-phase image processing.

        Phase 1: Extract text from images (if any)
        Phase 2: Process main request with enhanced context

        Args:
            pending: PendingRequest object
        """
        note_path = pending.note_path
        request = pending.request

        # Check if already processed
        if self.rate_limiter.is_processed(note_path, request.request_hash):
            logger.debug(f"Request already processed: {note_path}")
            return

        # Calculate total API calls needed
        image_api_calls = 0
        if request.image_wikilinks and self.config.get('image_processing.enabled', True):
            if self.config.get('image_processing.count_ocr_toward_rate_limit', True):
                # Limit to max_images_per_request if configured
                max_images = self.config.get('image_processing.ocr_extraction.max_images_per_request', 5)
                image_api_calls = min(len(request.image_wikilinks), max_images)

        main_request_calls = 1
        total_api_calls = image_api_calls + main_request_calls

        # Check if we have enough quota for all API calls
        current_usage = self.rate_limiter.get_current_usage()
        available_quota = current_usage['remaining_requests']

        if total_api_calls > available_quota:
            raise RateLimitExceededError(
                f"Insufficient rate limit quota: need {total_api_calls} API calls "
                f"({image_api_calls} image OCR + {main_request_calls} main request), "
                f"but only {available_quota} remaining in current hour"
            )

        logger.info(f"Processing request from {note_path} (requires {total_api_calls} API call(s))")

        # PHASE 1: Extract text from images (if any) and insert inline
        extracted_image_text = {}
        if request.image_wikilinks:
            logger.info(f"Phase 1: Extracting text from {len(request.image_wikilinks)} image(s)")

            # Check if image processing is enabled
            if self.config.get('image_processing.enabled', True):
                # Record each image OCR as a separate API call for rate limiting
                count_ocr = self.config.get('image_processing.count_ocr_toward_rate_limit', True)

                extracted_image_text = self.image_extractor.extract_text_from_images(
                    image_filenames=request.image_wikilinks,
                    source_note_path=note_path
                )

                # Record API calls for each image processed
                if count_ocr:
                    for image_filename in request.image_wikilinks[:len(extracted_image_text)]:
                        self.rate_limiter.record_request(
                            note_path=f"{note_path}:image:{image_filename}",
                            request_hash="ocr",
                            response_path=None
                        )
                        logger.debug(f"Recorded OCR API call for {image_filename}")

                # Insert extracted text under each image in the note
                if extracted_image_text:
                    updated_content = self.response_writer.insert_image_text_under_images(
                        note_content=pending.note_content,
                        extracted_image_text=extracted_image_text
                    )

                    # Update the note with extracted image text
                    self.response_writer.update_source_note(
                        note_path=note_path,
                        updated_content=updated_content
                    )

                    logger.info(f"Phase 1 complete: Inserted extracted text under {len(extracted_image_text)} image(s)")

                    # Re-read the note to get fresh content (positions have shifted)
                    pending.note_content = self.cli_client.read_note(note_path)

                    # Re-parse to get updated @claude marker positions
                    request = self.request_parser.find_first_request(pending.note_content)
                    if not request:
                        raise MCPError("Request marker not found after image text insertion")
            else:
                logger.info("Image processing disabled in config, skipping Phase 1")

        # Build enhanced context with image text (for Claude's context)
        if extracted_image_text:
            enhanced_context = self.image_extractor.build_context_with_image_text(
                original_context=request.context,
                extracted_image_text=extracted_image_text
            )
        else:
            enhanced_context = request.context

        # Log context information
        if enhanced_context:
            logger.debug(f"Including context ({len(enhanced_context)} chars) with {len(request.wikilinks)} wikilinks")
            if extracted_image_text:
                logger.debug(f"Context enhanced with {len(extracted_image_text)} image extraction(s)")

        # PHASE 2: Send main request to Claude and create separate response note
        logger.info("Phase 2: Processing main request with enhanced context")
        response_text = self.claude_client.process_request(
            request_text=request.request_text,
            context=enhanced_context,
            wikilinks=request.wikilinks
        )

        # Create separate response note
        response_path = self.response_writer.create_response_note(
            source_note_path=note_path,
            request_text=request.request_text,
            response_text=response_text,
            status="Success"
        )

        # Mark @claude as @claude-done with response link
        updated_content = self.request_parser.mark_request_processed(
            content=pending.note_content,
            request=request,
            response_link=self.response_writer.extract_note_name(response_path)
        )

        # Update source note with @claude-done marker
        self.response_writer.update_source_note(
            note_path=note_path,
            updated_content=updated_content
        )

        # Record in rate limiter
        self.rate_limiter.record_request(
            note_path=note_path,
            request_hash=request.request_hash,
            response_path=response_path  # Points to separate response note
        )

        logger.info(f"Successfully processed request from {note_path}, response in {response_path}")

    def _mark_request_error(self, pending, error_message: str) -> None:
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

            self.response_writer.update_source_note(
                note_path=pending.note_path,
                updated_content=updated_content
            )

            logger.info(f"Marked request as error in {pending.note_path}")

        except Exception as e:
            logger.error(f"Failed to mark error in note: {e}")

    def status(self) -> int:
        """
        Check and display system status.

        Returns:
            Exit code
        """
        try:
            self.initialize()

            print("Obsidian-Claude Agent Status")
            print("=" * 40)

            # Check vault connection
            print("\n[Obsidian Vault]")
            try:
                self.cli_client.connect()
                print(f"  Path: {self.config.obsidian_vault_path}")
                print("  Status: ✓ Connected")
                self.cli_client.disconnect()
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


def run_agent(args) -> int:
    """
    Run the agent with parsed arguments.

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
        return agent.run(dry_run=args.dry_run)
    elif args.command == 'status':
        return agent.status()
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
    # Load environment variables from .env file
    load_dotenv()

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

    # Run agent
    try:
        exit_code = run_agent(args)
        return exit_code
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
