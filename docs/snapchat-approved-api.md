# Approved Snapchat API publishing

The `Approved Snapchat API` workflow uses the existing `BUNDLE_API_KEY` and
`BUNDLE_TEAM_ID` repository secrets. It checks that the connected account is
`executivesaudi`. Pushes only run a read-only connection check. Publishing is
manual on main, after the actual media has been reviewed and approved.
No model generation, scheduled posting, or browser authentication is involved.

## Publishing a new approved package

1. Commit the exact approved PNG/JPEG/MP4 media and a JSON manifest to the repository.
2. Set `approved: true` only after owner approval; use the event's actual expiry.
3. Run `Approved Snapchat API`, mode `publish`, passing the manifest path.
4. Success requires `POSTED` for every card, in order. Scheduling is not success.

Manifest structure (illustrative, not an approved package):

```json
{
  "account": "executivesaudi",
  "approved": false,
  "title": "Reviewed story title",
  "expires_at": "2026-09-15T21:00:00Z",
  "media": [{"path": "approved/story/01.png", "sha256": "EXACT_SHA256"}]
}
```

Media is sent as one upload per STORY post, preserving the reviewed images.
The manual path accepts 1–10 files, without requiring a fixed card count.
Review dimensions, visual safe areas, factual accuracy and timing before approval.
The account lookup proves access, not successful public publication. Only a real
approved next package can verify the end-to-end posting path.

## Recovery

The `snapchat-api-state` branch stores upload IDs, post IDs and delivery status.
Its files contain no API credentials. GitHub's contents SHA acts as a
compare-and-swap guard; the workflow additionally serializes all API deliveries.
Never delete or reset the state branch. State is committed before create-post.
If the create response is lost, automatic recovery stops rather than guessing.
An operator must look up the matching upload/post in Bundle and record its verified
post ID before resuming. A known post ID is polled again, never recreated.
Provider error/deleted posts also stop for review.

Identical ordered media cannot be reposted merely by changing filenames or title.
This guard does not detect previously posted browser stories or edited/reordered
packages. Do not submit the already-published foldable-display story. API is the
publishing path for newly approved packages; avoid parallel browser posting.

OAuth reconnection may still be required when Snapchat revokes/expires the linked
account. API access removes routine browser login, not platform reauthorization.

Official references:
- https://info.bundle.social/api-reference/client/socialaccount/get-social-account-by-team-and-type
- https://info.bundle.social/api-reference/platforms/snapchat

## Review-only sources (20 September 2026)

The owner removed F-35's source card from Snapchat. Do not recreate it.
Every automatic review now includes a final sources card, but public delivery
selects only explicitly typed `info` and `story` media. Manual manifest rows must
include `kind` and adapter-verified `image` rights metadata (`license`, restrictions,
and attribution requirement). Untyped legacy manifests stop before upload.

CC BY 2.0/4.0 attribution remains supported in review artifacts. Private credits
alone do not satisfy public attribution: automatic public candidates currently
use Public domain/CC0 assets. CC BY images require a separate reviewed, visible
attribution implementation before public use; never strip their credits and post.
Videos containing a review credits frame are rejected, and the automatic renderer
no longer compiles that credits card into public video. Manual video manifests are
held pending an explicit editorial-frame delivery contract. Photos publish normally.
No previous approved or published package should be reclassified and reposted.
