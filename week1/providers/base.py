"""
Shared types and base abstractions across providers.
"""
from __future__ import annotations
import json
import sys
import time
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass
class Usage:
    """Token usage from a single API call. Provider-agnostic."""
    input_tokens: int
    output_tokens: int


@dataclass
class CompletionResult:
    """Provider-agnostic result of a single API call."""
    text: str
    structured: dict | None
    usage: Usage
    provider: str
    model: str


class APIError(Exception):
    """Raised when an upstream API call fails after retries."""

    def __init__(self, status: int, error_type: str, message: str, raw: dict | None = None):
        self.status = status
        self.error_type = error_type
        self.message = message
        self.raw = raw
        super().__init__(f"[{status}] {error_type}: {message}")


def extract_api_error(response: httpx.Response) -> APIError:
    """Pull the API's actual error info out of a failed response body."""
    status = response.status_code
    try:
        body = response.json()
        err = body.get("error", {})
        return APIError(
            status=status,
            error_type=err.get("type", "unknown_error"),
            message=err.get("message", response.text[:500]),
            raw=body,
        )
    except (ValueError, json.JSONDecodeError):
        return APIError(
            status=status,
            error_type="non_json_response",
            message=response.text[:500],
        )


def post_with_retries(
    url: str,
    headers: dict,
    body: dict,
    max_retries: int = 3,
    timeout: float = 60.0,
) -> dict:
    """
    Shared HTTP POST with exponential backoff on transient failures.
    Returns parsed JSON. Raises APIError on permanent failures.
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = httpx.post(url, headers=headers, json=body, timeout=timeout)

            if 200 <= response.status_code < 300:
                return response.json()

            if 400 <= response.status_code < 500 and response.status_code != 429:
                raise extract_api_error(response)

            err = extract_api_error(response)
            wait = 2 ** attempt
            print(
                f"Attempt {attempt + 1}/{max_retries} failed: {err}. "
                f"Retrying in {wait}s...",
                file=sys.stderr,
            )
            last_exception = err
            time.sleep(wait)
            continue

        except httpx.TimeoutException as e:
            wait = 2 ** attempt
            print(
                f"Attempt {attempt + 1}/{max_retries} timed out. Retrying in {wait}s...",
                file=sys.stderr,
            )
            last_exception = APIError(0, "timeout", str(e))
            time.sleep(wait)
            continue

        except httpx.NetworkError as e:
            raise APIError(0, "network_error", str(e))

    raise last_exception or APIError(0, "max_retries_exceeded", f"Failed after {max_retries} attempts")


class Provider(Protocol):
    """Interface every provider must implement."""

    name: str
    default_model: str

    def complete(
        self,
        prompt: str,
        instructions: str | None = None,
        json_schema: dict | None = None,
    ) -> CompletionResult:
        ...