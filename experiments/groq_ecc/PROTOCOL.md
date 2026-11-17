# ECC patterns / existing Groq integration — 2026-11-17

Question: do the cost-aware patterns offer measurable benefit for StitchWeather?
No ECC installation, hooks or runtime dependency. No production modifications.
Provider/model unchanged: use the already configured Groq model and credentials.
Never print or persist the key. Only synthetic weather inputs leave this machine.

Four weather scenarios × ES/EN. Compare existing Groq direction with the existing
local director: same model, completion reserve, reasoning options and context.
Alternate randomized arm order. Capture API-reported usage, finish reason,
wall latency and validation through the application's actual parser.
Inspect the generated messages; parser validity alone is not advice quality.

Four exact repeat calls characterize provider-side prefix cache usage.
Four further logical requests through an isolated 300-second full-response cache
should make only two provider calls. Cache identity includes full messages,
model and completion parameters. This tests one deliberately repetitive workload,
not the hit rate or savings of real production traffic.

Bounded: at most 22 successful real requests, ≤1024 completion tokens/request,
abort on rate limiting/authentication failures or >45000 observed total tokens.
Do not reduce completion reserves or switch to a smaller model for this test.

Amendment after the first provider limit (before completing the comparison):
seven requests succeeded, the eighth received HTTP 429. Preserve those samples
and resume only unfinished cases, at 22-second spacing, retaining max_retries=0.
The overall bound includes this failed attempt: 23 real attempts maximum.
Stop again on any subsequent provider failure. No successful sample is repeated
to select better-looking advice or alter the A/B outcome.
Conclude separately about useful practices and whether installing ECC is justified.
