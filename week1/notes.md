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