"""Fail-closed validation for bulk visual-repair photo candidates."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from PIL import Image

import image_precheck
from runtime_relevance import COUNTABLE


_PERSON_STORY_BEATS = frozenset({"person", "early_work", "product_or_company", "legacy"})


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    verdict: str
    reason: str
    temp_path: Path | None
    sha256: str
    dhash: int | None


def _result(reason, *, verdict="", path=None, sha="", dhash=None, accepted=False):
    return ValidationResult(accepted, verdict, reason, path, sha, dhash)


def _fold(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def _identity_proven(candidate):
    """Require a declared identity in source metadata, before model review.

    Search queries and visual-model guesses are deliberately excluded: neither
    independently establishes what a downloaded image depicts.
    """
    metadata = "\n".join((candidate.title, candidate.description, *candidate.depicts))
    folded = _fold(metadata)
    return any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", folded)
               for identity in candidate.required_identity
               if (alias := _fold(identity)))


def _reject(path, reason, *, verdict="", sha="", dhash=None):
    path.unlink(missing_ok=True)
    return _result(reason, verdict=verdict, sha=sha, dhash=dhash)


def _photo_surface_error(path):
    """Reject obvious low-palette marks/diagrams from the archive photo slot.

    This is intentionally a narrow negative classifier, not evidence of
    relevance. Unreadable/indeterminate input fails closed in the caller.
    Continuous-tone photos exceed the bounded palette query, while simple
    logo-like rasters return their small exact colour set.
    """
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        colours = rgb.getcolors(maxcolors=32)
    if colours is not None:
        return f"flat graphic/logo-like image ({len(colours)} colours)"
    return ""


def _relevance_verdict(relevance_fn, story, candidate, path):
    """Normalize a reviewer response; every malformed/error response fails closed."""
    try:
        response = relevance_fn(story, candidate, path)
    except Exception as exc:  # External reviewers are allowed to be unavailable.
        return "", f"EXTERNAL_API_ERROR: {exc.__class__.__name__}"
    if isinstance(response, str):
        verdict = response.strip().upper()
    elif isinstance(response, dict):
        verdict = str(response.get("verdict", "")).strip().upper()
        # Structured production reviews must affirm that their source evidence
        # is sufficient. This does not apply to the small string test adapter.
        if response.get("source_metadata_sufficient") is not True:
            return verdict, "VALIDATION_ERROR: source metadata not sufficient"
    else:
        return "", "VALIDATION_ERROR: malformed relevance response"
    if verdict not in COUNTABLE | {"WEAK_GENERIC", "WRONG_ENTITY"}:
        return verdict, "VALIDATION_ERROR: unknown relevance verdict"
    return verdict, ""


def validate_candidate(story, candidate, existing_paths, temp_dir,
                       relevance_fn, download_fn):
    """Validate in the mandated download/decode/guard/dedupe/identity order."""
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(prefix="bulk-candidate-", suffix=".img", dir=temp_dir)
    os.close(fd)
    path = Path(raw_path)
    sha = ""
    dhash = None
    try:
        # 1. Materialize before trusting any declared dimensions or metadata.
        download_fn(candidate, path)

        # 2. A full load catches truncated files; conversion proves RGB decode.
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            image.convert("RGB").load()

        # 3. Renderer usability dimensions.
        if width < 300 or height < 250:
            return _reject(path, f"VALIDATION_ERROR: image too small ({width}x{height})")

        # 4. Render sanity applies even though this is an archive/photo slot.
        precheck = image_precheck.Candidate(
            path=str(path),
            caption=" ".join((candidate.title, candidate.description)),
            slot="archive",
            matched_on=candidate.matched_on,
            archive_id=candidate.source_id,
        )
        render_error = image_precheck.guard_render(precheck)
        if render_error:
            return _reject(path, f"VALIDATION_ERROR: {render_error}")
        surface_error = _photo_surface_error(path)
        if surface_error:
            return _reject(path, f"VALIDATION_ERROR: {surface_error}")

        # 5. Exact byte identity.
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        for existing in map(Path, existing_paths):
            if existing.is_file() and image_precheck.sha256(existing) == sha:
                return _reject(path, "DUPLICATE_ONLY: exact duplicate", sha=sha)

        # 6. Perceptual identity, using the runtime precheck threshold.
        dhash = image_precheck.dhash(path)
        if dhash is None:
            return _reject(path, "VALIDATION_ERROR: perceptual hash unavailable", sha=sha)
        for existing in map(Path, existing_paths):
            other = image_precheck.dhash(existing) if existing.is_file() else None
            if other is not None and (dhash ^ other).bit_count() <= image_precheck.DHASH_MAX_DISTANCE:
                return _reject(path, "DUPLICATE_ONLY: perceptual duplicate", sha=sha, dhash=dhash)

        # 7. Identity/context comes only from explicit source metadata for
        # every story class. The model may veto, never manufacture, evidence.
        if not _identity_proven(candidate):
            subject = "exact person identity" if candidate.beat_key in _PERSON_STORY_BEATS else "required identity/context"
            return _reject(path, f"IDENTITY_UNPROVEN: {subject} absent from source metadata",
                           sha=sha, dhash=dhash)

        # 8–9. The reviewer can veto evidence, but cannot replace it.
        verdict, error = _relevance_verdict(relevance_fn, story, candidate, path)
        if error:
            return _reject(path, error, verdict=verdict, sha=sha, dhash=dhash)
        if verdict not in COUNTABLE:
            return _reject(path, f"relevance rejected candidate as {verdict}", verdict=verdict,
                           sha=sha, dhash=dhash)
        return _result("accepted", accepted=True, verdict=verdict, path=path,
                       sha=sha, dhash=dhash)
    except Exception as exc:
        return _reject(path, f"VALIDATION_ERROR: {exc.__class__.__name__}: {exc}",
                       sha=sha, dhash=dhash)
