"""Immutable geometry for the approved Riyadh six-frame Story format."""

FORMAT_ID = "riyadh-story-v1"
CANVAS = (1080, 1920)
MARGIN = 96

HEADER_RULE = (874, 170, 984, 180)
KICKER_Y = 216
COUNTER_Y = 292

PHOTO_TOP = 420
PHOTO_ASPECT_HEIGHT = 0.72
PHOTO_RADIUS = 36
PHOTO_TEXT_GAP = 80

TITLE_SIZE = 60
BODY_SIZE = 42

# Frames 1-5 keep this band blank. Frame 6 alone carries sources.
FOOTER_REGION = (48, 1832, 1032, 1918)
FOOTER_Y = 1870


def require_story_format(requested=None):
    selected = (requested or FORMAT_ID).strip()
    if selected != FORMAT_ID:
        raise ValueError(
            f"unsupported Story format {selected!r}; required {FORMAT_ID!r}"
        )
    return FORMAT_ID
