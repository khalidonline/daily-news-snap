# Daily paid API accounting

## Current policy: 4 November 2026

The owner removed the aggregate $3/day production ceiling after explicit warning
that this permits spending above $3 without a daily cap. `shared_ledger()` and
`autopilot_daily_limit()` now select an unbounded aggregate ledger (Python `None`,
JSON `null`). The autopilot policy retains historical limits before 4 November
(Saudi date); legacy workflow environment values cannot restore the obsolete cap
on current runs. The daily lane's percentage allocation applies only to bounded
ledgers: a share of an unlimited daily allowance is not a separate dollar limit.

This does **not** remove package writing/review limits, finite token/search bounds,
known-provider/model checks, credential requirements, CAS ledger integrity,
unknown-outcome reservations, workflow holds, quota checks, publishing approvals,
duplicate protection or schedules. It does not authorize a paid call or publication.
Accounting continues internally; no cost-reporting feature is introduced.

Explicit bounded Ledger callers, historical one-off scripts and experimental
budgets remain bounded. The Ledger constructor retains its legacy $3 default for
those callers; production factories explicitly request no aggregate ceiling.
Existing entries are preserved when a current runner records a null ceiling.
Updated bounded callers can settle those rows and enforce their own limits;
old code revisions cannot read null ceilings and fail closed, rather than being
silently upgraded or enabling held routes. Do not run old recovery scripts to
bypass a hold. No ledger branch is changed merely by merging this patch.

Provider/account billing limits, quotas, credit balances, service rate limits and
platform charges remain outside this repository. Their current settings were not
queried or changed. Thus this supports **no application-wide daily dollar cap**,
not unlimited provider access or removal of every per-request/package safeguard.

The sealed design master retains historical USD3 wording to avoid silently
changing hashes of approved media/preparation. The newer owner decision and
AGENTS.md override that spending-policy wording only. No content needs resealing
for this code-only change. Production remains unchanged until this draft is
approved and merged/deployed through the normal process.

## Historical policy (superseded only for the aggregate production ceiling)

Owner instruction, 10 September 2026: **$3 USD total per Saudi calendar day**,
shared by News, Topic, Story, Breaking, manual pilots, and paid repairs/retries.

The workflow bootstrap installs `daily_budget.py` into the runner's temporary
Python path before checking out production code. It therefore also covers the
Story repair branch, legacy repair checkouts, and recovery subprocesses. All
credential-bearing workflows on main and the active Story branch install it.

Before a paid request, the guard atomically reserves a conservative upper cost
in `daily/YYYY-MM-DD.json` on the dedicated `cost-ledger` branch. GitHub Contents
SHA preconditions prevent two runners from spending the same remaining money.
All workflows use their existing contents-write GITHUB_TOKEN. No new service is
required. The ledger branch has no workflows, so its updates cannot run bots.

Successful responses settle against provider usage and release unused money.
Unknown prices, unavailable/corrupt state, missing usage, and ambiguous network
failures retain reservations or block requests. A new run ID, retry, manual
invocation, or branch checkout does not reset the allowance. In-flight calls
belong to the Saudi date when their reservation was authorized. A late response
settles that original date. No unused allowance rolls into the next day.

Current supported rates and context bounds are explicit for Sonnet 5, Opus 5,
and Haiku 4.5. Requests reserve full possible output, uncached text byte bounds,
full image/document context, server-search context, search fees, and cache-write
premiums. Search is limited to one direct server search per request; dynamic
filtering is replaced by direct search to avoid unbounded server-code charges.
Existing source/editorial/photo quality checks continue to determine whether a
result is publishable. Paid image generation and unpriced models/API modes are
blocked. Free image retrieval and existing-artifact delivery remain available.

Reservations can hold a request before actual spending reaches $3 if its maximum
cost does not fit. This is deliberately more conservative than an after-the-fact
cost report. Uncertain reservations are not automatically refunded.

Deployment-day spending before this guard cannot be reconstructed reliably from
all old runs. That day's allowance is held (not represented as actual billed
usage); the first fresh $3 allowance begins at the next Saudi midnight.

Scope: API requests from these guarded Python workflows, at the documented
first-party rates. It does not alter provider-account billing settings, taxes,
fixed subscriptions, GitHub Actions charges, old workflow revisions, or external
programs that use the same API keys. Provider invoices remain authoritative.

Pricing reference, checked 10 September 2026:
https://platform.claude.com/docs/en/about-claude/pricing
