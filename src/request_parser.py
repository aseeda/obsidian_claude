"""
Request Parser Module

Extracts and parses @claude requests from Obsidian note content.
Supports multiple request formats and ignores requests in code blocks and comments.
"""

import re
import hashlib
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class ClaudeRequest:
    """Represents a parsed @claude request."""
    request_text: str
    start_position: int
    end_position: int
    request_hash: str
    original_marker: str  # The original @claude marker for replacement
    context: str = ""  # Content above the request for context
    wikilinks: list = None  # Wikilinks found in context
    image_wikilinks: list = None  # Image wikilinks found in context
    extracted_image_text: dict = None  # Dict mapping filename -> extracted text

    def __post_init__(self):
        """Initialize lists and dict if not provided."""
        if self.wikilinks is None:
            self.wikilinks = []
        if self.image_wikilinks is None:
            self.image_wikilinks = []
        if self.extracted_image_text is None:
            self.extracted_image_text = {}


class RequestParser:
    """
    Parses @claude requests from note content.

    Supported formats:
    - @claude [request text]
    - @claude: [request text]
    - @claude - [request text]
    - @claude \"\"\"
      [multi-line request]
      \"\"\"

    Ignores requests inside:
    - Markdown code blocks (triple backticks)
    - HTML comments
    """

    # Regex patterns for different request formats
    INLINE_PATTERN = re.compile(
        r'(?P<marker>@claude)\s*(?P<separator>:|-|)\s*(?P<request>.+?)(?=\n|$)',
        re.IGNORECASE
    )

    MULTILINE_PATTERN = re.compile(
        r'(?P<marker>@claude)\s+"""\s*\n(?P<request>.*?)"""',
        re.DOTALL
    )

    CODE_BLOCK_PATTERN = re.compile(r'```.*?```', re.DOTALL)
    HTML_COMMENT_PATTERN = re.compile(r'<!--.*?-->', re.DOTALL)
    WIKILINK_PATTERN = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')  # Matches [[link]] or [[link|alias]]
    IMAGE_WIKILINK_PATTERN = re.compile(
        r'!\[\[([^\]]+\.(?:jpg|jpeg|png|gif|webp))\]\]',
        re.IGNORECASE
    )  # Matches ![[image.jpg]] or ![[image.png]], etc.

    def __init__(self, case_sensitive: bool = True):
        """
        Initialize the request parser.

        Args:
            case_sensitive: If True, only match lowercase '@claude'
        """
        self.case_sensitive = case_sensitive

    def _extract_context(self, content: str, start_position: int) -> str:
        """
        Extract all content above the request marker.

        Args:
            content: The full note content
            start_position: Position where the @claude request starts

        Returns:
            Content before the request
        """
        return content[:start_position].strip()

    def _extract_wikilinks(self, text: str) -> list:
        """
        Extract all wikilinks from text.

        Args:
            text: Text to extract wikilinks from

        Returns:
            List of note names (without [[ ]])
        """
        matches = self.WIKILINK_PATTERN.findall(text)
        return [match.strip() for match in matches]

    def _extract_image_wikilinks(self, text: str) -> list:
        """
        Extract all image wikilinks from text.

        Args:
            text: Text to extract image wikilinks from

        Returns:
            List of image filenames (without ![[ ]])
        """
        matches = self.IMAGE_WIKILINK_PATTERN.findall(text)
        return [match.strip() for match in matches]

    def find_first_request(self, content: str) -> Optional[ClaudeRequest]:
        """
        Find the first unprocessed @claude request in the content.

        Args:
            content: The note content to parse

        Returns:
            ClaudeRequest object if found, None otherwise
        """
        # Remove code blocks and HTML comments to avoid false matches
        cleaned_content = self._remove_ignored_sections(content)

        # Try to find multi-line request first (higher precedence)
        multiline_match = self._find_multiline_request(cleaned_content, content)
        if multiline_match:
            return multiline_match

        # Try inline request
        inline_match = self._find_inline_request(cleaned_content, content)
        if inline_match:
            return inline_match

        return None

    def _remove_ignored_sections(self, content: str) -> str:
        """
        Remove code blocks and HTML comments from content.

        Args:
            content: Original content

        Returns:
            Content with ignored sections replaced by spaces
        """
        # Replace with spaces to maintain position indices
        cleaned = self.CODE_BLOCK_PATTERN.sub(
            lambda m: ' ' * len(m.group(0)),
            content
        )
        cleaned = self.HTML_COMMENT_PATTERN.sub(
            lambda m: ' ' * len(m.group(0)),
            cleaned
        )
        return cleaned

    def _find_multiline_request(
        self,
        cleaned_content: str,
        original_content: str
    ) -> Optional[ClaudeRequest]:
        """Find multi-line triple-quote request."""
        match = self.MULTILINE_PATTERN.search(cleaned_content)

        if not match:
            return None

        # Check case sensitivity
        if self.case_sensitive and match.group('marker') != '@claude':
            return None

        request_text = match.group('request').strip()
        start_pos = match.start()
        end_pos = match.end()

        # Extract context, wikilinks, and image wikilinks
        context = self._extract_context(original_content, start_pos)
        wikilinks = self._extract_wikilinks(context)
        image_wikilinks = self._extract_image_wikilinks(context)

        return ClaudeRequest(
            request_text=request_text,
            start_position=start_pos,
            end_position=end_pos,
            request_hash=self._generate_hash(request_text),
            original_marker=match.group(0),
            context=context,
            wikilinks=wikilinks,
            image_wikilinks=image_wikilinks
        )

    def _find_inline_request(
        self,
        cleaned_content: str,
        original_content: str
    ) -> Optional[ClaudeRequest]:
        """Find inline single-line request."""
        match = self.INLINE_PATTERN.search(cleaned_content)

        if not match:
            return None

        # Check case sensitivity
        if self.case_sensitive and match.group('marker') != '@claude':
            return None

        request_text = match.group('request').strip()
        start_pos = match.start()
        end_pos = match.end()

        # Extract context, wikilinks, and image wikilinks
        context = self._extract_context(original_content, start_pos)
        wikilinks = self._extract_wikilinks(context)
        image_wikilinks = self._extract_image_wikilinks(context)

        return ClaudeRequest(
            request_text=request_text,
            start_position=start_pos,
            end_position=end_pos,
            request_hash=self._generate_hash(request_text),
            original_marker=match.group(0),
            context=context,
            wikilinks=wikilinks,
            image_wikilinks=image_wikilinks
        )

    def _generate_hash(self, request_text: str) -> str:
        """
        Generate a unique hash for a request.

        Args:
            request_text: The request text to hash

        Returns:
            SHA256 hash of the request (first 16 characters)
        """
        return hashlib.sha256(request_text.encode('utf-8')).hexdigest()[:16]

    def mark_request_processed(
        self,
        content: str,
        request: ClaudeRequest,
        response_link: Optional[str] = None
    ) -> str:
        """
        Mark a request as processed by replacing @claude with @claude-done.

        Args:
            content: Original note content
            request: The ClaudeRequest to mark as processed
            response_link: Optional link to response note

        Returns:
            Updated content with request marked as done
        """
        # Replace @claude with @claude-done
        replacement = request.original_marker.replace('@claude', '@claude-done', 1)

        # Add response link if provided
        if response_link:
            replacement += f'\n**Response:** [[{response_link}]]'

        # Perform replacement at specific position
        updated_content = (
            content[:request.start_position] +
            replacement +
            content[request.end_position:]
        )

        return updated_content

    def mark_request_error(
        self,
        content: str,
        request: ClaudeRequest,
        error_message: str
    ) -> str:
        """
        Mark a request as failed by replacing @claude with @claude-error.

        Args:
            content: Original note content
            request: The ClaudeRequest that failed
            error_message: Error description to include

        Returns:
            Updated content with error marker
        """
        # Replace @claude with @claude-error
        replacement = request.original_marker.replace('@claude', '@claude-error', 1)
        replacement += f'\n**Error:** {error_message}'

        # Perform replacement at specific position
        updated_content = (
            content[:request.start_position] +
            replacement +
            content[request.end_position:]
        )

        return updated_content
