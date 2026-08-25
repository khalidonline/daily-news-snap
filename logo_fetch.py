#!/usr/bin/env python3
"""
جلب شعار — يملأ مجلد images/logos/ لقصص البوت. يُشغَّل يدوياً فقط.

    python logo_fetch.py aramco "أرامكو" "Aramco"

الخطوة 1: الشعار الحالي من مقالة الجهة نفسها في ويكيبيديا (المقالة موثّقة
بالعنوان — الطريق الوحيد المأمون عبر المقالات). يُحفظ باسم <slug>-current.png.

الخطوة 2: مرشحات تاريخية من بحث Commons — تُنزَّل إلى مجلد مؤقت وتُرسل إلى
تيليجرام بعنوان "للمراجعة"، ولا يدخل أي منها المجلد بنفسه: إعادة التسمية
اليدوية إلى images/logos/<slug>-<سنة>.png هي الموافقة. وسم الحقبة لا يمكن
التحقق منه آلياً، والوسم الخاطئ هو نفس صنف أخطاء «الكيان الغلط» الذي بُني
هذا الأنبوب لإصلاحه.
"""

import json
import sys
import tempfile
import urllib.request
from pathlib import Path

try:
    from news_bot import (
        PUBLIC_API_UA, _wiki_get, _latin_word_re, _arabic_word_re,
        _commons_fileinfo, _commons_search, _commons_meta,
        _commons_licence_ok, notify, notify_album, WIKI_LANGS,
    )
except ImportError as exc:
    raise SystemExit(f"news_bot.py is missing something logo_fetch needs ({exc})")

LOGOS_DIR = Path("images/logos")


def _download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": PUBLIC_API_UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        Path(dest).write_bytes(resp.read())


def _page_references_domain(lang, page, domain):
    """Does the article's external-link set carry the declared domain?

    The domain is the company's identity per the stories.txt `logo:` field;
    an article that never links it is some other entity with a similar
    name, and its infobox file must not be taken.
    """
    try:
        data = _wiki_get(f"https://{lang}.wikipedia.org/w/api.php", {
            "action": "query", "format": "json",
            "pageids": str(page.get("pageid", "")),
            "prop": "extlinks", "ellimit": "200",
        }, label=f"{lang}.wikipedia extlinks")
        for pg in (data.get("query") or {}).get("pages", {}).values():
            for el in pg.get("extlinks", []) or []:
                if domain in str(el.get("*", "")).lower():
                    return True
    except Exception as exc:
        print(f"  ! extlinks check failed ({exc}) — treating as no match")
    return False


def _article_logo_files(name, require_domain=None):
    """File: titles containing logo/شعار from the subject's OWN article.

    pageimages was the first attempt and returned the article's lead PHOTO —
    Aramco's headquarters from the air, saved as if it were the logo. The
    infobox logo is just another file on the page, so list the page's files
    and keep the ones whose names say logo. The article must still be
    title-verified: every word of the query in the title, whole words.
    """
    out = []
    for lang in WIKI_LANGS:
        data = _wiki_get(f"https://{lang}.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": name, "gsrnamespace": "0", "gsrlimit": "3",
            "redirects": "1", "prop": "images", "imlimit": "50",
        }, label=f"{lang}.wikipedia")
        pages = list((data.get("query") or {}).get("pages", {}).values())
        pages.sort(key=lambda p: (p.get("title", "").strip().lower()
                                  != name.strip().lower()))
        import re as _re
        wanted = [w for w in _re.split(r"\W+", name.lower()) if len(w) > 2]
        checks = [(_latin_word_re([w]) if w.isascii() else _arabic_word_re([w]))
                  for w in wanted]
        for page in pages:
            title = (page.get("title") or "").lower()
            if not checks or not all(rx.search(title) for rx in checks):
                continue
            if require_domain and not _page_references_domain(
                    lang, page, require_domain):
                print(f"  ! {page.get('title')}: article does not reference "
                      f"{require_domain} — wrong entity, skipping")
                continue
            for im in page.get("images", []) or []:
                t = im.get("title", "")
                if not ("logo" in t.lower() or "شعار" in t):
                    continue
                # this fetch caches the CURRENT mark: a file the article
                # labels as a historical logo (Samsung first logo.svg)
                # must never become <slug>-current.png — era marks stay
                # manual, era matching is mandatory
                if _re.search(r"\b(first|old|former|original|19\d\d|"
                              r"20[01]\d)\b", t.lower()):
                    continue
                # The file title must carry the subject's name too — every
                # article's file list includes Commons-logo.svg and friends,
                # wiki furniture that says "logo" and belongs to nobody.
                # Same title-verification principle as portraits.
                if not any(rx.search(t.lower()) for rx in checks):
                    continue
                out.append((lang, t))
    return list(dict.fromkeys(out))


def _local_file_url(lang, title):
    """Direct URL of a file hosted on that wiki itself (not Commons)."""
    data = _wiki_get(f"https://{lang}.wikipedia.org/w/api.php", {
        "action": "query", "format": "json", "titles": title,
        "prop": "imageinfo", "iiprop": "url", "iiurlwidth": "1200",
    }, label=f"{lang}.wikipedia file")
    for page in (data.get("query") or {}).get("pages", {}).values():
        for info in page.get("imageinfo", []) or []:
            return info.get("thumburl") or info.get("url")
    return None


def wikidata_entity_files(names, domain=None):
    """Subject-bound Commons files straight from the Wikidata ENTITY:
    P18 (image) and P154 (logo). String search matched a Sufi painting
    and a Polish river to SAMA and the founder's son to Jameel; the
    entity's own claims cannot. Verification: P856 host equality when a
    domain is declared, exact label/alias match otherwise — a homonym
    that merely ranks high never qualifies. Returns [(prop, filename)]."""
    from urllib.parse import urlparse

    def _host(u):
        return (urlparse(str(u)).hostname or "").lower()

    wanted = {str(n).casefold() for n in names if n}
    for name in [n for n in names if n][:2]:
        se = _wiki_get("https://www.wikidata.org/w/api.php",
                       {"action": "wbsearchentities", "format": "json",
                        "language": "en", "type": "item",
                        "search": name, "limit": "5"},
                       label="wikidata") or {}
        ids = [c.get("id") for c in se.get("search", []) if c.get("id")]
        if not ids:
            continue
        ent = _wiki_get("https://www.wikidata.org/w/api.php",
                        {"action": "wbgetentities", "format": "json",
                         "ids": "|".join(ids),
                         "props": "claims|labels|aliases"},
                        label="wikidata") or {}
        entities = ent.get("entities", {})
        for qid in ids:
            e = entities.get(qid, {})
            claims = e.get("claims", {})
            if domain:
                sites = [c.get("mainsnak", {}).get("datavalue", {})
                          .get("value", "") for c in claims.get("P856", [])]
                ok = any(_host(u) == domain or _host(u) == "www." + domain
                         or _host(u).endswith("." + domain) for u in sites)
            else:
                labels = {v.get("value", "").casefold()
                          for v in e.get("labels", {}).values()}
                labels |= {a.get("value", "").casefold()
                           for al in e.get("aliases", {}).values()
                           for a in al}
                # single-word aliases are the homonym class: 'SAMA'
                # label-matched the Asturian town of Sama. Without a
                # domain to verify against, only a multi-word alias may
                # claim an entity by label.
                ok = bool(labels & {w for w in wanted
                                    if len(w.split()) >= 2})
            if not ok:
                continue
            out = []
            for prop in ("P18", "P154"):
                for c in claims.get(prop, []):
                    if "P582" in (c.get("qualifiers") or {}):
                        continue
                    v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                    if v:
                        out.append((prop, str(v)))
                        break
            return out
    return []


def wikidata_p154_logo(names, domain):
    """Probe: the subject's Wikidata logo (P154), the entity verified by
    its official website (P856) HOST equalling the declared domain —
    substring matching would verify Samsung Galaxy (P856
    samsung.com/global/galaxy/) as readily as Samsung Electronics, so
    candidates are walked in wbsearchentities ranked order and the
    first host-verified one wins. Statements with an end date (P582,
    how Wikidata marks superseded logos) are passed over. Probe-only:
    returns the Commons filename or None, downloads nothing."""
    from urllib.parse import urlparse

    def _host(u):
        return (urlparse(str(u)).hostname or "").lower()

    for name in [n for n in names if n][:2]:
        se = _wiki_get("https://www.wikidata.org/w/api.php",
                       {"action": "wbsearchentities", "format": "json",
                        "language": "en", "type": "item",
                        "search": name, "limit": "5"},
                       label="wikidata") or {}
        ids = [c.get("id") for c in se.get("search", []) if c.get("id")]
        if not ids:
            continue
        ent = _wiki_get("https://www.wikidata.org/w/api.php",
                        {"action": "wbgetentities", "format": "json",
                         "ids": "|".join(ids), "props": "claims"},
                        label="wikidata") or {}
        entities = ent.get("entities", {})
        for qid in ids:
            claims = entities.get(qid, {}).get("claims", {})
            sites = [c.get("mainsnak", {}).get("datavalue", {})
                      .get("value", "") for c in claims.get("P856", [])]
            if not any(_host(u) == domain or _host(u) == "www." + domain
                       or _host(u).endswith("." + domain) for u in sites):
                continue
            for c in claims.get("P154", []):
                if "P582" in (c.get("qualifiers") or {}):
                    continue
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if v:
                    return str(v)
            return None
    return None


def _renders_as_a_mark(path):
    """The black-bar class: a mark that rasterizes to a flat block or a
    bar is not a logo anyone can read on the cream card (Lucid, Tokyo)."""
    try:
        import image_precheck as ipc
        why = ipc.guard_render(ipc.Candidate(path=str(path), caption="",
                                             slot="logo"))
    except Exception:
        return True
    if why:
        print(f"  ! fetched mark rejected: {why}")
        try:
            Path(path).unlink()
        except OSError:
            pass
        return False
    return True


def fetch_current(slug, names, require_domain=None):
    """The subject's current logo, from its own article's infobox files.

    Commons renders SVG sources to PNG at thumburl, so no rasterising
    dependency is needed — always prefer thumburl over the original url.
    """
    review = []
    for name in names:
        pairs = _article_logo_files(name, require_domain=require_domain)
        # prefer the file whose title is closest to '<name> logo': the
        # Samsung article lists 'Samsung Galaxy logo.svg' before its own
        # wordmark, and a sub-brand's mark is not the company's
        pairs.sort(key=lambda lt: len(lt[1].split()))
        if not pairs:
            continue
        # Commons-hosted (freely licensed): save automatically.
        commons_titles = ["File:" + t.split(":", 1)[1] for _, t in pairs]
        for page, info in _commons_fileinfo(commons_titles):
            if not _commons_licence_ok(info):
                print(f"  ! {page['title']}: licence unusable — skipping")
                continue
            link = info.get("thumburl") or info.get("url")
            dest = LOGOS_DIR / f"{slug}-current.png"
            _download(link, dest)
            if not _renders_as_a_mark(dest):
                continue
            print(f"  saved {dest}  <- {page['title']}  "
                  f"({_commons_meta(info, 'LicenseShortName') or 'no licence tag'})")
            return dest
        # Not on Commons: the normal case for a trademarked company logo,
        # hosted locally on the wiki as non-free. These used to go to
        # Telegram for review — that refusal was the manual-approval design,
        # and the owner's LOGO_AUTO_CURRENT policy supersedes it: a current
        # logo on a story about its company is ordinary editorial imagery.
        # The title-verification above still stands — the file title must
        # carry the subject's name, the rule that keeps wiki furniture and
        # wrong-entity files out.
        review.extend(pairs)

    for lang, title in review[:3]:
        link = _local_file_url(lang, title)
        if not link:
            continue
        dest = LOGOS_DIR / f"{slug}-current.png"
        try:
            _download(link, dest)
        except Exception as exc:
            print(f"  ! download failed for {title}: {exc}")
            continue
        if not _renders_as_a_mark(dest):
            continue
        print(f"  saved {dest}  <- {title}  (non-free, {lang}.wikipedia)")
        return dest
    print("  ! no usable article logo found for the current logo")
    return None


def fetch_historical_candidates(slug, names):
    """Candidates only — reviewed by a human, never written into the folder."""
    tmp = Path(tempfile.mkdtemp(prefix=f"logos-{slug}-"))
    found = []
    for name in names:
        if len(found) >= 5:
            break
        for decade in ("1930s", "1940s", "1950s", "1960s", "1970s", "old"):
            if len(found) >= 5:
                break
            for page, info in _commons_search(f"{name} logo {decade}", limit=3):
                if len(found) >= 5:
                    break
                if not _commons_licence_ok(info):
                    continue
                link = info.get("thumburl") or info.get("url")
                if not link:
                    continue
                dest = tmp / f"{len(found):02d}-{page['title'][5:60].replace('/', '_')}.png"
                try:
                    _download(link, dest)
                except Exception as exc:
                    print(f"  ! candidate download failed: {exc}")
                    continue
                found.append((dest, page["title"]))
                print(f"  candidate: {page['title']}")
    if not found:
        print("  no historical candidates found")
        return tmp, []
    caption = (f"شعارات تاريخية مرشحة لـ {slug} — للمراجعة. "
               f"الموافقة = إعادة تسمية الملف إلى images/logos/{slug}-<سنة>.png")
    notify_album(caption, [str(p) for p, _ in found])
    print(f"  sent {len(found)} candidate(s) to Telegram for review "
          f"(files kept in {tmp})")
    return tmp, found


def update_index(slug, names):
    index_path = LOGOS_DIR / "index.json"
    try:
        index = json.loads(index_path.read_text("utf-8"))
    except Exception:
        index = {}
    merged = list(dict.fromkeys(index.get(slug, []) + list(names)))
    index[slug] = merged
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    print(f"  index.json: {slug} -> {merged}")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: logo_fetch.py <slug> [name ...]")
    slug = sys.argv[1].strip().lower()
    names = sys.argv[2:] or [slug]
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"1/3 current logo for {slug}...")
    fetch_current(slug, names)
    print("2/3 historical candidates (review required)...")
    fetch_historical_candidates(slug, names)
    print("3/3 index...")
    update_index(slug, names)


if __name__ == "__main__":
    main()
