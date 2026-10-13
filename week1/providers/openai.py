"""
OpenAI provider implementation. Uses the Responses API.
"""
import json as _json
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

_URL = "https://api.openai.com/v1/responses"


class OpenAIProvider:
    name = "openai"
    default_model = "gpt-4o-mini"

    def __init__(self, model: str | None = None):
        self.model = model or self.default_model
        self._api_key = os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise APIError(0, "missing_api_key", "OPENAI_API_KEY not set in environment")

    def complete(
        self,
        prompt: str,
        instructions: str | None = None,
        json_schema: dict | None = None,
    ) -> CompletionResult:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }

        body: dict[str, Any] = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": 2048,
        }

        if instructions:
            body["instructions"] = instructions

        if json_schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": json_schema.get("name", "structured_response"),
                    "schema": json_schema.get("schema", json_schema),
                    "strict": True,
                }
            }
            body["temperature"] = 0

        data = post_with_retries(_URL, headers, body)

        usage = Usage(
            input_tokens=data["usage"]["input_tokens"],
            output_tokens=data["usage"]["output_tokens"],
        )

        text = ""
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text = content.get("text", "")
                        break

        if json_schema is not None:
            try:
                structured = _json.loads(text)
            except _json.JSONDecodeError as e:
                raise APIError(0, "invalid_structured_response",
                               f"Could not parse structured output: {e}")
            return CompletionResult(
                text="", structured=structured, usage=usage,
                provider=self.name, model=self.model,
            )

        return CompletionResult(
            text=text, structured=None, usage=usage,
            provider=self.name, model=self.model,
        )