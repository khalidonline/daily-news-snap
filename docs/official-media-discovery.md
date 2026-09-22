# Official image discovery — 22 September 2026

The Ceer probe could not produce a public image pool because recovery searched
Commons, Flickr and the Met only. The initial Commons results included unrelated
CEER/CEERS names and one automotive logo under an unsupported CC BY-SA license.
This was not evidence that Ceer photographs were unavailable.

The new bounded first-party adapter reads public newsroom links and media album
metadata, with CEER as the first verified profile. It follows at most four news
articles, returns up to 50 unique assets, verifies exact asset hosts and dimensions,
and shares its per-run cache across company/product aliases. Unknown subjects
retain the existing recovery path without additional network calls. The renderer
records discovered official options, while publication eligibility remains separate.

Live validation found 48 images, including 44 in the EXOBOT launch album:
https://ceermotors.com/news/exobot-bold-extraordinary-saudi/

Three original images were downloaded, decoded and visually inspected:

- EXOBOT Sedan Exterior: 4000 × 2233, 738091 bytes.
- EXOBOT Intelligent Cockpit: 4000 × 2250, 880469 bytes.
- EXOBOT SUV Doors Open: 4000 × 2231, 385079 bytes.

No LLM requests were used for this retrieval check. The original files were only
used as temporary inspection material; the repository stores no third-party photos.

CEER's terms require prior written consent for reproduction/distribution:
https://ceermotors.com/terms-of-use/

The album's download controls do not override those terms. These assets remain
permission_required, never falsely labeled public-domain or CC-licensed. A hold
now records images_found_usage_clearance_required and the concrete image options,
instead of reporting no images. This does not establish general web-image coverage
or complete public posting readiness. Additional verified source profiles and a
source-level editorial use grant or licensed supplier remain necessary.

Verification: 313 publishing-v2 tests passed; live discovery and three downloads
passed. Existing design and attribution rendering were not changed.
