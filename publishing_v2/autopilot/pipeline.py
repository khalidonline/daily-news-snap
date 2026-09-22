"""Coordinator: bounded work, durable handoffs, no agent publishing tools."""
import copy
from datetime import datetime
from pathlib import Path

from daily_budget import BudgetBlocked
from . import policy
from .feedback import EDITORIAL_FEEDBACK
from .evidence import hydrate_editor
from .eligibility import routine_trigger_rejection
from .sources import attention_source


class PersistenceError(Exception):
    """An uncertain journal must stop work, never trigger generation repair."""


class Pipeline:
    def __init__(self, *, agent, sources, render, store, publish, output, now, engine='test'):
        self.agent, self.sources, self.render = agent, sources, render
        self.store, self.publish = store, publish
        self.output, self.now = Path(output), now
        self.engine = engine

    def save(self, state, event, **values):
        state.update(values)
        entry = {'event': event, 'at': self.now().isoformat()}
        for key in ('reason', 'feedback', 'candidate_id', 'source_title', 'editor_round'):
            if key in values: entry[key] = values[key]
        state.setdefault('audit', []).append(entry)
        receipts = state.setdefault('agent_receipts', [])
        for receipt in getattr(self.agent, 'receipts', []):
            if receipt not in receipts:
                receipts.append(copy.deepcopy(receipt))
        try:
            self.store.save(state)
        except Exception:
            raise PersistenceError('journal_write_unconfirmed') from None

    def run(self, lane, mode, *, rollout_verified=False):
        state = self.prepare(lane, mode, rollout_verified=rollout_verified)
        # Delivery is deliberately outside ALL generation-repair handlers.
        if mode == 'live' and state['status'] in {'approved', 'publishing', 'delivery_pending'}:
            return self.deliver(state)
        return state

    def prepare(self, lane, mode, *, rollout_verified=False):
        if lane not in {'daily', 'local'} or mode not in {'shadow', 'live'}:
            raise ValueError('invalid_lane_or_mode')
        if mode == 'live' and not rollout_verified:
            raise ValueError('live_rollout_not_verified')
        state = self.store.read()
        if state:
            if state.get('engine') != self.engine:
                raise ValueError('slot_engine_changed')
            if state.get('lane') != lane or state.get('mode') != mode:
                raise ValueError('slot_identity_changed')
            if state['status'] in {'shadow_passed', 'published', 'held'}:
                return state
            if state['status'] in {'approved', 'publishing', 'delivery_pending'}:
                return state
            # A crashed generation attempt cannot start an unlimited new paid run.
            self.save(state, 'interrupted_generation', status='held', reason='generation_interrupted')
            return state
        state = {'version': 1, 'engine': self.engine, 'lane': lane, 'mode': mode, 'status': 'working',
                 'started_at': self.now().isoformat(), 'expires_at': policy.expiry(self.now()), 'audit': []}
        self.save(state, 'started')
        try:
            candidates = self.sources.discover(lane, self.now())
            excluded = list(getattr(self.sources, 'discovery_rejections', []))
            eligible = []
            for candidate in candidates:
                reason = routine_trigger_rejection(candidate)
                if reason:
                    excluded.append({'candidate_id': candidate['id'],
                                     'source_title': candidate['title'], 'reason': reason})
                else:
                    eligible.append(candidate)
            if excluded:
                self.save(state, 'triggers_filtered', eligibility_rejections=excluded)
            candidates = eligible
            if not candidates:
                raise ValueError('no_current_candidates')
            ids = {c['id']: c for c in candidates}
            for choice in self.editor_choices(state, lane, candidates):
                for key in ('why_saudi', 'angle', 'why_now', 'share_reason', 'research_query'):
                    policy.text(choice.get(key), 500)
                candidate = dict(ids[choice['id']], editorial=choice)
                self.save(state, 'candidate_considered', candidate=candidate,
                          candidate_id=candidate['id'], visual_preflight=None)
                try:
                    if 'evidence_format' in choice:
                        candidate['editorial'] = hydrate_editor(choice, candidate)
                    policy.validate_editor_binding(candidate)
                    policy.validate_attention(candidate, self.now())
                    attention = [s for s in self.sources.attention(candidate)
                                 if attention_source(s, candidate)]
                    if not attention:
                        raise ValueError('attention_article_not_retrieved')
                    timing = self.agent.run('timing', {'candidate': candidate, 'sources': attention,
                                                       'lane': lane, 'now': self.now().isoformat()})
                    self.save(state, 'timing_checked', candidate_id=candidate['id'], timing=timing)
                    policy.validate_timing(timing, attention, self.now())
                    sources = self.sources.research(candidate)
                    if not any(attention_source(s, candidate) for s in sources):
                        raise ValueError('attention_article_not_retrieved')
                    visual_options = []
                    planner = getattr(self.render, 'plan_visuals', None)
                    if planner:
                        visual_options = planner(candidate)
                        discovered = candidate.get('visual_discovery', [])
                        if discovered:
                            self.save(state, 'official_images_discovered', candidate_id=candidate['id'],
                                      official_image_candidates=discovered)
                        if len({r['asset_id'] for r in visual_options}) < 2:
                            if discovered:
                                raise ValueError('images_found_usage_clearance_required')
                            raise ValueError('insufficient_subject_visuals_before_drafting')
                        self.save(state, 'visual_preflight_passed', candidate_id=candidate['id'], visual_preflight={
                            'candidate_id': candidate['id'],
                            'asset_ids': [r['asset_id'] for r in visual_options],
                            'distinct_count': len(visual_options)})
                    self.save(state, 'selected', candidate_id=candidate['id'])
                    research = self.agent.run('researcher', {'candidate': candidate, 'sources': sources,
                                                            'verified_timing': timing, 'lane': lane, 'now': self.now().isoformat()})
                    policy.validate_research(research, sources, lane, self.now())
                    original_sources = sources
                    sources = policy.evidence_snapshot(research, sources)
                    expires = state['expires_at']
                    if lane in {'daily', 'local'}:
                        activation = datetime.fromisoformat(research['event_date']).replace(tzinfo=policy.RIYADH)
                        expires = min(expires, policy.expiry(activation))
                    self.save(state, 'researched', sources=sources, research=research)
                    feedback = ''
                    excluded_images = set()
                    for attempt in range(3):
                        review = None
                        try:
                            draft = self.agent.run('writer', {'candidate': candidate, 'research': research,
                                                              'visual_options': visual_options,
                                                              'feedback': feedback})
                            policy.validate_draft(draft, research)
                            self.save(state, 'drafted', draft=draft)
                            package = dict(draft, sources=sources, research=research, lane=lane,
                                           editorial_feedback=EDITORIAL_FEEDBACK,
                                           candidate=candidate, expires_at=expires, as_of=self.now().isoformat(),
                                           repair={'feedback': feedback, 'excluded_image_ids': sorted(excluded_images)})
                            folder = self.output / choice['id'] / str(attempt)
                            paths = self.render(package, folder)
                            if len(paths) != len(package['cards']):
                                raise ValueError('missing_rendered_cards')
                            snapshot = policy.seal(package, paths)
                            # Fresh request: no writer conversation or self-review is reused.
                            review_input = dict(copy.deepcopy(package), original_sources=original_sources)
                            review = self.agent.run('reviewer', review_input, images=paths)
                            review['input_sha256'] = policy.digest(review_input)
                            learn = getattr(self.sources, 'record_visual_feedback', None)
                            if learn:
                                learn(candidate, package, review)
                            policy.validate_review(review, len(paths))
                            policy.verify_seal(package, paths, snapshot, self.now())
                            self.save(state, 'review_passed', status='approved', package=package,
                                      paths=[str(p) for p in paths], approval=snapshot, review=review)
                            if mode == 'shadow':
                                self.save(state, 'shadow_complete', status='shadow_passed')
                                return state
                            return state
                        except BudgetBlocked:
                            raise
                        except (ValueError, RuntimeError, OSError) as error:
                            if str(error) == 'agent_input_too_large':
                                raise  # Rewriting prose cannot repair a structural input error.
                            feedback = str(error) if isinstance(error, ValueError) else type(error).__name__
                            # Reviewer reasoning is useful repair feedback, not new instructions.
                            if 'review' in locals() and isinstance(review, dict):
                                feedback += ': ' + str(review.get('reason', ''))[:2000]
                                for card, check in zip(package['cards'], review.get('card_checks', [])):
                                    ident = card.get('image', {}).get('asset_id')
                                    if isinstance(check, dict) and check.get('relevant') is False and isinstance(ident, str):
                                        excluded_images.add(ident)
                            self.save(state, 'repair_required', feedback=feedback)
                except BudgetBlocked:
                    raise
                except (ValueError, RuntimeError, OSError) as error:
                    self.save(state, 'candidate_rejected', reason=str(error)[:250] if isinstance(error, ValueError) else type(error).__name__,
                              candidate_id=candidate['id'], source_title=candidate['title'])
            self.save(state, 'exhausted_candidates', status='held', reason='no_package_passed_review')
        except PersistenceError:
            raise
        except Exception as error:
            details = {'budget_diagnostic': error.diagnostic} if isinstance(error, BudgetBlocked) else {}
            self.save(state, 'stopped', status='held', reason=type(error).__name__, **details)
        return state

    def editor_choices(self, state, lane, candidates):
        """Try at most two shortlists, never researching a candidate twice."""
        used = set()
        for round_number in range(1, 3):
            remaining = [candidate for candidate in candidates if candidate['id'] not in used]
            if not remaining:
                return
            allowed = {candidate['id'] for candidate in remaining}
            self.save(state, 'editor_round_started', editor_round=round_number)
            selected = self.agent.run('editor', {
                'lane': lane, 'now': self.now().isoformat(),
                'editorial_feedback': EDITORIAL_FEEDBACK,
                'candidates': remaining,
                'previous_rejections': [
                    {'candidate_id': entry['candidate_id'], 'reason': entry['reason']}
                    for entry in state['audit'] if entry['event'] == 'candidate_rejected'],
            })
            ranked = selected.get('candidates', [])
            if not isinstance(ranked, list) or not 1 <= len(ranked) <= 4:
                raise ValueError('invalid_selection')
            for choice in ranked:
                if not isinstance(choice, dict) or choice.get('id') not in allowed or choice['id'] in used:
                    raise ValueError('unknown_or_duplicate_candidate')
                used.add(choice['id'])
                yield choice

    def deliver(self, state):
        package = state['package']
        try:
            paths = [Path(p) for p in state['paths']]
            if not all(p.is_file() for p in paths):
                # Rehydrate only the sealed package, never select/write a new one.
                paths = self.render(package, self.output / 'resume')
            policy.validate_review(state['review'], len(paths))
            policy.verify_seal(package, paths, state['approval'], self.now())
            self.save(state, 'publishing', status='publishing')
            receipt = self.publish(package, paths)
            expected_posts = 1 if package.get('delivery', {}).get('kind') == 'video' else sum(c.get('kind') != 'credits' for c in package['cards'])
            if receipt.get('status') != 'POSTED' or len(receipt.get('post_ids', [])) != expected_posts:
                raise RuntimeError('delivery_not_confirmed')
            self.save(state, 'delivery_verified', status='published', receipt=receipt)
        except Exception as error:
            self.save(state, 'delivery_unresolved', status='delivery_pending', reason=type(error).__name__)
        return state
