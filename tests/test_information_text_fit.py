import pytest


SHORT = [
    'رايان إير كانت تخسر؛ غيرت شغلها لطيران اقتصادي، وصارت تبيع الرحلة بسعر أقل.',
    'تبي شنطة إضافية أو تختار كرسيك؟ تدفع لحالها، بدل تدخل بسعر كل تذكرة.',
    'حتى جيب الكرسي شالوه لتقليل التنظيف، وخلوا الكراسي ثابتة عشان تقل التصليحات.',
    'هدفهم ينزلون الركاب ويركبون غيرهم خلال ٢٥ دقيقة؛ عشان تطير الطيارة رحلات أكثر.',
]


def draft():
    return dict(headline='رايان إير… التوفير وصل لجيب الكرسي!', bullets=SHORT,
                closing='أنت توفر بالتذكرة… وهم يوفرون بالدقيقة!')


def test_compact_draft_has_counts_lines_and_bound_receipt():
    from publishing_v2.information_text_fit import prepare_text, receipt_matches
    d = draft()
    result = prepare_text(d)
    assert result['fit'], result
    assert [b['line_count'] for b in result['fields'] if b['role']=='bullet'] == [2]*4
    assert result['fields'][1]['characters'] == len(SHORT[0])
    assert receipt_matches(d, result['receipt'])
    assert result['body_budget']['remaining_height_px'] > 0
    d['headline'] += '!'
    assert not receipt_matches(d, result['receipt'])


@pytest.mark.parametrize('field,value', [
    ('bullets', []), ('bullets', ['نقطة']*5), ('bullets', ['كلام طويل '*80]),
    ('headline', 'عنوان '*50), ('closing', 'النهاية '*50),
    ('headline', ''), ('headline', '\u200b'), ('headline', 'x'*200),
    ('bullets', [None]), ('headline', '\u064e'),
])
def test_invalid_copy_never_exposes_display_text(field, value):
    from publishing_v2.information_text_fit import prepare_text
    d = draft(); d[field] = value
    r = prepare_text(d)
    assert not r['fit']
    assert 'display_text' not in r and 'receipt' not in r


def test_original_three_line_paragraph_rejected():
    from publishing_v2.information_text_fit import prepare_text
    d = draft()
    d['bullets'] = ['على طاري كلام رايان إير عن غلاء التذاكر، هالشركة الأوروبية لها سالفة: كانت تخسر، وقلبت شغلها لطيران اقتصادي.']
    r = prepare_text(d)
    assert not r['fit']
    assert r['fields'][1]['line_count'] == 3


def test_equal_character_count_is_not_a_fit_guarantee():
    from publishing_v2.information_text_fit import prepare_text
    a = draft(); b = draft()
    a['headline'] = 'i'*40; b['headline'] = 'W'*40
    assert prepare_text(a)['fit']
    assert not prepare_text(b)['fit']


def test_mixed_copy_matches_renderer_geometry():
    from publishing_v2.information_text_fit import prepare_text
    from publishing_v2.fixed_information_template import render
    from PIL import Image
    d = draft(); d['bullets'] = ['رايان Ryanair في 2026: رحلة بـ ٢٥ ريال؟']
    r = prepare_text(d)
    _, blocks = render(**d, photos=[Image.new('RGB',(10,10))], captions=['صورة'])
    assert r['fit']
    assert r['fields'][1]['line_boxes'] == next(b for b in blocks if b['role']=='bullet')['line_boxes']


def test_receipt_rejects_changed_assets():
    from publishing_v2.information_text_fit import prepare_text, receipt_matches
    from copy import deepcopy
    d = draft(); receipt = prepare_text(d)['receipt']
    for key in ('settings_sha256', 'fonts', 'implementation'):
        stale = deepcopy(receipt); stale[key] = 'changed'
        assert not receipt_matches(d, stale)


def test_cli_overflow_nonzero_without_display_text():
    import subprocess, sys, json
    d = draft(); d['headline'] = 'عنوان '*100
    p = subprocess.run([sys.executable, '-m', 'publishing_v2.information_text_fit'],
                       input=json.dumps(d), capture_output=True, text=True)
    assert p.returncode == 1
    assert 'display_text' not in json.loads(p.stdout)


@pytest.mark.parametrize('asset', ['publishing_v2/design-settings.json', 'fonts/Almarai-Bold.ttf'])
def test_actual_changed_asset_invalidates_receipt(tmp_path, monkeypatch, asset):
    import shutil
    import publishing_v2.information_text_fit as fit
    d = draft(); receipt = fit.prepare_text(d)['receipt']
    for relative in ('publishing_v2/design-settings.json', 'fonts/Almarai-Bold.ttf',
                     'fonts/Almarai-Regular.ttf', 'publishing_v2/information_text_fit.py',
                     'publishing_v2/fixed_information_template.py', 'publishing_v2/design_contract.py'):
        target = tmp_path/relative; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fit.ROOT/relative, target)
    with (tmp_path/asset).open('ab') as stream:
        stream.write(b' ')
    monkeypatch.setattr(fit, 'ROOT', tmp_path)
    assert not fit.receipt_matches(d, receipt)
