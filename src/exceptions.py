"""Custom exceptions for Obsidian-Claude Agent."""


class ObsidianClaudeError(Exception):
    """Base exception for all Obsidian-Claude Agent errors."""
    pass


# MCP-related exceptions
class MCPError(ObsidianClaudeError):
    """Base exception for MCP-related errors."""
    pass


class MCPConnectionError(MCPError):
    """Raised when connection to MCP server fails."""
    pass


class MCPTimeoutError(MCPError):
    """Raised when MCP operation times out."""
    pass


class MCPToolError(MCPError):
    """Raised when MCP tool execution fails."""
    pass


# Configuration exceptions
class ConfigurationError(ObsidianClaudeError):
    """Raised when configuration is invalid or missing."""
    pass


# Request processing exceptions
class RequestParsingError(ObsidianClaudeError):
    """Raised when request parsing fails."""
    pass


class UnauthorizedToolError(ObsidianClaudeError):
    """Raised when an unauthorized tool is requested."""
    pass


# Rate limiting exceptions
class RateLimitExceededError(ObsidianClaudeError):
    """Raised when rate limit is exceeded."""
    pass


# Claude API exceptions
class ClaudeAPIError(ObsidianClaudeError):
    """Raised when Claude API call fails."""
    pass


class ClaudeAPIUnavailableError(ClaudeAPIError):
    """Raised when Claude API is unavailable."""
    pass


# Response writing exceptions
class ResponseWriteError(ObsidianClaudeError):
    """Raised when writing response fails."""
    pass
