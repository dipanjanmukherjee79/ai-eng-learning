# AI Engineering Learning — Notes

## Week 1 — Day 1 (Mon 5 May 2026)

### What I built today
- Raw `httpx` call to Anthropic Messages API, no SDK
- Tested failure modes: empty input, oversized input, bad auth, no network

### What surprised me
- (write your own observation here — e.g. "The token count for my one-sentence question was X, lower/higher than I expected")
- the stop_reason value of end_turn,not sure how thats determined during the API call
- (a third)

### What broke
- (write what didn't work — e.g. "First run got 401 because I had a typo in the env var name")

### What I can now do that I couldn't yesterday
-  "Read the shape of an Anthropic API response without needing to look at docs"
-  "Able to call an anthropic api to create a user assiatnt message loop"

### Open questions
- dont understand whats the response.raise_for_status() function completely 

### Day 1 — what raise_for_status() actually does
- httpx returns a Response object whatever the status code is — 200, 404, 500 all "succeed" from the library's perspective
- raise_for_status() converts 4xx and 5xx status codes into HTTPStatusError exceptions
- It does NOT extract the API's error message from the body — that's still in response.json()
- Production pattern: read the body and extract the real error message before letting the exception propagate
- 4xx = client's fault, don't retry. 5xx and 429 = server's fault, retry with backoff



## Day 2 (06/05/2026)

### What I built
- Typed APIError exception extracts type and message from response body
- Retry logic with exponential backoff: retries 429 and 5xx, fails fast on 4xx
- Token usage and AUD cost printed after each call

### Failure mode tests run
- Missing CLI arg → clean usage message, exit 1, no API call
- Whitespace-only input → 400 invalid_request_error with field-level detail, no retry
- Oversized prompt (1M tokens) → 413 with actual token count and limit
- Bad API key → 401 authentication_error, no retry
- Bad model name → 404 not_found_error, no retry

### What surprised me
- (your specific observation, e.g. "Anthropic's 413 error tells me exactly which token limit I hit, not just 'too big'")
- (another)

### Key insight
- Without typed error extraction, every failure looks the same to your logs ("Client error 4XX"). With it, you can grep your logs for `error_type: rate_limit_error` and instantly know what kind of failure pattern you're seeing.
## Day 4 (17/05/2026)

### Test A — non-recipe input
- Observed: Claude returns a fully-formed JSON with null values across the board
- Schema rule was followed correctly — but the result is a silent failure from an application perspective
- Lesson: the model can only signal what your schema gives it a vocabulary for. Add an explicit "is_recipe" boolean (or "valid_input", "confidence", etc.) so the model can refuse, not just comply emptily
- Production implication: silent nulls in pipelines = invisible failures. Always design schemas with a "this isn't valid input" signal.
### Today's assertion patterns
- `assert <cond>, <msg>` — Python shortcut for "raise AssertionError if cond is false"
- `key in dict` checks if a key exists (not a value)
- Assertions can be disabled with python -O, so don't use them for production validation
- For real schema validation, Pydantic is the standard — assertions are training wheels for now

### Test B — markdown wrapping
- Without explicit "no markdown" rule: Claude wrapped output in (describe what you saw — ```json fences? plain ``` fences? no wrapping at all?)
- With the rule restored: (did it stop?)
- strip_code_fences handled it transparently — but in production you can't assume the model follows even explicit format instructions
- Lesson: prompt-based schema enforcement is unreliable for *format* as much as for *content*. Tool Use API addresses this structurally.
### Test C — temperature variance, finer observation
- Only `casual_narrative` varied across runs at temperature=1.0
- `clean_structured` and `ambiguous_quantities` stayed essentially identical
- This is because temperature controls sampling spread, not the underlying probability distribution
- Sharp/peaked distributions (unambiguous inputs) produce stable output even at temp=1
- Flat distributions (genuinely ambiguous inputs) produce variable output
- Insight: variance under temperature is a diagnostic for input ambiguity, not just a randomness setting
- In production: running an eval set at temperature=1 reveals which inputs your prompt fails to constrain — these are where your prompt needs work
### Test C — correction to earlier observation
- Tried "Make some pasta. It's good." at temp=1.0, three runs — identical output
- This pushed against my initial mental model
- Refined principle: temperature varies *only across what the model considers plausible*, and the schema rules define what's plausible
- "Plausible" here was constrained by my "use null when uncertain" rule — the model didn't invent details
- Real variance requires inputs where multiple legitimate schema-fillings exist (e.g. unspecified quantities in chicken curry, where multiple `quantity` strings would all be "correct")
- Bigger lesson: well-designed schema rules can suppress variance even at temperature=1.0 — they constrain creativity more than temperature does
- Use this in production: if you find your extraction is too variable, sharpen the schema rules rather than lowering temperature
### Test D — partial rule compliance
- With "translate all string fields to English" rule applied:
  - title field: "Spaghetti Aglio e Olio" — NOT translated (likely preserved as proper noun)
  - ingredients, steps, quantities: all correctly translated to English
- The rule was applied partially — some fields obeyed, title field did not
- Hypothesis: well-known dish names are treated as proper nouns by training priors, overriding the explicit translation rule
- Bigger lesson: rules in prompts are heuristics weighted against training priors. Strong priors can override explicit instructions.
- Compliance is FIELD-BY-FIELD, not all-or-nothing — and the failure pattern isn't always predictable
- Production-grade fixes: post-processing validation, tool use / function calling for stricter schema enforcement, two-stage extraction, or separate calls per field for critical reliability

### Day 4 — Key insight
- Prompt-based schema enforcement is best-effort, not contract. Today's 4 tests demonstrated 4 distinct failure modes:
  - A: non-recipe input → schema-compliant but semantically empty output
  - B: markdown wrapping → format violations unless explicitly forbidden
  - C: temperature variance → nondeterminism on inputs with multiple valid fillings
  - D: multilingual → partial rule compliance when prior conflicts with rule
- These aren't edge cases — they're predictable behaviours of LLMs operating on natural-language schema rules
- Structural fix: Anthropic Tool Use API (Day 5) — moves schema from prose-rules to API-contract level
- Today's cost: AUD $X


## Day 5 — Tool Use as structural schema enforcement

### What I built
- day5_tool_use.py: same recipe extraction, but using Anthropic Tool Use API
- Schema defined as JSON Schema in the tool's input_schema, not as prose in system prompt
- tool_choice={"type": "tool", "name": "save_recipe"} forces Claude to call the tool
- Added is_recipe boolean to give Claude a way to signal "this isn't valid input"

### How Day 5 fixed Day 4's failure modes
- Test A (non-recipe): is_recipe=false now signals invalid input cleanly — no more silent nulls
- Test B (markdown wrapping): structurally impossible — tool calls can't be prose-wrapped
- Test C (temperature): (your observation on whether variance reduced)
- Test D (translation): (your observation on title translation)

### What didn't change
- The model's underlying training priors still apply
- Tool use makes schema enforcement structural, but doesn't eliminate ambiguity in the source text
- (other observations from your runs)

### Key insight
- Tool use moves schema enforcement from "polite request in prose" to "API-level contract"
- The model can still produce semantically wrong content, but it can't produce structurally wrong content
- Different problem to solve, different solution. Same problem space, different lever.
- Field-level descriptions in tool schemas are processed differently from system-prompt rules — they appear to have stronger effect on per-field compliance.

### When to use which
- Tool use: when schema correctness matters more than free-form output (extraction, classification, structured agent actions)
- Prompt-based JSON: when you need flexibility or the schema is fluid
- Prose generation: when there's no schema at all (summaries, explanations, creative content)