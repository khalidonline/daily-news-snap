"""Fixed offline-only Cloud Run smoke entry point."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from . import evaluate


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        print(json.dumps({"status": "unexpected_arguments"}))
        return 2
    with tempfile.TemporaryDirectory(prefix="publishing-v2-offline-") as directory:
        report = evaluate.run("offline", Path(directory), env={})
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0 if report.get("status") == "offline_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
