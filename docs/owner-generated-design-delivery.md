# Owner-reviewed original designs

Use `python -m publishing_v2.bundle_api validate --manifest PATH` to validate
finished artwork without API keys, network calls, receipts or publication.
The Approved Snapchat API workflow exposes the same `validate` mode. Publishing
runs validation before the existing serialized, receipt-backed publisher.

The ordinary licensed-photo manifest remains unchanged. For an original
ChatGPT-generated illustration approved by the owner, use the separate format:

```json
{
  "format": "owner-generated-design-v1",
  "approved": true,
  "account": "executivesaudi",
  "title": "Package title",
  "expires_at": "2026-09-22T00:00:00+03:00",
  "owner_review": {
    "reference": "Reference to the owner's explicit publication approval",
    "reviewed_at": "2026-09-21T08:00:00+00:00",
    "approved_media_sha256": ["SHA256 of the exact reviewed PNG"]
  },
  "media": [{
    "kind": "info",
    "path": "approved/example/card-01.png",
    "sha256": "SHA256 of the exact reviewed PNG",
    "provenance": {
      "provider": "openai_imagegen",
      "library_file_id": "Exact Library ID returned for the generated image",
      "usage": "illustration",
      "third_party_assets": false
    }
  }]
}
```

Repository paths are relative to its root. Repeat media entries in the reviewed
publication order; `kind` may be `info` or `story`, including an ending Info card.
Use actual IDs/hashes and current timestamps; the example is not publishable.
Images must be still PNGs in 9:16 proportions (one-pixel rounding allowed), with
width 512–4096, height 900–8192 and at most 20 MB each. Accepted bytes are sent
unchanged: no resizing, recompression, crop or re-rendering after approval.

This is a trusted repository owner attestation, not automatic evidence that an
image is owned or generated. The person preparing it must inspect actual source
provenance and owner approval. Do not use it for a downloaded photograph, generated
edits containing third-party photographs, or documentary depictions of real
breaking events. Those require the existing rights/relevance process. A Library
ID alone is not proof. No model-written approval is accepted through the normal
autonomous pipeline, whose attribution and independent review gates are unchanged.

`validate` is **not** proof of publication or autonomous editorial readiness.
`publish` still requires explicit owner authorization and the existing account
check, durable intent, sequential POSTED polling and duplicate protection. Files
already posted manually must not be used as a live test: browser posting does not
create the API publisher's duplicate journal.
