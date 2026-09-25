"""Compatibility entry point; defaults to free preview, never paid regeneration."""
from publishing_v2.apple_correction import SPEC, validate_spec, validate_review, main

if __name__ == "__main__":
    main()
