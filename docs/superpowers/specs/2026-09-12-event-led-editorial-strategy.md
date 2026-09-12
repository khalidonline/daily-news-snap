# Approved event-led Info, Topic, and Story strategy

Status: editorial strategy approved by the owner on 2026-09-12. This document records that approval; it does not mean runtime implementation or deployment is complete.

## Account promise

«مع الحدث، بمعلومة وموضوع وقصة تستاهل المشاركة»

Help Saudi Arabic-speaking Snapchat viewers stay connected to what is happening today and discover an interesting fact, topic, or true story worth sharing with friends.

News is the trigger for selection, not a post format. The three published formats are Info, Topic, and Story.

## Event theme and timing

Select a timely, credible event with strong audience interest. The event creates a temporary editorial theme. An iPhone launch can make iPhone, its technology, people, and relevant history the theme.

A theme lasts for the activation day and the following Saudi calendar day at most, using Asia/Riyadh. It expires at the start of the third day; subsequent runs must not extend that deadline. This is a calendar-day rule, not a rolling 48-hour cache.

Replace the theme earlier if a materially stronger trigger emerges or its useful angles are exhausted. Do not renew an expired theme by changing its headline or source URL. A genuinely new development requires its own dated evidence.

Validate the event time independently of article publication time. A freshly republished article does not make an old event current. Match language to upcoming, live, or completed status, and recheck timing before delivery and recovery.

All categories remain eligible without fixed rotation or automatic category preference.

## Published formats

| Format | Purpose | Required editorial value |
| --- | --- | --- |
| Info / معلومة | A short surprising fact connected to the active event | One verified detail that earns attention; the headline reveals or opens curiosity about the fact, rather than repeating the announcement |
| Topic / موضوع | An interesting question, phenomenon, or comparison connected to the event | A satisfying explanation with evidence; no routine buying advice or generic news recap |
| Story / قصة | A documented real story connected to the event | People or a concrete subject, stakes, a turning point, and an outcome; preserve the approved six-frame format and visual standards |

The connection may be through the event's people, technology, competitors, or history. It must be immediately understandable to the viewer. Do not fabricate a connection simply to use an existing card.

An event must earn each format separately. Do not manufacture a weak Topic or Story merely to fill a three-format package. Search for stronger connected material or move to a stronger trigger when necessary.

## Editorial gate

Every candidate must answer:

1. Why today?
2. What is interesting here?
3. Why would someone share it with a friend?

Require verified facts, an explicit relationship to the active event, and a distinct payoff. Info, Topic, and Story must not recycle the same fact in different wording.

Sharing is the editorial goal, not a requirement to append a generic question or call to action.

Illustrative angles discussed with the owner are creative directions, not verified claims or approved production copy. In particular, any new-iPhone capability must be confirmed for the actual announced model, and any launch anecdote must be documented before use.

## Cross-format coordination

Maintain one shared event record containing:
- Stable event identity and source references.
- Supported event time and current event status.
- Theme activation and immutable expiry in Saudi time.
- Why the event is interesting to this audience.
- Separate proposed Info angles, Topic angles, and real Story candidates.
- Used facts and delivered angles across all three formats.
- Replacement reason when a theme changes.

Read shared state before selection, generation, and delivery. Write state atomically. Failed delivery must not be mistaken for a published angle. Recovery must respect both the active theme and the original evidence.

Repeated coverage of the same event is permitted only for a distinct interesting fact or format. Existing blanket event/source deduplication must therefore become cross-format fact/angle deduplication for this strategy.

## Visuals and delivery

Preserve relevant photographs, verified portraits, exact logos, and appropriate explanatory graphics. Every Story frame must have a meaningful relevant visual. No unrelated fallback imagery or invented documentary scenes.

Preserve Telegram review and existing delivery validation. Snapchat publishing remains disabled. The owner subsequently approved increased spend for reliability and removed the $3 ceiling as a design constraint. Keep the current production guard until a reviewed rollout replaces it; isolated supplier evaluation uses an explicit $10 experiment bound. Reuse verified research within the event window, not repeated published copy.

## Implementation findings from repository inspection

- daily_news_runner.py configures the News selection prompt and applies source deduplication; it must support Info selection and shared theme context.
- news_editorial_prompt.txt still describes a News editor and blanket event deduplication.
- news_bot.py also tells the model not to revisit the same event. This must be scoped carefully because Breaking shares this renderer.
- daily_news_fresh_runner.py owns News notification labels and recovery behavior.
- topic_snapchat.py adds current-event candidates but can fall back to unrelated catalog subjects. Its scheduled selector and research context must consume the shared theme.
- .github/workflows/daily.yml labels the format as News; .github/workflows/topic.yml currently labels Topic as معلومة تهمك. Public format labels must distinguish Info and Topic.
- .github/workflows/story.yml checks out repair/all-story-visuals-2026-08-29 for the renderer. Editing Story code on main alone will not change scheduled Story output.
- story_delivery_recovery.py clears the selected Story after a scheduled failure. Replacement selection must remain connected to the active theme.
- The repair branch's guarded_story_publish.py enforces prevalidated visuals. Retain those checks while changing candidate selection.

## Acceptance evidence before claiming deployment

- Saudi midnight boundary tests prove a theme works on activation day and the next day, then expires without renewal.
- Recycled articles cannot refresh old events.
- Info, Topic, and Story read the same active event, including after runner retries and independent workflow checkouts.
- Duplicate facts are rejected; distinct facts about one active event remain eligible.
- Topic and Story recovery cannot silently choose unrelated catalog entries.
- True-story and six-frame visual gates still apply.
- Existing production guards remain until rollout; new evaluation has separate explicit paid-call bounds. Telegram review and disabled Snapchat publishing remain effective.
- Review a complete event package using verified evidence: one Info, one Topic, and one six-frame Story. The package must visibly demonstrate why it is relevant today and why each post is worth sharing.
- Report deployment separately from this editorial approval.

