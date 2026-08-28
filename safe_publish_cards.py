#!/usr/bin/env python3
"""Safety wrapper for reviewed-card publishing.

Bundle/Snapchat Public Profile publishing supports one media item per Story
post. Our live tests showed that neither multiple Bundle image posts nor one
video produces the requested six separate photo snaps. Refuse that unsupported
live operation instead of silently publishing the wrong shape.
"""

import publish_cards as publisher


def guard_bundle_multiframe(provider, frames, dry_run=False):
    frames = list(frames or [])
    if provider == "bundle" and not dry_run and len(frames) > 1:
        raise SystemExit(
            f"Bundle cannot publish {len(frames)} separate Snapchat Story photos "
            "reliably. Live publishing is blocked to prevent another one-item "
            "Story. Use DRY_RUN=1 for preview, or a publishing path that can "
            "prove separate Story snaps."
        )


def main():
    selector = publisher.resolve_story_selector(publisher.STAMP)
    _stamp, frames = publisher.find_story(selector)
    if not frames:
        raise SystemExit(f"no story cards found in {publisher.CARDS_DIR}/")
    guard_bundle_multiframe(publisher.POST_PROVIDER, frames, publisher.DRY_RUN)
    publisher.main()


if __name__ == "__main__":
    main()
