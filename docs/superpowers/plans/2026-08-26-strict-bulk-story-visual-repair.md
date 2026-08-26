# Strict Bulk Story Visual Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable strict bulk-repair pipeline that drives the entire 123-story catalogue to the existing runtime requirement of 4 distinct approved local photos plus 1 relevant local logo, without story-by-story manual repair loops or any weakening of relevance rules.

**Architecture:** Keep `story_runtime.coverage()` as the only PASS/FAIL authority. Add small focused modules for board generation, exact logo identity resolution, source discovery, validation, registration, and orchestration; every accepted candidate must flow through the current runtime relevance/dedupe policy before it can improve coverage. GitHub Actions runs the repair in bounded batches, commits only validated changes, rebuilds the authoritative board after every batch, and stops at 123/123 PASS or a fail-closed no-progress report.

**Tech Stack:** Python 3.12, Pillow, `urllib.request`, existing `story_runtime.py`, `story_bot.py`, `news_bot.py`, `runtime_relevance.py`, `image_precheck.py`, Python `unittest`, GitHub Actions, Wikimedia Commons/Wikidata, Library of Congress, Openverse, and exact first-party source URLs.

**Spec:** `docs/superpowers/specs/2026-08-26-strict-bulk-story-visual-repair-design.md`

## Global Constraints

- Runtime completion remains exactly 4 distinct relevant usable local photos + at least 1 relevant local logo per story.
- `story_runtime.coverage()` is authoritative; no parallel repair score may declare PASS.
- Only `DIRECT` and `STRONG_CONTEXT` verdicts count.
- `WEAK_GENERIC`, `WRONG_ENTITY`, and unreviewed `rt-*` assets never count.
- Exact SHA duplicates and perceptual dHash duplicates within `image_precheck.DHASH_MAX_DISTANCE` count once.
- Person identity must be supported by trustworthy source metadata; automated face recognition is not an identity proof.
- First-party assets may be used with source/credit provenance, but must not be described as open-license unless the source says so.
- A transient source/model/API failure never becomes approval.
- The bulk pipeline must preserve existing curated non-`rt-*` relevance entries, including the Jack Bogle repair.
- Re-running the pipeline must be idempotent: no duplicate files, duplicate index rows, duplicate logo aliases, or destructive ledger rewrites.
- A workflow green check is not catalogue completion unless a fresh authoritative board reports exactly 123 stories and 123 PASS.
- PR #2 remains draft until the 123/123 completion gate and representative renderer sanity sample pass.

## File Structure

- Create `tools/bulk_visual_board.py` — authoritative coverage rows, backlog ordering, CSV/JSON board output.
- Create `tools/bulk_visual_identity.py` — exact story/entity/person terms and fail-closed logo identity resolution.
- Create `tools/bulk_visual_sources.py` — story beat planning plus candidate metadata discovery from structured sources.
- Create `tools/bulk_visual_validate.py` — download/decode/photo-vs-graphic/dedupe/identity/relevance validation.
- Create `tools/bulk_visual_register.py` — atomic/idempotent writes to local files, `images/images.txt`, `images/relevance.json`, logo index, and story metadata when a verified logo domain is added.
- Create `tools/bulk_visual_repair.py` — resumable batch orchestrator and no-progress/unresolved reporting.
- Modify `tools/build_runtime_review.py` — consume the shared board instead of rebuilding status independently.
- Create `.github/workflows/bulk-visual-repair.yml` — bounded repair workflow with tests, commits, and review artifact.
- Modify `.github/workflows/runtime-relevance-tests.yml` — run bulk unit tests and add catalogue invariants.
- Create `tests/test_bulk_visual_board.py`.
- Create `tests/test_bulk_visual_identity.py`.
- Create `tests/test_bulk_visual_sources.py`.
- Create `tests/test_bulk_visual_validate.py`.
- Create `tests/test_bulk_visual_register.py`.
- Create `tests/test_bulk_visual_repair.py`.

---

### Task 1: Make one authoritative machine-readable repair board

**Files:**
- Create: `tools/bulk_visual_board.py`
- Create: `tests/test_bulk_visual_board.py`
- Modify: `tools/build_runtime_review.py`

**Interfaces:**
- Consumes: `story_bot.load_stories()`, `story_runtime.coverage(story)`.
- Produces: `CoverageRow`, `build_board()`, `repair_backlog()`, `write_board()`.
- `CoverageRow` fields: `story: str`, `photos: tuple[str, ...]`, `logos: tuple[str, ...]`, `need_photos: int`, `need_logo: bool`, `status: str`.

- [ ] **Step 1: Write the failing board tests**

```python
# tests/test_bulk_visual_board.py
import unittest
from unittest.mock import patch

from tools.bulk_visual_board import build_board, repair_backlog


class BulkVisualBoardTests(unittest.TestCase):
    @patch("tools.bulk_visual_board.sr.coverage")
    def test_board_uses_runtime_coverage_without_recomputing_policy(self, coverage):
        coverage.side_effect = [
            (["a", "b", "c", "d"], ["logo"], "PASS"),
            (["a", "b", "c"], [], "NEEDS 1 MORE PHOTO + LOGO"),
        ]
        rows = build_board(["Story A", "Story B"])
        self.assertEqual(rows[0].status, "PASS")
        self.assertEqual(rows[0].need_photos, 0)
        self.assertFalse(rows[0].need_logo)
        self.assertEqual(rows[1].need_photos, 1)
        self.assertTrue(rows[1].need_logo)

    @patch("tools.bulk_visual_board.sr.coverage")
    def test_backlog_orders_cheapest_gaps_first(self, coverage):
        coverage.side_effect = [
            (["a", "b", "c", "d"], [], "NEEDS LOGO"),
            (["a", "b", "c"], ["logo"], "NEEDS 1 MORE PHOTO"),
            (["a"], [], "NEEDS 3 MORE PHOTOS + LOGO"),
        ]
        rows = build_board(["Logo", "One", "Large"])
        self.assertEqual([r.story for r in repair_backlog(rows)], ["Logo", "One", "Large"])
```

- [ ] **Step 2: Run the tests and confirm RED**

Run:
```bash
python -m unittest -v tests/test_bulk_visual_board.py
```
Expected: import failure because `tools.bulk_visual_board` does not exist.

- [ ] **Step 3: Implement the board model using production coverage**

```python
# tools/bulk_visual_board.py
from dataclasses import asdict, dataclass
import csv
import json
from pathlib import Path

import story_bot as sb
import story_runtime as sr


@dataclass(frozen=True)
class CoverageRow:
    story: str
    photos: tuple[str, ...]
    logos: tuple[str, ...]
    need_photos: int
    need_logo: bool
    status: str


def build_board(stories=None):
    stories = list(stories if stories is not None else sb.load_stories())
    rows = []
    for story in stories:
        photos, logos, status = sr.coverage(story)
        rows.append(CoverageRow(
            story=story,
            photos=tuple(Path(p).name for p in photos),
            logos=tuple(Path(p).name for p in logos),
            need_photos=max(0, 4 - len(photos)),
            need_logo=not bool(logos),
            status=status,
        ))
    return rows


def repair_backlog(rows):
    failing = [r for r in rows if r.status != "PASS"]
    return sorted(failing, key=lambda r: (
        r.need_photos + int(r.need_logo),
        r.need_photos,
        int(r.need_logo),
        r.story.casefold(),
    ))


def write_board(rows, out_dir="out/bulk-visual-repair"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = [asdict(r) for r in rows]
    (out / "board.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "board.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        fields = ["story", "photo_count", "logo_count", "need_photos", "need_logo", "status", "photos", "logos"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({
                "story": row.story,
                "photo_count": len(row.photos),
                "logo_count": len(row.logos),
                "need_photos": row.need_photos,
                "need_logo": int(row.need_logo),
                "status": row.status,
                "photos": "; ".join(row.photos),
                "logos": "; ".join(row.logos),
            })
    return out / "board.json"
```

- [ ] **Step 4: Replace `tools/build_runtime_review.write_status()` internals with `build_board()` output**

The review script must import `build_board` and serialize the same rows rather than calling `sr.coverage()` through a second implementation path. Keep the existing `status.csv` column names for artifact compatibility.

- [ ] **Step 5: Run board and existing runtime tests**

```bash
python -m unittest -v tests/test_bulk_visual_board.py tests/test_runtime_relevance.py
PYTHONPATH=. python tools/build_runtime_review.py
```
Expected: all tests PASS; `out/runtime-review/status.csv` still contains 123 rows.

- [ ] **Step 6: Commit**

```bash
git add tools/bulk_visual_board.py tools/build_runtime_review.py tests/test_bulk_visual_board.py
git commit -m "feat: add authoritative bulk visual repair board"
```

---

### Task 2: Resolve existing local logos without guessing

**Files:**
- Create: `tools/bulk_visual_identity.py`
- Create: `tests/test_bulk_visual_identity.py`

**Interfaces:**
- Consumes: exact story line, `story_bot.story_aliases()`, `story_bot.story_logo_domain()`, approved local photo tags from `news_bot.load_local_images()`, `images/logos/index.json`.
- Produces: `LogoIdentity(slug, domain, aliases, reason) | None`, `resolve_existing_logo_identity(story)`.

- [ ] **Step 1: Write fail-closed logo identity tests**

```python
# tests/test_bulk_visual_identity.py
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.bulk_visual_identity import choose_unique_logo_slug


class BulkVisualIdentityTests(unittest.TestCase):
    def test_unique_exact_alias_match_is_accepted(self):
        index = {"apple.com": ["Apple", "Steve Jobs", "apple.com"]}
        self.assertEqual(
            choose_unique_logo_slug({"Steve Jobs"}, index),
            "apple.com",
        )

    def test_ambiguous_alias_match_fails_closed(self):
        index = {
            "tesla.com": ["Elon Musk"],
            "spacex.com": ["Elon Musk"],
        }
        self.assertIsNone(choose_unique_logo_slug({"Elon Musk"}, index))

    def test_substring_does_not_create_logo_identity(self):
        index = {"snap.com": ["Snap"]}
        self.assertIsNone(choose_unique_logo_slug({"Snapdragon"}, index))
```

- [ ] **Step 2: Run the tests and confirm RED**

```bash
python -m unittest -v tests/test_bulk_visual_identity.py
```
Expected: import failure.

- [ ] **Step 3: Implement exact normalized identity matching**

```python
# tools/bulk_visual_identity.py
from dataclasses import dataclass
import json
from pathlib import Path

import image_precheck as ipc
import news_bot as nb
import story_bot as sb
import story_runtime as sr

LOGO_DIR = Path("images/logos")
LOGO_INDEX = LOGO_DIR / "index.json"


@dataclass(frozen=True)
class LogoIdentity:
    slug: str
    domain: str
    aliases: tuple[str, ...]
    reason: str


def norm(value):
    return ipc.normalize(str(value or ""))


def choose_unique_logo_slug(names, index):
    wanted = {norm(n) for n in names if norm(n)}
    matches = []
    for slug, aliases in index.items():
        hay = {norm(slug), *(norm(a) for a in aliases)}
        if wanted & hay:
            matches.append(slug)
    return matches[0] if len(set(matches)) == 1 else None


def story_identity_terms(story):
    terms = set(sb.story_aliases(story))
    terms |= set(sb._STORY_PERSONS.get(str(story).strip()) or [])
    for entry in nb.load_local_images():
        if entry["path"].name in {p.name for p in sr.approved_runtime_visuals(story)[0]}:
            terms |= set(entry.get("tags", []))
    return {t for t in terms if str(t).strip()}


def resolve_existing_logo_identity(story, index_path=LOGO_INDEX):
    domain = sb.story_logo_domain(story)
    if domain and (LOGO_DIR / f"{domain}-current.png").exists():
        return LogoIdentity(domain, domain, (domain,), "declared-domain-local-file")
    try:
        index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    slug = choose_unique_logo_slug(story_identity_terms(story), index)
    if not slug:
        return None
    files = list(LOGO_DIR.glob(f"{slug}-*.png"))
    if not files:
        return None
    return LogoIdentity(slug, slug if "." in slug else "", tuple(index.get(slug, [])), "unique-local-logo-alias")
```

- [ ] **Step 4: Add a regression proving the Steve Jobs-style case is resolved only because the logo index explicitly contains the person alias**

Use a temporary logo index with `apple.com: ["Apple", "Steve Jobs", "apple.com"]`; do not infer Apple from the word "company" or from generic knowledge.

- [ ] **Step 5: Run tests**

```bash
python -m unittest -v tests/test_bulk_visual_identity.py tests/test_runtime_relevance.py
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/bulk_visual_identity.py tests/test_bulk_visual_identity.py
git commit -m "feat: resolve local story logos fail closed"
```

---

### Task 3: Add structured logo discovery for stories with no local logo

**Files:**
- Modify: `tools/bulk_visual_identity.py`
- Modify: `tests/test_bulk_visual_identity.py`

**Interfaces:**
- Consumes: canonical entity aliases from story metadata/approved photo tags, Wikidata search API, Wikidata entity JSON (`P154` logo image and `P856` official website).
- Produces: `discover_verified_logo_identity(story, opener=urllib.request.urlopen) -> DiscoveredLogo | None` where `DiscoveredLogo` includes `entity_label`, `domain`, `commons_filename`, `source_url`, and `aliases`.

- [ ] **Step 1: Write mocked Wikidata tests**

```python
def test_wikidata_logo_requires_exact_entity_label_and_official_site(self):
    # Fixture search result label is exactly "Apple Inc." and P856 is apple.com.
    # P154 is Apple_logo_black.svg. Expected: accepted DiscoveredLogo.
    ...

def test_wikidata_logo_rejects_search_result_with_only_partial_label(self):
    # Story term "Amazon" must not accept "Amazon rainforest".
    ...

def test_wikidata_logo_rejects_entity_without_p154_or_p856(self):
    ...
```

The test fixtures must be literal dictionaries in the test file; no network access in unit tests.

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m unittest -v tests/test_bulk_visual_identity.py
```

- [ ] **Step 3: Implement Wikidata lookup with exact normalized label/alias matching**

Use:

```python
WIKIDATA_SEARCH = "https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&limit=8&search={query}"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
COMMONS_FILE = "https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
```

Rules implemented in code:

```python
# Accept only when one QID has an exact normalized match against a canonical
# entity term from story metadata or approved-photo tags.
# Require P154 and P856 on that same QID.
# Parse hostname from P856; reject non-http(s), blank, or hostname-less values.
# The logo file is retrieved from Commons via P154, preserving the QID and
# Commons filename as provenance.
```

Do not use loose title keywords as entity terms. Person-only aliases may not be converted directly into an organization logo; they remain for the next deterministic relation step.

- [ ] **Step 4: Add person-to-organization relation resolution only when unique and corroborated**

For a canonical person QID, inspect structured organization relations in this order:

1. `P108` employer from the person item;
2. organizations returned by a Wikidata SPARQL query where `wdt:P112` (founded by) points to the person;
3. organizations returned where `wdt:P169` (chief executive officer) points to the person.

Keep an organization only when its label/aliases intersect the tags of the story's already-approved photos or an explicit story entity alias. If exactly one corroborated organization remains and it has `P154` + `P856`, accept it; otherwise return `None`.

- [ ] **Step 5: Add a downloader that saves the verified P154 asset as `<domain>-current.png` and validates it with Pillow / `image_precheck.guard_render()` before registration**

SVG P154 files must be rasterized through the project's existing SVG/image path if available; otherwise reject the candidate rather than adding a new rendering dependency in this task.

- [ ] **Step 6: Run tests**

```bash
python -m unittest -v tests/test_bulk_visual_identity.py
python image_precheck.py --selftest
```

- [ ] **Step 7: Commit**

```bash
git add tools/bulk_visual_identity.py tests/test_bulk_visual_identity.py
git commit -m "feat: discover verified story logos from Wikidata"
```

---

### Task 4: Model story beats and structured photo candidates

**Files:**
- Create: `tools/bulk_visual_sources.py`
- Create: `tests/test_bulk_visual_sources.py`

**Interfaces:**
- Produces:
  - `StoryBeat(key: str, queries: tuple[str, ...], required_identity: tuple[str, ...])`
  - `SourceCandidate(source, source_page, direct_url, title, description, creator, license, license_url, width, height, beat_key, matched_on)`
  - `plan_story_beats(story) -> list[StoryBeat]`
  - discovery adapters returning `list[SourceCandidate]` without downloading into `images/`.

- [ ] **Step 1: Write beat planner tests**

```python
# tests/test_bulk_visual_sources.py
import unittest
from tools.bulk_visual_sources import plan_story_beats


class StoryBeatPlannerTests(unittest.TestCase):
    def test_person_story_starts_with_exact_person_identity(self):
        beats = plan_story_beats("Jack Bogle: أنشأ صندوق المؤشرات ورفض أن يصبح ملياردير")
        self.assertEqual(beats[0].key, "person")
        self.assertIn("Jack Bogle", beats[0].required_identity)

    def test_beats_are_distinct_keys(self):
        beats = plan_story_beats("قصة NVIDIA: من رقائق الألعاب إلى أغلى شركة في العالم")
        self.assertEqual(len({b.key for b in beats}), len(beats))
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m unittest -v tests/test_bulk_visual_sources.py
```

- [ ] **Step 3: Implement data classes and deterministic beat planning**

Beat order:

```python
# person story
person -> early_work -> product_or_company -> legacy

# company/entity story
origin -> early_operation -> turning_point -> modern_result

# place/history/topic story
origin_or_early -> subject_detail -> turning_point -> modern_or_legacy
```

Queries must be assembled from exact canonical aliases and beat terms; never from generic words such as `business`, `office`, `city`, `meeting`, or `street` alone.

- [ ] **Step 4: Add structured discovery adapters**

Implement `discover_commons()`, `discover_loc()`, and `discover_openverse()` as metadata-returning adapters. Each adapter must:

- request only a bounded number of results per query;
- retain source page/direct URL, title/description, creator, explicit license fields when available, dimensions, and stable source ID;
- filter `news_bot.BLOCKED_IMAGE_TERMS`, `BLOCKED_AR_TERMS`, `NOT_A_PHOTOGRAPH_TERMS`, and obvious artwork/document metadata before returning candidates;
- never write directly to `images/`.

- [ ] **Step 5: Add first-party discovery only for a verified official domain**

`discover_first_party(beat, domain)` may inspect the verified official site's pages/assets, but every returned candidate must have a direct image URL under the same registrable domain or a first-party CDN referenced by that page, plus the page URL as provenance. If page-to-asset provenance cannot be established, return no candidate.

- [ ] **Step 6: Run source tests with mocked HTTP fixtures**

```bash
python -m unittest -v tests/test_bulk_visual_sources.py
```
Expected: PASS with zero real network calls.

- [ ] **Step 7: Commit**

```bash
git add tools/bulk_visual_sources.py tests/test_bulk_visual_sources.py
git commit -m "feat: add structured story visual source discovery"
```

---

### Task 5: Validate every candidate before it can count

**Files:**
- Create: `tools/bulk_visual_validate.py`
- Create: `tests/test_bulk_visual_validate.py`

**Interfaces:**
- Consumes: `SourceCandidate`, story, existing approved photo paths.
- Produces: `ValidationResult(accepted: bool, verdict: str, reason: str, temp_path: Path | None, sha256: str, dhash: int | None)`.
- Main function: `validate_candidate(story, candidate, existing_paths, temp_dir, relevance_fn) -> ValidationResult`.

- [ ] **Step 1: Write tests for decode, dimensions, graphics, exact duplicates, perceptual duplicates, person identity, and relevance verdicts**

```python
class BulkVisualValidationTests(unittest.TestCase):
    def test_wrong_entity_never_accepts(self): ...
    def test_weak_generic_never_accepts(self): ...
    def test_exact_duplicate_never_accepts(self): ...
    def test_perceptual_duplicate_never_accepts(self): ...
    def test_person_candidate_requires_name_in_trusted_source_metadata(self): ...
    def test_direct_candidate_accepts_only_after_local_decode(self): ...
```

Use temporary generated images; no external network calls.

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m unittest -v tests/test_bulk_visual_validate.py
```

- [ ] **Step 3: Implement local download and physical image checks**

Validation order must be exactly:

```python
1. download to a temporary file;
2. Pillow decode + RGB conversion;
3. minimum size >= 300x250;
4. `image_precheck.guard_render()` must not identify a flat/solid/bar graphic;
5. SHA-256 duplicate rejection;
6. dHash duplicate rejection using `image_precheck.DHASH_MAX_DISTANCE`;
7. exact-person metadata proof when the beat is a person beat;
8. relevance classification;
9. accept only DIRECT or STRONG_CONTEXT.
```

- [ ] **Step 4: Implement fail-closed relevance classification**

Reuse the existing vision/relevance machinery rather than inventing a looser classifier. The adapter supplied as `relevance_fn` must return one of the four runtime verdict strings. Production wiring may call the existing image-vision gate/model with the exact story, beat, candidate title/description, and local image. Any exception, timeout, malformed response, or unknown verdict returns an unaccepted `EXTERNAL_API_ERROR`/`VALIDATION_ERROR`; it never defaults to `DIRECT`.

- [ ] **Step 5: Implement person identity proof from metadata, not face recognition**

For a person beat, require the canonical person name or an explicit canonical alias in a trusted source's title/description/structured depicts metadata. If only a generic company/event caption is present, the candidate may be considered for a non-person contextual beat but must not satisfy the person beat.

- [ ] **Step 6: Run tests and precheck self-test**

```bash
python -m unittest -v tests/test_bulk_visual_validate.py tests/test_runtime_relevance.py
python image_precheck.py --selftest
```

- [ ] **Step 7: Commit**

```bash
git add tools/bulk_visual_validate.py tests/test_bulk_visual_validate.py
git commit -m "feat: validate bulk story visual candidates fail closed"
```

---

### Task 6: Register accepted assets atomically and idempotently

**Files:**
- Create: `tools/bulk_visual_register.py`
- Create: `tests/test_bulk_visual_register.py`

**Interfaces:**
- Produces:
  - `register_photo(story, candidate, result, images_dir, index_path, ledger_path) -> Path`
  - `register_logo(story, discovered_logo, logos_dir, logo_index_path, stories_path) -> Path`
  - `merge_relevance_entry(doc, filename, story, verdict, source_url, note="") -> dict`.

- [ ] **Step 1: Write ledger-preservation and idempotency tests**

```python
class BulkVisualRegistrationTests(unittest.TestCase):
    def test_register_photo_preserves_existing_bogle_entry(self): ...
    def test_register_photo_does_not_duplicate_images_txt_line(self): ...
    def test_register_photo_same_source_is_idempotent(self): ...
    def test_register_logo_does_not_duplicate_alias(self): ...
    def test_register_logo_adds_verified_logo_domain_once(self): ...
```

The Bogle preservation fixture must include a non-`rt-*` `DIRECT` row and `edison-stock-ticker.jpg: WEAK_GENERIC`, then verify both survive an unrelated registration.

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m unittest -v tests/test_bulk_visual_register.py
```

- [ ] **Step 3: Implement deterministic filenames and atomic file moves**

Photo names:

```python
bulk-<story-slug>-<beat-key>-<source-id-short>.jpg
```

Rules:

- normalize to JPEG only after validation;
- source candidate stable ID or SHA contributes to filename so reruns resolve to the same path;
- write to a sibling `.tmp` path, `fsync`, then `Path.replace()`;
- never replace an existing different file under the same deterministic name.

- [ ] **Step 4: Implement additive `images/images.txt` + ledger updates**

Index line format stays:

```text
filename.jpg | tag1, tag2 | credit/source description
```

Ledger entry:

```json
{
  "stories": {"<exact story>": "DIRECT"},
  "source_url": "https://...",
  "note": "source/license/beat metadata"
}
```

Merge with the existing document in place; never reconstruct the full non-`rt-*` ledger from scratch.

- [ ] **Step 5: Implement verified logo registration**

Save under `images/logos/<domain>-current.png`, merge exact entity/person aliases into `images/logos/index.json`, and add `logo:<domain>` to the story metadata only when the domain came from the verified identity resolver. If the story already has a different declared `logo:` domain, fail closed and report `LOGO_IDENTITY_CONFLICT` rather than overwrite it.

- [ ] **Step 6: Run tests**

```bash
python -m unittest -v tests/test_bulk_visual_register.py tests/test_apply_repair_assets.py
```

- [ ] **Step 7: Commit**

```bash
git add tools/bulk_visual_register.py tests/test_bulk_visual_register.py
git commit -m "feat: register repaired story visuals idempotently"
```

---

### Task 7: Build the resumable bulk repair orchestrator

**Files:**
- Create: `tools/bulk_visual_repair.py`
- Create: `tests/test_bulk_visual_repair.py`

**Interfaces:**
- Consumes all interfaces from Tasks 1–6.
- CLI:

```text
python tools/bulk_visual_repair.py --batch-stories 15 --max-candidates-per-beat 12
python tools/bulk_visual_repair.py --board-only
python tools/bulk_visual_repair.py --story "<exact story>"
```

- Produces:
  - `out/bulk-visual-repair/board.json`
  - `out/bulk-visual-repair/board.csv`
  - `out/bulk-visual-repair/attempts.jsonl`
  - `out/bulk-visual-repair/unresolved.json`
  - exit code 0 when work completed safely, exit code 2 on no-safe-progress with unresolved stories, exit code 3 on invariant violation.

- [ ] **Step 1: Write orchestrator tests with fake source/validator/register functions**

```python
class BulkVisualRepairTests(unittest.TestCase):
    def test_one_story_failure_does_not_abort_next_story(self): ...
    def test_pass_story_is_skipped(self): ...
    def test_logo_only_story_is_repaired_before_photo_gap(self): ...
    def test_rerun_after_partial_progress_does_not_repeat_registered_candidate(self): ...
    def test_zero_progress_with_failures_returns_no_progress_status(self): ...
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m unittest -v tests/test_bulk_visual_repair.py
```

- [ ] **Step 3: Implement the deterministic repair loop**

Core control flow:

```python
board = build_board()
backlog = repair_backlog(board)
processed = 0
progress = 0

for row in backlog:
    if processed >= args.batch_stories:
        break
    if row.need_logo:
        progress += repair_logo(row.story)
    fresh = row_for_story(build_board(), row.story)
    if fresh.need_photos:
        progress += repair_photos(fresh.story, fresh.need_photos)
    processed += 1
    write_board(build_board())

final = build_board()
write_unresolved(final, attempts)
if all(r.status == "PASS" for r in final):
    return 0
if progress == 0:
    return 2
return 0
```

A story/source exception must be caught, written as one attempt record, and processing must continue to the next story. Invariant exceptions such as a registered candidate disappearing from runtime coverage must terminate with exit code 3.

- [ ] **Step 4: Implement candidate exhaustion and beat diversity**

For each photo deficit, iterate planned beats that are not already represented by accepted filename metadata. Stop searching a beat after `--max-candidates-per-beat`; accept the first strictly valid candidate, rebuild runtime coverage, then continue only if the deficit remains. Do not add extra files after the runtime story reaches 4 approved photos.

- [ ] **Step 5: Implement attempt records with explicit failure codes**

Each JSONL row must include:

```json
{
  "story": "...",
  "kind": "photo|logo",
  "beat": "origin",
  "source": "commons",
  "source_page": "https://...",
  "candidate": "...",
  "result": "ACCEPTED|SOURCE_UNAVAILABLE|NO_SAFE_CANDIDATE|IDENTITY_UNPROVEN|DUPLICATE_ONLY|LOGO_IDENTITY_MISSING|VALIDATION_ERROR|EXTERNAL_API_ERROR",
  "reason": "..."
}
```

- [ ] **Step 6: Run the full unit suite**

```bash
python -m unittest -v \
  tests/test_bulk_visual_board.py \
  tests/test_bulk_visual_identity.py \
  tests/test_bulk_visual_sources.py \
  tests/test_bulk_visual_validate.py \
  tests/test_bulk_visual_register.py \
  tests/test_bulk_visual_repair.py \
  tests/test_runtime_relevance.py \
  tests/test_apply_repair_assets.py
```

- [ ] **Step 7: Commit**

```bash
git add tools/bulk_visual_repair.py tests/test_bulk_visual_repair.py
git commit -m "feat: orchestrate strict bulk story visual repair"
```

---

### Task 8: Add GitHub Actions batch execution and safe checkpoint commits

**Files:**
- Create: `.github/workflows/bulk-visual-repair.yml`
- Modify: `.github/workflows/runtime-relevance-tests.yml`

**Interfaces:**
- Workflow inputs: `batch_stories` default `15`, `max_candidates_per_beat` default `12`.
- Secrets: reuse existing Anthropic/source credentials already available to Story workflow where needed; no posting credentials are used.

- [ ] **Step 1: Add the workflow**

```yaml
name: Bulk visual repair

on:
  workflow_dispatch:
    inputs:
      batch_stories:
        description: Stories to process in this batch
        required: false
        default: "15"
      max_candidates_per_beat:
        description: Candidate cap for each story beat
        required: false
        default: "12"

permissions:
  contents: write

jobs:
  repair:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.ref_name }}
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - name: Unit tests before writes
        run: python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py
      - name: Strict bulk repair
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          set +e
          PYTHONPATH=. python tools/bulk_visual_repair.py \
            --batch-stories "${{ inputs.batch_stories }}" \
            --max-candidates-per-beat "${{ inputs.max_candidates_per_beat }}"
          rc=$?
          echo "repair_exit=$rc" >> "$GITHUB_ENV"
          if [ "$rc" -eq 3 ]; then exit "$rc"; fi
      - name: Verify runtime after writes
        run: |
          python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py
          PYTHONPATH=. python tools/build_runtime_review.py
      - name: Commit validated repair progress
        shell: bash
        run: |
          if git diff --quiet -- images stories.txt; then
            echo "No validated repair changes"
          else
            git config user.name "story-visual-repair-bot"
            git config user.email "actions@github.com"
            git add images stories.txt
            git commit -m "assets: bulk repair story visual coverage"
            git pull --rebase origin "${GITHUB_REF_NAME}"
            git push origin HEAD:"${GITHUB_REF_NAME}"
          fi
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: bulk-visual-repair-${{ github.run_id }}
          path: |
            out/bulk-visual-repair/**
            out/runtime-review/**
          retention-days: 7
      - name: Mark unresolved no-progress run
        if: env.repair_exit == '2'
        run: exit 2
```

- [ ] **Step 2: Expand runtime-relevance CI path filters and tests**

Add `tools/bulk_visual_*.py`, `tests/test_bulk_visual_*.py`, `images/logos/**`, and `stories.txt` to path filters. Add a board invariant step that imports `build_board()` and asserts `len(board) == 123` and that every row claiming `PASS` has `need_photos == 0` and `need_logo is False`.

- [ ] **Step 3: Compile all new modules**

```bash
python -m py_compile tools/bulk_visual_board.py tools/bulk_visual_identity.py tools/bulk_visual_sources.py tools/bulk_visual_validate.py tools/bulk_visual_register.py tools/bulk_visual_repair.py
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/bulk-visual-repair.yml .github/workflows/runtime-relevance-tests.yml
git commit -m "ci: run strict bulk story visual repair"
```

---

### Task 9: Run the bulk repair until the authoritative board is 123/123 PASS

**Files:**
- Modify through the pipeline only: `images/**`, `stories.txt` when verified logo metadata is added.
- No hand-editing of verdicts merely to improve the count.

**Interfaces:**
- Consumes: Tasks 1–8 production pipeline.
- Produces: fresh authoritative 123/123 board and unresolved count 0.

- [ ] **Step 1: Record the pre-run baseline**

```bash
PYTHONPATH=. python tools/bulk_visual_repair.py --board-only
```
Record exact PASS count and status distribution from `out/bulk-visual-repair/board.json`.

- [ ] **Step 2: Execute bounded repair batches**

Run `bulk-visual-repair.yml` repeatedly or execute the same CLI locally in an isolated worktree. After each successful batch, inspect the board delta: PASS count must stay flat or rise; no previously PASS story may regress.

- [ ] **Step 3: Treat no-progress as a source-adapter bug/backlog, not permission to lower standards**

When exit code 2 occurs, group `unresolved.json` by failure code and add only the narrow source/identity capability required for that class. Each new capability gets a RED→GREEN test in the relevant module before rerunning the batch.

- [ ] **Step 4: Run the final completion assertion**

```bash
python - <<'PY'
from tools.bulk_visual_board import build_board

board = build_board()
assert len(board) == 123, len(board)
failed = [r for r in board if r.status != "PASS"]
assert not failed, [(r.story, r.status) for r in failed]
for row in board:
    assert len(row.photos) >= 4, (row.story, row.photos)
    assert len(row.logos) >= 1, (row.story, row.logos)
print("123/123 PASS")
PY
```

- [ ] **Step 5: Run all relevance/dedupe regression tests**

```bash
python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py
python image_precheck.py --selftest
PYTHONPATH=. python tools/build_runtime_review.py
```

- [ ] **Step 6: Commit final asset state**

```bash
git add images stories.txt
git commit -m "assets: complete 123 story runtime visual coverage"
```

---

### Task 10: Verify renderer consumption on a representative sample and finish PR #2

**Files:**
- Modify production code only if a sampled render exposes a renderer-contract regression.
- Modify/add tests before any such renderer fix.

**Interfaces:**
- Consumes: 123/123 runtime PASS state and existing `story_runtime._enforce_approved_photo_contract()`.
- Produces: representative six-frame artifacts showing 4 visible relevant photos + relevant logo, plus final PR evidence.

- [ ] **Step 1: Select a deterministic five-story sample**

Choose one story from each class after the board is 123/123:

1. technology/company;
2. biography/person;
3. Saudi company/person;
4. historical/abstract topic;
5. place/travel.

Jack Bogle remains in the biography sample unless another person story exercises a stricter identity edge case.

- [ ] **Step 2: Dry-run the five stories through `story_runtime.py`**

For each run, confirm logs contain `runtime photo contract: 4 approved photos will appear in the rendered deck` and a local logo selection.

- [ ] **Step 3: Inspect the six-frame artifacts**

For each sampled deck verify visually:

- at least four frames visibly contain actual photographs;
- the photographs are distinct and relevant;
- the person frame, when present, depicts the correct named person by source provenance;
- at least one relevant local logo/official mark is visibly present;
- no quote card, chart, logo, or flat graphic is being counted as one of the four photos.

- [ ] **Step 4: If a new renderer bug appears, add a focused regression first**

Use `tests/test_runtime_relevance.py` for frame-slot contract logic or a new focused renderer test when the defect is raster/layout-specific. Do not patch a sampled story with a one-off exception when the defect is a general renderer rule.

- [ ] **Step 5: Final verification before completion claim**

Run:

```bash
python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py
python image_precheck.py --selftest
PYTHONPATH=. python tools/build_runtime_review.py
```

Confirm the final runtime review summary says `Stories: 123` and `PASS: 123`.

- [ ] **Step 6: Update PR #2 evidence and only then mark it ready for merge**

Record the final board artifact/run IDs, representative render run IDs, and any source-adapter limitations encountered. Do not merge while the board is below 123/123 or a sampled deck violates the visible-photo requirement.
