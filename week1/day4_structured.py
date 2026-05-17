import json
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-5"


SCHEMA_DESCRIPTION = """
Return a single JSON object with this exact shape:
{
  "title": string,
  "servings": integer,
  "prep_minutes": integer,
  "ingredients": [
    {"item": string, "quantity": string}
  ],
  "steps": [string]
}

Rules:
-  Return ONLY the JSON object. No explanations, no preamble, no markdown code fences.
-  All string field values must be in English, regardless of the input language.
- If a value cannot be inferred from the input, use null for that field.
- prep_minutes must be a single integer in minutes (not a range, not a string).
"""


def strip_code_fences(text: str) -> str:
    """
    Remove markdown code fences from a model response, if present.
    Handles both ```json ... ``` and ``` ... ``` formats.
    """
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def extract_recipe(text: str) -> dict:
    """
    Send recipe text to Claude and get back a structured dict.
    Raises json.JSONDecodeError if the response can't be parsed.
    """
    response = httpx.post(
        URL,
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 2048,
            "temperature": 0,
            "system": SCHEMA_DESCRIPTION,
            "messages": [
                {"role": "user", "content": f"Extract recipe info from this text:\n\n{text}"}
            ],
        },
        timeout=60.0,
    )
    response.raise_for_status()
    raw = response.json()["content"][0]["text"]
    #print(f"\nRaw model response:\n{raw}\n")
    #print(f"\n[DEBUG raw response]: {raw!r}\n")
    raw = strip_code_fences(raw)
    return json.loads(raw)


TEST_INPUTS = [
    {
        "name": "clean_structured",
        "text": """Banana Bread. Serves 8. Prep 15 min. You'll need: 3 ripe bananas, 1/3 cup melted butter,
3/4 cup sugar, 1 egg, 1 tsp vanilla, 1 tsp baking soda, 1.5 cups flour. Mash bananas, mix in
butter, then sugar, egg, vanilla. Add baking soda. Add flour. Bake at 350F for 60 min.""",
    },
    {   "name": "non_recipe_input",
        "text": "What is the meaning of life? Please philosophise."
    },
    {
        "name": "casual_narrative",
        "text": """My grandma's chicken curry — feeds a family of four. Takes about 20 minutes to prep before
cooking. Get yourself some chicken thighs (about 1kg), an onion, garlic, ginger, tomatoes,
cumin, turmeric, garam masala, and coconut milk. First brown the chicken, then sauté the
aromatics, add spices, tomatoes, then coconut milk and simmer.""",
    },
    {
        "name": "ambiguous_quantities",
        "text": """quick eggs benedict for two. Need 4 eggs, 2 english muffins, 4 slices ham, hollandaise
(3 yolks, butter, lemon, salt). Poach eggs, toast muffins, warm ham, make hollandaise,
assemble. 15 min total.""",
    },
 {
    "name": "italian_obscure",
    "text": "Bavette alla salsa di rapanelli per 4 persone. 400g bavette, 1 mazzo di rapanelli, aglio, olio, sale. Cuocere la pasta, frullare i rapanelli con aglio e olio, mescolare. 15 minuti.",
},
]


if __name__ == "__main__":
    for case in TEST_INPUTS:
        print(f"\n--- {case['name']} ---")
        try:
            result = extract_recipe(case["text"])
            print(json.dumps(result, indent=2))
            assert "title" in result, "missing title"
            assert isinstance(result.get("ingredients"), list), "ingredients must be a list"
            print("\n✓ Parsed and basic schema OK")
        except json.JSONDecodeError as e:
            print(f"\n✗ Failed to parse JSON: {e}")
        except AssertionError as e:
            print(f"\n✗ Schema mismatch: {e}")
        except Exception as e:
            print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")