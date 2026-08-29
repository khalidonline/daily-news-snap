#!/usr/bin/env python3
"""Compatibility entrypoint for the shared news/photo pipeline.

The implementation lives in news_bot_core.py unchanged. This wrapper installs
the global editorial photo-quality guard before exposing that module, so every
bot that imports news_bot receives the same guarded functions.
"""

import sys
import news_bot_core as _core
from photo_quality_guard import install as _install_photo_quality

_install_photo_quality(_core)

if __name__ == "__main__":
    _core.main()
else:
    # Preserve module identity: callers that assign news_bot.IMAGES_INDEX,
    # OUT_DIR, etc. must mutate the actual core globals used by its functions.
    sys.modules[__name__] = _core
