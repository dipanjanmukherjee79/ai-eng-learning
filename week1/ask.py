"""
Unified CLI for prompting LLMs across providers.

Usage:
    uv run python week1/ask.py "your prompt"
    uv run python week1/ask.py --provider openai "your prompt"
    uv run python week1/ask.py --instructions "Answer in 2 sentences." "your prompt"
"""
import argparse
import json
import sys

from providers import APIError, get_provider
from pricing import calculate_cost_aud


def main():
    parser = argparse.ArgumentParser(
        description="Unified LLM CLI supporting Claude and OpenAI.",
    )
    parser.add_argument("prompt", help="The prompt to send")
    parser.add_argument(
        "--provider", "-p",
        default="claude",
        choices=["claude", "openai"],
        help="LLM provider to use (default: claude)",
    )
    parser.add_argument(
        "--model", "-m",
        help="Specific model to use (optional, uses provider default)",
    )
    parser.add_argument(
        "--instructions", "-i",
        help="System-level instructions to prepend",
    )

    args = parser.parse_args()

    try:
        provider = get_provider(args.provider, args.model)
        result = provider.complete(
            prompt=args.prompt,
            instructions=args.instructions,
        )
    except APIError as e:
        print(f"\n❌ API call failed: {e}", file=sys.stderr)
        if e.raw:
            print(f"   Full error body: {json.dumps(e.raw, indent=2)}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)

    print(result.text)
    cost = calculate_cost_aud(result.provider, result.model, result.usage)
    print(
        f"\n[provider: {result.provider}, model: {result.model}, "
        f"tokens in: {result.usage.input_tokens}, out: {result.usage.output_tokens}, "
        f"cost: AUD ${cost:.6f}]",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()