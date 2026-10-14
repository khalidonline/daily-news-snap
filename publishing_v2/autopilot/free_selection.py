"""Validate a free editorial handoff; never call a model to pick its replacement.

The brief is editorial work, not authority to publish. Retrieved quotations,
current timing and downloaded image identities are checked again here; normal
research, text approval, visual review and publication gates still follow.
"""
import copy
import json
from pathlib import Path

from . import policy


def load_brief(path):
    if not path:
        return None
    source = Path(path).resolve()
    if source.stat().st_size > 64_000:
        raise ValueError('selection_brief_too_large')
    brief = json.loads(source.read_text())
    if not isinstance(brief, dict):
        raise ValueError('invalid_free_selection')
    return brief


def select(brief, lane, candidates):
    if not isinstance(brief, dict) or brief.get('version') != 1 or brief.get('lane') != lane:
        raise ValueError('free_selection_brief_required')
    choice = brief.get('choice')
    if (not isinstance(choice, dict) or choice.get('id') != brief.get('candidate_id')
            or choice['id'] not in {c['id'] for c in candidates}):
        raise ValueError('free_selection_not_in_current_pool')
    return copy.deepcopy(choice)


def validate_story(brief, sources):
    beats = brief.get('story')
    if not isinstance(beats, list) or not 3 <= len(beats) <= 6:
        raise ValueError('documented_story_progression_required')
    by_id = {s['id']: s for s in sources}
    quotes = set()
    for beat in beats:
        if not isinstance(beat, dict):
            raise ValueError('invalid_story_beat')
        policy.text(beat.get('point'), 500)
        quote = policy.text(beat.get('quote'), 1000)
        if len(quote) < 12 or quote not in by_id.get(beat.get('source_id'), {}).get('text', ''):
            raise ValueError('story_not_supported_by_retrieved_source')
        quotes.add(quote)
    if len(quotes) != len(beats):
        raise ValueError('repeated_story_evidence')


def validate_images(brief, candidate):
    plan = brief.get('image_plan')
    if not isinstance(plan, list) or not 3 <= len(plan) <= 8:
        raise ValueError('image_plan_required_for_each_card')
    available = {row['asset_id'] for row in candidate.get('visual_feasibility', [])}
    chosen = []
    for card in plan:
        if not isinstance(card, dict) or card.get('asset_id') not in available:
            raise ValueError('planned_image_not_retrieved')
        policy.text(card.get('purpose'), 500)
        chosen.append(card['asset_id'])
    if len(set(chosen)) < len(chosen) - 1 or len(chosen[1:]) != len(set(chosen[1:])):
        raise ValueError('story_images_must_be_distinct')
