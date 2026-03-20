"""
Claude Client Module

Handles communication with Claude AI API.
Manages tool restrictions and request processing.
"""

import logging
import os
from typing import List, Optional, Dict, Any

from anthropic import Anthropic
from anthropic.types import Message

from .exceptions import ClaudeAPIError, UnauthorizedToolError

logger = logging.getLogger(__name__)


class ClaudeClient:
    """
    Manages interactions with Claude AI API.

    Responsibilities:
    - Send requests to Claude with context
    - Enforce tool permission restrictions
    - Provide MCP tools to Claude
    - Handle API errors and retries
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        allowed_tools: Optional[List[str]] = None
    ):
        """
        Initialize the Claude client.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if None)
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            allowed_tools: List of allowed tool names (kept for future use)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ClaudeAPIError("API key not provided and ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=self.api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.allowed_tools = set(allowed_tools or [])

        logger.info(f"Initialized Claude client with model: {model}")

    def process_request(
        self,
        request_text: str,
        context: Optional[str] = None,
        wikilinks: Optional[List[str]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Process a user request through Claude.

        Args:
            request_text: The user's request
            context: Optional context from the note (content above the request)
            wikilinks: Optional list of wikilinks found in context
            system_prompt: Optional system prompt for context

        Returns:
            Claude's response text

        Raises:
            ClaudeAPIError: If API request fails
            UnauthorizedToolError: If Claude attempts to use disallowed tool
        """
        try:
            # Build user message with context if available
            user_content = request_text

            if context or wikilinks:
                context_parts = []

                if wikilinks:
                    context_parts.append(f"**Referenced notes:** {', '.join(wikilinks)}")

                if context:
                    context_parts.append(f"**Note context:**\n{context}")

                # Prepend context to request
                user_content = "\n\n".join(context_parts) + f"\n\n**Request:** {request_text}"

            # Build messages
            messages = [
                {
                    "role": "user",
                    "content": user_content
                }
            ]

            # Prepare API call parameters
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": messages
            }

            # Add system prompt if provided
            if system_prompt:
                kwargs["system"] = system_prompt

            # Make API call
            logger.info(f"Sending request to Claude (model: {self.model})")
            response: Message = self.client.messages.create(**kwargs)

            # Extract text response
            response_text = self._extract_response_text(response)

            logger.info(f"Received response ({len(response_text)} chars)")
            return response_text

        except UnauthorizedToolError:
            raise

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise ClaudeAPIError(f"API request failed: {e}")

    def _extract_response_text(self, response: Message) -> str:
        """
        Extract text content from Claude's response.

        Args:
            response: Claude API response

        Returns:
            Response text
        """
        # Extract text content from response
        text_parts = []
        for block in response.content:
            if hasattr(block, 'text'):
                text_parts.append(block.text)

        return "\n".join(text_parts) if text_parts else ""

    def validate_tool_permission(self, tool_name: str) -> bool:
        """
        Check if a tool is allowed.

        Args:
            tool_name: Name of the tool

        Returns:
            True if allowed, False otherwise
        """
        return tool_name in self.allowed_tools

    def process_vision_request(
        self,
        prompt: str,
        image_data: str,
        mime_type: str = "image/jpeg"
    ) -> str:
        """
        Process a vision request with an image using Claude.

        Args:
            prompt: The prompt/instruction for image analysis
            image_data: Base64-encoded image data
            mime_type: MIME type of the image (e.g., "image/jpeg")

        Returns:
            Claude's response text

        Raises:
            ClaudeAPIError: If API request fails
        """
        try:
            # Build multi-modal message with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]

            # Make API call
            logger.info(f"Sending vision request to Claude (model: {self.model})")
            response: Message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=messages
            )

            # Extract text response
            response_text = self._extract_response_text(response)

            logger.info(f"Received vision response ({len(response_text)} chars)")
            return response_text

        except Exception as e:
            logger.error(f"Claude Vision API error: {e}")
            raise ClaudeAPIError(f"Vision API request failed: {e}")

    def get_allowed_tools(self) -> List[str]:
        """
        Get list of allowed tools.

        Returns:
            List of allowed tool names
        """
        return list(self.allowed_tools)

    def set_allowed_tools(self, tools: List[str]) -> None:
        """
        Update the list of allowed tools.

        Args:
            tools: New list of allowed tool names
        """
        self.allowed_tools = set(tools)
        logger.info(f"Updated allowed tools: {tools}")
