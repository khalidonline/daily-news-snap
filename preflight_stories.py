#!/usr/bin/env python3
"""الفحص المسبق — offline illustration coverage for every stories.txt line.

Run by hand (or occasionally) BEFORE stories are picked:

    python preflight_stories.py            # all lines
    python preflight_stories.py saudi      # one pool

For each line it answers, without a research call: could this story be
illustrated? The bar (typographic frames allowed, owner decision): at
least ONE confident visual anchor must exist —
  - person-led  -> a verified portrait (the runtime's own pre-check), or
  - a logo identity (curated file, or a declared `logo:domain.com` whose
    article-infobox file is title+domain verified), or
  - the archive answers for the subject (one Commons probe).
Typographic frames carry the interiors, so one anchor is enough; a line
with NO anchor fails and becomes the curation worklist: add a
`logo:domain.com` field, drop a curated file, or retire the line.

Results land in state/story_coverage.json; choose_story skips entries
recorded there as failing. A line not yet checked is never blocked.
"""

import hashlib
import io
import contextlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from story_bot import (
        load_stories, story_aliases, story_pool, story_logo_domain,
        person_name, find_portrait, _logo_slug, LOGOS_DIR, OUT_DIR,
        _STORY_SUBJECT, _subject_keys, resolve_runtime_visuals,
    )
    from logo_fetch import (_article_logo_files, wikidata_p154_logo,
                            wikidata_entity_files)
    from news_bot import _owner_rejected
    from news_bot import (_commons_search, _image_is_safe, commit_and_push,
                          load_local_images)
    import image_precheck as ipc
except ImportError as exc:
    raise SystemExit(f"a bot module is missing something preflight needs "
                     f"({exc}) — the files move together")

COVERAGE_FILE = Path("state/story_coverage.json")


def _subject_terms(line):
    """The best archive-probe terms for a line: Latin identities first.

    Question-headed lines («من اخترع الفأرة؟ قصة Douglas Engelbart...»)
    carry their findable name mid-line, not in the head — so Latin proper
    tokens are extracted from the WHOLE line, then aliases, then the head.
    """
    import re as _re
    terms = [a for a in story_aliases(line) if a.isascii()]
    latin = _re.findall(r"[A-Z][A-Za-z&.'-]+(?:\s+[A-Z][A-Za-z&.'-]+)*",
                        line.split("|")[0])
    terms += [t for t in latin if len(t) > 3]
    terms += [a for a in story_aliases(line) if not a.isascii()]
    return list(dict.fromkeys(terms))[:3]


def _curated_logo_exists(line):
    """A curated file whose slug/alias EQUALS this line's identity."""
    domain = story_logo_domain(line)
    names = {n.casefold() for n in story_aliases(line)}
    slugs = {_logo_slug(n) for n in story_aliases(line) if _logo_slug(n)}
    try:
        index = json.loads((LOGOS_DIR / "index.json").read_text("utf-8"))
    except Exception:
        index = {}
    for f in LOGOS_DIR.glob("*-current.png"):
        slug = f.stem.rsplit("-", 1)[0]
        if domain and slug == domain:
            return True
        if slug in slugs:
            return True
        if any(a.casefold() in names for a in index.get(slug, [])):
            return True
    return False


AUDIT_TTL_DAYS = int(os.getenv("AUDIT_TTL_DAYS", "").strip() or "30")


def _norm_img_name(name):
    """A filename reduced to its comparable core: the seeded
    willis-carrier-1915.jpg and Commons' 'Willis Carrier 1915.jpg' (and
    its '(cropped)' sibling) are one picture and must count once."""
    stem = str(name).removeprefix("File:").rsplit(".", 1)[0]
    return re.sub(r"[^a-z0-9\u0600-\u06ff]+", "", stem.casefold())
_YEAR_RE = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")


def _identity_hash(line):
    """Changes when the line's identity tail changes — a re-probe trigger."""
    ident = (",".join(story_aliases(line)) + "|"
             + (story_logo_domain(line) or "") + "|"
             + _STORY_SUBJECT.get(str(line).strip(), ""))
    return hashlib.md5(ident.encode()).hexdigest()[:10]


def _story_year(line):
    """The line's own era, when the head names one."""
    years = [int(y) for y in _YEAR_RE.findall(line.split("|")[0])]
    return min(years) if years else None


def _curated_logo_eras(line):
    """Era keys of curated files matching this line's identity."""
    domain = story_logo_domain(line)
    names = {n.casefold() for n in story_aliases(line)}
    slugs = {_logo_slug(n) for n in story_aliases(line) if _logo_slug(n)}
    try:
        index = json.loads((LOGOS_DIR / "index.json").read_text("utf-8"))
    except Exception:
        index = {}
    eras = []
    for f in LOGOS_DIR.glob("*.png"):
        if "-" not in f.stem:
            continue
        slug, era = f.stem.rsplit("-", 1)
        if not (slug == domain or slug in slugs
                or any(a.casefold() in names for a in index.get(slug, []))):
            continue
        eras.append(era)
    return eras


def _classify(entry):
    """Class from RUNTIME-resolvable local files only (owner doctrine:
    a smaller truthful READY beats stories producing blank frames)."""
    photos = entry.get("local_photos", [])
    logos = entry.get("local_logos", [])
    n, has_logo = len(photos), bool(logos)
    need_photos = max(0, 4 - n)
    if need_photos == 0 and has_logo:
        entry["runtime_status"] = "PASS"
    elif need_photos and not has_logo:
        entry["runtime_status"] = f"NEEDS {need_photos} MORE PHOTOS + LOGO"
    elif need_photos:
        entry["runtime_status"] = f"NEEDS {need_photos} MORE PHOTOS"
    else:
        entry["runtime_status"] = "NEEDS LOGO"
    entry.pop("era_gap", None)
    if n == 0 and not has_logo:
        entry["readiness"] = "NOT READY"
    elif need_photos == 0 and has_logo:
        entry["readiness"] = "READY"
    elif n == 0 and has_logo:
        entry["readiness"] = "LOGO-ONLY"
    else:
        entry["readiness"] = "THIN"
    return entry


def _ipc_story(line):
    """The line as an image_precheck Story, for the homonym guard."""
    person = person_name(line)
    return ipc.Story(title=line.split("|")[0].strip(),
                     person_aliases=[person] if person else [],
                     entity_aliases=list(story_aliases(line)))


def check_line(line):
    """The readiness audit for one line — every probe, one entry.

    Counts SUBJECT-BOUND images: a verified portrait, the brand mark
    (curated file / fetchable infobox / Wikidata P154 — one asset class,
    counted once), and archive photos (capped at 2 — beyond two, more
    hits prove popularity, not coverage). READY needs 2+, THIN exactly
    1, NOT READY zero — or a wholly historical story (a year <= 2000 in
    its head) whose only assets are current-era marks: a 2026 logo
    cannot carry a 1951 railway story, so it is not really covered.
    """
    entry = {"pool": story_pool(line), "at": datetime.now().isoformat(),
             "thash": _identity_hash(line)}
    anchors, evidence, images = [], [], 0
    era_ok = 0                     # assets usable on a historical frame
    story_year = _story_year(line)
    historical = story_year is not None and story_year <= 2000
    if historical:
        entry["historical"] = story_year

    # -- portrait (people are era-safe: archives hold period portraits)
    name = person_name(line)
    if name:
        entry["person"] = name
        found = None
        # slot/alias typing (image_precheck rule): on a TYPED line only
        # declared person aliases may fill the portrait slot — the
        # entity alias 'Dallah Al Baraka' once probed as a portrait
        from story_bot import _STORY_PERSONS
        declared = _STORY_PERSONS.get(str(line).strip())
        cands = (declared if declared is not None
                 else [name] + story_aliases(line))
        with contextlib.redirect_stdout(io.StringIO()):
            for cand in cands:
                try:
                    if find_portrait(cand, OUT_DIR / "preflight.jpg"):
                        found = cand
                        break
                except Exception:
                    pass
        if found:
            anchors.append(f"portrait:{found}")
            evidence.append(f"portrait:{found}")
            images += 1
            era_ok += 1

    # -- the owner's seeded library: tag-matched images/ photos are the
    # strongest coverage there is (chosen by hand for this exact beat) —
    # the audit was blind to them, so seeding never moved a class
    lib_terms = {t.casefold() for t in _subject_terms(line)}
    lib_terms |= {a.casefold() for a in story_aliases(line)}
    lib_norms = set()
    for entry_img in load_local_images():
        tags = {t.casefold() for t in entry_img.get("tags", [])}
        if any(t in tag or tag in t for t in lib_terms for tag in tags):
            anchors.append(f"library:{entry_img['path'].name}")
            evidence.append(f"library:{entry_img['path'].name}")
            images += 1
            era_ok += 1
            lib_norms.add(_norm_img_name(entry_img["path"].name))

    def _same_as_seed(title):
        n = _norm_img_name(title)
        return any(n and l and (l in n or n in l) for l in lib_norms)

    # -- the brand mark: one asset class, counted once
    domain = story_logo_domain(line)
    if _curated_logo_exists(line):
        anchors.append("logo:curated")
        images += 1
        eras = _curated_logo_eras(line)
        dated = [int(e) for e in eras if e.isdigit() and len(e) == 4]
        if historical and any(abs(y - story_year) <= 25 for y in dated):
            evidence.append(f"logo:curated:era-matched")
            era_ok += 1
        else:
            evidence.append("logo:curated:current")
    elif domain:
        got = None
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                for nm in story_aliases(line)[:2] or [line.split("|")[0]]:
                    if _article_logo_files(nm, require_domain=domain):
                        got = "logo:fetchable"
                        break
                if not got:
                    p154 = wikidata_p154_logo(
                        [a for a in story_aliases(line) if a.isascii()],
                        domain)
                    if p154:
                        got = f"logo:p154:{p154}"
        except Exception:
            pass
        if got:
            anchors.append(got.split(":", 2)[0] + ":" + got.split(":", 2)[1])
            evidence.append(got + ":current")
            images += 1

    # -- archive photos, evidence-only: errors are never verdicts
    errors = 0
    # the ENTITY's own images first (P18/P154): subject-bound by claim,
    # immune to the acronym collisions that string search served up
    entity_files = []
    latin = [a for a in story_aliases(line) if a.isascii()]
    if latin:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                entity_files = wikidata_entity_files(
                    latin, story_logo_domain(line) or None)
        except Exception:
            entity_files = []
        for prop, fname in entity_files:
            if _owner_rejected(fname) or _same_as_seed(fname):
                continue
            if prop == "P18":
                anchors.append("entity:P18")
                evidence.append(f"entity:P18:{fname[:90]}")
                images += 1
                era_ok += 1
            elif prop == "P154" and "logo" not in " ".join(evidence):
                anchors.append("logo:p154")
                evidence.append(f"logo:p154:{fname[:90]}:current")
                images += 1
    terms = _subject_terms(line)
    if terms:
        import time
        ipc_story = _ipc_story(line)
        # aggregate across both terms, deduped by file title — breaking
        # at the first term with ANY hit kept Souk Al-Manakh THIN while
        # its second alias held the photo that made it READY. The seen
        # set is seeded with the ENTITY's files: one picture, one count
        # (the owner's dedupe-before-counting rule).
        seen_titles = {ipc.normalize(f) for _, f in entity_files}
        for term in terms[:2]:
            hits = None
            for attempt in (1, 2):
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        hits = list(_commons_search(term, limit=3))
                    break
                except Exception:
                    errors += 1
                    time.sleep(2 if attempt == 1 else 0)
            # count only what the RUNTIME would accept: the same
            # title/description safety+document+artwork filters, photos
            # only (a PDF thesis cover titled 'Saudi Arabia: a kingdom
            # in decline' counted as the dates story's coverage; a
            # sufi-manuscript painting counted for SAMA)
            def _countable(h):
                page = h[0] if isinstance(h, tuple) else h
                info = (h[1] if isinstance(h, tuple)
                        else (page.get("imageinfo") or [{}])[0])
                mime = str(info.get("mime") or "")
                if not mime.startswith("image/") or "svg" in mime:
                    return False
                meta = info.get("extmetadata") or {}
                desc = " ".join(str((meta.get(k) or {}).get("value", ""))
                                for k in ("ImageDescription", "ObjectName",
                                          "Categories"))
                with contextlib.redirect_stdout(io.StringIO()):
                    return _image_is_safe(f"{page.get('title', '')} {desc}")
            def _on_subject(h):
                pg = h[0] if isinstance(h, tuple) else h
                cand = ipc.Candidate(path=pg.get("title", ""),
                                     caption=pg.get("title", ""),
                                     slot="archive", matched_on=term)
                why = ipc.guard_homonym(cand, ipc_story)
                if why:
                    print(f"      ✗ {pg.get('title', '')[:50]}: {why}")
                return not why
            fresh_hits = [h for h in (hits or [])
                          if ipc.normalize((h[0] if isinstance(h, tuple)
                                            else h).get("title", ""))
                          not in seen_titles
                          and not _same_as_seed(
                              (h[0] if isinstance(h, tuple) else h)
                              .get("title", ""))
                          and _countable(h) and _on_subject(h)]
            seen_titles.update(
                ipc.normalize((h[0] if isinstance(h, tuple) else h)
                              .get("title", "")) for h in (hits or []))
            if fresh_hits:
                anchors.append(f"archive:{term}")
                evidence.append(f"archive:{term}:{len(fresh_hits)}")
                images += min(len(fresh_hits), 2)
                era_ok += min(len(fresh_hits), 2)
                for h in fresh_hits[:2]:
                    pg = h[0] if isinstance(h, tuple) else h
                    entry.setdefault("files", []).append(
                        pg.get("title", ""))
            if images >= 4:
                break               # enough — spare the archive
        time.sleep(0.4)             # politeness between lines
    elif not anchors:
        # concept line with no probeable subject: illustrability is a
        # RUNTIME property (era keywords, typographic floor) — THIN by
        # policy, neither preferred nor starved
        anchors.append("typographic:policy")
        evidence.append("typographic:policy")

    # -- classification
    entry["images"] = images
    entry["era_ok"] = era_ok
    entry["evidence"] = evidence
    # RUNTIME TRUTH (owner rule after the Bogle false-READY): the class
    # comes from the same resolver the deck generator uses. Probed
    # evidence above remains as LEADS for the repair queue — it never
    # inflates the class again.
    photos, logos = resolve_runtime_visuals(line)
    entry["local_photos"] = [f.name for f in photos]
    entry["local_logos"] = [f.name for f in logos]
    if images > len(photos):
        print(f"      RUNTIME COVERAGE MISMATCH: declared={images}, "
              f"resolvable_distinct_local={len(photos)}")
    _classify(entry)
    entry["anchors"] = anchors
    if anchors:
        entry["pass"] = True
    elif errors:
        entry["error"] = True       # unknown, never gates selection
    else:
        entry["pass"] = False
    return entry


def load_coverage():
    try:
        return json.loads(COVERAGE_FILE.read_text("utf-8"))
    except Exception:
        return {"entries": {}}


def _fix_type(line, e):
    """Which curation move unblocks this entry."""
    ev = " ".join(e.get("evidence", []))
    if e.get("era_gap"):
        return ("curate an ERA-MATCHED logo file "
                "(images/logos/<slug>-<year>.png)")
    if e.get("person") and "portrait:" not in ev:
        return "no portrait found — add archive-name aliases or a licensed file to images/"
    if story_logo_domain(line) and "logo" not in ev:
        return "logo: declared but nothing fetchable — drop a curated file"
    return "seed images/ with a subject photo, or add archive aliases"


def main():
    args = [a for a in sys.argv[1:]]
    force = "--force" in args
    only_pool = next((a for a in args if not a.startswith("-")), "").lower()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stories = load_stories()
    if only_pool:
        stories = [s2 for s2 in stories if story_pool(s2) == only_pool]
    cov = load_coverage()
    cutoff = (datetime.now() - timedelta(days=AUDIT_TTL_DAYS)).isoformat()
    fresh_probes = 0
    for i, line in enumerate(stories, 1):
        prev = cov["entries"].get(line)
        if (not force and prev and prev.get("readiness")
                and prev.get("thash") == _identity_hash(line)
                and prev.get("at", "") >= cutoff):
            entry = prev            # cache hit: identity unchanged, fresh
        else:
            entry = check_line(line)
            fresh_probes += 1
        cov["entries"][line] = entry
        mark = entry.get("readiness", "?ERR")
        print(f"[{i}/{len(stories)}] {mark:<9} {line[:52]}"
              f"  {entry.get('evidence', [])[:2]}")
    # CROSS-SUBJECT DISQUALIFIER (owner rule, pass-2 review): a file
    # offered as a candidate for 3+ UNRELATED subjects is generic by
    # definition — speaker icons, solid rectangles, stock placeholders
    # recurred across McLean, Wilkes and Al-Naimi. Same-subject
    # repetition (the Aramco trio share their subject keys) stays legal.
    title_holders = {}
    for line in stories:
        for t in cov["entries"].get(line, {}).get("files", []):
            if t:
                title_holders.setdefault(t, []).append(line)
    generic = set()
    for t, holders in title_holders.items():
        groups = []
        for ln in holders:
            keys = set(_subject_keys(ln))
            for g in groups:
                if g & keys:
                    g |= keys
                    break
            else:
                groups.append(set(keys))
        if len(groups) >= 3:
            generic.add(t)
    if generic:
        print(f"\n  ! {len(generic)} generic file(s) disqualified "
              "(candidates for 3+ unrelated subjects):")
        for t in sorted(generic):
            print(f"      - {t[:70]}")
        for line in stories:
            e = cov["entries"].get(line, {})
            hit = [t for t in e.get("files", []) if t in generic]
            if not hit:
                continue
            e["images"] = max(0, e.get("images", 0) - len(hit))
            e["era_ok"] = max(0, e.get("era_ok", 0) - len(hit))
            e["files"] = [t for t in e.get("files", []) if t not in generic]
            e.setdefault("evidence", []).append(
                f"generic-disqualified:{len(hit)}")
            _classify(e)
    # entries for lines no longer in the file are left in place — they
    # cost nothing and return if the line does
    cov["checked_at"] = datetime.now().isoformat()
    COVERAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COVERAGE_FILE.write_text(json.dumps(cov, ensure_ascii=False, indent=1),
                             encoding="utf-8")

    buckets = {"READY": [], "LOGO-ONLY": [], "THIN": [], "NOT READY": []}
    for line in stories:
        e = cov["entries"].get(line, {})
        buckets.setdefault(e.get("readiness", "THIN"), []).append(line)
    print(f"\n=== readiness ({len(stories)} entries, "
          f"{fresh_probes} probed fresh) ===")
    for klass in ("READY", "LOGO-ONLY", "THIN", "NOT READY"):
        print(f"\n{klass} — {len(buckets.get(klass, []))}")
        for line in buckets[klass]:
            print(f"  - {line[:64]}")
    work = {}
    for line in buckets["THIN"] + buckets["NOT READY"]:
        e = cov["entries"].get(line, {})
        if "typographic:policy" in " ".join(e.get("evidence", [])):
            continue                # policy lines are not a worklist
        work.setdefault(_fix_type(line, e), []).append(line)
    if work:
        print("\n=== curation worklist, by fix ===")
        for fix, lines in sorted(work.items()):
            print(f"\n{fix} ({len(lines)}):")
            for line in lines:
                print(f"  - {line[:64]}")
    commit_and_push(COVERAGE_FILE, "story readiness audit")


if __name__ == "__main__":
    main()
