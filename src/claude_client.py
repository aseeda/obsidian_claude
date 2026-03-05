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
from .mcp_client import MCPClient

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
        allowed_tools: Optional[List[str]] = None,
        mcp_client: Optional[MCPClient] = None
    ):
        """
        Initialize the Claude client.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if None)
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            allowed_tools: List of allowed tool names
            mcp_client: MCP client for providing Obsidian tools
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ClaudeAPIError("API key not provided and ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=self.api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.allowed_tools = set(allowed_tools or [])
        self.mcp_client = mcp_client

        logger.info(f"Initialized Claude client with model: {model}")

    async def process_request(
        self,
        request_text: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Process a user request through Claude.

        Args:
            request_text: The user's request
            system_prompt: Optional system prompt for context

        Returns:
            Claude's response text

        Raises:
            ClaudeAPIError: If API request fails
            UnauthorizedToolError: If Claude attempts to use disallowed tool
        """
        try:
            # Build messages
            messages = [
                {
                    "role": "user",
                    "content": request_text
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

            # Add tools if MCP client is available
            if self.mcp_client and self.allowed_tools:
                tools = await self._prepare_tools()
                if tools:
                    kwargs["tools"] = tools

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

    async def _prepare_tools(self) -> List[Dict[str, Any]]:
        """
        Prepare tool definitions for Claude.

        Returns:
            List of tool definitions filtered by allowed tools
        """
        # Define available Obsidian tools
        all_tools = [
            {
                "name": "read_note",
                "description": "Read the content of a note from the Obsidian vault",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the note relative to vault root"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "search_notes",
                "description": "Search for notes in the Obsidian vault by content",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text"
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of results (default: 5)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "write_note",
                "description": "Create or overwrite a note in the Obsidian vault",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the note relative to vault root"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content of the note"
                        }
                    },
                    "required": ["path", "content"]
                }
            }
        ]

        # Filter by allowed tools
        filtered_tools = [
            tool for tool in all_tools
            if tool["name"] in self.allowed_tools
        ]

        logger.debug(f"Providing {len(filtered_tools)} tools to Claude: {[t['name'] for t in filtered_tools]}")
        return filtered_tools

    def _extract_response_text(self, response: Message) -> str:
        """
        Extract text content from Claude's response.

        Args:
            response: Claude API response

        Returns:
            Response text
        """
        # Handle different response content types
        text_parts = []

        for block in response.content:
            if hasattr(block, 'text'):
                text_parts.append(block.text)
            elif hasattr(block, 'type') and block.type == 'tool_use':
                # Check if tool is allowed
                tool_name = getattr(block, 'name', 'unknown')
                if tool_name not in self.allowed_tools:
                    raise UnauthorizedToolError(
                        f"Claude attempted to use unauthorized tool: {tool_name}"
                    )
                # Log tool use
                logger.warning(f"Claude attempted to use tool: {tool_name}")

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
