"""
Response Writer Module

Creates and formats response notes in Obsidian vault.
Uses CLI client for direct file system vault operations.
"""

import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from .cli_client import ObsidianCLIClient
from .exceptions import MCPError

logger = logging.getLogger(__name__)


class ResponseWriter:
    """
    Creates formatted response notes and updates source notes.

    Responsibilities:
    - Generate response note filenames with timestamps
    - Format response content with metadata
    - Create response notes via MCP
    - Update source notes with response links
    """

    def __init__(
        self,
        cli_client: ObsidianCLIClient,
        response_suffix: str = "response",
        include_timestamp: bool = True,
        max_response_length: Optional[int] = None
    ):
        """
        Initialize the response writer.

        Args:
            cli_client: CLI client for vault operations
            response_suffix: Suffix for response note filenames
            include_timestamp: Whether to include timestamps in responses
            max_response_length: Maximum response length (None for unlimited)
        """
        self.cli_client = cli_client
        self.response_suffix = response_suffix
        self.include_timestamp = include_timestamp
        self.max_response_length = max_response_length

    def create_response_note(
        self,
        source_note_path: str,
        request_text: str,
        response_text: str,
        status: str = "Success"
    ) -> str:
        """
        Create a response note in the vault.

        Args:
            source_note_path: Path to source note containing request
            request_text: The original request text
            response_text: Claude's response
            status: Status of the request (Success/Error)

        Returns:
            Path to created response note

        Raises:
            MCPError: If note creation fails
        """
        # Generate response note path
        response_path = self._generate_response_path(source_note_path)

        # Format response content
        content = self._format_response(
            source_note_path=source_note_path,
            request_text=request_text,
            response_text=response_text,
            status=status
        )

        # Create the note via CLI client
        try:
            self.cli_client.create_note(
                path=response_path,
                content=content
            )
            logger.info(f"Created response note: {response_path}")
            return response_path

        except Exception as e:
            logger.error(f"Failed to create response note: {e}")
            raise MCPError(f"Failed to create response note: {e}")

    def _generate_response_path(self, source_note_path: str) -> str:
        """
        Generate a unique response note path.

        Args:
            source_note_path: Path to source note

        Returns:
            Path for response note with timestamp
        """
        # Extract note name without extension
        source_path = Path(source_note_path)
        note_name = source_path.stem
        parent_dir = source_path.parent

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Build response filename
        response_filename = f"{note_name}_{self.response_suffix}_{timestamp}.md"

        # Combine with parent directory
        if str(parent_dir) != '.':
            response_path = str(parent_dir / response_filename)
        else:
            response_path = response_filename

        return response_path

    def _format_response(
        self,
        source_note_path: str,
        request_text: str,
        response_text: str,
        status: str
    ) -> str:
        """
        Format response content with metadata.

        Args:
            source_note_path: Path to source note
            request_text: Original request
            response_text: Claude's response
            status: Request status

        Returns:
            Formatted response content
        """
        # Truncate response if needed
        if self.max_response_length and len(response_text) > self.max_response_length:
            response_text = (
                response_text[:self.max_response_length] +
                f"\n\n[Response truncated at {self.max_response_length} characters]"
            )

        # Extract note name for wikilink
        source_name = Path(source_note_path).stem

        # Build content sections
        sections = ["# Claude Response\n"]

        # Source and request info
        sections.append(f"**Source Note:** [[{source_name}]]")
        sections.append(f"**Request:** {request_text}")

        if self.include_timestamp:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sections.append(f"**Timestamp:** {timestamp}")

        sections.append(f"**Status:** {status}\n")
        sections.append("---\n")

        # Response content
        sections.append("## Response\n")
        sections.append(response_text)
        sections.append("\n---\n")

        # Footer
        sections.append("*Generated by Obsidian-Claude Agent*")

        return "\n".join(sections)

    def update_source_note(
        self,
        note_path: str,
        updated_content: str
    ) -> None:
        """
        Update source note with modified content.

        Args:
            note_path: Path to note
            updated_content: New content

        Raises:
            MCPError: If update fails
        """
        try:
            self.cli_client.update_note(
                path=note_path,
                content=updated_content
            )
            logger.info(f"Updated source note: {note_path}")

        except Exception as e:
            logger.error(f"Failed to update source note: {e}")
            raise MCPError(f"Failed to update source note: {e}")

    def extract_note_name(self, note_path: str) -> str:
        """
        Extract note name from path for wikilinks.

        Args:
            note_path: Full path to note

        Returns:
            Note name without extension
        """
        return Path(note_path).stem
