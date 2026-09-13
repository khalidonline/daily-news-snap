# Disabled legacy workflows

On September 13, 2026, the repository owner requested disabling every workflow except the new event-led Publishing v2 strategy.

The 21 legacy workflow definitions were moved here unchanged from `.github/workflows/`. GitHub Actions does not discover workflows in this directory. This stops their default-branch schedules and new dispatch entry points while retaining a reversible archive. Restore an individual definition only after explicit authorization.

Only the eight `publishing-v2-*.yml` definitions remain in the active directory. These cover preview, evaluation, image evidence, cloud setup and offline checks. They do not constitute an unattended daily publishing service. No new schedule or publishing authorization is introduced by this change.

Old run history remains. Moving definitions does not cancel already queued/running executions or disable external schedulers or workflows stored on other branches; those require separate controls.
