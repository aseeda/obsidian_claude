"""
Rate Limiter Module

Manages request throttling and tracks processed requests.
Persists state to JSON file for tracking across runs.
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from pathlib import Path

from .exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Manages rate limiting and request state tracking.

    Tracks:
    - Processed requests (note path + request hash)
    - Request timestamps for rate limiting
    - Response note paths
    - Automatic cleanup of old entries
    """

    def __init__(
        self,
        state_file: str,
        max_requests_per_hour: int = 5,
        cleanup_after_days: int = 7
    ):
        """
        Initialize the rate limiter.

        Args:
            state_file: Path to JSON state file
            max_requests_per_hour: Maximum requests allowed per hour
            cleanup_after_days: Days after which to clean up old entries
        """
        self.state_file = Path(state_file)
        self.max_requests_per_hour = max_requests_per_hour
        self.cleanup_after_days = cleanup_after_days

        # In-memory state
        self.processed_requests: Set[str] = set()
        self.request_timestamps: List[datetime] = []
        self.response_map: Dict[str, str] = {}

        # Ensure state directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state
        self._load_state()

    def _load_state(self) -> None:
        """Load state from JSON file."""
        if not self.state_file.exists():
            logger.info(f"No existing state file found at {self.state_file}")
            return

        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)

            self.processed_requests = set(data.get('processed_requests', []))
            self.response_map = data.get('response_map', {})

            # Parse timestamps
            timestamp_strs = data.get('request_timestamps', [])
            self.request_timestamps = [
                datetime.fromisoformat(ts) for ts in timestamp_strs
            ]

            # Clean up old entries immediately after loading
            self._cleanup_old_entries()

            logger.info(
                f"Loaded state: {len(self.processed_requests)} processed requests, "
                f"{len(self.request_timestamps)} recent timestamps"
            )

        except Exception as e:
            logger.error(f"Failed to load state file: {e}")
            # Start with empty state if loading fails
            self.processed_requests = set()
            self.request_timestamps = []
            self.response_map = {}

    def _save_state(self) -> None:
        """Save state to JSON file."""
        try:
            data = {
                'processed_requests': list(self.processed_requests),
                'request_timestamps': [
                    ts.isoformat() for ts in self.request_timestamps
                ],
                'response_map': self.response_map,
                'last_updated': datetime.now().isoformat()
            }

            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"State saved to {self.state_file}")

        except Exception as e:
            logger.error(f"Failed to save state file: {e}")

    def _cleanup_old_entries(self) -> None:
        """Remove entries older than cleanup_after_days."""
        cutoff_date = datetime.now() - timedelta(days=self.cleanup_after_days)

        # Clean up old timestamps
        original_count = len(self.request_timestamps)
        self.request_timestamps = [
            ts for ts in self.request_timestamps
            if ts > cutoff_date
        ]

        cleaned_count = original_count - len(self.request_timestamps)
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old timestamp entries")

    def is_processed(self, note_path: str, request_hash: str) -> bool:
        """
        Check if a request has already been processed.

        Args:
            note_path: Path to the note
            request_hash: Hash of the request text

        Returns:
            True if already processed, False otherwise
        """
        request_id = f"{note_path}:{request_hash}"
        return request_id in self.processed_requests

    def can_process_request(self) -> bool:
        """
        Check if a new request can be processed within rate limits.

        Returns:
            True if within rate limits, False otherwise
        """
        # Clean up timestamps older than 1 hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        self.request_timestamps = [
            ts for ts in self.request_timestamps
            if ts > one_hour_ago
        ]

        return len(self.request_timestamps) < self.max_requests_per_hour

    def get_next_available_time(self) -> Optional[datetime]:
        """
        Get the next time when a request can be processed.

        Returns:
            datetime when next request is allowed, or None if can process now
        """
        if self.can_process_request():
            return None

        # Find the oldest timestamp in the current window
        if not self.request_timestamps:
            return None

        oldest_timestamp = min(self.request_timestamps)
        next_available = oldest_timestamp + timedelta(hours=1)

        return next_available

    def record_request(
        self,
        note_path: str,
        request_hash: str,
        response_path: Optional[str] = None
    ) -> None:
        """
        Record a processed request.

        Args:
            note_path: Path to the note
            request_hash: Hash of the request text
            response_path: Optional path to response note

        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        if not self.can_process_request():
            next_time = self.get_next_available_time()
            raise RateLimitExceededError(
                f"Rate limit exceeded. Next request available at {next_time}"
            )

        request_id = f"{note_path}:{request_hash}"

        # Record the request
        self.processed_requests.add(request_id)
        self.request_timestamps.append(datetime.now())

        # Store response mapping if provided
        if response_path:
            self.response_map[request_id] = response_path

        # Save state immediately
        self._save_state()

        logger.info(
            f"Recorded request: {request_id} "
            f"({len(self.request_timestamps)}/{self.max_requests_per_hour} "
            f"requests in current hour)"
        )

    def get_response_path(self, note_path: str, request_hash: str) -> Optional[str]:
        """
        Get the response note path for a processed request.

        Args:
            note_path: Path to the note
            request_hash: Hash of the request text

        Returns:
            Response note path if exists, None otherwise
        """
        request_id = f"{note_path}:{request_hash}"
        return self.response_map.get(request_id)

    def get_current_usage(self) -> Dict[str, int]:
        """
        Get current rate limit usage statistics.

        Returns:
            Dictionary with usage stats
        """
        # Clean up old timestamps first
        one_hour_ago = datetime.now() - timedelta(hours=1)
        current_hour_requests = [
            ts for ts in self.request_timestamps
            if ts > one_hour_ago
        ]

        return {
            'current_hour_requests': len(current_hour_requests),
            'max_requests_per_hour': self.max_requests_per_hour,
            'remaining_requests': max(
                0,
                self.max_requests_per_hour - len(current_hour_requests)
            ),
            'total_processed': len(self.processed_requests)
        }

    def reset_processed(self, note_path: Optional[str] = None) -> int:
        """
        Reset processed request tracking.

        Args:
            note_path: If provided, only reset requests for this note.
                      If None, reset all requests.

        Returns:
            Number of entries removed
        """
        if note_path is None:
            # Reset all
            count = len(self.processed_requests)
            self.processed_requests.clear()
            self.response_map.clear()
            logger.info(f"Reset all {count} processed requests")
        else:
            # Reset only for specific note
            prefix = f"{note_path}:"
            to_remove = {
                req for req in self.processed_requests
                if req.startswith(prefix)
            }
            count = len(to_remove)

            self.processed_requests -= to_remove

            # Also remove from response map
            for req_id in to_remove:
                self.response_map.pop(req_id, None)

            logger.info(f"Reset {count} requests for note: {note_path}")

        self._save_state()
        return count
