"""
Notifier Module

Provides desktop notifications for important events.
Cross-platform support via plyer library.
"""

import logging
from typing import Optional
from plyer import notification

logger = logging.getLogger(__name__)


class Notifier:
    """
    Sends desktop notifications for important agent events.

    Supports notifications for:
    - Successful request processing
    - Errors and failures
    - Rate limit warnings
    - Connection issues
    """

    def __init__(
        self,
        app_name: str = "Obsidian-Claude Agent",
        enabled: bool = True
    ):
        """
        Initialize the notifier.

        Args:
            app_name: Name to display in notifications
            enabled: Whether notifications are enabled
        """
        self.app_name = app_name
        self.enabled = enabled

    def notify_success(
        self,
        title: str,
        message: str,
        timeout: int = 10
    ) -> None:
        """
        Send a success notification.

        Args:
            title: Notification title
            message: Notification message
            timeout: How long to display (seconds)
        """
        self._send_notification(
            title=title,
            message=message,
            timeout=timeout
        )

    def notify_error(
        self,
        title: str,
        message: str,
        timeout: int = 15
    ) -> None:
        """
        Send an error notification.

        Args:
            title: Notification title
            message: Error message
            timeout: How long to display (seconds)
        """
        self._send_notification(
            title=f"❌ {title}",
            message=message,
            timeout=timeout
        )

    def notify_rate_limit(
        self,
        next_available: str,
        timeout: int = 12
    ) -> None:
        """
        Send a rate limit notification.

        Args:
            next_available: When next request is available
            timeout: How long to display (seconds)
        """
        self._send_notification(
            title="Rate Limit Reached",
            message=f"Next request available at {next_available}",
            timeout=timeout
        )

    def notify_processed(
        self,
        count: int,
        timeout: int = 8
    ) -> None:
        """
        Notify about successfully processed requests.

        Args:
            count: Number of requests processed
            timeout: How long to display (seconds)
        """
        if count == 0:
            return

        message = f"Processed {count} request{'s' if count != 1 else ''}"
        self._send_notification(
            title=self.app_name,
            message=message,
            timeout=timeout
        )

    def _send_notification(
        self,
        title: str,
        message: str,
        timeout: int = 10
    ) -> None:
        """
        Internal method to send a notification.

        Args:
            title: Notification title
            message: Notification message
            timeout: How long to display (seconds)
        """
        if not self.enabled:
            logger.debug(f"Notifications disabled, skipping: {title}")
            return

        try:
            notification.notify(
                title=title,
                message=message,
                app_name=self.app_name,
                timeout=timeout
            )
            logger.debug(f"Notification sent: {title}")

        except Exception as e:
            # Don't let notification failures crash the app
            logger.warning(f"Failed to send notification: {e}")

    def enable(self) -> None:
        """Enable notifications."""
        self.enabled = True
        logger.info("Notifications enabled")

    def disable(self) -> None:
        """Disable notifications."""
        self.enabled = False
        logger.info("Notifications disabled")

    def is_enabled(self) -> bool:
        """
        Check if notifications are enabled.

        Returns:
            True if enabled, False otherwise
        """
        return self.enabled
