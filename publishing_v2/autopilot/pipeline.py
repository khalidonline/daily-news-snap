"""Coordinator: bounded work, durable handoffs, no agent publishing tools."""
import copy
from datetime import datetime
from pathlib import Path

from daily_budget import BudgetBlocked
from . import policy
from publishing_v2.editorial_production import approve_text, TextRejected, repair_indices, apply_card_patches
from .feedback import EDITORIAL_FEEDBACK
from .evidence import hydrate_editor
from .eligibility import routine_trigger_rejection
from .sources import attention_source


class PersistenceError(Exception):
    """An uncertain journal must stop work, never trigger generation repair."""


# The viewer-persona judge's score, 1-10, below which a researched candidate is
# dropped before writing. 7 = "would tap through and maybe share".
MIN_HOOK_SCORE = 7


class Pipeline:
    def __init__(self, *, agent, sources, render, store, publish, output, now, engine='test', candidate_memory=None, published_memory=None, excluded_candidate_ids=None, hooks=False, free_selection=None):
        self.agent, self.sources, self.render = agent, sources, render
        # Owner 2026-09-26: three competing openings and a viewer-persona judge
        # before the writer. Off by default so fixture agents keep their scripts.
        self.hooks = hooks
        self.store, self.publish = store, publish
        self.output, self.now = Path(output), now
        self.engine = engine
        self.candidate_memory = candidate_memory
        self.published_memory = published_memory
        self.excluded_candidate_ids = set(excluded_candidate_ids or ())
        self.free_selection = free_selection

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
            # Owner asked why a stronger trigger (the Oman match) was not used;
            # without the pool on record nobody could tell if it was offered.
            self.save(state, 'pool', pool=[{'id': c.get('id'), 'title': str(c.get('title', ''))[:160],
                                            'published_at': c.get('published_at')} for c in candidates])
            excluded = list(getattr(self.sources, 'discovery_rejections', []))
            eligible = []
            for candidate in candidates:
                reason = ('selected_in_sibling_lane' if candidate.get('id') in self.excluded_candidate_ids else None)
                reason = reason or (self.published_memory.reason(candidate) if self.published_memory else None)
                reason = reason or routine_trigger_rejection(candidate)
                if not reason and self.candidate_memory:
                    reason = self.candidate_memory.reason(candidate, self.engine)
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
                self.agent.package_id = candidate['id']
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
                    free = getattr(self.agent, 'requires_free_selection', False)
                    timing = (copy.deepcopy(self.free_selection.get('timing', {})) if free else
                              self.agent.run('timing', {'candidate': candidate, 'sources': attention,
                                                       'lane': lane, 'now': self.now().isoformat()}))
                    self.save(state, 'timing_checked', candidate_id=candidate['id'], timing=timing)
                    policy.validate_timing(timing, attention, self.now())
                    if self.hooks and not free:
                        self.judge_pitch(state, candidate)
                    sources = self.sources.research(candidate)
                    if not any(attention_source(s, candidate) for s in sources):
                        raise ValueError('attention_article_not_retrieved')
                    if free:
                        candidate['card_image_plan'] = copy.deepcopy(self.free_selection.get('image_plan', []))
                    screen = getattr(self.render, 'screen_visuals', None)
                    if screen and not screen(candidate):
                        raise ValueError('insufficient_subject_visuals_before_research')
                    if free:
                        from .free_selection import validate_story, validate_images
                        validate_story(self.free_selection, sources)
                        validate_images(self.free_selection, candidate)
                        self.save(state, 'free_preflight_passed', free_selection=copy.deepcopy(self.free_selection),
                                  selection_assessment={'status':'evidence_passed', 'cost_micro_usd':0,
                                      'candidate_id':candidate['id'], 'timing':timing,
                                      'saudi_relevance':choice['why_saudi'],
                                      'discovery':choice['angle'], 'share_reason':choice['share_reason'],
                                      'documented_story_beats':len(self.free_selection['story']),
                                      'planned_images':len(self.free_selection['image_plan']),
                                      'note':'Evidence feasibility, not a predicted audience score.'})
                    visual_options = []
                    self.save(state, 'selected', candidate_id=candidate['id'])
                    research = self.agent.run('researcher', {'candidate': candidate, 'sources': sources,
                                                            'verified_timing': timing,
                                                            'story_plan': self.free_selection.get('story') if free else None,
                                                            'lane': lane, 'now': self.now().isoformat()})
                    research, pruned_claim_ids = policy.prune_unsupported_number_claims(research, sources)
                    if pruned_claim_ids:
                        self.save(state, 'research_claims_pruned', candidate_id=candidate['id'],
                                  pruned_claim_ids=pruned_claim_ids)
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
                    draft = None
                    package = None
                    affected = []
                    accepted_images = {}
                    hook = self.choose_hook(state, candidate, research) if self.hooks and not free else None
                    hook_input = {'chosen_hook': hook} if hook else {}
                    fmt = candidate.get('editorial', {}).get('format')
                    if fmt:
                        hook_input['format'] = fmt
                    shortened = False
                    for attempt in range(4):
                        review = None
                        try:
                            if shortened:
                                shortened = False  # already cut to the photographed cards; re-approve as is
                            elif draft is None:
                                draft = self.agent.run('writer', {'candidate': candidate, 'research': research,
                                    'visual_options': visual_options, 'feedback': feedback, **hook_input})
                            elif affected:
                                patches = self.agent.run('card_repair', {'candidate': candidate,
                                    'research': research, 'draft': draft, 'repair_indices': affected,
                                    'visual_options': visual_options, 'feedback': feedback, **hook_input})
                                draft = apply_card_patches(draft, patches, affected)
                            else:
                                raise ValueError('repair_scope_missing_or_invalid')
                            try:
                                policy.validate_draft(draft, research)
                            except ValueError as error:
                                fixable = policy.style_repair_indices(draft)
                                if not fixable or not str(error).startswith(('owner_style_violation', 'unsupported_arrow_symbol')):
                                    raise
                                raise TextRejected({'repair_indices': fixable, 'reason': str(error)})
                            self.save(state, 'drafted', draft=draft)
                            package = dict(copy.deepcopy(draft), sources=sources, research=research, lane=lane,
                                           verified_timing=timing,
                                           editorial_feedback=EDITORIAL_FEEDBACK,
                                           candidate=candidate, expires_at=expires, as_of=state['started_at'],
                                           repair={'feedback': feedback, 'excluded_image_ids': sorted(excluded_images)})
                            # Text approval is persisted before any render/visual-selection call.
                            approve_text(package, self.agent, original_sources)
                            self.save(state, 'text_approved', working_draft=copy.deepcopy(draft),
                                      text_approval=package['text_approval'], revision=attempt + 1)
                            planner = getattr(self.render, 'plan_visuals', None)
                            if planner and not visual_options:
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
                            for index, image in accepted_images.items():
                                if index not in affected:
                                    package['cards'][index]['image'] = copy.deepcopy(image)
                            folder = self.output / choice['id'] / 'current'
                            paths = self.render(package, folder)
                            accepted_images = {i:copy.deepcopy(c['image']) for i,c in enumerate(package['cards'])
                                               if c.get('kind') != 'credits' and c.get('image')}
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
                        except policy.VisualShortfall as error:
                            drop = set(error.indices)
                            kept = [c for i, c in enumerate(draft['cards']) if i not in drop]
                            # Info carries the hook and at least two story beats must
                            # remain; otherwise the story is not tellable honestly.
                            if 0 in drop or len(kept) < 3:
                                raise ValueError('insufficient_distinct_story_photos: ' + str(error)[:300])
                            draft = dict(draft, cards=kept)
                            shortened, affected, accepted_images = True, [], {}
                            feedback = str(error)
                            self.save(state, 'visual_shortened', candidate_id=candidate['id'],
                                      dropped_cards=sorted(drop), working_draft=copy.deepcopy(draft))
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
                            failure_review = error.review if isinstance(error, TextRejected) else review
                            if not isinstance(failure_review, dict):
                                raise  # Infrastructure/schema faults never trigger a full paid rewrite.
                            affected = repair_indices(failure_review, len(draft['cards']))
                            self.save(state, 'repair_required', feedback=feedback,
                                      affected_cards=affected, working_draft=copy.deepcopy(draft),
                                      recovery_policy='patch_affected_cards_only')
                    raise ValueError('editorial_repairs_exhausted')
                except BudgetBlocked:
                    raise
                except (ValueError, RuntimeError, OSError) as error:
                    reason = str(error)[:250] if isinstance(error, ValueError) else type(error).__name__
                    self.remember_rejection(candidate, reason)
                    self.save(state, 'candidate_rejected', reason=reason,
                              candidate_id=candidate['id'], source_title=candidate['title'])
            self.save(state, 'exhausted_candidates', status='held', reason='no_package_passed_review')
        except PersistenceError:
            raise
        except Exception as error:
            details = {'budget_diagnostic': error.diagnostic} if isinstance(error, BudgetBlocked) else {}
            self.save(state, 'stopped', status='held', reason=str(error)[:250] if isinstance(error, ValueError) else type(error).__name__, **details)
        return state

    def remember_rejection(self, candidate, reason):
        if self.candidate_memory:
            try:
                self.candidate_memory.record(candidate, reason, self.engine)
            except Exception:
                raise PersistenceError('candidate_memory_write_unconfirmed') from None

    def judge_pitch(self, state, candidate):
        """Score the editor's pitch before any research is paid for.

        27 Sep: the research, hooks, writer and reviews were bought for Harry
        Kane, US golf and a Gulf Cup statistic the hook judge then scored 6.
        The same viewer judge now scores the pitch itself (a few cents) and a
        weak one never reaches the researcher. Faults pass the pitch through:
        the later hook gate still stands.
        """
        editorial = candidate.get('editorial', {})
        try:
            verdict = self.agent.run('pitch_judge', {
                'format': editorial.get('format', 'story'), 'title': candidate.get('title'),
                'why_now': editorial.get('why_now'), 'angle': editorial.get('angle'),
                'share_reason': editorial.get('share_reason')})
            score = verdict.get('score')
            if type(score) is not int or not 1 <= score <= 10:
                raise ValueError('invalid_pitch_score')
            reason = policy.text(verdict.get('reason'), 500)
        except BudgetBlocked:
            raise
        except (ValueError, RuntimeError, OSError, AttributeError, TypeError) as error:
            self.save(state, 'pitch_unscored', candidate_id=candidate['id'],
                      reason=str(error)[:250] if isinstance(error, ValueError) else type(error).__name__)
            return
        self.save(state, 'pitch_scored', candidate_id=candidate['id'], pitch={'score': score, 'reason': reason})
        if score < MIN_HOOK_SCORE:
            raise ValueError('weak_pitch: scored %d/10: %s' % (score, reason[:200]))

    def choose_hook(self, state, candidate, research):
        """Three evidence-bound openings; a viewer-persona judge picks one.

        A hook is advice to the writer, never evidence: every option must cite
        existing research claims, and the text gates still check the draft.
        Any fault here returns None so the writer proceeds unguided rather than
        losing the candidate after research has been paid for.
        """
        known = {claim['id'] for claim in research['claims']}
        try:
            options = self.agent.run('hooks', {'candidate': candidate, 'research': research}).get('options')
            if not isinstance(options, list) or len(options) != 3:
                raise ValueError('invalid_hook_options')
            for option in options:
                if not isinstance(option, dict) or set(option) != {'title', 'opening', 'share_line', 'claim_ids'}:
                    raise ValueError('invalid_hook_fields')
                policy.text(option['title'], 85)
                policy.text(option['opening'], 200)
                policy.text(option['share_line'], 200)
                ids = option['claim_ids']
                if not isinstance(ids, list) or not ids or any(i not in known for i in ids):
                    raise ValueError('unsupported_hook_claim')
            verdict = self.agent.run('hook_judge', {'options': [
                {k: o[k] for k in ('title', 'opening', 'share_line')} for o in options]})
            choice = verdict.get('choice')
            if type(choice) is not int or not 0 <= choice < 3:
                raise ValueError('invalid_hook_choice')
            policy.text(verdict.get('reason'), 500)
            score = verdict.get('score')
            if type(score) is not int or not 1 <= score <= 10:
                raise ValueError('invalid_hook_score')
        except BudgetBlocked:
            raise
        except (ValueError, RuntimeError, OSError, AttributeError, TypeError) as error:
            self.save(state, 'hook_skipped', reason=str(error)[:250] if isinstance(error, ValueError)
                      else type(error).__name__, candidate_id=candidate['id'])
            return None
        hook = {'options': options, 'choice': choice, 'score': score, 'reason': verdict['reason']}
        if score < MIN_HOOK_SCORE:
            # Owner, 2026-09-27: a correct but unremarkable package is a failure.
            # Stop before the writer and the reviews are paid for; the next
            # candidate gets the slot.
            self.save(state, 'hook_too_weak', candidate_id=candidate['id'], hook=hook)
            raise ValueError('weak_hook: best opening scored %d/10: %s' % (score, verdict['reason'][:200]))
        self.save(state, 'hook_chosen', candidate_id=candidate['id'], hook=hook)
        return dict(options[choice])

    def editor_choices(self, state, lane, candidates):
        """Try at most three shortlists, never researching a candidate twice."""
        if getattr(self.agent, 'requires_free_selection', False):
            from .free_selection import select
            # Exactly one free handoff. No second paid candidate on rejection.
            yield select(self.free_selection, lane, candidates)
            return
        used = set()
        for round_number in range(1, 4):
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
            if not isinstance(ranked, list) or not 0 <= len(ranked) <= 4:
                raise ValueError('invalid_selection')
            if not ranked:
                return
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
                raise ValueError('saved_media_missing_restore_approved_artifact')
            policy.validate_review(state['review'], len(paths))
            policy.verify_seal(package, paths, state['approval'], self.now())
            self.save(state, 'publishing', status='publishing')
            receipt = self.publish(package, paths)
            expected_posts = 1 if package.get('delivery', {}).get('kind') == 'video' else sum(c.get('kind') != 'credits' for c in package['cards'])
            if receipt.get('status') != 'POSTED' or len(receipt.get('post_ids', [])) != expected_posts:
                raise RuntimeError('delivery_not_confirmed')
            self.save(state, 'delivery_verified', status='published', reason=None, receipt=receipt)
        except Exception as error:
            self.save(state, 'delivery_unresolved', status='delivery_pending', reason=type(error).__name__)
        return state
