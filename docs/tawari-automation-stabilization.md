# Tawari automation: offline stabilization checkpoint

This checkpoint is for the information/news (طواري) route only. It does not
change challenge scheduling, production schedules, owner approval or delivery.

## Verified defect and bounded fix

`autopilot.runtime.engine_id` formerly hashed Python files, dependency manifests
and configured model names, but not the design master or pinned visual assets.
A changed information template or font could therefore retain the same readiness
identity. The engine identity now also hashes:

- `publishing_v2/design-settings.json`;
- Almarai Regular and Bold font bytes;
- the original brand badge;
- the base artwork selected by the information master.

Missing required files fail closed. Master artwork outside the repository,
including a symlink resolving outside it, is rejected before reading its bytes.
Changes invalidate earlier readiness rather than relabeling or refreshing it.
This does not make legacy rendering compliant with the current template.

## Safe offline verification

Run from the repository with its image/test dependencies already installed:

```
python -m unittest tests.test_v2_autopilot_design_readiness -v
FONT_FAMILY=Almarai THEME=light python -m pytest -q
python -m publishing_v2.evaluate --mode offline --output /tmp/tawari-evaluation
```

The regression test uses temporary synthetic files and no external services.
The existing test suite uses fixtures/mocked delivery. The evaluation command
only loads historical corpus cases: `offline_ready` is NOT proof of rendering,
editorial approval, licensing, deployed production or successful delivery.

Do not substitute the legacy `--mode shadow` workflow for an offline test.
The workflow invokes production editorial agents, writes remote state and sends
its outcome through Telegram even in shadow mode. Its current triggers are
manual dispatch and a main-branch change to `autopilot-trigger.txt`, not cron.
External scheduling cannot be established from workflow files alone.

## Remaining end-to-end gates

The legacy autopilot still renders through `preview.render_card` and
`story_bot.render_frame`. It does not use the current fixed information renderer
through the complete prepared-information lifecycle. Its `publish_package`
uses the Story publisher without separate current Saved Story completion.
A green unit suite or recent legacy shadow cannot close these gaps.

Before claiming current Tawari automation is stabilized:

1. Integrate the fixed information renderer and text-fit gate without changing
   approved wording, fonts, master geometry or the required sharing CTA.
2. Prepare exact package bytes with both approvals false. Preserve final-hash
   review, uploaded-preview verification and explicit owner authorization.
3. Exercise Story and Saved Story separately through the established guarded
   publisher, including partial success, uncertain delivery reconciliation and
   duplicate suppression. Never regenerate approved media on delivery failure.
4. Obtain authorization for any paid or externally sending test. Do not run old
   workflow triggers, enable schedules or promote from historical readiness.
5. Verify authorized real delivery receipts and the actual scheduler before
   declaring an end-to-end production result.

This code-only checkpoint does not perform or authorize those production steps.
