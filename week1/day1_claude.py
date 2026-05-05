import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
URL = "https://api.anthropic.com/v1/messages"


def ask_claude(question: str) -> str:
    response = httpx.post(
        URL,
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-5",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": question}],
        },
        timeout=30.0,
    )
    
    # New: print the actual API response on error
    if response.status_code >= 400:
        print(f"--- API ERROR {response.status_code} ---")
        print(response.text)
        print("--- END ERROR ---")
    
    response.raise_for_status()
    data = response.json()
    return data["content"][0]["text"]

if __name__ == "__main__":
    answer = ask_claude("In one sentence, what is a vector embedding?")
    print(answer)