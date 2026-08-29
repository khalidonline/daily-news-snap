# Saudi Snapchat Freshness Amendment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this amendment together with `2026-08-29-saudi-snapchat-editorial-implementation.md`.

**Goal:** Make the normal daily-news bot prefer recent stories while allowing strong, still-relevant stories up to 48 hours old.

**Architecture:** Preserve publication time on internal feed items, widen the normal daily lookback to 48 hours, expose article age to the model, and use recency as a tie-break/ranking factor rather than a hard preference for weak newer material. Breaking-news behavior remains unchanged.

**Tech Stack:** Python 3.12, existing `datetime`, RSS/Atom parsing, `unittest`, GitHub Actions workflow YAML.

**Spec:** `docs/superpowers/specs/2026-08-29-saudi-snapchat-freshness-amendment.md`

## Global Constraints

- Normal daily-news maximum age: 48 hours.
- 0–12h receives strongest freshness preference; 12–24h remains fully eligible; 24–48h remains eligible when editorial value is strong.
- Older than 48h is excluded from normal daily-news candidates.
- Newer wins only when stories are otherwise similarly valuable.
- A strong 24–48h story may outrank a weak 0–12h story.
- Existing posted-story memory/deduplication remains active.
- Do not add publication metadata to the public card JSON schema.
- Do not loosen breaking-news recency or confirmation rules.

---

### Task 1: Preserve article publication time

**Files:**
- Modify: `news_bot.py` in `fetch_headlines()`
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Internal feed item gains `published_at: str | None` containing UTC ISO-8601.

- [ ] **Step 1: Write a failing test**

Add a fixture-level test that calls the feed-item construction helper (extract one if needed) and asserts a parsed timestamp is retained as UTC ISO-8601.

```python
self.assertEqual(item["published_at"], "2026-08-28T12:00:00+00:00")
```

- [ ] **Step 2: Run the test and verify failure**

```bash
python -m unittest tests.test_news_editorial -v
```

Expected: FAIL because feed items currently do not retain `published_at`.

- [ ] **Step 3: Implement minimal timestamp retention**

In `fetch_headlines()`, after parsing `published`, store:

```python
"published_at": published.astimezone(timezone.utc).isoformat() if published else None,
```

Keep the field internal only.

- [ ] **Step 4: Run tests and commit**

```bash
python -m unittest tests.test_news_editorial -v
git add news_bot.py tests/test_news_editorial.py
git commit -m "feat: retain feed publication time"
```

---

### Task 2: Widen normal daily lookback to 48 hours

**Files:**
- Modify: `news_bot.py` configuration default
- Modify: `.github/workflows/daily.yml`
- Test: `tests/test_news_editorial.py`

- [ ] **Step 1: Add a policy test**

Add an assertion that the editorial freshness constant/default is 48 hours. If configuration remains in `news_bot.py`, expose or import a stable constant rather than parsing source text.

```python
self.assertEqual(DEFAULT_LOOKBACK_HOURS, 48)
```

- [ ] **Step 2: Verify the test fails**

```bash
python -m unittest tests.test_news_editorial -v
```

- [ ] **Step 3: Implement the 48-hour default and workflow override**

Change the Python default from 30 to 48 hours and the production daily workflow override from 10 to 48 hours.

Do **not** change `breaking.yml` as part of this task.

- [ ] **Step 4: Run tests and inspect workflow diff**

```bash
python -m unittest tests.test_news_editorial -v
git diff -- news_bot.py .github/workflows/daily.yml
```

Expected: daily lookback is 48; breaking workflow untouched.

- [ ] **Step 5: Commit**

```bash
git add news_bot.py .github/workflows/daily.yml tests/test_news_editorial.py
git commit -m "feat: widen daily news lookback to 48 hours"
```

---

### Task 3: Add explicit freshness age to shortlist/model input

**Files:**
- Modify: `news_editorial.py`
- Modify: `news_bot.py` in `summarize()` feed-text construction
- Modify: `tests/test_news_editorial.py`

**Interfaces:**
- Produce: `publication_age_hours(item: dict, now: datetime | None = None) -> float | None`
- Produce: `format_age_label(item: dict, now: datetime | None = None) -> str`

- [ ] **Step 1: Write failing age-label tests**

```python
self.assertEqual(format_age_label(item, now=fixed_now), "4h")
self.assertEqual(format_age_label(older_item, now=fixed_now), "31h")
```

- [ ] **Step 2: Implement age helpers**

Parse `published_at`, calculate non-negative elapsed hours, and return rounded-down integer labels such as `4h`, `31h`; unknown timestamps return `unknown`.

- [ ] **Step 3: Include age in model feed text**

Change each numbered candidate line from:

```python
f"{n}. [{i['source']}] {i['title']} — {i['summary']}"
```

to the equivalent of:

```python
f"{n}. [{i['source']}] [age={format_age_label(i)}] {i['title']} — {i['summary']}"
```

The item number must continue to map exactly to the shortlist so returned `item` values still resolve links correctly.

- [ ] **Step 4: Add a regression test proving `age=` appears in generated model input**

Extract a small `format_feed_text(shortlist, now=None)` helper if necessary so this is deterministic and does not call Anthropic.

- [ ] **Step 5: Run and commit**

```bash
python -m unittest tests.test_news_editorial -v
git add news_editorial.py news_bot.py tests/test_news_editorial.py
git commit -m "feat: expose article freshness to news editor"
```

---

### Task 4: Encode freshness ranking policy without discarding strong older stories

**Files:**
- Modify: `news_editorial.py` editorial prompt
- Modify: `tests/test_news_editorial.py`

- [ ] **Step 1: Add deterministic prompt-policy tests**

Assert the system prompt explicitly contains all of these concepts:

```python
self.assertIn("48", SYSTEM_PROMPT)
self.assertIn("0–12", SYSTEM_PROMPT)
self.assertIn("24–48", SYSTEM_PROMPT)
self.assertIn("الأحدث", SYSTEM_PROMPT)
```

Also assert it states that a strong older story can beat a weak newer story.

- [ ] **Step 2: Update the editorial prompt**

Add a concise Arabic freshness section with this policy:

- 0–12h: strongest freshness preference.
- 12–24h: fully eligible.
- 24–48h: eligible if still important/useful/discussed.
- >48h: not eligible in normal daily feed.
- If audience value is similar, prefer the newer story.
- Never choose a weak new story merely because it is newer; a major 30–48h story can win.

- [ ] **Step 3: Run tests and commit**

```bash
python -m unittest tests.test_news_editorial -v
git add news_editorial.py tests/test_news_editorial.py
git commit -m "feat: add freshness policy to Saudi news ranking"
```

---

### Task 5: Freshness regression verification

**Files:**
- Modify tests only if a real regression is discovered.

- [ ] **Step 1: Run focused editorial tests**

```bash
python -m unittest tests.test_news_editorial -v
```

Expected: PASS.

- [ ] **Step 2: Run existing repository tests**

```bash
python -m unittest discover -s tests -v
```

Expected: all existing tests PASS.

- [ ] **Step 3: Dry-run the daily bot with 48-hour lookback**

Use the existing dry-run workflow/manual path. Inspect logs and candidate output to confirm:

- no candidate exceeds 48 hours;
- 24–48h stories are present when available;
- the final ranked candidates still favor genuinely stronger/fresher stories;
- an older strong story is not automatically eliminated by trivial newer material;
- previously posted stories remain excluded.

- [ ] **Step 4: Verify breaking configuration is unchanged**

```bash
git diff HEAD~5 -- .github/workflows/breaking.yml breaking_watch.py
```

Expected: no freshness-policy changes to the breaking watcher from this amendment.

- [ ] **Step 5: Final commit only if verification required small fixes**

```bash
git add news_editorial.py news_bot.py tests/test_news_editorial.py .github/workflows/daily.yml
git commit -m "test: verify 48-hour Saudi news freshness"
```
