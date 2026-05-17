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