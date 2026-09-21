# Exclude clear ineligible triggers before paid selection

The owner requested continuing after shadow run 35580905577. That run selected
a guava/cholesterol headline and paid the researcher $0.112725 before the
existing sensitive-topic gate held it. An obituary also occupied the shortlist.
Prompt instructions alone did not exclude these clearly ineligible triggers.

Added a small deterministic headline filter for clear Arabic obituaries,
English dies/died/dead-at-age headlines, and named cholesterol/diabetes/blood
pressure conditions plus nutrition/advice
phrasing. It is deliberately title-only: background mentions of a death do not
ban a company's history, and ordinary food festivals, hospital openings, travel,
sport, companies and culture remain available. This is not a comprehensive
safety classifier or permission to publish anything else; independent source,
sensitivity, factual, timing, image and final review gates remain mandatory.

Discovery excludes these titles before consuming each feed's eligible quota.
The coordinator also filters before the paid editor for alternative discovery
implementations. It journals exclusion reasons in one write, not a network write
per headline. Remaining candidates keep the existing editorial ranking; no fixed
category rotation, additional model call, subscription or increased budget.

Six regression tests failed before implementation and pass afterwards. They
cover the observed titles, ordinary-content counterexamples, eligible feed quota,
zero paid roles for an all-ineligible pool, and excluding ineligible IDs from the
editor's shortlist. Independent review identified overly broad generic-patient
matches; these were narrowed and hospital service counterexamples now pass.
The reviewer confirmed the issue resolved, with no remaining blockers. Offline
evaluation returned offline_ready and the final configured suite passed 288
tests. GitHub CI must pass before merge. No paid generation or publication was dispatched.

The shared $3/day cap and design are unchanged. Last verified daily settled spend
is $0.240961. Current-engine daily/local end-to-end qualification is still needed;
this fix is not a claim that image coverage or autonomous posting is solved.
