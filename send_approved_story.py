#!/usr/bin/env python3
"""Send a human-approved frozen Story artifact to Telegram without rerendering."""

from __future__ import annotations

import argparse
from pathlib import Path

import ready_story_publish as rsp


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    sent = rsp.deliver_approved_review(args.manifest)
    if not sent:
        raise SystemExit("approved Story was not sent (duplicate or notification blocked)")
    print(f"APPROVED_STORY_SENT: {args.manifest}")


if __name__ == "__main__":
    main()
