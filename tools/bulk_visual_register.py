"""Add validated bulk-repair assets without replacing curated metadata."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from PIL import Image


class RegistrationInvariantError(RuntimeError):
    """Raised when an existing deterministic asset has different content."""


class LogoIdentityConflict(RegistrationInvariantError):
    """Raised when verified logo metadata contradicts an existing declaration."""


def _atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _atomic_text(path, text):
    _atomic_bytes(path, text.encode("utf-8"))


def _slug(value, fallback="story"):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return value[:64] or fallback


def deterministic_photo_name(story, candidate, content_sha=""):
    """Return a stable name; source identity, not discovery order, is the key."""
    source_id = str(getattr(candidate, "source_id", "") or "")
    stable = source_id or str(getattr(candidate, "direct_url", "") or "") or str(content_sha)
    if not stable:
        raise RegistrationInvariantError("candidate has no stable source or content identity")
    suffix = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:12]
    beat = _slug(getattr(candidate, "beat_key", "photo"), "photo")
    return f"bulk-{_slug(story)}-{beat}-{suffix}.jpg"


def merge_relevance_entry(doc, filename, story, verdict, source_url, note=""):
    """Add one exact-story review while retaining every unrelated ledger field."""
    assets = doc.setdefault("assets", {})
    entry = assets.setdefault(filename, {})
    entry.setdefault("stories", {})[story] = verdict
    if source_url:
        entry["source_url"] = source_url
    if note:
        entry["note"] = note
    return doc


def append_index_line(path, filename, tags, credit):
    """Append an image-library row once, keyed by its exact filename column."""
    path = Path(path)
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if any(line.split("|", 1)[0].strip() == filename for line in current.splitlines()
           if line.strip() and not line.lstrip().startswith("#")):
        return False
    line = f"{filename} | {', '.join(dict.fromkeys(map(str, tags)))}"
    if credit:
        line += f" | {credit}"
    updated = current + ("" if not current or current.endswith("\n") else "\n") + line + "\n"
    _atomic_text(path, updated)
    return True


def merge_logo_aliases(index, slug, aliases):
    existing = index.setdefault(slug, [])
    seen = {str(alias).casefold() for alias in existing}
    for alias in aliases:
        alias = str(alias).strip()
        if alias and alias.casefold() not in seen:
            existing.append(alias)
            seen.add(alias.casefold())
    return index


def add_logo_domain_to_story_text(text, story, domain):
    """Add a verified domain only to the unique exact story record."""
    domain = str(domain).strip().casefold()
    matches = []
    lines = text.splitlines(keepends=True)
    for number, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            continue
        title = line.rstrip("\r\n").split("|", 1)[0].strip()
        if title == story:
            matches.append(number)
    if len(matches) != 1:
        raise RegistrationInvariantError(f"expected one exact story line, found {len(matches)}")
    number = matches[0]
    ending = "\n" if lines[number].endswith("\n") else ""
    body = lines[number].rstrip("\r\n")
    domains = re.findall(r"(?:^|[,|]\s*)logo:([^,|\s]+)", body, flags=re.I)
    if domains:
        if {item.casefold() for item in domains} != {domain}:
            raise LogoIdentityConflict(f"existing logo domain conflicts with {domain}")
        return text
    separator = ", " if "|" in body else " | "
    lines[number] = f"{body}{separator}logo:{domain}{ending}"
    return "".join(lines)


def _install_file(source, destination, *, image_format=None):
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if image_format:
        with Image.open(source) as image:
            fd, tmp = tempfile.mkstemp(suffix=".png", dir=destination.parent)
            os.close(fd)
            try:
                image.convert("RGBA").save(tmp, image_format)
                data = Path(tmp).read_bytes()
            finally:
                Path(tmp).unlink(missing_ok=True)
    else:
        data = source.read_bytes()
    if destination.exists():
        if destination.read_bytes() != data:
            raise RegistrationInvariantError(f"refusing to overwrite {destination}")
    else:
        _atomic_bytes(destination, data)
    return destination


def _snapshot(paths):
    return {Path(path): (Path(path).read_bytes() if Path(path).exists() else None)
            for path in paths}


def _rollback(snapshot):
    """Restore a transaction without using patchable public write helpers."""
    for path, data in snapshot.items():
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.rollback.", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)


def _assert_provenance_compatible(doc, filename, story, verdict, source_url, note):
    entry = doc.get("assets", {}).get(filename)
    if not entry:
        return
    existing_verdict = entry.get("stories", {}).get(story)
    conflicts = (
        existing_verdict not in (None, verdict),
        bool(entry.get("source_url") and source_url and entry["source_url"] != source_url),
        bool(entry.get("note") and note and entry["note"] != note),
    )
    if any(conflicts):
        raise RegistrationInvariantError(f"conflicting provenance for {filename}")


def register_photo(story, candidate, validation, *, image_dir="images",
                   index_path="images/images.txt", ledger_path="images/relevance.json"):
    if not getattr(validation, "accepted", False) or not getattr(validation, "temp_path", None):
        raise RegistrationInvariantError("only an accepted local validation may be registered")
    if getattr(validation, "verdict", "") not in {"DIRECT", "STRONG_CONTEXT"}:
        raise RegistrationInvariantError("registered photo verdict must be runtime-countable")
    source_bytes = Path(validation.temp_path).read_bytes()
    content_sha = getattr(validation, "sha256", "") or hashlib.sha256(source_bytes).hexdigest()
    filename = deterministic_photo_name(story, candidate, content_sha)
    destination = Path(image_dir) / filename
    credit = " / ".join(filter(None, (getattr(candidate, "creator", ""), getattr(candidate, "license", ""))))
    ledger = Path(ledger_path)
    doc = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"version": 2, "assets": {}}
    note = "; ".join(filter(None, (getattr(candidate, "source", ""), getattr(candidate, "license", ""),
                                     getattr(candidate, "beat_key", ""))))
    source_url = getattr(candidate, "source_page", "")
    _assert_provenance_compatible(doc, filename, story, validation.verdict, source_url, note)
    merge_relevance_entry(doc, filename, story, validation.verdict, source_url, note)
    snapshot = _snapshot((destination, index_path, ledger))
    try:
        _install_file(validation.temp_path, destination)
        append_index_line(index_path, filename, [story, *getattr(candidate, "required_identity", ())], credit)
        _atomic_text(ledger, json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    except Exception:
        _rollback(snapshot)
        raise
    return destination


def register_logo(source_path, story, domain, aliases=(), *, logos_dir="images/logos",
                  index_path="images/logos/index.json", stories_path="stories.txt"):
    """Register a raster logo for an already verified exact domain association."""
    domain = str(domain).strip().casefold()
    if not domain or "/" in domain or "\\" in domain:
        raise RegistrationInvariantError("invalid verified logo domain")
    # Check the exact-story identity invariant before creating any asset or
    # metadata file; a conflict must leave the registration set untouched.
    stories_file = Path(stories_path)
    original_stories = stories_file.read_text(encoding="utf-8")
    updated_stories = add_logo_domain_to_story_text(original_stories, story, domain)
    index_file = Path(index_path)
    index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else {}
    merge_logo_aliases(index, domain, [*aliases, story, domain])
    destination = Path(logos_dir) / f"{domain}-current.png"
    snapshot = _snapshot((destination, index_file, stories_file))
    try:
        _install_file(source_path, destination, image_format="PNG")
        _atomic_text(index_file, json.dumps(index, ensure_ascii=False, indent=2) + "\n")
        if updated_stories != original_stories:
            _atomic_text(stories_file, updated_stories)
    except Exception:
        _rollback(snapshot)
        raise
    return destination
