# Public image acquisition and recovery

This extends the approved supplier-independent pilot with two credential-free search adapters: Wikimedia Commons and NASA Images. Getty is not imported or called. The code downloads image files and retains provenance for internal review; it does not publish them or certify reuse rights.

`public_images.acquire(query, output)` searches Commons, tries up to five downloads, then tries NASA if necessary. The same query is preserved on source fallback. NASA is a specialist space/science source, not an alternative for every Saudi, entertainment or business subject. No search result is automatically judged relevant. Each source is tried once per acquisition; rate-limit errors move on without a retry storm. This is bounded sequential acquisition, not a persistent cross-run circuit breaker.

The transport sends no credentials, restricts HTTPS requests to four fixed official API/media hosts, rejects redirects, sets a 12-second request timeout, and bounds JSON at 2 MiB and image files at 16 MiB. Pillow fully decodes JPEG/PNG/WebP, rejects animations, oversized pixel counts and inadequate dimensions. These checks do not detect semantic mismatch, watermark, deceptive captions or poor portrait crops.

Downloads remain unchanged and are named by SHA-256; separate manifests retain the source, caption, date and credit/license metadata. Every result has licensing_verified, visual_approved, relevance_verified and production_ready false. A NASA domain does not establish public-domain status; third-party material and illustrations require review. Commons license/attribution metadata must be checked against the original file page. These downloads are temporary review evidence; a production asset bank needs approved retention/reuse rights and immutable cloud storage. Existing files are checked for corruption, but network-free cache recovery is not implemented by this slice.

## Evidence run

The **Publishing v2 public image evidence** workflow runs only manually or when its own file changes on main. It receives no model, Getty, Telegram, Snapchat or Google Cloud credentials. It tries iPhone 16 and Riyadh Metro through Commons and Voyager through Commons/NASA, then deliberately fails Commons and tests NASA recovery for the same Voyager query. Artifacts last seven days. An incomplete download case makes the job fail while retaining completed evidence. These are historical discovery probes, not current editorial packages or six-frame Story acceptance.

Run locally with:

```bash
python -m pip install -r requirements-v2-images.txt
python -m publishing_v2.image_probe --output /tmp/public-image-evidence
```

Next required integration: extend official subject-specific media sources, secure rights/relevance decisions and cloud storage, map approved visuals to every frame, render for review, and connect durable Telegram delivery. The three-day live trial remains unstarted.

References: [MediaWiki image information](https://www.mediawiki.org/wiki/API:Imageinfo), [NASA Images API](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf), [NASA media-use guidance](https://www.nasa.gov/nasa-brand-center/images-and-media/), [Commons reuse requirements](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia).
