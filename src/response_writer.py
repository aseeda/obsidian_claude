"""
Response Writer Module

Creates and formats response notes in Obsidian vault.
Uses CLI client for direct file system vault operations.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict
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

    def insert_image_text_under_images(
        self,
        note_content: str,
        extracted_image_text: Dict[str, str]
    ) -> str:
        """
        Insert extracted text immediately under each image wikilink.

        Inserts from bottom to top to avoid position shifting.

        Args:
            note_content: Current note content
            extracted_image_text: Dict of filename -> extracted text

        Returns:
            Updated note content with text inserted under images
        """
        if not extracted_image_text:
            return note_content

        # Find all image positions in the note
        image_insertions = []

        for filename, extracted_text in extracted_image_text.items():
            # Create pattern to find ![[filename]]
            pattern = re.escape(f"![[{filename}]]")

            # Find all matches (there might be multiple references to same image)
            for match in re.finditer(pattern, note_content):
                insertion_pos = match.end()  # Position right after ![[filename]]

                # Build the text to insert
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                insertion_text = (
                    f"\n\n**Extracted from {filename} ({timestamp}):**\n"
                    f"{extracted_text}\n\n---\n"
                )

                image_insertions.append({
                    'position': insertion_pos,
                    'text': insertion_text,
                    'filename': filename
                })

        if not image_insertions:
            logger.warning("No image wikilinks found in note for extracted text")
            return note_content

        # Sort by position descending (insert from bottom to top)
        image_insertions.sort(key=lambda x: x['position'], reverse=True)

        # Insert text for each image
        updated_content = note_content
        for insertion in image_insertions:
            pos = insertion['position']
            text = insertion['text']
            updated_content = (
                updated_content[:pos] +
                text +
                updated_content[pos:]
            )
            logger.debug(f"Inserted extracted text under {insertion['filename']} at position {pos}")

        logger.info(f"Inserted extracted text under {len(image_insertions)} image(s)")
        return updated_content

    def append_response_to_note(
        self,
        note_path: str,
        note_content: str,
        request_marker: str,
        response_text: str,
        extracted_image_text: Optional[dict] = None,
        start_position: Optional[int] = None,
        end_position: Optional[int] = None
    ) -> str:
        """
        Append response and extracted image text directly to note after @claude marker.

        Args:
            note_path: Path to the note
            note_content: Current note content
            request_marker: The @claude marker to replace
            response_text: Claude's response to append
            extracted_image_text: Optional dict of filename -> extracted text
            start_position: Optional start position of the request marker (for position-based replacement)
            end_position: Optional end position of the request marker (for position-based replacement)

        Returns:
            Updated note content

        Raises:
            MCPError: If update fails
        """
        # Build the done marker
        done_marker = request_marker.replace('@claude', '@claude-done')

        # Use position-based replacement if positions are provided (safer than string replacement)
        if start_position is not None and end_position is not None:
            # Replace @claude with @claude-done at exact position
            updated_content = (
                note_content[:start_position] +
                done_marker +
                note_content[end_position:]
            )
            # Insertion point is immediately after the done marker
            insertion_point = start_position + len(done_marker)
        else:
            # Fallback to string replacement (less safe, but backwards compatible)
            logger.warning("Using string-based replacement (no position info provided)")
            updated_content = note_content.replace(
                request_marker,
                done_marker,
                1
            )

            # Find position after @claude-done marker
            marker_pos = updated_content.find(done_marker)

            if marker_pos == -1:
                logger.error("Could not find @claude-done marker after replacement")
                raise MCPError("Failed to locate marker in note")

            # Calculate insertion point (after the marker)
            insertion_point = marker_pos + len(done_marker)

        # Build sections to append
        append_sections = ["\n\n---\n"]

        # Add extracted image text section
        if extracted_image_text:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            append_sections.append(f"**Extracted Image Text ({timestamp}):**\n")

            for filename, text in extracted_image_text.items():
                append_sections.append(f"\n**From {filename}:**\n{text}\n")

            append_sections.append("\n---\n")

        # Add main response
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        append_sections.append(f"**Response ({timestamp}):**\n")

        # Truncate response if needed
        if self.max_response_length and len(response_text) > self.max_response_length:
            response_text = (
                response_text[:self.max_response_length] +
                f"\n\n[Response truncated at {self.max_response_length} characters]"
            )

        append_sections.append(response_text)
        append_sections.append("\n---\n")

        # Insert sections at calculated position
        final_content = (
            updated_content[:insertion_point] +
            "".join(append_sections) +
            updated_content[insertion_point:]
        )

        # Update the note
        try:
            self.cli_client.update_note(
                path=note_path,
                content=final_content
            )
            logger.info(f"Appended response to note: {note_path}")
            return final_content

        except Exception as e:
            logger.error(f"Failed to append response to note: {e}")
            raise MCPError(f"Failed to update note: {e}")

    def extract_note_name(self, note_path: str) -> str:
        """
        Extract note name from path for wikilinks.

        Args:
            note_path: Full path to note

        Returns:
            Note name without extension
        """
        return Path(note_path).stem
