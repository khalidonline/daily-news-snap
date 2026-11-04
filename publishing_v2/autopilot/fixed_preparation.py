"""Fixed-template preparation from validated research, never publication.

Invoked only by runtime --mode fixed-preview. Paid writer/reviewer and image
acquisition require an independently authorized run; tests inject fixtures.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from publishing_v2.editorial_production import TextRejected
from publishing_v2.information_text_fit import prepare_text
from publishing_v2.prepared_information import safe_path
from publishing_v2.public_images import download_image, get_bytes, atomic_write
from publishing_v2.publication import image_without_public_credit
from .policy import digest, validate_image_variety
from . import fixed_information as fixed
from .information_bridge import stage


def _json_bytes(value):
    # ASCII escaping preserves even rejected surrogate/control codepoints.
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')


def _persisted_writer_draft(agent, context, output):
    """Persist the exact parsed provider result before any validation.

    A durable intent prevents duplicate paid calls after uncertain interruption.
    Never infer authorization to regenerate from an incomplete or changed file.
    """
    output.mkdir(parents=True, exist_ok=True)
    paths = {key: output / f'fixed-writer-{key}.json' for key in
             ('raw', 'context', 'normalized', 'repair')}
    for path in paths.values():
        safe_path(path)
        if path.is_symlink():
            raise ValueError('fixed_writer_recovery_unsafe_artifact')
    context_sha = digest(context)
    if any(path.exists() for path in paths.values()):
        if not paths['context'].exists() or not paths['raw'].exists():
            raise ValueError('fixed_writer_recovery_incomplete_no_regeneration')
        try:
            binding = json.loads(paths['context'].read_bytes())
            raw_bytes = paths['raw'].read_bytes()
            raw = json.loads(raw_bytes)
            if (binding.get('context_sha256') != context_sha
                    or binding.get('raw_sha256') != hashlib.sha256(raw_bytes).hexdigest()):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise ValueError('fixed_writer_recovery_binding_mismatch') from None
    else:
        # Exclusive intent creation also prevents concurrent duplicate writers.
        with paths['context'].open('xb') as stream:
            stream.write(_json_bytes({'context_sha256': context_sha, 'status': 'writer_started'}))
            stream.flush()
            import os
            os.fsync(stream.fileno())
        raw = agent.run('fixed_information_writer', {
            'candidate': context['candidate'], 'research': context['research'],
            'verified_timing': context['verified_timing']})
        raw_bytes = _json_bytes(raw)
        atomic_write(paths['raw'], raw_bytes)
        atomic_write(paths['context'], _json_bytes({
            'context_sha256': context_sha, 'status': 'writer_saved',
            'raw_sha256': hashlib.sha256(raw_bytes).hexdigest()}))
    normalized, changes = fixed.normalize_unapproved_draft(raw)
    normalized_bytes = _json_bytes(normalized)
    atomic_write(paths['normalized'], normalized_bytes)
    receipt = {'schema_version': 1, 'status': 'validated',
               'context_sha256': context_sha,
               'raw_sha256': hashlib.sha256(raw_bytes).hexdigest(),
               'normalized_sha256': hashlib.sha256(normalized_bytes).hexdigest(),
               'changes': changes, 'approved': False,
               'publish_authorized': False, 'preview_allowed': False}
    try:
        fixed.validate_draft(normalized, context['research'])
    except ValueError as exc:
        receipt['status'] = 'rejected'
        receipt['diagnostic'] = (exc.diagnostic if isinstance(exc, fixed.DraftTextError)
                                 else {'reason': str(exc)})
        atomic_write(paths['repair'], _json_bytes(receipt))
        raise
    atomic_write(paths['repair'], _json_bytes(receipt))
    return normalized


def validate_saved_draft(request, research):
    from .saved_draft_recovery import validate_artifacts
    return validate_artifacts(request, research)


def _persisted_editorial_draft(request, context, output):
    """Keep immutable provider artifacts separate from a reviewed editorial patch.

    The original writer context is NOT rebound to current source text. A separate
    audit binds the exact patch to fresh context; independent review still follows.
    """
    data = validate_saved_draft(request, context['research'])
    output = safe_path(output)
    output.mkdir(parents=True, exist_ok=True)
    payloads = {f'fixed-writer-{key}.json': row['text'].encode('utf-8')
                for key, row in data['artifacts'].items()}
    payloads['fixed-editorial-draft.json'] = _json_bytes(data['edited_draft'])
    payloads['fixed-editorial-repair.json'] = _json_bytes({
        'schema_version': 1, 'status': 'requires_independent_review',
        'request_sha256': digest(request), 'fresh_context_sha256': digest(context),
        'artifact_sha256': {key: row['sha256'] for key, row in data['artifacts'].items()},
        'edited_sha256': hashlib.sha256(payloads['fixed-editorial-draft.json']).hexdigest(),
        'changes': data['changes'], 'approved': False,
        'publish_authorized': False, 'preview_allowed': False})
    # Check every existing file before writing any; never replace retained bytes.
    for name, raw in payloads.items():
        path = output / name
        if path.is_symlink() or (path.exists() and path.read_bytes() != raw):
            raise ValueError('saved_draft_artifact_changed')
        safe_path(path)
    for name, raw in payloads.items():
        path = output / name
        if not path.exists():
            with path.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                import os
                os.fsync(stream.fileno())
    return copy.deepcopy(data['edited_draft'])


def _new_review_paths(output):
    paths = {key: output / name for key, name in {
        'context': 'fixed-text-review-context.json',
        'response': 'fixed-text-review-response.json',
        'package': 'fixed-text-reviewed.json',
    }.items()}
    # An existing result, rejection or uncertain call needs explicit recovery.
    # Never turn a missing/corrupt artifact into permission for another paid call.
    for path in paths.values():
        if path.is_symlink() or path.exists():
            raise ValueError('fixed_text_review_already_started_no_automatic_retry')
        safe_path(path)
    return paths


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_review_artifact(path, raw, *, new=False):
    """Install complete durable bytes; exclusive artifacts are never replaced."""
    if path.is_symlink():
        raise ValueError('fixed_text_review_unsafe_artifact')
    safe_path(path)
    if new:
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-fixed-text-')
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # Unlike replace, link atomically refuses concurrent review intent.
            try:
                os.link(temporary, path)
            except FileExistsError:
                raise ValueError('fixed_text_review_already_started_no_automatic_retry') from None
        finally:
            os.unlink(temporary)
    else:
        atomic_write(path, raw)
    _sync_directory(path.parent)


def _persisted_text_review(package, agent, context, output):
    """Save the actual independent response and approved text before visuals.

    No saved approval is replayed here. Interrupted, rejected and completed
    attempts all stop on re-entry, retaining their original evidence unchanged.
    """
    paths = _new_review_paths(output)
    output.mkdir(parents=True, exist_ok=True)
    _sync_directory(output.parent)
    data = fixed.text_input(package)
    original_sources = context['original_sources']
    request = dict(data, original_sources=original_sources) if original_sources else data
    binding = {
        'schema_version': 1, 'status': 'review_started',
        'context_sha256': digest(context), 'input_sha256': digest(data),
        'review_request_sha256': digest(request),
        'unreviewed_package_sha256': digest(package),
        'approved': False, 'publish_authorized': False, 'preview_allowed': False,
    }
    _write_review_artifact(paths['context'], _json_bytes(binding), new=True)

    class RecordingReviewer:
        def run(self, role, actual_request):
            if (role != 'fixed_information_text_review'
                    or digest(actual_request) != binding['review_request_sha256']):
                raise ValueError('fixed_text_review_request_changed')
            review = agent.run(role, actual_request)
            raw = _json_bytes(review)
            _write_review_artifact(paths['response'], raw, new=True)
            binding.update(status='review_response_saved',
                           review_response_sha256=hashlib.sha256(raw).hexdigest())
            _write_review_artifact(paths['context'], _json_bytes(binding))
            return review

    try:
        fixed.approve_text(package, RecordingReviewer(), original_sources)
    except TextRejected:
        binding['status'] = 'text_review_rejected'
        _write_review_artifact(paths['context'], _json_bytes(binding))
        raise
    fixed.require_text_approval(package)
    raw = _json_bytes(package)
    _write_review_artifact(paths['package'], raw, new=True)
    binding.update(status='text_review_approved',
                   reviewed_package_sha256=hashlib.sha256(raw).hexdigest())
    _write_review_artifact(paths['context'], _json_bytes(binding))


class FixedInformationPreparer:
    def __init__(self, agent, renderer):
        self.agent, self.renderer = agent, renderer
        self._preflight_plan = None

    def preflight(self, context, draft):
        """Measure and resolve the exact free catalog before review admission.

        The returned payloads can be cost-estimated before recovery journal CAS.
        A private deep copy pins that same catalog and context for preparation.
        This grants no text, design, preview or publication approval.
        """
        fixed.validate_draft(draft, context['research'])
        for card in draft['cards']:
            fit = prepare_text(fixed.card_draft(card))
            if not fit['fit']:
                raise ValueError('fixed_information_text_does_not_fit: ' + '; '.join(fit['violations']))
        package = dict(copy.deepcopy(draft), **{k: copy.deepcopy(v) for k, v in context.items()
                                              if k != 'original_sources'}, information_schema_version=1)
        catalog = [row for row in self.renderer.image_catalog(package) if image_without_public_credit(row)]
        if not catalog:
            raise ValueError('fixed_information_caption_rights_compatible_source_unavailable')
        data = fixed.text_input(package)
        sources = context['original_sources']
        plan = {'package': package, 'catalog': catalog,
                'review_payload': dict(data, original_sources=copy.deepcopy(sources)) if sources else data,
                'visual_payload': {'cards': package['cards'], 'options': catalog,
                                   'fixed_images': [], 'repair': {}}}
        self._preflight_plan = copy.deepcopy(plan)
        self._preflight_context_sha256 = digest(context)
        self._preflight_draft_sha256 = digest(draft)
        return copy.deepcopy(plan)

    def __call__(self, context, output):
        output = safe_path(output)
        name = 'tawari-' + context['as_of'][:10].replace('-', '') + '-' + context['lane'] + '-' + digest(context)[:12]
        # No model call or regeneration if a prior attempt already installed it.
        if (Path('approved')/name).exists():
            raise ValueError('Fixed package already exists; inspect original handoff, never regenerate')
        _new_review_paths(output)
        if (self._preflight_plan is not None
                and self._preflight_context_sha256 != digest(context)):
            raise ValueError('fixed_preflight_binding_mismatch')
        request = getattr(self, 'saved_draft_recovery', None)
        draft = (_persisted_editorial_draft(request, context, output) if request is not None
                 else _persisted_writer_draft(self.agent, context, output))
        if self._preflight_plan is None:
            plan = self.preflight(context, draft)
        else:
            if self._preflight_draft_sha256 != digest(draft):
                raise ValueError('fixed_preflight_binding_mismatch')
            plan = copy.deepcopy(self._preflight_plan)
        package, catalog = plan['package'], plan['catalog']
        _persisted_text_review(package, self.agent, context, output)
        choices = self.agent.run('visual', plan['visual_payload'])
        ids = choices.get('image_ids', [])
        if not isinstance(ids,list) or len(ids) != len(package['cards']):
            raise ValueError('incomplete_fixed_visual_selection')
        raws = []
        for card, ident in zip(package['cards'],ids):
            matches = [row for row in catalog if row.get('asset_id') == ident]
            if len(matches) != 1:
                raise ValueError('unknown_or_ambiguous_fixed_image')
            image = copy.deepcopy(matches[0])
            raw = download_image(image, fetch=get_bytes)
            sha = hashlib.sha256(raw).hexdigest()
            if image.get('sha256') and image['sha256'] != sha:
                raise ValueError('fixed_source_changed')
            image['sha256'] = sha
            card['image'] = image
            raws.append(raw)
        validate_image_variety(package['cards'])
        output.mkdir(parents=True,exist_ok=True)
        for i,raw in enumerate(raws):
            atomic_write(output/f'source-{i:02d}.jpg',raw)
        return stage(package,output,name)
