"""
Provider package — exposes Claude and OpenAI implementations.
"""
from .base import APIError, CompletionResult, Usage, Provider
from .claude import ClaudeProvider
from .openai import OpenAIProvider

__all__ = [
    "APIError",
    "CompletionResult",
    "Usage",
    "Provider",
    "ClaudeProvider",
    "OpenAIProvider",
]


def get_provider(name: str, model: str | None = None) -> Provider:
    """Factory function to get a provider by name."""
    if name == "claude":
        return ClaudeProvider(model)
    if name == "openai":
        return OpenAIProvider(model)
    raise ValueError(f"Unknown provider: {name}. Use 'claude' or 'openai'.")