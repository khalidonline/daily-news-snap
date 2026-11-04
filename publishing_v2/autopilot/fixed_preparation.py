"""Fixed-template preparation from validated research, never publication.

Invoked only by runtime --mode fixed-preview. Paid writer/reviewer and image
acquisition require an independently authorized run; tests inject fixtures.
"""
import copy
import hashlib
from pathlib import Path

from publishing_v2.information_text_fit import prepare_text
from publishing_v2.prepared_information import safe_path
from publishing_v2.public_images import download_image, get_bytes, atomic_write
from publishing_v2.publication import image_without_public_credit
from .policy import digest, validate_image_variety
from . import fixed_information as fixed
from .information_bridge import stage


class FixedInformationPreparer:
    def __init__(self, agent, renderer):
        self.agent, self.renderer = agent, renderer

    def __call__(self, context, output):
        output = safe_path(output)
        name = 'tawari-' + context['as_of'][:10].replace('-', '') + '-' + context['lane'] + '-' + digest(context)[:12]
        # No model call or regeneration if a prior attempt already installed it.
        if (Path('approved')/name).exists():
            raise ValueError('Fixed package already exists; inspect original handoff, never regenerate')
        draft = self.agent.run('fixed_information_writer', {
            'candidate':context['candidate'], 'research':context['research'],
            'verified_timing':context['verified_timing']})
        fixed.validate_draft(draft, context['research'])
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
