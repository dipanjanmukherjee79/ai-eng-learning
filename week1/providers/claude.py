"""
Claude provider implementation.
"""
import os
from typing import Any

from dotenv import load_dotenv

from .base import (
    APIError,
    CompletionResult,
    Usage,
    post_with_retries,
)

load_dotenv()

_URL = "https://api.anthropic.com/v1/messages"


class ClaudeProvider:
    name = "claude"
    default_model = "claude-sonnet-4-5"

    def __init__(self, model: str | None = None):
        self.model = model or self.default_model
        self._api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise APIError(0, "missing_api_key", "ANTHROPIC_API_KEY not set in environment")

    def complete(
        self,
        prompt: str,
        instructions: str | None = None,
        json_schema: dict | None = None,
    ) -> CompletionResult:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }

        if instructions:
            body["system"] = instructions

        if json_schema is not None:
            tool_name = json_schema.get("name", "structured_response")
            body["tools"] = [json_schema]
            body["tool_choice"] = {"type": "tool", "name": tool_name}
            body["temperature"] = 0

        data = post_with_retries(_URL, headers, body)

        usage = Usage(
            input_tokens=data["usage"]["input_tokens"],
            output_tokens=data["usage"]["output_tokens"],
        )

        if json_schema is not None:
            structured = None
            for block in data.get("content", []):
                if block.get("type") == "tool_use":
                    structured = block.get("input")
                    break
            if structured is None:
                raise APIError(
                    0, "no_tool_call",
                    f"Expected tool call but got stop_reason={data.get('stop_reason')}",
                )
            return CompletionResult(
                text="", structured=structured, usage=usage,
                provider=self.name, model=self.model,
            )

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text = block.get("text", "")
                break

        return CompletionResult(
            text=text, structured=None, usage=usage,
            provider=self.name, model=self.model,
        )