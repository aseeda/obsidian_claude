"""
Tests for Request Parser Module
"""

import pytest
from src.request_parser import RequestParser, ClaudeRequest


class TestRequestParser:
    """Test suite for RequestParser class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = RequestParser()

    def test_inline_request_basic(self):
        """Test basic inline request format."""
        content = "Some text\n@claude What is the weather?\nMore text"
        request = self.parser.find_first_request(content)

        assert request is not None
        assert request.request_text == "What is the weather?"
        assert request.original_marker == "@claude What is the weather?"

    def test_inline_request_with_colon(self):
        """Test inline request with colon separator."""
        content = "@claude: Summarize this document"
        request = self.parser.find_first_request(content)

        assert request is not None
        assert request.request_text == "Summarize this document"

    def test_inline_request_with_dash(self):
        """Test inline request with dash separator."""
        content = "@claude - List all items"
        request = self.parser.find_first_request(content)

        assert request is not None
        assert request.request_text == "List all items"

    def test_multiline_request(self):
        """Test multi-line triple-quote request."""
        content = '''@claude """
This is a multi-line request.
It spans multiple lines.
Please process this.
"""'''
        request = self.parser.find_first_request(content)

        assert request is not None
        assert "This is a multi-line request" in request.request_text
        assert "It spans multiple lines" in request.request_text
        assert "Please process this" in request.request_text

    def test_case_sensitive_uppercase_ignored(self):
        """Test that uppercase @CLAUDE is ignored when case_sensitive=True."""
        content = "@CLAUDE This should be ignored"
        request = self.parser.find_first_request(content)

        assert request is None

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        parser = RequestParser(case_sensitive=False)
        content = "@CLAUDE This should match"
        request = parser.find_first_request(content)

        assert request is not None
        assert request.request_text == "This should match"

    def test_ignore_in_code_block(self):
        """Test that @claude in code blocks is ignored."""
        content = '''
Some text
```python
@claude This is in a code block
print("hello")
```
@claude This is outside the block
'''
        request = self.parser.find_first_request(content)

        assert request is not None
        assert request.request_text == "This is outside the block"

    def test_ignore_in_html_comment(self):
        """Test that @claude in HTML comments is ignored."""
        content = '''
<!-- @claude This is in a comment -->
@claude This is not in a comment
'''
        request = self.parser.find_first_request(content)

        assert request is not None
        assert request.request_text == "This is not in a comment"

    def test_no_request_found(self):
        """Test when no request is present."""
        content = "Just some regular text without any requests"
        request = self.parser.find_first_request(content)

        assert request is None

    def test_multiline_takes_precedence(self):
        """Test that multiline request is found first."""
        content = '''@claude Inline request
@claude """
Multi-line request
"""'''
        request = self.parser.find_first_request(content)

        assert request is not None
        assert "Multi-line request" in request.request_text

    def test_request_hash_generation(self):
        """Test that request hash is generated correctly."""
        content = "@claude Test request"
        request = self.parser.find_first_request(content)

        assert request is not None
        assert len(request.request_hash) == 16
        assert request.request_hash.isalnum()

    def test_same_request_same_hash(self):
        """Test that identical requests produce the same hash."""
        content1 = "@claude Test request"
        content2 = "@claude Test request"

        request1 = self.parser.find_first_request(content1)
        request2 = self.parser.find_first_request(content2)

        assert request1.request_hash == request2.request_hash

    def test_different_request_different_hash(self):
        """Test that different requests produce different hashes."""
        content1 = "@claude Request one"
        content2 = "@claude Request two"

        request1 = self.parser.find_first_request(content1)
        request2 = self.parser.find_first_request(content2)

        assert request1.request_hash != request2.request_hash

    def test_mark_request_processed(self):
        """Test marking a request as processed."""
        content = "Some text\n@claude What is this?\nMore text"
        request = self.parser.find_first_request(content)

        updated = self.parser.mark_request_processed(
            content,
            request,
            response_link="response_note"
        )

        assert "@claude-done" in updated
        assert "@claude What is this?" not in updated
        assert "[[response_note]]" in updated

    def test_mark_request_processed_no_link(self):
        """Test marking a request as processed without response link."""
        content = "@claude Test request"
        request = self.parser.find_first_request(content)

        updated = self.parser.mark_request_processed(content, request)

        assert "@claude-done" in updated
        assert "@claude Test" not in updated

    def test_mark_request_error(self):
        """Test marking a request with an error."""
        content = "@claude Invalid request"
        request = self.parser.find_first_request(content)

        updated = self.parser.mark_request_error(
            content,
            request,
            "Unauthorized tool requested"
        )

        assert "@claude-error" in updated
        assert "Unauthorized tool requested" in updated

    def test_position_tracking(self):
        """Test that positions are tracked correctly."""
        content = "Line 1\nLine 2\n@claude Request here\nLine 4"
        request = self.parser.find_first_request(content)

        assert request is not None
        assert request.start_position > 0
        assert request.end_position > request.start_position
        assert content[request.start_position:request.end_position] == request.original_marker

    def test_multiple_code_blocks(self):
        """Test handling multiple code blocks."""
        content = '''
```
@claude First block
```
Some text
```js
@claude Second block
```
@claude Real request
'''
        request = self.parser.find_first_request(content)

        assert request is not None
        assert request.request_text == "Real request"

    def test_nested_markers_in_request(self):
        """Test request containing @claude-done or @claude-error."""
        content = '@claude Can you explain @claude-done and @claude-error markers?'
        request = self.parser.find_first_request(content)

        assert request is not None
        assert "@claude-done" in request.request_text
        assert "@claude-error" in request.request_text

    def test_empty_content(self):
        """Test parsing empty content."""
        request = self.parser.find_first_request("")
        assert request is None

    def test_whitespace_only(self):
        """Test parsing whitespace-only content."""
        request = self.parser.find_first_request("   \n\n   \t  ")
        assert request is None

    def test_multiline_with_extra_whitespace(self):
        """Test multiline request with extra whitespace."""
        content = '''@claude   """

  Request with whitespace

  """'''
        request = self.parser.find_first_request(content)

        assert request is not None
        assert "Request with whitespace" in request.request_text
