# Complete supervised review package

The user's established visual design is mandatory. Info and Topic reuse the current light `news_bot.render_story` renderer (the same renderer used by the existing light Topic workflow). Story uses `story_bot.render_frame`. Almarai, the existing badge, colors, photo boxes and spacing remain controlled by those production renderers. This change does not modify the production renderers or schedules.

The manual complete-preview workflow prepares eight cards: corrected Info, Topic and six connected historical Story frames. All assets are pinned by SHA-256. A curated crop on Story frame four retains both Earth and the lunar module within the existing photo box. Credits accompany the Telegram cards. NASA informational/public-domain assets here are manually curated; this is not general automatic rights clearance.

Every rendered card must pass the bounded pixel review and its digest must still match immediately before delivery. One Telegram album is sent only after all eight pass. An ambiguous or incomplete receipt stays unknown and is not retried in the same run. Workflow reruns cannot send. A separately dispatched new run has a new journal: the supervisor must check previous receipts and the chat before dispatching again. This is not cross-run idempotency or an unattended production posting system.

The trigger is NASA's September 12, 2026 astronomy feature; the Apollo story is historical, from July 1969. The identity expires at the end of September 13 Saudi time. No Snapchat publishing or three-day live trial is enabled by this workflow.

Validation: 84 unit tests; local rendering and inspection of all eight cards. Live delivery status must be established from the workflow receipt, not inferred from these checks.
