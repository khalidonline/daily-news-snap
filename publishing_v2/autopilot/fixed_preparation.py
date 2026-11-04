"""Fixed-template preparation from validated research, never publication.

Invoked only by runtime --mode fixed-preview. Paid writer/reviewer and image
acquisition require an independently authorized run; tests inject fixtures.
"""
import copy
import hashlib
import json
from pathlib import Path

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


class FixedInformationPreparer:
    def __init__(self, agent, renderer):
        self.agent, self.renderer = agent, renderer

    def __call__(self, context, output):
        output = safe_path(output)
        name = 'tawari-' + context['as_of'][:10].replace('-', '') + '-' + context['lane'] + '-' + digest(context)[:12]
        # No model call or regeneration if a prior attempt already installed it.
        if (Path('approved')/name).exists():
            raise ValueError('Fixed package already exists; inspect original handoff, never regenerate')
        draft = _persisted_writer_draft(self.agent, context, output)
        for card in draft['cards']:
            fit = prepare_text(fixed.card_draft(card))
            if not fit['fit']:
                raise ValueError('fixed_information_text_does_not_fit: ' + '; '.join(fit['violations']))
        package = dict(copy.deepcopy(draft), **{k:copy.deepcopy(v) for k,v in context.items()
                                              if k != 'original_sources'}, information_schema_version=1)
        fixed.approve_text(package, self.agent, context['original_sources'])
        catalog = [row for row in self.renderer.image_catalog(package) if image_without_public_credit(row)]
        if not catalog:
            raise ValueError('fixed_information_caption_rights_compatible_source_unavailable')
        choices = self.agent.run('visual', {'cards':package['cards'], 'options':catalog,
                                            'fixed_images':[], 'repair':{}})
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
