import json
import os
import sys
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
URL = "https://api.openai.com/v1/responses"
MODEL = "gpt-4o-mini"

# Pricing as of early 2026, per million tokens, in AUD
# Verify yourself at openai.com/api/pricing
PRICING_AUD = {
    "gpt-4o-mini": {"input": 0.23, "output": 0.93},
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


def ask_gpt(question: str, instructions: str | None = None, max_retries: int = 3) -> dict:
    """
    Call OpenAI's Responses API with retry on transient failures.
    Optionally pass instructions to set system-level guidance.
    Returns the parsed response dict.
    """
    body = {
        "model": MODEL,
        "input": question,
        "max_output_tokens": 1024,
    }
    if instructions:
        body["instructions"] = instructions

    last_exception = None

    for attempt in range(max_retries):
        try:
            response = httpx.post(
                URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "content-type": "application/json",
                },
                json=body,
                timeout=30.0,
            )

            if 200 <= response.status_code < 300:
                return response.json()

            if 400 <= response.status_code < 500 and response.status_code != 429:
                raise _extract_error(response)

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
            raise APIError(0, "network_error", str(e))

    raise last_exception or APIError(0, "max_retries_exceeded", f"Failed after {max_retries} attempts")

def extract_text(response: dict) -> str:
    """
    Walk the Responses API output[] structure to find the assistant text.
    """
    for item in response.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "")
    return ""


def calculate_cost_aud(model: str, usage: dict) -> float:
    """Calculate the AUD cost of a single API call from the usage block."""
    rates = PRICING_AUD.get(model)
    if not rates:
        return 0.0
    input_cost = (usage["input_tokens"] / 1_000_000) * rates["input"]
    output_cost = (usage["output_tokens"] / 1_000_000) * rates["output"]
    return input_cost + output_cost


if __name__ == "__main__":
    # Simple example usage
    try:
        response = ask_gpt(
            "Explain a transformer architecture.",
            instructions="Answer in exactly two sentences. No analogies.",
        )
    except APIError as e:
        print(f"\n❌ API call failed: {e}", file=sys.stderr)
        if e.raw:
            print(f"   Full error body: {json.dumps(e.raw, indent=2)}", file=sys.stderr)
        sys.exit(1)

    answer = extract_text(response)
    usage = response["usage"]
    cost_aud = calculate_cost_aud(MODEL, usage)

    print(answer)
    print(
        f"\n[tokens in: {usage['input_tokens']}, out: {usage['output_tokens']}, "
        f"cost: AUD ${cost_aud:.6f}]",
        file=sys.stderr,
    )