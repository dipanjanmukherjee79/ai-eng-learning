import json
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-5"


# Tool definition — the schema is now a JSON Schema object, not prose.
# Claude is forced to produce a tool_use block matching this shape.
RECIPE_TOOL = {
    "name": "save_recipe",
    "description": "Save a structured recipe extracted from text. Call this once with the extracted recipe data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The name of the recipe, in English. Translate the title if the source is in another language.",
            },
            "servings": {
                "type": ["integer", "null"],
                "description": "Number of servings as a single integer. Use null if not stated or not inferable.",
            },
            "prep_minutes": {
                "type": ["integer", "null"],
                "description": "Preparation time in whole minutes. Use null if not stated.",
            },
            "ingredients": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string", "description": "The ingredient name in English."},
                        "quantity": {
                            "type": ["string", "null"],
                            "description": "Quantity as written in the source, or null if not specified.",
                        },
                    },
                    "required": ["item", "quantity"],
                },
            },
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Recipe steps in order, in English.",
            },
            "is_recipe": {
                "type": "boolean",
                "description": "True if the input text describes a recipe. False if the input is unrelated to cooking (e.g. philosophical questions, random text). If false, leave other fields empty/null.",
            },
        },
        "required": ["title", "servings", "prep_minutes", "ingredients", "steps", "is_recipe"],
    },
}


def extract_recipe(text: str) -> dict:
    """
    Extract structured recipe using Claude Tool Use.
    Returns the dict that Claude passed to the save_recipe tool.
    Raises ValueError if Claude doesn't call the tool.
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
            "tools": [RECIPE_TOOL],
            "tool_choice": {"type": "tool", "name": "save_recipe"},
            "messages": [
                {"role": "user", "content": f"Extract recipe info from this text:\n\n{text}"}
            ],
        },
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()

    # Find the tool_use block in the response content
    for block in data.get("content", []):
        if block.get("type") == "tool_use" and block.get("name") == "save_recipe":
            return block["input"]

    raise ValueError(
        f"Claude did not call save_recipe. stop_reason={data.get('stop_reason')}, "
        f"content={data.get('content')}"
    )


TEST_INPUTS = [
    {
        "name": "clean_structured",
        "text": """Banana Bread. Serves 8. Prep 15 min. You'll need: 3 ripe bananas, 1/3 cup melted butter,
3/4 cup sugar, 1 egg, 1 tsp vanilla, 1 tsp baking soda, 1.5 cups flour. Mash bananas, mix in
butter, then sugar, egg, vanilla. Add baking soda. Add flour. Bake at 350F for 60 min.""",
    },
    {
        "name": "casual_narrative",
        "text": """My grandma's chicken curry — feeds a family of four. Takes about 20 minutes to prep before
cooking. Get yourself some chicken thighs (about 1kg), an onion, garlic, ginger, tomatoes,
cumin, turmeric, garam masala, and coconut milk. First brown the chicken, then sauté the
aromatics, add spices, tomatoes, then coconut milk and simmer.""",
    },
    {
        "name": "non_recipe_input",
        "text": "What is the meaning of life? Please philosophise.",
    },
    {
        "name": "italian_input",
        "text": "Spaghetti aglio e olio per 4 persone. 400g spaghetti, 6 spicchi d'aglio, olio extravergine, peperoncino, prezzemolo. Cuocere la pasta, soffriggere l'aglio, mescolare. 15 minuti.",
    },
]


if __name__ == "__main__":
    for case in TEST_INPUTS:
        print(f"\n--- {case['name']} ---")
        try:
            result = extract_recipe(case["text"])
            print(json.dumps(result, indent=2, ensure_ascii=False))

            assert "title" in result, "missing title"
            assert "is_recipe" in result, "missing is_recipe flag"
            assert isinstance(result.get("ingredients"), list), "ingredients must be a list"
            print("\n✓ Tool called with structured schema")

        except ValueError as e:
            print(f"\n✗ Tool not called: {e}")
        except AssertionError as e:
            print(f"\n✗ Schema mismatch: {e}")
        except Exception as e:
            print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")