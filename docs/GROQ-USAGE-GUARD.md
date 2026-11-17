# Groq usage protection on Render Free

The persistent daily counter has been removed. AI works without a disk, database
or additional environment variables. Old GROQ_BUDGET_PATH and
GROQ_DAILY_REQUEST_LIMIT variables are ignored and can be removed.
There is no application-wide daily budget or guaranteed financial spending cap.

## In-memory advice cache

- Validated advice is reused for 300 seconds by default. The SHA-256 key includes
  full weather context, prompt, language, model, director and completion cap.
- Maximum 512 active keys per process. Expired entries are reclaimed; when full,
  new keys return weather without AI rather than growing memory without a bound.
- A lock reserves each key before calling Groq. Concurrent identical requests in
  the same worker do not call Groq twice. The second request returns weather
  without AI while the first is pending; later requests can reuse valid advice.
- Pending keys expire after 120 seconds. Reservation identity prevents an old
  request from overwriting a newer result after its reservation expired.
- Provider failures and invalid responses have a 30-second cooldown per key.
  They are never cached as successful advice. The SDK does not retry automatically.
- Cached values are copied before returning them so callers cannot mutate them.
- Only hashes, advice and expiry times are held in memory; no disk writes or
  stored credentials, prompts or client IPs. Restarting clears the cache and
  permits normal AI calls again. Multiple workers have separate caches.

Optional settings (existing defaults require no Render configuration):

```dotenv
GROQ_CACHE_TTL_SECONDS=300
GROQ_CACHE_MAX_ENTRIES=512
API_TRUSTED_PROXY_HOPS=0
```

The production cache guard stays enabled. No plan upgrade or paid resource is
required by these protections. The provider account's own quotas still apply.

## Request limits and graceful degradation

Before consuming the process-wide request allowance, a sliding 60-second window
limits each visitor:

| Route | Per visitor/minute | Global per process/minute |
| --- | ---: | ---: |
| clima | 6 | 30 |
| lugares | 40 | 120 |
| alertas | 20 | 60 |
| voz | 3 | 6 |

Rate-limited HTTP requests return 429, Retry-After and Cache-Control: no-store.
Health is exempt. AI failures or a pending/full cache return the existing advice
state no_disponible while preserving current weather and forecast. The frontend
already handles this state without reading a previous advice aloud.

Visitor identifiers use an HMAC of the connection IP; IPv6 addresses within one
/64 share an allowance. Up to 4096 route/visitor keys are retained per process;
new keys are rejected until expired entries can be reclaimed. Users behind one
public IP share an allowance. Limits reset on process restart.

X-Forwarded-For is ignored by default. Only set API_TRUSTED_PROXY_HOPS after
verifying the ingress appends/overwrites the real client IP, the number of trusted
hops, and that clients cannot access the application directly. Trusted hops are
counted from the right, not from an arbitrary client-supplied prefix. Leaving 0
behind a proxy may group visitors together; setting it without verification may
allow spoofing. This hosting verification remains separate from the cache change.

These are abuse and availability controls, not total DDoS protection or a financial
hard cap. Distributed clients can still consume provider quotas. Check Groq,
OpenWeather, Render and Vercel account plans separately; this code does not change
billing settings or upgrade any plan.

## Verification

Run python scripts/test_backend.py --verbosity 0. Tests use mock HTTP transports
and no real API calls. They cover concurrent reservations, valid cache expiry,
failed/invalid response cooldowns, cache capacity, late completion ownership,
cache reset, production AI without persistent storage, weather-only fallback,
visitor isolation and forwarded-header handling. The suite again forbids database
writes; the fixed read-only geographic catalog is its only allowed SQLite access.
