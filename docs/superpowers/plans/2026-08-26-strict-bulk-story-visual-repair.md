# Strict Bulk Story Visual Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable strict bulk-repair pipeline that drives all 123 Story Bot stories to the existing runtime requirement of 4 distinct approved local photos plus 1 relevant local logo, without story-by-story manual repair loops and without weakening relevance rules.

**Architecture:** `story_runtime.coverage()` remains the only PASS/FAIL authority. Focused modules own board generation, exact identity/logo resolution, source discovery, candidate validation, asset registration, and orchestration. A PR workflow loops through bounded repair batches, validates and pushes each batch, rebuilds the runtime board after every batch, and terminates only at 123/123 PASS or a fail-closed no-progress report.

**Tech Stack:** Python 3.12, Pillow, `urllib.request`, existing `story_runtime.py`, `story_bot.py`, `news_bot.py`, `runtime_relevance.py`, `image_precheck.py`, Python `unittest`, GitHub Actions, Wikimedia Commons/Wikidata, Library of Congress, Openverse, and exact first-party source pages.

**Spec:** `docs/superpowers/specs/2026-08-26-strict-bulk-story-visual-repair-design.md`

## Global Constraints

- Runtime completion remains 4 distinct relevant usable local photos plus at least 1 relevant local logo per story.
- `story_runtime.coverage()` is authoritative; no repair-specific score may declare PASS.
- Only `DIRECT` and `STRONG_CONTEXT` verdicts count.
- `WEAK_GENERIC`, `WRONG_ENTITY`, and unreviewed `rt-*` assets never count.
- Exact SHA duplicates and perceptual dHash duplicates within `image_precheck.DHASH_MAX_DISTANCE` count once.
- Person identity must be supported by trustworthy source metadata; automated face recognition is not an identity proof.
- First-party assets may be used with source/credit provenance, but must not be described as open-license unless the source says so.
- A source/model/API failure never becomes approval.
- Existing curated non-`rt-*` relevance entries, including the Jack Bogle repair, must survive every run.
- Re-running the pipeline must be idempotent: no duplicate files, index rows, logo aliases, or destructive ledger rewrites.
- A green workflow is not catalogue completion unless a fresh authoritative board reports exactly 123 stories and 123 PASS.
- PR #2 stays draft until the 123/123 completion gate and representative renderer sanity sample pass.

## File Structure

- Create `tools/bulk_visual_board.py` — authoritative coverage rows, backlog ordering, CSV/JSON output.
- Create `tools/bulk_visual_identity.py` — exact story/person/entity terms and fail-closed logo identity resolution.
- Create `tools/bulk_visual_sources.py` — story beat planning and structured candidate discovery.
- Create `tools/bulk_visual_validate.py` — download/decode/photo-vs-graphic/dedupe/identity/relevance validation.
- Create `tools/bulk_visual_register.py` — atomic/idempotent photo, logo, index, ledger, and verified story-metadata writes.
- Create `tools/bulk_visual_repair.py` — resumable batch orchestrator and unresolved reporting.
- Modify `tools/build_runtime_review.py` — reuse the shared board.
- Create `.github/workflows/bulk-visual-repair.yml` — PR-triggered bounded loop plus manual dispatch after the workflow exists on the default branch.
- Modify `.github/workflows/runtime-relevance-tests.yml` — bulk unit tests and catalogue invariants.
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
- Produces: `CoverageRow`, `build_board()`, `repair_backlog()`, `row_for_story()`, `write_board()`.

- [ ] **Step 1: Write the failing board tests**

```python
# tests/test_bulk_visual_board.py
import unittest
from unittest.mock import patch

from tools.bulk_visual_board import build_board, repair_backlog


class BulkVisualBoardTests(unittest.TestCase):
    @patch("tools.bulk_visual_board.sr.coverage")
    def test_board_uses_runtime_coverage(self, coverage):
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
    def test_backlog_orders_smallest_gap_first(self, coverage):
        coverage.side_effect = [
            (["a", "b", "c", "d"], [], "NEEDS LOGO"),
            (["a", "b", "c"], ["logo"], "NEEDS 1 MORE PHOTO"),
            (["a"], [], "NEEDS 3 MORE PHOTOS + LOGO"),
        ]
        rows = build_board(["Logo", "One", "Large"])
        self.assertEqual([row.story for row in repair_backlog(rows)], ["Logo", "One", "Large"])
```

- [ ] **Step 2: Run RED**

```bash
python -m unittest -v tests/test_bulk_visual_board.py
```
Expected: import failure because `tools.bulk_visual_board` does not exist.

- [ ] **Step 3: Implement the board model**

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
            photos=tuple(Path(path).name for path in photos),
            logos=tuple(Path(path).name for path in logos),
            need_photos=max(0, 4 - len(photos)),
            need_logo=not bool(logos),
            status=status,
        ))
    return rows


def repair_backlog(rows):
    failing = [row for row in rows if row.status != "PASS"]
    return sorted(failing, key=lambda row: (
        row.need_photos + int(row.need_logo),
        row.need_photos,
        int(row.need_logo),
        row.story.casefold(),
    ))


def row_for_story(rows, story):
    return next(row for row in rows if row.story == story)


def write_board(rows, out_dir="out/bulk-visual-repair"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "board.json").write_text(
        json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (out / "board.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        fields = ["story", "photo_count", "logo_count", "need_photos", "need_logo", "status", "photos", "logos"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
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

- [ ] **Step 4: Make `tools/build_runtime_review.write_status()` serialize `build_board()` rows**

Keep the existing `status.csv` column names so previous review artifacts remain readable. Do not call a second coverage implementation.

- [ ] **Step 5: Run GREEN and review generation**

```bash
python -m unittest -v tests/test_bulk_visual_board.py tests/test_runtime_relevance.py
PYTHONPATH=. python tools/build_runtime_review.py
```
Expected: tests PASS and runtime review still emits 123 status rows.

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
- Consumes: `story_bot.story_aliases()`, `story_bot.story_logo_domain()`, `story_runtime.approved_runtime_visuals()`, `news_bot.load_local_images()`, `images/logos/index.json`.
- Produces: `LogoIdentity`, `story_identity_terms(story)`, `choose_unique_logo_slug(names, index)`, `resolve_existing_logo_identity(story)`.

- [ ] **Step 1: Write fail-closed local-logo tests**

```python
# tests/test_bulk_visual_identity.py
import unittest
from tools.bulk_visual_identity import choose_unique_logo_slug


class BulkVisualIdentityTests(unittest.TestCase):
    def test_unique_exact_alias_match_is_accepted(self):
        index = {"apple.com": ["Apple", "Steve Jobs", "apple.com"]}
        self.assertEqual(choose_unique_logo_slug({"Steve Jobs"}, index), "apple.com")

    def test_ambiguous_alias_match_fails_closed(self):
        index = {
            "tesla.com": ["Elon Musk"],
            "spacex.com": ["Elon Musk"],
        }
        self.assertIsNone(choose_unique_logo_slug({"Elon Musk"}, index))

    def test_substring_does_not_create_logo_identity(self):
        index = {"snap.com": ["Snap"]}
        self.assertIsNone(choose_unique_logo_slug({"Snapdragon"}, index))

    def test_person_only_match_requires_explicit_index_alias(self):
        index = {"apple.com": ["Apple", "Steve Jobs", "apple.com"]}
        self.assertEqual(choose_unique_logo_slug({"Steve Jobs"}, index), "apple.com")
        index = {"apple.com": ["Apple", "apple.com"]}
        self.assertIsNone(choose_unique_logo_slug({"Steve Jobs"}, index))
```

- [ ] **Step 2: Run RED**

```bash
python -m unittest -v tests/test_bulk_visual_identity.py
```

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
    wanted = {norm(name) for name in names if norm(name)}
    matches = []
    for slug, aliases in index.items():
        hay = {norm(slug), *(norm(alias) for alias in aliases)}
        if wanted & hay:
            matches.append(slug)
    return matches[0] if len(set(matches)) == 1 else None


def story_identity_terms(story):
    terms = set(sb.story_aliases(story))
    terms |= set(sb._STORY_PERSONS.get(str(story).strip()) or [])
    approved, _ = sr.approved_runtime_visuals(story)
    approved_names = {path.name for path in approved}
    for entry in nb.load_local_images():
        if entry["path"].name in approved_names:
            terms |= set(entry.get("tags", []))
    return {term for term in terms if str(term).strip()}


def resolve_existing_logo_identity(story, index_path=LOGO_INDEX):
    domain = sb.story_logo_domain(story)
    if domain and (LOGO_DIR / f"{domain}-current.png").exists():
        return LogoIdentity(domain, domain, (domain,), "declared-domain-local-file")
    try:
        index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    slug = choose_unique_logo_slug(story_identity_terms(story), index)
    if not slug or not list(LOGO_DIR.glob(f"{slug}-*.png")):
        return None
    return LogoIdentity(slug, slug if "." in slug else "", tuple(index.get(slug, [])), "unique-local-logo-alias")
```

- [ ] **Step 4: Run GREEN**

```bash
python -m unittest -v tests/test_bulk_visual_identity.py tests/test_runtime_relevance.py
```

- [ ] **Step 5: Commit**

```bash
git add tools/bulk_visual_identity.py tests/test_bulk_visual_identity.py
git commit -m "feat: resolve local story logos fail closed"
```

---

### Task 3: Discover missing logos from structured identity data

**Files:**
- Modify: `tools/bulk_visual_identity.py`
- Modify: `tests/test_bulk_visual_identity.py`

**Interfaces:**
- Add `DiscoveredLogo(entity_label: str, domain: str, commons_filename: str, source_url: str, aliases: tuple[str, ...])`.
- Add `discover_wikidata_logo_for_terms(terms, json_get) -> DiscoveredLogo | None`.
- Add `discover_verified_logo_identity(story, json_get=_json_get) -> DiscoveredLogo | None`.

- [ ] **Step 1: Write concrete mocked Wikidata tests**

```python
from tools.bulk_visual_identity import discover_wikidata_logo_for_terms


def _apple_json_get(url):
    if "wbsearchentities" in url:
        return {"search": [{"id": "Q312", "label": "Apple Inc.", "aliases": ["Apple"]}]}
    return {
        "entities": {
            "Q312": {
                "labels": {"en": {"value": "Apple Inc."}},
                "aliases": {"en": [{"value": "Apple"}]},
                "claims": {
                    "P154": [{"mainsnak": {"datavalue": {"value": "Apple logo black.svg"}}}],
                    "P856": [{"mainsnak": {"datavalue": {"value": "https://www.apple.com/"}}}],
                },
            }
        }
    }


def test_wikidata_logo_requires_exact_entity_alias(self):
    logo = discover_wikidata_logo_for_terms({"Apple"}, _apple_json_get)
    self.assertEqual(logo.domain, "apple.com")
    self.assertEqual(logo.commons_filename, "Apple logo black.svg")


def test_wikidata_logo_rejects_wrong_sense(self):
    def fake(url):
        if "wbsearchentities" in url:
            return {"search": [{"id": "Q3783", "label": "Amazon River", "aliases": ["Amazon"]}]}
        return {"entities": {}}
    self.assertIsNone(discover_wikidata_logo_for_terms({"Amazon.com"}, fake))


def test_wikidata_logo_requires_both_logo_and_official_site(self):
    def fake(url):
        if "wbsearchentities" in url:
            return {"search": [{"id": "Q1", "label": "Example Corp", "aliases": ["Example Corp"]}]}
        return {"entities": {"Q1": {"claims": {"P154": []}}}}
    self.assertIsNone(discover_wikidata_logo_for_terms({"Example Corp"}, fake))
```

- [ ] **Step 2: Run RED**

```bash
python -m unittest -v tests/test_bulk_visual_identity.py
```

- [ ] **Step 3: Implement exact Wikidata lookup**

```python
WIKIDATA_SEARCH = "https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&limit=8&search={query}"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
```

Acceptance rules: one QID must have a normalized label/alias exactly equal to a canonical entity term; the same QID must expose `P154` and `P856`; normalize the `P856` hostname by stripping only a leading `www.`; preserve the QID and P154 filename as provenance; partial title matches never count.

- [ ] **Step 4: Implement unique person-to-organization relation resolution**

```python
def corroborated_org_qids(person_qid, explicit_entity_terms, approved_photo_tags, entity_get, sparql_get):
    candidates = set(entity_get(person_qid).get("P108", []))
    candidates |= set(sparql_get("P112", person_qid))
    candidates |= set(sparql_get("P169", person_qid))
    wanted = {norm(value) for value in [*explicit_entity_terms, *approved_photo_tags]}
    kept = []
    for qid in candidates:
        entity = entity_get(qid)
        names = {norm(entity["label"]), *(norm(alias) for alias in entity.get("aliases", []))}
        if wanted & names:
            kept.append(qid)
    return kept
```

Production code accepts an organization only when `corroborated_org_qids()` returns exactly one QID and that QID has both P154 and P856.

- [ ] **Step 5: Download P154 through MediaWiki imageinfo**

Use the Commons API with `prop=imageinfo&iiprop=url&iiurlwidth=1024`. Download `thumburl` when present so SVG logos arrive as rasterized thumbnails without a new SVG dependency; otherwise use `url`. Decode with Pillow and run `image_precheck.guard_render(image_precheck.Candidate(path=str(temp), caption=entity_label, slot="logo"))`. Reject any nonempty guard reason.

- [ ] **Step 6: Run GREEN**

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
- `StoryBeat(key: str, queries: tuple[str, ...], required_identity: tuple[str, ...])`.
- `SourceCandidate(source: str, source_id: str, source_page: str, direct_url: str, title: str, description: str, creator: str, license: str, license_url: str, width: int, height: int, beat_key: str, matched_on: str, required_identity: tuple[str, ...], depicts: tuple[str, ...])`.
- `plan_story_beats(story) -> list[StoryBeat]`.
- `discover_commons(beat, limit=12, json_get=_json_get)`, `discover_loc(beat, limit=12, json_get=_json_get)`, `discover_openverse(beat, limit=12, json_get=_json_get)`, and `discover_first_party(beat, domain, limit=12)` return metadata only.

- [ ] **Step 1: Write beat planner tests**

```python
# tests/test_bulk_visual_sources.py
import unittest
from tools.bulk_visual_sources import StoryBeat, discover_commons, plan_story_beats


class StoryBeatPlannerTests(unittest.TestCase):
    def test_person_story_starts_with_exact_person_identity(self):
        beats = plan_story_beats("Jack Bogle: أنشأ صندوق المؤشرات ورفض أن يصبح ملياردير")
        self.assertEqual(beats[0].key, "person")
        self.assertIn("Jack Bogle", beats[0].required_identity)

    def test_company_story_has_four_distinct_beats(self):
        beats = plan_story_beats("قصة NVIDIA: من رقائق الألعاب إلى أغلى شركة في العالم")
        self.assertEqual(
            [beat.key for beat in beats[:4]],
            ["origin", "early_operation", "turning_point", "modern_result"],
        )

    def test_commons_filters_artwork_and_preserves_license(self):
        beat = StoryBeat("person", ("Jack Bogle",), ("Jack Bogle", "John C. Bogle"))
        def fake_json_get(url):
            return {
                "query": {
                    "pages": {
                        "1": {
                            "pageid": 1,
                            "title": "File:John C Bogle 2007.jpg",
                            "imageinfo": [{
                                "url": "https://upload.wikimedia.org/bogle.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:John_C_Bogle_2007.jpg",
                                "width": 594,
                                "height": 792,
                                "extmetadata": {
                                    "ImageDescription": {"value": "John C. Bogle in 2007"},
                                    "Artist": {"value": "Bill Cramer"},
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                },
                            }],
                        },
                        "2": {
                            "pageid": 2,
                            "title": "File:Jack Bogle illustration.svg",
                            "imageinfo": [{
                                "url": "https://upload.wikimedia.org/bogle-art.svg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Jack_Bogle_illustration.svg",
                                "width": 800,
                                "height": 800,
                                "extmetadata": {
                                    "ImageDescription": {"value": "Illustration of Jack Bogle"},
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                },
                            }],
                        },
                    }
                }
            }
        found = discover_commons(beat, json_get=fake_json_get)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].source_id, "commons:1")
        self.assertEqual(found[0].license, "CC BY-SA 4.0")
        self.assertIn("John C. Bogle", found[0].description)
```

- [ ] **Step 2: Run RED**

```bash
python -m unittest -v tests/test_bulk_visual_sources.py
```

- [ ] **Step 3: Implement deterministic beat planning**

Use these orders: person = `person`, `early_work`, `product_or_company`, `legacy`; company/entity = `origin`, `early_operation`, `turning_point`, `modern_result`; place/history/topic = `origin_or_early`, `subject_detail`, `turning_point`, `modern_or_legacy`. Queries combine exact canonical aliases with beat-specific terms and never consist only of generic words such as `business`, `office`, `city`, `meeting`, or `street`.

- [ ] **Step 4: Implement Commons, Library of Congress, and Openverse metadata adapters**

Each adapter returns a bounded list with stable source ID, source page, direct URL, title/description, creator, license metadata when available, dimensions, matched query, required identity, and structured depicts names when the source supplies them. Filter metadata matching `news_bot.BLOCKED_IMAGE_TERMS`, `BLOCKED_AR_TERMS`, `NOT_A_PHOTOGRAPH_TERMS`, or `NOT_A_PHOTOGRAPH_AR` before returning candidates.

- [ ] **Step 5: Implement first-party discovery only for a verified official domain**

`discover_first_party()` may follow image URLs referenced by an official page. Accept page host only when `host == domain` or `host.endswith("." + domain)`. A candidate image may be same-domain or a CDN URL explicitly referenced by that accepted page. Record both page and direct image URLs; a naked CDN URL with no first-party page provenance is rejected.

- [ ] **Step 6: Run GREEN and commit**

```bash
python -m unittest -v tests/test_bulk_visual_sources.py
git add tools/bulk_visual_sources.py tests/test_bulk_visual_sources.py
git commit -m "feat: add structured story visual source discovery"
```

---

### Task 5: Validate every candidate before it can count

**Files:**
- Create: `tools/bulk_visual_validate.py`
- Create: `tests/test_bulk_visual_validate.py`

**Interfaces:**
- `ValidationResult(accepted: bool, verdict: str, reason: str, temp_path: Path | None, sha256: str, dhash: int | None)`.
- `validate_candidate(story, candidate, existing_paths, temp_dir, relevance_fn, download_fn) -> ValidationResult`.

- [ ] **Step 1: Write concrete validation tests**

```python
# tests/test_bulk_visual_validate.py
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from runtime_relevance import DIRECT, WEAK_GENERIC, WRONG_ENTITY
from tools.bulk_visual_sources import SourceCandidate
from tools.bulk_visual_validate import validate_candidate


def make_image(path, fmt="JPEG"):
    image = Image.new("RGB", (640, 480), (230, 230, 230))
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 60, 300, 420), fill=(80, 100, 120))
    draw.ellipse((330, 90, 590, 350), fill=(170, 120, 90))
    image.save(path, fmt)


def candidate(title="Jack Bogle", description="John C. Bogle at Vanguard"):
    return SourceCandidate(
        source="commons",
        source_id="commons:1",
        source_page="https://commons.wikimedia.org/wiki/File:Bogle.jpg",
        direct_url="https://upload.wikimedia.org/bogle.jpg",
        title=title,
        description=description,
        creator="Bill Cramer",
        license="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        width=640,
        height=480,
        beat_key="person",
        matched_on="Jack Bogle",
        required_identity=("Jack Bogle", "John C. Bogle"),
        depicts=("John C. Bogle",),
    )


class BulkVisualValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.download_source = self.root / "download.jpg"
        make_image(self.download_source)
        self.download = lambda cand, dest: shutil.copy2(self.download_source, dest)

    def test_wrong_entity_never_accepts(self):
        result = validate_candidate("Jack Bogle story", candidate(), [], self.root, lambda *args: WRONG_ENTITY, self.download)
        self.assertFalse(result.accepted)
        self.assertEqual(result.verdict, WRONG_ENTITY)

    def test_weak_generic_never_accepts(self):
        result = validate_candidate("Jack Bogle story", candidate(), [], self.root, lambda *args: WEAK_GENERIC, self.download)
        self.assertFalse(result.accepted)

    def test_exact_duplicate_never_accepts(self):
        existing = self.root / "existing.jpg"
        shutil.copy2(self.download_source, existing)
        result = validate_candidate("Jack Bogle story", candidate(), [existing], self.root, lambda *args: DIRECT, self.download)
        self.assertFalse(result.accepted)
        self.assertIn("duplicate", result.reason.lower())

    def test_perceptual_duplicate_never_accepts(self):
        existing = self.root / "existing.png"
        make_image(existing, "PNG")
        result = validate_candidate("Jack Bogle story", candidate(), [existing], self.root, lambda *args: DIRECT, self.download)
        self.assertFalse(result.accepted)
        self.assertIn("duplicate", result.reason.lower())

    def test_person_candidate_requires_source_metadata_identity(self):
        cand = candidate(title="Vanguard office", description="Vanguard headquarters")
        cand = cand.__class__(**{**cand.__dict__, "depicts": tuple()})
        result = validate_candidate("Jack Bogle story", cand, [], self.root, lambda *args: DIRECT, self.download)
        self.assertFalse(result.accepted)
        self.assertIn("identity", result.reason.lower())

    def test_direct_candidate_accepts_after_local_decode(self):
        result = validate_candidate("Jack Bogle story", candidate(), [], self.root, lambda *args: DIRECT, self.download)
        self.assertTrue(result.accepted)
        self.assertEqual(result.verdict, DIRECT)
        self.assertTrue(result.temp_path.exists())
```

- [ ] **Step 2: Run RED**

```bash
python -m unittest -v tests/test_bulk_visual_validate.py
```

- [ ] **Step 3: Implement validation in this exact order**

1. download to a unique temporary file;
2. Pillow decode and RGB conversion;
3. require at least 300x250 pixels;
4. run `image_precheck.guard_render()` on an `image_precheck.Candidate` with `slot="archive"`;
5. reject exact SHA matches;
6. reject dHash matches within `image_precheck.DHASH_MAX_DISTANCE`;
7. for person beats, require a canonical person name/alias in trusted source title, description, or `candidate.depicts`;
8. call the relevance adapter;
9. accept only `DIRECT` or `STRONG_CONTEXT`.

- [ ] **Step 4: Wire fail-closed relevance classification**

The production `relevance_fn` reuses the existing image vision/relevance path with exact story, beat, source metadata, and local image. Unknown verdict, malformed response, exception, timeout, or missing key returns a rejected `EXTERNAL_API_ERROR` or `VALIDATION_ERROR`; it never defaults to `DIRECT`.

- [ ] **Step 5: Run GREEN and precheck self-test**

```bash
python -m unittest -v tests/test_bulk_visual_validate.py tests/test_runtime_relevance.py
python image_precheck.py --selftest
```

- [ ] **Step 6: Commit**

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
- `deterministic_photo_name(story, candidate) -> str`.
- `merge_relevance_entry(doc, filename, story, verdict, source_url, note="") -> dict`.
- `append_index_line(path, filename, tags, credit) -> bool`.
- `merge_logo_aliases(index, slug, aliases) -> dict`.
- `add_logo_domain_to_story_text(text, story, domain) -> str`.
- `register_photo()` and `register_logo()` return the registered `Path`.

- [ ] **Step 1: Write concrete preservation/idempotency tests**

```python
# tests/test_bulk_visual_register.py
import copy
import tempfile
import unittest
from pathlib import Path

from tools.bulk_visual_register import (
    LogoIdentityConflict,
    add_logo_domain_to_story_text,
    append_index_line,
    merge_logo_aliases,
    merge_relevance_entry,
)


class BulkVisualRegistrationTests(unittest.TestCase):
    def test_merge_preserves_bogle_entries(self):
        original = {
            "assets": {
                "bogle-vanguard-1959.jpg": {"stories": {"Jack Bogle": "DIRECT"}},
                "edison-stock-ticker.jpg": {"stories": {"Jack Bogle": "WEAK_GENERIC"}},
            }
        }
        result = merge_relevance_entry(copy.deepcopy(original), "bulk-story-x-origin-abc.jpg", "Story X", "DIRECT", "https://example.com/photo")
        self.assertEqual(result["assets"]["bogle-vanguard-1959.jpg"], original["assets"]["bogle-vanguard-1959.jpg"])
        self.assertEqual(result["assets"]["edison-stock-ticker.jpg"], original["assets"]["edison-stock-ticker.jpg"])

    def test_index_line_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "images.txt"
            self.assertTrue(append_index_line(path, "x.jpg", ["Story X"], "Commons / CC BY 4.0"))
            self.assertFalse(append_index_line(path, "x.jpg", ["Story X"], "Commons / CC BY 4.0"))
            self.assertEqual(path.read_text(encoding="utf-8").count("x.jpg"), 1)

    def test_logo_alias_merge_is_idempotent(self):
        index = {"apple.com": ["Apple"]}
        first = merge_logo_aliases(index, "apple.com", ["Apple", "Steve Jobs"])
        second = merge_logo_aliases(first, "apple.com", ["Steve Jobs"])
        self.assertEqual(second["apple.com"].count("Steve Jobs"), 1)

    def test_verified_logo_domain_is_added_once(self):
        text = "قصة Steve Jobs: الطرد من شركته ثم العودة | Steve Jobs\n"
        once = add_logo_domain_to_story_text(text, "قصة Steve Jobs: الطرد من شركته ثم العودة", "apple.com")
        twice = add_logo_domain_to_story_text(once, "قصة Steve Jobs: الطرد من شركته ثم العودة", "apple.com")
        self.assertEqual(twice.count("logo:apple.com"), 1)

    def test_conflicting_logo_domain_fails_closed(self):
        text = "قصة Tesla | Tesla, logo:tesla.com\n"
        with self.assertRaises(LogoIdentityConflict):
            add_logo_domain_to_story_text(text, "قصة Tesla", "apple.com")
```

- [ ] **Step 2: Run RED**

```bash
python -m unittest -v tests/test_bulk_visual_register.py
```

- [ ] **Step 3: Implement deterministic filenames and atomic writes**

Photo filename format is `bulk-<story-slug>-<beat-key>-<source-id-short>.jpg`. Source stable ID or candidate SHA determines the suffix. Write validated image bytes to a sibling temporary path, flush and `os.fsync()`, then replace atomically. If the deterministic destination already exists with different bytes, raise an invariant error rather than overwrite it.

- [ ] **Step 4: Implement additive index and ledger writes**

A registered photo adds exactly one `images/images.txt` line and merges exactly one exact-story verdict into the existing ledger. The ledger stores `source_url` and a note containing source, license string when present, and beat key. Never rebuild all non-`rt-*` rows.

- [ ] **Step 5: Implement verified logo registration**

Save a validated raster logo as `images/logos/<domain>-current.png`, merge exact aliases into `images/logos/index.json`, and add `logo:<domain>` to the exact story line only when the identity resolver supplied the verified domain. A conflicting existing logo domain raises `LogoIdentityConflict`.

- [ ] **Step 6: Run GREEN and commit**

```bash
python -m unittest -v tests/test_bulk_visual_register.py tests/test_apply_repair_assets.py
git add tools/bulk_visual_register.py tests/test_bulk_visual_register.py
git commit -m "feat: register repaired story visuals idempotently"
```

---

### Task 7: Build the resumable bulk repair orchestrator

**Files:**
- Create: `tools/bulk_visual_repair.py`
- Create: `tests/test_bulk_visual_repair.py`

**Interfaces:**
- CLI: `python tools/bulk_visual_repair.py --batch-stories 15 --max-candidates-per-beat 12`, `--board-only`, and `--story "Jack Bogle: أنشأ صندوق المؤشرات ورفض أن يصبح ملياردير"`.
- Add `BatchResult(progress: int, processed: int, exit_code: int)`.
- Exit codes: `0` = 123/123 complete; `10` = safe progress made and backlog remains; `2` = no safe progress and backlog remains; `3` = invariant violation.
- Output: `out/bulk-visual-repair/board.json`, `board.csv`, `attempts.jsonl`, `unresolved.json`.

- [ ] **Step 1: Write concrete orchestrator tests around a pure row processor**

```python
# tests/test_bulk_visual_repair.py
import unittest
from tools.bulk_visual_board import CoverageRow
from tools.bulk_visual_repair import process_rows


def row(story, need_photos, need_logo, status):
    return CoverageRow(story, tuple(), tuple(), need_photos, need_logo, status)


class BulkVisualRepairTests(unittest.TestCase):
    def test_one_story_failure_does_not_abort_next_story(self):
        calls = []
        def repair_photo(story, deficit):
            calls.append(story)
            if story == "Broken":
                raise RuntimeError("source down")
            return 1
        result = process_rows(
            [row("Broken", 1, False, "NEEDS 1 MORE PHOTO"), row("Good", 1, False, "NEEDS 1 MORE PHOTO")],
            batch_stories=2,
            repair_logo_fn=lambda story: 0,
            repair_photos_fn=repair_photo,
            refresh_fn=lambda story: row(story, 1, False, "NEEDS 1 MORE PHOTO"),
            attempt_fn=lambda record: None,
        )
        self.assertEqual(calls, ["Broken", "Good"])
        self.assertEqual(result.progress, 1)

    def test_pass_story_is_skipped(self):
        called = []
        result = process_rows(
            [row("Done", 0, False, "PASS")],
            1,
            lambda story: called.append(story) or 1,
            lambda story, deficit: called.append(story) or 1,
            lambda story: row(story, 0, False, "PASS"),
            lambda record: None,
        )
        self.assertEqual(called, [])
        self.assertEqual(result.progress, 0)

    def test_logo_runs_before_photo_for_same_story(self):
        calls = []
        process_rows(
            [row("Mixed", 1, True, "NEEDS 1 MORE PHOTO + LOGO")],
            1,
            lambda story: calls.append("logo") or 1,
            lambda story, deficit: calls.append("photo") or 1,
            lambda story: row(story, 1, False, "NEEDS 1 MORE PHOTO"),
            lambda record: None,
        )
        self.assertEqual(calls, ["logo", "photo"])

    def test_zero_progress_returns_no_progress_exit(self):
        result = process_rows(
            [row("Blocked", 1, True, "NEEDS 1 MORE PHOTO + LOGO")],
            1,
            lambda story: 0,
            lambda story, deficit: 0,
            lambda story: row(story, 1, True, "NEEDS 1 MORE PHOTO + LOGO"),
            lambda record: None,
        )
        self.assertEqual(result.exit_code, 2)

    def test_second_run_pass_row_performs_no_writes(self):
        writes = []
        process_rows(
            [row("Already fixed", 0, False, "PASS")],
            1,
            lambda story: writes.append("logo") or 1,
            lambda story, deficit: writes.append("photo") or 1,
            lambda story: row(story, 0, False, "PASS"),
            lambda record: writes.append("attempt"),
        )
        self.assertEqual(writes, [])
```

- [ ] **Step 2: Run RED**

```bash
python -m unittest -v tests/test_bulk_visual_repair.py
```

- [ ] **Step 3: Implement `repair_logo()` and `repair_photos()`**

`repair_logo(story)` first tries `resolve_existing_logo_identity()`, then structured Wikidata discovery, then `register_logo()`. `repair_photos(story, deficit)` iterates unrepresented planned beats and source adapters in source order, validates candidates, registers only accepted candidates, rebuilds runtime coverage after each registration, and stops immediately when the story reaches four approved photos.

- [ ] **Step 4: Implement `process_rows()` and CLI loop**

Catch per-story/source exceptions, append an attempt record, and continue. Rebuild the board after each story. If a newly registered asset is absent from `story_runtime.coverage()` for that exact story, take the invariant path and exit 3.

- [ ] **Step 5: Use explicit attempt records**

```json
{
  "story": "Jack Bogle: أنشأ صندوق المؤشرات ورفض أن يصبح ملياردير",
  "kind": "photo",
  "beat": "legacy",
  "source": "commons",
  "source_page": "https://commons.wikimedia.org/wiki/File:Photo_of_a_John_C._Bogle_By_Bill_Cramer.jpg",
  "candidate": "Photo of a John C. Bogle By Bill Cramer.jpg",
  "result": "ACCEPTED",
  "reason": "DIRECT; identity proved by Commons metadata"
}
```

Allowed failure results are `SOURCE_UNAVAILABLE`, `NO_SAFE_CANDIDATE`, `IDENTITY_UNPROVEN`, `DUPLICATE_ONLY`, `LOGO_IDENTITY_MISSING`, `VALIDATION_ERROR`, and `EXTERNAL_API_ERROR`.

- [ ] **Step 6: Run the full unit suite**

```bash
python -m unittest -v tests/test_bulk_visual_board.py tests/test_bulk_visual_identity.py tests/test_bulk_visual_sources.py tests/test_bulk_visual_validate.py tests/test_bulk_visual_register.py tests/test_bulk_visual_repair.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py
```

- [ ] **Step 7: Commit**

```bash
git add tools/bulk_visual_repair.py tests/test_bulk_visual_repair.py
git commit -m "feat: orchestrate strict bulk story visual repair"
```

---

### Task 8: Add a PR workflow that loops batches without user story-by-story actions

**Files:**
- Create: `.github/workflows/bulk-visual-repair.yml`
- Modify: `.github/workflows/runtime-relevance-tests.yml`

**Interfaces:**
- PR defaults: 15 stories per batch, 12 candidates per beat, 12 batches per job.
- Manual inputs after the workflow is available on the default branch: `batch_stories`, `max_candidates_per_beat`, `max_batches`.

- [ ] **Step 1: Add the workflow with both triggers**

```yaml
name: Bulk visual repair

on:
  pull_request:
    paths:
      - "tools/bulk_visual_*.py"
      - "tests/test_bulk_visual_*.py"
      - "images/**"
      - "stories.txt"
      - ".github/workflows/bulk-visual-repair.yml"
  workflow_dispatch:
    inputs:
      batch_stories:
        required: false
        default: "15"
      max_candidates_per_beat:
        required: false
        default: "12"
      max_batches:
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
          ref: ${{ github.head_ref || github.ref_name }}
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - name: Unit tests before writes
        run: python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py
      - name: Repair in bounded pushed batches
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          BATCH_STORIES: ${{ inputs.batch_stories || '15' }}
          MAX_CANDIDATES: ${{ inputs.max_candidates_per_beat || '12' }}
          MAX_BATCHES: ${{ inputs.max_batches || '12' }}
          TARGET_BRANCH: ${{ github.head_ref || github.ref_name }}
        shell: bash
        run: |
          set -euo pipefail
          for batch in $(seq 1 "$MAX_BATCHES"); do
            set +e
            PYTHONPATH=. python tools/bulk_visual_repair.py \
              --batch-stories "$BATCH_STORIES" \
              --max-candidates-per-beat "$MAX_CANDIDATES"
            rc=$?
            set -e

            python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py
            PYTHONPATH=. python tools/build_runtime_review.py

            if ! git diff --quiet -- images stories.txt; then
              git config user.name "story-visual-repair-bot"
              git config user.email "actions@github.com"
              git add images stories.txt
              git commit -m "assets: bulk repair story visual coverage batch ${batch}"
              git pull --rebase origin "$TARGET_BRANCH"
              git push origin HEAD:"$TARGET_BRANCH"
            fi

            if [ "$rc" -eq 0 ]; then exit 0; fi
            if [ "$rc" -eq 10 ]; then continue; fi
            exit "$rc"
          done
          exit 2
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: bulk-visual-repair-${{ github.run_id }}
          path: |
            out/bulk-visual-repair/**
            out/runtime-review/**
          retention-days: 7
```

- [ ] **Step 2: Expand runtime-relevance CI with an exact board invariant**

```yaml
      - name: Bulk board invariants
        run: |
          PYTHONPATH=. python - <<'PY'
          from tools.bulk_visual_board import build_board
          board = build_board()
          assert len(board) == 123, len(board)
          for row in board:
              if row.status == "PASS":
                  assert row.need_photos == 0, (row.story, row.need_photos)
                  assert row.need_logo is False, (row.story, row.need_logo)
          PY
```

Also add `tools/bulk_visual_*.py`, `tests/test_bulk_visual_*.py`, `images/logos/**`, and `stories.txt` to that workflow's path filters.

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

### Task 9: Execute automatic batches until the authoritative board is 123/123 PASS

**Files:**
- Modify only through pipeline registration: `images/**` and verified `stories.txt` logo metadata.

**Interfaces:**
- Consumes Tasks 1–8.
- Produces a fresh board with 123 rows, 123 PASS, and unresolved count zero.

- [ ] **Step 1: Record the baseline**

```bash
PYTHONPATH=. python tools/bulk_visual_repair.py --board-only
```
Capture the exact status distribution from `out/bulk-visual-repair/board.json`.

- [ ] **Step 2: Let the PR workflow execute bounded batches**

Each batch pushes validated progress before beginning the next batch. PASS count must stay flat or rise; a previously PASS story may not regress.

- [ ] **Step 3: Handle no-progress by improving one narrow source/identity adapter**

When exit code 2 occurs, group `unresolved.json` by failure result. Add only the source/identity capability needed for the dominant unresolved class, with a failing unit test first. Do not mass-approve assets and do not lower thresholds.

- [ ] **Step 4: Run the final completion assertion**

```bash
python - <<'PY'
from tools.bulk_visual_board import build_board

board = build_board()
assert len(board) == 123, len(board)
failed = [row for row in board if row.status != "PASS"]
assert not failed, [(row.story, row.status) for row in failed]
for row in board:
    assert len(row.photos) >= 4, (row.story, row.photos)
    assert len(row.logos) >= 1, (row.story, row.logos)
print("123/123 PASS")
PY
```

- [ ] **Step 5: Run all relevance/dedupe regressions**

```bash
python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py
python image_precheck.py --selftest
PYTHONPATH=. python tools/build_runtime_review.py
```

- [ ] **Step 6: Commit any final local asset state if the workflow did not already push it**

```bash
git add images stories.txt
git commit -m "assets: complete 123 story runtime visual coverage"
```

---

### Task 10: Verify renderer consumption on a representative sample and finish PR #2

**Files:**
- Modify production code only if a sampled render exposes a general renderer-contract bug.
- Add a failing regression before any renderer change.

**Interfaces:**
- Consumes 123/123 runtime PASS and `story_runtime._enforce_approved_photo_contract()`.
- Produces five representative six-frame artifacts that visibly satisfy 4 photos + logo.

- [ ] **Step 1: Select one deterministic sample from each class**

Use one technology/company story, one biography/person story, one Saudi company/person story, one historical/abstract topic, and one place/travel story. Keep Jack Bogle in the biography sample unless another person story exercises a stricter identity edge case.

- [ ] **Step 2: Dry-run the five stories through `story_runtime.py`**

Confirm each log contains `runtime photo contract: 4 approved photos will appear in the rendered deck` plus a local logo selection.

- [ ] **Step 3: Inspect all six frames in each sampled artifact**

Verify at least four frames visibly contain actual photographs; the photos are distinct and relevant; named-person photos have correct source provenance; at least one relevant local logo/official mark is visible; and no quote card, chart, logo, or flat graphic is being counted as a photo.

- [ ] **Step 4: Fix any newly exposed renderer class with RED→GREEN tests**

Use `tests/test_runtime_relevance.py` for slot-contract logic or a new focused renderer test for raster/layout behavior. Do not add a one-story exception for a general renderer defect.

- [ ] **Step 5: Run final verification**

```bash
python -m unittest -v tests/test_bulk_visual_*.py tests/test_runtime_relevance.py tests/test_apply_repair_assets.py
python image_precheck.py --selftest
PYTHONPATH=. python tools/build_runtime_review.py
```

The final runtime review must report `Stories: 123` and `PASS: 123`.

- [ ] **Step 6: Update PR #2 evidence and only then mark it ready for merge**

Record the final board artifact/run ID, the five representative render run IDs, and any remaining source-adapter limitations. Do not merge while the board is below 123/123 or any sampled deck violates the visible-photo requirement.
