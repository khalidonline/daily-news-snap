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

import io
import contextlib
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from story_bot import (
        load_stories, story_aliases, story_pool, story_logo_domain,
        person_name, find_portrait, _logo_slug, LOGOS_DIR, OUT_DIR,
    )
    from logo_fetch import _article_logo_files
    from news_bot import _commons_search, commit_and_push
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


def check_line(line):
    entry = {"pool": story_pool(line), "at": datetime.now().isoformat()}
    anchors = []

    name = person_name(line)
    if name:
        entry["person"] = name
        found = None
        with contextlib.redirect_stdout(io.StringIO()):
            for cand in [name] + story_aliases(line):
                try:
                    if find_portrait(cand, OUT_DIR / "preflight.jpg"):
                        found = cand
                        break
                except Exception:
                    pass
        if found:
            anchors.append(f"portrait:{found}")

    if _curated_logo_exists(line):
        anchors.append("logo:curated")
    else:
        domain = story_logo_domain(line)
        if domain:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    pairs = []
                    for nm in story_aliases(line)[:2] or [line.split("|")[0]]:
                        pairs = _article_logo_files(nm, require_domain=domain)
                        if pairs:
                            break
                if pairs:
                    anchors.append(f"logo:fetchable:{domain}")
            except Exception:
                pass

    errors = 0
    if not anchors and not _subject_terms(line):
        # A concept/question line with no proper-noun subject cannot be
        # probed offline — any generic token matches SOMETHING on Commons
        # and proves nothing (the first attempt passed everything on
        # anchors like «العالم»). Its illustrability is a RUNTIME
        # property: the model's era/place keywords, archival neutrals and
        # the typographic floor. Pass by POLICY, labelled as such; the
        # runtime skip-and-flag still catches the truly bare ones.
        anchors.append("typographic:policy")
    if not anchors:
        # the archive probe is last: it is the slowest and the weakest.
        # A network error is NOT a verdict — a long run gets throttled,
        # and marking a line uncovered because Commons timed out would
        # bench a perfectly illustrable story.
        import time
        for term in _subject_terms(line):
            for attempt in (1, 2):
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        hits = list(_commons_search(term, limit=3))
                    break
                except Exception:
                    errors += 1
                    time.sleep(2 if attempt == 1 else 0)
                    hits = None
            if hits:
                anchors.append(f"archive:{term}")
                break
        time.sleep(0.4)                      # politeness between lines

    entry["anchors"] = anchors
    if anchors:
        entry["pass"] = True
    elif errors:
        entry["error"] = True                # unknown, never gates selection
    else:
        entry["pass"] = False
    return entry


def load_coverage():
    try:
        return json.loads(COVERAGE_FILE.read_text("utf-8"))
    except Exception:
        return {"entries": {}}


def main():
    only_pool = sys.argv[1].strip().lower() if len(sys.argv) > 1 else ""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stories = load_stories()
    if only_pool:
        stories = [s for s in stories if story_pool(s) == only_pool]
    cov = load_coverage()
    fails = []
    for i, line in enumerate(stories, 1):
        entry = check_line(line)
        cov["entries"][line] = entry
        mark = ("ok  " if entry.get("pass") else
                "?err" if entry.get("error") else "FAIL")
        print(f"[{i}/{len(stories)}] {mark} {line[:56]}"
              f"  {entry['anchors'][:1] or ''}")
        if entry.get("pass") is False:
            fails.append(line)
    cov["checked_at"] = datetime.now().isoformat()
    COVERAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COVERAGE_FILE.write_text(json.dumps(cov, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    print(f"\n{len(stories) - len(fails)} pass, {len(fails)} fail")
    if fails:
        print("curation worklist (add logo:domain, curate a file, or retire):")
        for line in fails:
            print(f"  - {line}")
    commit_and_push(COVERAGE_FILE, "story coverage preflight")


if __name__ == "__main__":
    main()
