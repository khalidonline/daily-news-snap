# Story Cost Control — Editorial Quality Gate Addendum

Date: 2026-08-29
Status: Approved in chat

This addendum is part of the approved `2026-08-29-story-cost-control-design.md` contract.

## Requirement

A generated editorial brief MUST NOT become `EDITORIAL_LOCKED` merely because the model call succeeded or the JSON parsed.

Before persistence as the reusable locked revision, the brief must pass a deterministic editorial-quality gate. The gate is intentionally local/deterministic in phase 1 so it does not create another paid Claude call.

The gate must reject or route to REVIEW when any of the following is true:

- fewer than the configured story frame count are present;
- required frame fields are missing or empty (`heading`, `text`, `punch`, subject/visual targeting fields expected by the renderer);
- the narrative has obvious duplicate/repeated headings or near-identical frame bodies;
- the opening, middle, and closing structure is incomplete;
- the final frame is missing a concrete payoff/meaning statement;
- unsupported comparative/superlative wording is present where current house rules prohibit it;
- Arabic text is structurally malformed for rendering (empty/placeholder fragments, excessive raw URLs/JSON, or obvious model boilerplate);
- source/search evidence required by the existing research contract is absent;
- existing Story Focus / city normalization policy marks the brief invalid.

A passing brief becomes `EDITORIAL_LOCKED` and is cached. A failing brief becomes `EDITORIAL_REVIEW` or `EDITORIAL_FAILED`; it is not stored as an approved cache hit and ordinary reruns must not silently buy another generation.

## Quality principle

Cost control must preserve or improve publication quality. Caching prevents approved copy from drifting on visual reruns; it must never be used to freeze an unreviewed weak first draft.

## Acceptance criteria

1. A syntactically valid but editorially weak mocked brief fails before lock/cache.
2. A valid publication-shaped mocked brief passes and becomes reusable.
3. Cache hits return only previously quality-passed briefs.
4. A failed editorial gate does not trigger an automatic second model call.
5. Visual-only runs cannot bypass the editorial lock requirement.
