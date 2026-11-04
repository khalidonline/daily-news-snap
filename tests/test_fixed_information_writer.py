"""Offline fixed-copy contract: no provider, publishing or fabricated review calls."""
import copy
import pytest
from publishing_v2.autopilot import fixed_information as fixed
from publishing_v2.editorial_production import TEXT_CHECKS, TextRejected


def draft():
    return {'title': 'سالفة القهوة', 'cards': [{'kind': 'info', 'title': 'كيف بدأت القهوة؟',
        'bullets': ['بدأت بفكرة بسيطة.', 'وبعدها تغيرت طريقة تقديمها.'],
        'punch': 'فكرة صغيرة غيرت أشياء كثيرة.', 'claim_ids': ['c1'],
        'image_query': 'coffee cup', 'image_caption': 'كوب قهوة'}]}


def package():
    return dict(draft(), research={'claims': [{'id': 'c1', 'fact': 'fact'}]},
                sources=[{'id': 's1', 'text': 'evidence'}], lane='daily',
                candidate={'id': 'candidate', 'visual_discovery': {'unused': 1}},
                as_of='2026-11-04T00:00:00+03:00', expires_at='2026-11-05T00:00:00+03:00')


class Reviewer:
    def run(self, role, data):
        assert role == 'fixed_information_text_review'
        assert data['cards'][0]['bullets'] == draft()['cards'][0]['bullets']
        return {'checks': {k: True for k in TEXT_CHECKS}, 'repair_indices': [], 'reason': 'fixture review'}


@pytest.mark.parametrize('count', [1, 2])
def test_accepts_one_or_two_cards(count):
    value = draft(); value['cards'] *= count
    fixed.validate_draft(value, {'claims': [{'id': 'c1'}]})
    assert fixed.card_draft(value['cards'][0]) == {
        'headline': value['cards'][0]['title'], 'bullets': value['cards'][0]['bullets'],
        'closing': value['cards'][0]['punch']}


@pytest.mark.parametrize('mutation', [
    lambda d: d['cards'].extend(copy.deepcopy(d['cards'])*2),
    lambda d: d['cards'][0].update(kind='story'),
    lambda d: d['cards'][0].update(body='legacy paragraph'),
    lambda d: d['cards'][0].update(bullets=[]),
    lambda d: d['cards'][0].update(bullets=['نقطة']*5),
    lambda d: d['cards'][0].update(bullets='نص'),
    lambda d: d['cards'][0].update(bullets=['نص\nآخر']),
    lambda d: d['cards'][0].update(bullets=['نصّ']),
    lambda d: d['cards'][0].update(claim_ids=['unknown']),
    lambda d: d['cards'][0].update(image_caption=' '),
])
def test_rejects_ambiguous_or_unsupported_schema(mutation):
    value = draft(); mutation(value)
    with pytest.raises(ValueError):
        fixed.validate_draft(value, {'claims': [{'id': 'c1'}]})


@pytest.mark.parametrize('field,value', [
    ('title','عنوان آخر'), ('bullets',['تغيير']), ('punch','ختام جديد'),
    ('claim_ids',['c2']), ('image_query','tea cup'), ('image_caption','شاي'),
])
def test_any_copy_mutation_invalidates_approval(field, value):
    value_package = package(); fixed.approve_text(value_package, Reviewer())
    fixed.require_text_approval(value_package)
    value_package['cards'][0][field] = value
    with pytest.raises(ValueError): fixed.require_text_approval(value_package)


def test_bullet_order_and_split_are_approval_bound():
    value = package(); fixed.approve_text(value, Reviewer())
    value['cards'][0]['bullets'].reverse()
    with pytest.raises(ValueError): fixed.require_text_approval(value)


def test_visual_metadata_does_not_invalidate_text_but_evidence_does():
    value = package(); fixed.approve_text(value, Reviewer())
    value['cards'][0]['image'] = {'sha256': 'new'}
    value['candidate']['visual_discovery'] = {'unused': 2}
    fixed.require_text_approval(value)
    value['sources'][0]['text'] = 'changed'
    with pytest.raises(ValueError): fixed.require_text_approval(value)


@pytest.mark.parametrize('change', [
    lambda r: r.update(reason=''), lambda r: r.update(repair_indices=[0]),
    lambda r: r['checks'].update(factual=1),
])
def test_malformed_review_never_authorizes_copy(change):
    value = package(); fixed.approve_text(value, Reviewer())
    change(value['text_approval']['review'])
    with pytest.raises(ValueError): fixed.require_text_approval(value)


def test_review_rejection_removes_previous_approval():
    value = package(); fixed.approve_text(value, Reviewer())
    class Reject:
        def run(self, role, data): return {'checks': {}, 'reason': 'unsupported'}
    with pytest.raises(TextRejected): fixed.approve_text(value, Reject())
    assert 'text_approval' not in value


@pytest.mark.parametrize('mutate', [
    lambda p: p.update(title='عنوان آخر'),
    lambda p: p.update(information_schema_version=True),
    lambda p: p['cards'][0].update(body='hidden legacy text'),
    lambda p: p['cards'][0].update(extra_public_text='new unchecked text'),
    lambda p: p['cards'][0]['bullets'].append('نقطة جديدة'),
    lambda p: p['cards'][0]['bullets'].__setitem__(0, p['cards'][0]['bullets'][0]+' '),
    lambda p: p['research']['claims'][0].update(fact='new evidence'),
    lambda p: p.update(expires_at='2027-11-05T00:00:00+03:00'),
])
def test_all_approval_scope_changes_fail_closed(mutate):
    value = package(); fixed.approve_text(value, Reviewer()); mutate(value)
    with pytest.raises(ValueError): fixed.require_text_approval(value)


def test_copy_projection_is_deep_and_never_edits_approved_wording():
    value = package(); before = copy.deepcopy(value)
    projection = fixed.text_input(value)
    projection['cards'][0]['bullets'].clear()
    assert value == before
    render_input = fixed.card_draft(value['cards'][0]); render_input['bullets'].clear()
    assert value == before
