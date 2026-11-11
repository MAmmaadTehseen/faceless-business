# Model providers

Anthropic remains the default. Selecting `lunaroute` never falls back to Anthropic,
including on authentication, quota, model, JSON or vision errors. Keys and gateway
configuration come only from the process environment. `LLM_PROVIDER` takes precedence
over the optional `llm_provider` database setting. No database migration is needed.

## Public API documentation (checked 2026-11-11)

| Interface | Base URL | Route |
|---|---|---|
| Anthropic Messages (used here) | `https://gw.lunaroute.com` | `/v1/messages` |
| OpenAI Chat Completions | `https://gw.lunaroute.com/v1` | `/chat/completions` |
| Responses | `https://gw.lunaroute.com/v1` | `/responses` |

The [Messages reference](https://docs.lunaroute.com/api/messages/) documents
`LUNAROUTE-API-KEY` authentication and `anthropic-version: 2023-06-01`.
It also accepts Bearer and `x-api-key` authentication for `lr_` keys.
This implementation always uses the dedicated LunaRoute header. The Messages
format carries image blocks, including the base64 images already used by QA.
The [Chat Completions reference](https://docs.lunaroute.com/api/chat-completions/)
and [API overview](https://docs.lunaroute.com/api/) describe the other interfaces.
`app.lunaroute.com` is the dashboard, not the inference base URL.
`LUNAROUTE_BASE_URL` can override the gateway; use an HTTPS root or `/v1` URL.
Do not embed credentials, queries or fragments in it.

[Concurrency documentation](https://docs.lunaroute.com/concepts/lanes/) explains
that capacity depends on the subscription. Extra requests can queue or overflow;
priority queue waiting is capped at 60 seconds, background waiting at 240 seconds.
[Errors and rate limits](https://docs.lunaroute.com/api/errors/) documents HTTP 429
and `Retry-After`; clients should allow more than 60 seconds for queued requests.
The adapter uses a 10-second connection and 300-second read timeout, with bounded
same-provider retries for 429/5xx, honoring integer Retry-After up to 60 seconds.
Inference redirects are refused to keep the API key on the configured gateway.
Exact owner-plan concurrency and model output limits are unverified. Confirm them
in the account; this implementation does not query the live catalog at startup.
The [Models API](https://docs.lunaroute.com/api/models/) describes per-model context
limits and capability metadata. Model availability can change; configure overrides
if the chosen IDs are unavailable. Do not assume a subscription includes BYOK costs.

Native JSON Schema enforcement for these specific models and the Messages route
could not be confirmed in public documentation. UI capability badges are not a
wire-format guarantee. The adapter requests JSON in the prompt, validates the same
pipeline schema locally and makes at most one repair request. The local validator
supports the schema vocabulary currently used by the pipeline and rejects unknown
constraints. No native output_config, Anthropic beta, server-side fallback or
server tools are sent to LunaRoute. Its separately documented search tools are not
assumed to implement Anthropic's server web_search contract.

## Configuration and models

Set `LLM_PROVIDER=lunaroute`, `LUNAROUTE_API_KEY` and optionally
`LUNAROUTE_BASE_URL=https://gw.lunaroute.com` in the owner's environment.
Leave `LLM_PROVIDER=anthropic` for existing behavior and `CLAUDE_MODEL` support.

| Step | LunaRoute default | Override |
|---|---|---|
| Script | glm-5.3 | LLM_MODEL_SCRIPT |
| Article | glm-5.3 | LLM_MODEL_ARTICLE |
| QA (also image default override) | glm-5.3-vision | LLM_MODEL_QA |
| Image QA, including recap | glm-5.3-vision | LLM_MODEL_VISION |
| Reply (`engage`) | glm-5.3-flash | LLM_MODEL_REPLY |
| Ideation | glm-5.3-flash | LLM_MODEL_IDEATE |
| Daily Short | glm-5.3 | LLM_MODEL_SHORT_DAILY |
| Recap text | glm-5.3 | LLM_MODEL_RECAP |
| Hook / review | glm-5.3 | LLM_MODEL_HOOK / LLM_MODEL_REVIEW |
| Optimize | glm-5.3-flash | LLM_MODEL_OPTIMIZE |

Overrides apply to the selected provider; clear incompatible overrides when switching.
LunaRoute included inference records zero marginal USD, retaining one costs row per
request attempt, including JSON repair responses and failed HTTP attempts (zero
usage when no response usage is available). The existing costs schema has no
provider column: LunaRoute rows encode provider and model as `lunaroute/<model>`;
Anthropic rows preserve their existing model IDs. Monthly cost accounting still
applies. LunaRoute estimates are zero; `LLM_MAX_CALLS_PER_CLIENT` (default 100) caps
all requests, including retries and repairs, independently of dollar cost. This is
per Claude instance, not an organization-wide concurrency or daily limit.

Research uses supplied ideation news and bounded HTTP source-text extraction (up to
eight HTTPS sources, 256 KB read and 12 KB text each, connect/read timeouts, no
redirects or private-address hosts). Google News redirect links or blocked paywalls
may yield no article text. Models are instructed not to infer claims from URLs.
Source text is untrusted input. Saved LunaRoute scripts retain `supplied_sources`;
articles reject evidence URLs outside that list. Legacy scripts without this
metadata require owner-verified source URLs before LunaRoute article generation.
Existing checks do not independently verify factual truth when source text is
unavailable. LunaRoute vision errors block QA instead of accepting probe-only results;
review initial outputs privately before regular production.

## Owner steps

1. Export configuration without printing keys. For Actions, add repository variable
   `LLM_PROVIDER=lunaroute`, secret `LUNAROUTE_API_KEY`, and optionally variable
   `LUNAROUTE_BASE_URL`. Never put keys in repository variables. Existing model jobs,
   sync and retry receive these values. Agents must not update your secrets.
2. Run the local comparison manually with exported configuration:
   `PYTHON_DOTENV_DISABLED=1 .venv/bin/python scripts/llm_compare.py --out out/llm-compare`.
   It makes four tasks (plus possible JSON repairs), writes script/article/vision/reply
   JSON and cost records under the provider directory, and never publishes or writes
   production data. It uses a fixed synthetic source and thumbnail; it is a quality
   comparison, not evidence verification or an end-to-end publishing test.
3. Run it under each provider only when that provider has available credit. Preserve
   both output folders for comparison. The Anthropic run still costs money.
4. Review accuracy, persona distinction, article sources, visual judgments and replies.
   Then run one private production. Existing publish/privacy/QA rules still apply.
