"""
Note Scanner Module

Scans Obsidian vault for notes containing @claude requests.
Uses CLI client for direct file system vault operations.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from dataclasses import dataclass

from .cli_client import ObsidianCLIClient
from .request_parser import RequestParser, ClaudeRequest
from .exceptions import MCPError

logger = logging.getLogger(__name__)


@dataclass
class PendingRequest:
    """Represents a pending @claude request found in a note."""
    note_path: str
    note_content: str
    request: ClaudeRequest


class NoteScanner:
    """
    Scans vault for notes with unprocessed @claude requests.

    Responsibilities:
    - Search for notes modified within timeframe
    - Filter notes containing @claude markers
    - Parse and extract request details
    - Return pending requests for processing
    """

    def __init__(
        self,
        cli_client: ObsidianCLIClient,
        request_parser: Optional[RequestParser] = None,
        timeframe_days: int = 7
    ):
        """
        Initialize the note scanner.

        Args:
            cli_client: CLI client for vault operations
            request_parser: Parser for extracting requests (creates default if None)
            timeframe_days: How many days back to scan for modified notes
        """
        self.cli_client = cli_client
        self.request_parser = request_parser or RequestParser()
        self.timeframe_days = timeframe_days

    def scan_for_requests(self) -> List[PendingRequest]:
        """
        Scan vault for pending @claude requests.

        Returns:
            List of pending requests found

        Raises:
            MCPError: If vault search fails
        """
        logger.info(f"Scanning vault for @claude requests (last {self.timeframe_days} days)")

        try:
            # Search for notes containing @claude
            note_paths = self._search_notes_with_marker()

            logger.info(f"Found {len(note_paths)} notes with @claude marker")

            # Process each note to find pending requests
            pending_requests = []

            for note_path in note_paths:
                try:
                    request = self._extract_request_from_note(note_path)
                    if request:
                        pending_requests.append(request)
                        logger.debug(f"Found pending request in: {note_path}")

                except Exception as e:
                    logger.warning(f"Failed to process note {note_path}: {e}")
                    continue

            logger.info(f"Found {len(pending_requests)} pending requests")
            return pending_requests

        except Exception as e:
            logger.error(f"Vault scan failed: {e}")
            raise MCPError(f"Failed to scan vault: {e}")

    def _search_notes_with_marker(self) -> List[str]:
        """
        Search for notes containing @claude marker.

        Returns:
            List of note paths
        """
        try:
            # Search for @claude in note content using CLI client
            results = self.cli_client.search_notes(query="@claude")

            # Extract paths from results
            note_paths = []
            if isinstance(results, list):
                for result in results:
                    if isinstance(result, dict) and 'path' in result:
                        note_paths.append(result['path'])
                    elif isinstance(result, str):
                        note_paths.append(result)

            return note_paths

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def _extract_request_from_note(
        self,
        note_path: str
    ) -> Optional[PendingRequest]:
        """
        Extract the first unprocessed request from a note.

        Args:
            note_path: Path to the note

        Returns:
            PendingRequest if found, None otherwise
        """
        try:
            # Read note content using CLI client
            content = self.cli_client.read_note(note_path)

            # Skip if content is empty
            if not content or not content.strip():
                return None

            # Parse for request
            request = self.request_parser.find_first_request(content)

            # Return None if no request found
            if not request:
                return None

            # Check if it's already processed (@claude-done or @claude-error)
            if '@claude-done' in request.original_marker or '@claude-error' in request.original_marker:
                return None

            return PendingRequest(
                note_path=note_path,
                note_content=content,
                request=request
            )

        except Exception as e:
            logger.error(f"Failed to read note {note_path}: {e}")
            raise

    def filter_by_modification_time(
        self,
        note_paths: List[str],
        days: Optional[int] = None
    ) -> List[str]:
        """
        Filter notes by modification time.

        Note: This is a placeholder. The MCP server doesn't provide
        modification times in search results, so we currently process
        all found notes. In a real implementation, this would filter
        based on file metadata.

        Args:
            note_paths: List of note paths
            days: Days to look back (uses instance default if None)

        Returns:
            Filtered list of note paths
        """
        # TODO: Implement once MCP provides file metadata
        # For now, return all notes
        return note_paths

    def get_note_content(self, note_path: str) -> str:
        """
        Get the full content of a note.

        Args:
            note_path: Path to the note

        Returns:
            Note content

        Raises:
            MCPError: If read fails
        """
        try:
            return self.cli_client.read_note(note_path)
        except Exception as e:
            raise MCPError(f"Failed to read note {note_path}: {e}")
