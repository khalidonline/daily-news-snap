#!/usr/bin/env python3
"""
Daily world-news -> Snapchat Story bot.

Pipeline:
  1. fetch   : pull recent items from world-news RSS feeds
  2. pick    : Claude ranks them and writes a Snapchat-sized summary
  3. render  : each story becomes a 1080x1920 PNG card
  4. post    : cards are uploaded and published as Snapchat Stories

Run with DRY_RUN=1 to do everything except posting (cards land in ./out).
"""

import base64
import json
import os
import re
import sys
import textwrap
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

FEEDS = [
    ("BBC",        "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("NPR",        "https://feeds.npr.org/1004/rss.xml"),
    ("France 24",  "https://www.france24.com/en/rss"),
]

STORIES_PER_DAY = int(os.getenv("STORIES_PER_DAY", "3"))
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "30"))
MAX_HEADLINES_TO_MODEL = 60

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
AYRSHARE_API_KEY = os.getenv("AYRSHARE_API_KEY", "").strip()
DRY_RUN = os.getenv("DRY_RUN", "").strip() not in ("", "0", "false", "False")

OUT_DIR = Path(os.getenv("OUT_DIR", "out"))
W, H = 1080, 1920

# Palette
BG_TOP = (14, 17, 26)
BG_BOTTOM = (28, 34, 52)
ACCENT = (255, 215, 64)
TEXT = (245, 246, 250)
MUTED = (150, 158, 178)

USER_AGENT = "Mozilla/5.0 (compatible; daily-news-bot/1.0)"


# --------------------------------------------------------------------------
# 1. Fetch
# --------------------------------------------------------------------------

def _http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&amp;", "&").replace("&#39;", "'")
                .replace("&quot;", '"').replace("&nbsp;", " ")
                .replace("&lt;", "<").replace("&gt;", ">"))
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(raw):
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fetch_headlines():
    """Return a list of recent {source, title, summary, link} dicts."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items, seen = [], set()

    for source, url in FEEDS:
        try:
            root = ET.fromstring(_http_get(url))
        except Exception as exc:                      # one bad feed shouldn't kill the run
            print(f"  ! {source}: {exc}", file=sys.stderr)
            continue

        # RSS 2.0 <item> and Atom <entry>
        entries = root.iter("item") if root.find(".//item") is not None else \
            root.iter("{http://www.w3.org/2005/Atom}entry")

        count = 0
        for entry in entries:
            def field(*names):
                for n in names:
                    el = entry.find(n)
                    if el is not None:
                        return el.text or el.get("href") or ""
                return ""

            title = _clean(field("title", "{http://www.w3.org/2005/Atom}title"))
            if not title:
                continue

            key = re.sub(r"[^a-z0-9]", "", title.lower())[:60]
            if key in seen:
                continue

            published = _parse_date(field(
                "pubDate", "{http://www.w3.org/2005/Atom}updated",
                "{http://www.w3.org/2005/Atom}published"))
            if published and published < cutoff:
                continue

            seen.add(key)
            items.append({
                "source": source,
                "title": title,
                "summary": _clean(field(
                    "description", "{http://www.w3.org/2005/Atom}summary"))[:400],
                "link": field("link", "{http://www.w3.org/2005/Atom}link"),
            })
            count += 1
        print(f"  {source}: {count} recent items")

    return items


# --------------------------------------------------------------------------
# 2. Pick + summarize
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the editor of a daily world-news Snapchat Story.

You will receive today's headlines. Pick the {n} most globally significant and \
genuinely interesting stories. Prefer hard news with real-world consequence over \
celebrity, sport, opinion, or listicles. Do not pick two stories about the same event.

For each story write:
- headline: max 55 characters, punchy, no clickbait, no trailing period
- summary: 2 short sentences, max 190 characters total, plain language, no jargon
- source: the outlet name given to you
- Never state anything the provided headline and blurb do not support.

Also write one caption: max 120 characters, the text that accompanies the Story post.

Respond with JSON only. No markdown, no backticks, no preamble:
{{"caption": "...", "stories": [{{"headline": "...", "summary": "...", "source": "..."}}]}}"""


def summarize(items):
    if not ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    feed_text = "\n".join(
        f"[{i['source']}] {i['title']} — {i['summary']}"
        for i in items[:MAX_HEADLINES_TO_MODEL]
    )

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1500,
        "system": SYSTEM_PROMPT.format(n=STORIES_PER_DAY),
        "messages": [{"role": "user", "content": f"Today's headlines:\n\n{feed_text}"}],
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())

    text = "".join(b.get("text", "") for b in data.get("content", [])).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


# --------------------------------------------------------------------------
# 3. Render
# --------------------------------------------------------------------------

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-{w}.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-{w}.ttf",
    "/System/Library/Fonts/Supplemental/Arial{w2}.ttf",
]


def load_font(size, bold=False):
    for tpl in FONT_CANDIDATES:
        path = tpl.format(w="Bold" if bold else "", w2=" Bold" if bold else "")
        path = path.replace("DejaVuSans-.ttf", "DejaVuSans.ttf") \
                   .replace("LiberationSans-.ttf", "LiberationSans-Regular.ttf")
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _wrap(draw, text, font, max_width):
    """Greedy word wrap that measures real pixel width."""
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def render_card(story, index, total, out_path):
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)

    # vertical gradient
    for y in range(H):
        t = y / H
        draw.line(
            [(0, y), (W, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
        )

    margin = 90
    max_w = W - 2 * margin

    f_kicker = load_font(38, bold=True)
    f_head = load_font(78, bold=True)
    f_body = load_font(46)
    f_foot = load_font(34)

    # header
    draw.rectangle([margin, 240, margin + 110, 250], fill=ACCENT)
    draw.text((margin, 290), datetime.now().strftime("%A, %d %B").upper(),
              font=f_kicker, fill=ACCENT)
    draw.text((W - margin, 290), f"{index}/{total}", font=f_kicker,
              fill=MUTED, anchor="ra")

    # headline + summary, vertically centred in the safe zone between
    # Snapchat's top profile chrome and the bottom swipe-up area
    head_lines = _wrap(draw, story["headline"], f_head, max_w)
    body_lines = _wrap(draw, story["summary"], f_body, max_w)
    block_h = len(head_lines) * 96 + 50 + len(body_lines) * 66
    y = max(430, (H - block_h) // 2 - 40)

    for line in head_lines:
        draw.text((margin, y), line, font=f_head, fill=TEXT)
        y += 96

    y += 50
    for line in body_lines:
        draw.text((margin, y), line, font=f_body, fill=(214, 219, 232))
        y += 66

    # footer
    draw.line([(margin, H - 250), (W - margin, H - 250)], fill=(60, 68, 92), width=2)
    draw.text((margin, H - 210), story.get("source", "").upper(),
              font=f_foot, fill=ACCENT)
    draw.text((W - margin, H - 210), "DAILY WORLD BRIEF",
              font=f_foot, fill=MUTED, anchor="ra")

    img.save(out_path, "PNG", optimize=True)
    return out_path


# --------------------------------------------------------------------------
# 4. Post
# --------------------------------------------------------------------------

def _ayrshare(path_, payload):
    req = urllib.request.Request(
        f"https://api.ayrshare.com/api/{path_}",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AYRSHARE_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Ayrshare {path_} failed: {exc.code} {exc.read().decode()}")


def upload_media(png_path):
    """Upload a local PNG, return the hosted URL Ayrshare gives back."""
    b64 = base64.b64encode(Path(png_path).read_bytes()).decode()
    res = _ayrshare("media/upload", {
        "file": f"data:image/png;base64,{b64}",
        "fileName": Path(png_path).name,
    })
    url = res.get("url") or res.get("mediaUrl")
    if not url:
        raise SystemExit(f"No media URL in upload response: {res}")
    return url


def post_story(caption, media_urls):
    return _ayrshare("post", {
        "post": caption,
        "platforms": ["snapchat"],
        "mediaUrls": media_urls,
        # omit snapChatOptions -> posts as a Story.
        # For permanent, discoverable posts use video + {"spotlight": true}.
    })


# --------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("1/4 fetching feeds...")
    items = fetch_headlines()
    if len(items) < 5:
        raise SystemExit(f"Only {len(items)} items fetched — aborting rather than posting thin.")
    print(f"    {len(items)} unique recent items")

    print("2/4 summarizing...")
    result = summarize(items)
    stories = result["stories"][:STORIES_PER_DAY]
    caption = result.get("caption", "Today's world brief")
    for s in stories:
        print(f"    • {s['headline']}  ({s.get('source')})")

    print("3/4 rendering cards...")
    stamp = datetime.now().strftime("%Y-%m-%d")
    paths = [
        render_card(s, i + 1, len(stories), OUT_DIR / f"{stamp}-{i + 1}.png")
        for i, s in enumerate(stories)
    ]

    if DRY_RUN:
        print(f"4/4 DRY_RUN — nothing posted. Cards in {OUT_DIR.resolve()}")
        return

    print("4/4 posting to Snapchat...")
    if not AYRSHARE_API_KEY:
        raise SystemExit("AYRSHARE_API_KEY is not set")
    urls = [upload_media(p) for p in paths]
    print("   ", post_story(caption, urls))


if __name__ == "__main__":
    main()
