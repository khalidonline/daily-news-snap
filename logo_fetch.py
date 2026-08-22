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


def _article_logo_files(name):
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
            for im in page.get("images", []) or []:
                t = im.get("title", "")
                if not ("logo" in t.lower() or "شعار" in t):
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


def fetch_current(slug, names):
    """The subject's current logo, from its own article's infobox files.

    Commons renders SVG sources to PNG at thumburl, so no rasterising
    dependency is needed — always prefer thumburl over the original url.
    """
    review = []
    for name in names:
        pairs = _article_logo_files(name)
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
            print(f"  saved {dest}  <- {page['title']}  "
                  f"({_commons_meta(info, 'LicenseShortName') or 'no licence tag'})")
            return dest
        # Not on Commons: the normal case for a trademarked company logo,
        # hosted locally on the wiki as non-free. Using one on a card is an
        # editorial and licence decision the OWNER takes, so it goes to
        # review like the historical candidates — never into the folder
        # unseen. The rename is the approval.
        review.extend(pairs)

    if review:
        import tempfile as _tf
        tmp = Path(_tf.mkdtemp(prefix=f"logo-current-{slug}-"))
        got = []
        for lang, title in review[:3]:
            link = _local_file_url(lang, title)
            if not link:
                continue
            dest = tmp / title.split(":", 1)[1].replace("/", "_")
            try:
                _download(link, dest)
                got.append(str(dest))
                print(f"  candidate (non-free, {lang}.wikipedia): {title}")
            except Exception as exc:
                print(f"  ! download failed for {title}: {exc}")
        if got:
            notify_album(
                f"الشعار الحالي لـ {slug} غير متاح بترخيص حر — للمراجعة. "
                f"الموافقة = إعادة تسميته إلى images/logos/{slug}-current.png",
                got)
            print(f"  sent {len(got)} current-logo candidate(s) to Telegram "
                  f"(files kept in {tmp})")
            return None
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
