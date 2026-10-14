# AI Engineering Learning — Notes

Lines marked `TODO(DJ)` are gaps only I can fill from my own runs. Don't fill them from memory if I can't remember — re-run and observe.

---

## Week 1 — Day 1 (Mon 5 May 2026)

### What I built today
- Raw `httpx` call to Anthropic Messages API, no SDK
- Tested failure modes: empty input, oversized input, bad auth, no network

### What surprised me
- The `stop_reason` value of `end_turn` — not sure how that's determined during the API call
- `"explain " * 10000` (~10K tokens) was accepted and Claude asked what I actually meant, rather than erroring. Under the context limit, so the API passed it through and the model fell back to clarification-seeking on a degenerate input
- `"explain " * 1000000` was rejected before the model saw it: `413 Payload Too Large`. Two different layers can refuse a request — the API (HTTP status) and the model (its reply)

### What broke
- The 413 surfaced only as httpx's generic `Client error '413 Payload Too Large'`. Anthropic's actual explanation was in the response body and my code threw it away

### What I can now do that I couldn't yesterday
- Read the shape of an Anthropic API response without needing to look at docs
- Call the Anthropic API directly and handle the user/assistant message structure

### Open questions
- ~~Don't fully understand `response.raise_for_status()`~~ — resolved, see below

### Day 1 — what raise_for_status() actually does
- httpx returns a Response object whatever the status code is — 200, 404, 500 all "succeed" from the library's perspective
- raise_for_status() converts 4xx and 5xx status codes into HTTPStatusError exceptions
- It does NOT extract the API's error message from the body — that's still in response.json()
- Production pattern: read the body and extract the real error message before letting the exception propagate
- 4xx = client's fault, don't retry. 5xx and 429 = server's fault, retry with backoff

### Setup lessons
- Postgres + pgvector running via Docker Compose
- First version of `docker-compose.yml` had the DB password hardcoded and committed. Moved to `${POSTGRES_*}` vars read from `.env` (gitignored), with `.env.example` committed as a template
- Principle: dev/prod parity — same env-var lookup in both, only the source of the value differs. Don't build the "it's only local" habit
- GitHub over SSH (ed25519 key). First push needed `--allow-unrelated-histories` and a README merge conflict fix because the GitHub repo was created with a README

---

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
- TODO(DJ): one specific observation from the failure tests

### Key insight
- Without typed error extraction, every failure looks the same to your logs ("Client error 4XX"). With it, you can grep your logs for `error_type: rate_limit_error` and instantly know what kind of failure pattern you're seeing.

---

## Day 3 — OpenAI Responses API + comparison (May 2026)

### What I built
- `day3_openai.py`: same retry/error pattern as Day 2, against OpenAI
- Optional `instructions` parameter on `ask_gpt()`

### Caught while reading the docs
- First version used Chat Completions (`/v1/chat/completions`). OpenAI's docs say the Responses API (`/v1/responses`) is recommended for all new projects; Chat Completions is legacy-supported
- Rebuilt against Responses. Lesson: read the docs before coding, not after — I'd otherwise have written legacy code for 11 weeks

### Anthropic Messages vs OpenAI Responses
- Endpoint: `api.anthropic.com/v1/messages` vs `api.openai.com/v1/responses`
- Auth: `x-api-key` + `anthropic-version` header vs `Authorization: Bearer`, no version header
- Request: `messages` array vs `input` (string or array); `max_tokens` vs `max_output_tokens`
- Answer text: `content[]` blocks, find `type == "text"` vs walk `output[]` for `type == "message"`, then `content[]` for `type == "output_text"`
- Usage: both use `input_tokens` / `output_tokens` (legacy Chat Completions used `prompt_tokens` / `completion_tokens` — Responses converged on Anthropic's naming)
- Errors: both nest under `error.message`, so one extraction function works for both

### System prompts
- Anthropic: top-level `system` field
- OpenAI Chat Completions: a `role: "system"` message
- OpenAI Responses: top-level `instructions` field, or a `role: "developer"` message in `input`
- OpenAI renamed `system` → `developer` to make the trust hierarchy explicit when devs and end-users both send instructions

### instructions field test
- Question: "Explain a transformer architecture."
- With `instructions="Answer in exactly two sentences. No analogies."`: 2 sentences, 26 in / 46 out, AUD $0.000049
- TODO(DJ): same question without instructions — tokens out and cost, for the comparison
- Output tokens drive cost; constraining output length is a real cost lever

### SDK vs raw httpx
- `client.responses.create(...)` is the SDK equivalent of my raw call; `client.chat.completions.create(...)` is the legacy endpoint
- SDK gives for free: auth from env, retries (`max_retries`), typed exceptions, typed responses, `response.output_text` convenience
- Raw first so I know what the SDK hides — and can debug it, or drop below it, when it misbehaves

---

## Interlude — cost incident (mid-May 2026)

### What happened
- OpenAI spend for 16 Apr – 16 May: USD $24.96. Two spikes: 7 May $11.49, 10 May $7.70. Normal learning days were $1–3
- 7 May usage export showed 25+ different models: `gpt-5.5` (35 calls, 3.47M input tokens — most of the spend), `gpt-3.5-turbo` (751 calls, autocomplete pattern), multiple `codex` variants, `o1`/`o3`/`o4-mini`
- My scripts only ever call `gpt-4o-mini`. The pattern was an AI editor, not my code

### Root cause
- Cursor was using my OpenAI key (BYOK) for autocomplete, chat and agent mode, while I used it for the Ed Donner course

### Fix
- Removed the key from Cursor (Cursor uses its own service now)
- Revoked all old keys; new key lives only in this repo's `.env`
- $10 prepaid credit, auto-recharge OFF — a hard ceiling stronger than a dashboard limit
- Checked git history for leaked keys: only the `.env.example` placeholder

### Lessons
- One key per purpose. Never share a learning key with a tool
- Hard spend ceilings on every provider before writing code
- Diagnose from usage data (model, tokens, requests), not from guesses — the model mix identified the culprit in minutes

---

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
- TODO(DJ): without the "no markdown" rule, what did Claude wrap the output in? With it restored, did the wrapping stop?
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

### Side observation — JSON Unicode escapes
- "Sauté" printed as `Sauté`. `json.dumps()` defaults to ASCII-safe output
- Same data, different display. `json.dumps(..., ensure_ascii=False)` prints the character directly

### Day 4 — Key insight
- Prompt-based schema enforcement is best-effort, not contract. Today's 4 tests demonstrated 4 distinct failure modes:
  - A: non-recipe input → schema-compliant but semantically empty output
  - B: markdown wrapping → format violations unless explicitly forbidden
  - C: temperature variance → nondeterminism on inputs with multiple valid fillings
  - D: multilingual → partial rule compliance when prior conflicts with rule
- These aren't edge cases — they're predictable behaviours of LLMs operating on natural-language schema rules
- Structural fix: Anthropic Tool Use API (Day 5) — moves schema from prose-rules to API-contract level
- TODO(DJ): Day 4 cost (check the Anthropic console)

### Personal reflection
- Genuinely interested in how variance, training priors and schema enforcement interact to produce different behaviour on different inputs. Only shows up when you run the experiments.

---

## Day 5 — Tool Use as structural schema enforcement

### What I built
- day5_tool_use.py: same recipe extraction, but using Anthropic Tool Use API
- Schema defined as JSON Schema in the tool's input_schema, not as prose in system prompt
- tool_choice={"type": "tool", "name": "save_recipe"} forces Claude to call the tool
- Added is_recipe boolean to give Claude a way to signal "this isn't valid input"

### How Day 5 fixed Day 4's failure modes
- Test A (non-recipe): is_recipe=false now signals invalid input cleanly — no more silent nulls
- Test B (markdown wrapping): structurally impossible — tool calls can't be prose-wrapped
- Test C (temperature): see "Test C — tool use stabilises variance" below
- Test D (translation): see "Test D — partial priors persist" below

### What didn't change
- The model's underlying training priors still apply
- Tool use makes schema enforcement structural, but doesn't eliminate ambiguity in the source text

### Key insight
- Tool use moves schema enforcement from "polite request in prose" to "API-level contract"
- The model can still produce semantically wrong content, but it can't produce structurally wrong content
- Different problem to solve, different solution. Same problem space, different lever.
- Field-level descriptions in tool schemas are processed differently from system-prompt rules — they appear to have stronger effect on per-field compliance.

### When to use which
- Tool use: when schema correctness matters more than free-form output (extraction, classification, structured agent actions)
- Prompt-based JSON: when you need flexibility or the schema is fluid
- Prose generation: when there's no schema at all (summaries, explanations, creative content)

### Test C — tool use stabilises variance even at temperature=1
- At temperature=1.0, chicken curry output was identical (or near-identical) across 3 runs
- On Day 4 at the same temperature, the same input produced visibly different outputs each time
- Mechanism: tool use makes the model fill structured arguments rather than generate prose JSON.
  The API enforces shape (fields, types, ordering) below the sampling layer, so temperature
  only varies the values, not the structure. Fewer decisions = less variance.
- Production implication: if you need temperature > 0 for other reasons, tool use still gives
  you reliable structured output.

### Test D — partial priors persist even in tool use
- Title field description: "Translate the title if the source is in another language"
- Result: still returned "Spaghetti Aglio e Olio" — Italian preserved
- Only worked when description was strengthened to: "Translate the title... even if it has no meaning"
- The phrase "even if it has no meaning" doesn't make the rule clearer — it signals to the model
  that you specifically want to override its prior about preserving well-known dish names
- Lesson: tool schemas have hard type/shape constraints but soft semantic ones. Field descriptions
  are interpreted by the model with training priors still in play. Strong priors require explicit
  conflict-resolution language to override.

### Day 5 — what tool use actually does
- Eliminates: markdown wrapping, format failures, schema-shape violations, silent nulls (with is_recipe), most temperature-driven variance
- Does NOT eliminate: training prior overriding semantic instructions in field descriptions
- The structural failures vanish; the semantic ones persist with reduced severity
- Production engineering: layer tool schemas + field descriptions + explicit priors-override language + post-processing validation

---

## Day 6 — Consolidation (completed 13/10/2026)

### What I built
- `providers/` package: `base.py` (Usage, CompletionResult, APIError, `extract_api_error`, `post_with_retries`, Provider Protocol), `claude.py`, `openai.py`, `__init__.py` with `get_provider()`
- `pricing.py`: AUD rates per provider per model, `calculate_cost_aud()`
- `ask.py`: one CLI, `--provider claude|openai`, `--model`, `--instructions`

### Test results
- Claude: "What is RAG in one sentence?" → 15 in / 38 out, AUD $0.000923
- OpenAI: same prompt → 15 in / 28 out, AUD $0.000029 (~30x cheaper)
- Claude with "Answer in exactly two sentences." → 19 in / 90 out, AUD $0.002111. Two sentences, but long ones — literal compliance, not necessarily helpful compliance
- `--provider gemini` → rejected by argparse, exit 2. My `get_provider()` error message never ran

### What went wrong during the rebuild
- `touch` created empty files; I never pasted the code. Empty `ask.py` = silent exit 0 — not broken, not working, just empty
- `pricing.py` ended up inside `providers/` instead of `week1/` → `ImportError: cannot import name 'calculate_cost_aud'`
- One file was saved as `ask,py` (comma)
- Diagnostic reflex: when something produces nothing, check the file exists, is where the import expects, and has content (`ls`, `head -5`) before debugging imports or environment

### Environment lessons
- `VIRTUAL_ENV` pointing at another project's venv (`post-trade-market-intel`) — left over from `source .venv/bin/activate` in another repo. `uv` ignored it and warned; plain `python` wouldn't have. Fix: `deactivate`. Better: always `uv run`, never manual activate
- `uv init agent_sdk_tutorials` inside this repo silently registered it as a uv workspace member in `pyproject.toml`. Committing that without the folder breaks `uv sync` for anyone who clones. Moved the tutorials out of the repo instead
- `.vscode/` added to `.gitignore`

### Tokens vs words
- 19 input tokens for a short prompt: system instructions + user prompt + provider message framing all count
- Tokens are subword units. Rough rule for English: 1 token ≈ 0.75 words. Rare words split into several tokens; non-English text inflates token counts
- Matters for cost estimates, context-window budgeting and prompt trimming

---

## Week 1 knowledge check (13/10/2026)

### Cold answers (no code, no notes)
1. Retry trace (529 ×3 then 200, `max_retries=3`): "Don't remember what 529 was for, maybe some error code, and 3 retries and final success code 200, not sure how many seconds slept"
2. Why loop over `content` blocks: "Content has the actual content to loop over and content[0] has the header or metadata" / "or content[0] has the system prompt"
3. Shape vs semantics (`is_recipe` vs Italian title): don't know
4. Duplicated information when adding a provider: "`get_provider()` and `pricing.py` have duplicate lists of provider names"
5. Why tool use reduced variance at temperature 1.0: "Tool use is deterministic and prompt-based JSON is still using the LLM to generate output"

Result: roughly 1 of 5. Several weeks off erased most of it — building and moving on doesn't retain on its own.

### Revised answers (after targeted review)
1. TODO(DJ): trace `post_with_retries` in `providers/base.py` — number of HTTP calls, seconds slept, what the caller gets
2. TODO(DJ): parked tutorial in `week1/exploration/`, search "content array"
3. TODO(DJ): from the Day 5 notes above
4. TODO(DJ): which duplication actually caused the gemini behaviour, and the registry design that removes it. Should `pricing.py` read from the registry?
5. TODO(DJ): from Day 5 Test C above — what does the API enforce vs what does the model still sample?
