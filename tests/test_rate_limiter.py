"""
Tests for Rate Limiter Module
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path

from src.rate_limiter import RateLimiter
from src.exceptions import RateLimitExceededError


class TestRateLimiter:
    """Test suite for RateLimiter class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary state file
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test_state.json')
        self.limiter = RateLimiter(
            state_file=self.state_file,
            max_requests_per_hour=5,
            cleanup_after_days=7
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove temporary files
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        os.rmdir(self.temp_dir)

    def test_initialization(self):
        """Test rate limiter initialization."""
        assert self.limiter.max_requests_per_hour == 5
        assert self.limiter.cleanup_after_days == 7
        assert len(self.limiter.processed_requests) == 0
        assert len(self.limiter.request_timestamps) == 0

    def test_can_process_request_initially(self):
        """Test that requests can be processed initially."""
        assert self.limiter.can_process_request() is True

    def test_record_single_request(self):
        """Test recording a single request."""
        self.limiter.record_request(
            note_path="test.md",
            request_hash="abc123",
            response_path="response.md"
        )

        assert self.limiter.is_processed("test.md", "abc123") is True
        assert len(self.limiter.request_timestamps) == 1

    def test_is_processed_check(self):
        """Test checking if request is processed."""
        assert self.limiter.is_processed("test.md", "abc123") is False

        self.limiter.record_request("test.md", "abc123")

        assert self.limiter.is_processed("test.md", "abc123") is True
        assert self.limiter.is_processed("test.md", "different") is False

    def test_rate_limit_enforcement(self):
        """Test that rate limit is enforced."""
        # Record max requests
        for i in range(5):
            self.limiter.record_request(
                note_path=f"test{i}.md",
                request_hash=f"hash{i}"
            )

        # Should not be able to process more
        assert self.limiter.can_process_request() is False

        # Should raise error when trying to record
        with pytest.raises(RateLimitExceededError):
            self.limiter.record_request("test6.md", "hash6")

    def test_get_next_available_time(self):
        """Test getting next available time."""
        # Initially should be None (can process now)
        assert self.limiter.get_next_available_time() is None

        # Fill up the rate limit
        for i in range(5):
            self.limiter.record_request(f"test{i}.md", f"hash{i}")

        # Should return a future time
        next_time = self.limiter.get_next_available_time()
        assert next_time is not None
        assert next_time > datetime.now()

    def test_response_path_mapping(self):
        """Test response path is stored and retrieved."""
        self.limiter.record_request(
            note_path="test.md",
            request_hash="abc123",
            response_path="response.md"
        )

        response = self.limiter.get_response_path("test.md", "abc123")
        assert response == "response.md"

    def test_response_path_not_found(self):
        """Test response path returns None when not found."""
        response = self.limiter.get_response_path("nonexistent.md", "hash")
        assert response is None

    def test_state_persistence(self):
        """Test state is saved and loaded correctly."""
        # Record some requests
        self.limiter.record_request("test1.md", "hash1", "response1.md")
        self.limiter.record_request("test2.md", "hash2", "response2.md")

        # Create new limiter with same state file
        new_limiter = RateLimiter(
            state_file=self.state_file,
            max_requests_per_hour=5
        )

        # Should load previous state
        assert new_limiter.is_processed("test1.md", "hash1") is True
        assert new_limiter.is_processed("test2.md", "hash2") is True
        assert new_limiter.get_response_path("test1.md", "hash1") == "response1.md"

    def test_get_current_usage(self):
        """Test getting current usage statistics."""
        usage = self.limiter.get_current_usage()

        assert usage['current_hour_requests'] == 0
        assert usage['max_requests_per_hour'] == 5
        assert usage['remaining_requests'] == 5
        assert usage['total_processed'] == 0

        # Record some requests
        self.limiter.record_request("test1.md", "hash1")
        self.limiter.record_request("test2.md", "hash2")

        usage = self.limiter.get_current_usage()
        assert usage['current_hour_requests'] == 2
        assert usage['remaining_requests'] == 3
        assert usage['total_processed'] == 2

    def test_reset_all_processed(self):
        """Test resetting all processed requests."""
        # Record some requests
        self.limiter.record_request("test1.md", "hash1", "response1.md")
        self.limiter.record_request("test2.md", "hash2", "response2.md")

        assert len(self.limiter.processed_requests) == 2

        # Reset all
        count = self.limiter.reset_processed()

        assert count == 2
        assert len(self.limiter.processed_requests) == 0
        assert len(self.limiter.response_map) == 0
        assert self.limiter.is_processed("test1.md", "hash1") is False

    def test_reset_specific_note(self):
        """Test resetting requests for a specific note."""
        # Record requests for different notes
        self.limiter.record_request("note1.md", "hash1")
        self.limiter.record_request("note1.md", "hash2")
        self.limiter.record_request("note2.md", "hash3")

        # Reset only note1.md
        count = self.limiter.reset_processed(note_path="note1.md")

        assert count == 2
        assert self.limiter.is_processed("note1.md", "hash1") is False
        assert self.limiter.is_processed("note1.md", "hash2") is False
        assert self.limiter.is_processed("note2.md", "hash3") is True

    def test_timestamp_cleanup(self):
        """Test that old timestamps are cleaned up."""
        # Manually add old timestamps
        old_time = datetime.now() - timedelta(hours=2)
        self.limiter.request_timestamps.append(old_time)

        # Add current timestamp
        self.limiter.record_request("test.md", "hash1")

        # Check that we can still process (old timestamp cleaned up)
        assert self.limiter.can_process_request() is True

        usage = self.limiter.get_current_usage()
        assert usage['current_hour_requests'] == 1  # Only the recent one

    def test_multiple_requests_same_note(self):
        """Test multiple different requests in the same note."""
        self.limiter.record_request("test.md", "hash1")
        self.limiter.record_request("test.md", "hash2")

        assert self.limiter.is_processed("test.md", "hash1") is True
        assert self.limiter.is_processed("test.md", "hash2") is True
        assert len(self.limiter.processed_requests) == 2

    def test_state_file_creation(self):
        """Test that state file is created."""
        self.limiter.record_request("test.md", "hash1")

        assert os.path.exists(self.state_file)

    def test_load_nonexistent_state_file(self):
        """Test loading when state file doesn't exist."""
        # Create limiter with non-existent file
        new_state_file = os.path.join(self.temp_dir, 'nonexistent.json')
        limiter = RateLimiter(state_file=new_state_file)

        # Should start with empty state
        assert len(limiter.processed_requests) == 0
        assert len(limiter.request_timestamps) == 0

    def test_request_id_format(self):
        """Test that request IDs are formatted correctly."""
        self.limiter.record_request("path/to/note.md", "abc123")

        # Request ID should be "path:hash"
        request_id = "path/to/note.md:abc123"
        assert request_id in self.limiter.processed_requests

    def test_concurrent_requests_within_limit(self):
        """Test processing multiple requests within the limit."""
        for i in range(5):
            assert self.limiter.can_process_request() is True
            self.limiter.record_request(f"note{i}.md", f"hash{i}")

        # 6th request should fail
        assert self.limiter.can_process_request() is False

    def test_rate_limit_window_reset(self):
        """Test that rate limit resets after time window."""
        # Add old timestamps (more than 1 hour ago)
        old_time = datetime.now() - timedelta(hours=1, minutes=5)
        for i in range(5):
            self.limiter.request_timestamps.append(old_time)

        # Should be able to process new requests (old ones outside window)
        assert self.limiter.can_process_request() is True
