import json
import os
import sys
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-5"

# Pricing as of early 2026, per million tokens, in AUD
# Source: Anthropic pricing page — verify these numbers yourself
# Roughly USD * 1.50 for AUD
PRICING_AUD = {
    "claude-sonnet-4-5": {"input": 4.50, "output": 22.50},
}


class APIError(Exception):
    """Raised when an upstream API call fails after retries."""

    def __init__(self, status: int, error_type: str, message: str, raw: dict | None = None):
        self.status = status
        self.error_type = error_type
        self.message = message
        self.raw = raw
        super().__init__(f"[{status}] {error_type}: {message}")


def _extract_error(response: httpx.Response) -> APIError:
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


def ask_claude(question: str, max_retries: int = 3) -> dict:
    """
    Call Claude with retry on transient failures.
    Returns the parsed response dict (not just the text), so callers can see usage.
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = httpx.post(
                URL,
                headers={
                    "x-api-key": API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": MODEL,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": question}],
                },
                timeout=30.0,
            )

            # 2xx — success, return parsed body
            if 200 <= response.status_code < 300:
                return response.json()

            # 4xx (other than 429) — client error, do NOT retry
            if 400 <= response.status_code < 500 and response.status_code != 429:
                raise _extract_error(response)

            # 429 (rate limit) or 5xx — retry with backoff
            err = _extract_error(response)
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
            # DNS failure, connection refused — fail fast, don't retry
            raise APIError(0, "network_error", str(e))

    # Exhausted retries
    raise last_exception or APIError(0, "max_retries_exceeded", f"Failed after {max_retries} attempts")


def calculate_cost_aud(model: str, usage: dict) -> float:
    """Calculate the AUD cost of a single API call from the usage block."""
    rates = PRICING_AUD.get(model)
    if not rates:
        return 0.0
    input_cost = (usage["input_tokens"] / 1_000_000) * rates["input"]
    output_cost = (usage["output_tokens"] / 1_000_000) * rates["output"]
    return input_cost + output_cost


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: uv run python week1/day2_claude_cli.py 'your question here'",
            file=sys.stderr,
        )
        sys.exit(1)
    # TEMP: oversized prompt test — remove before committing
    if len(sys.argv) > 1 and sys.argv[1] == "--torture":
        try:
            response = ask_claude("explain " * 1000000)
            print(response["content"][0]["text"])
        except APIError as e:
            print(f"\n❌ Torture test failed (as expected): {e}", file=sys.stderr)
            if e.raw:
                print(f"   Full error body: {json.dumps(e.raw, indent=2)}", file=sys.stderr)
        sys.exit(0)
    question = " ".join(sys.argv[1:])

    try:
        response = ask_claude(question)
    except APIError as e:
        print(f"\n❌ API call failed: {e}", file=sys.stderr)
        if e.raw:
            print(f"   Full error body: {json.dumps(e.raw, indent=2)}", file=sys.stderr)
        sys.exit(1)

    answer = response["content"][0]["text"]
    usage = response["usage"]
    cost_aud = calculate_cost_aud(MODEL, usage)

    print(answer)
    print(
        f"\n[tokens in: {usage['input_tokens']}, out: {usage['output_tokens']}, "
        f"cost: AUD ${cost_aud:.6f}]",
        file=sys.stderr,
    )