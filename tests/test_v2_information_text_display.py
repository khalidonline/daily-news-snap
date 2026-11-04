"""Display handoff tests run by the existing publishing-v2 offline CI suite."""
import json
from pathlib import Path


def draft():
    return json.loads(Path('tests/fixtures/ryanair-text-fit.json').read_text())


def run_display(d, *args):
    import subprocess, sys, json
    return subprocess.run(
        [sys.executable, '-m', 'publishing_v2.information_text_fit', '--display', *args],
        input=json.dumps(d, ensure_ascii=False), capture_output=True, text=True)


def test_display_mode_emits_only_freshly_checked_exact_text():
    import json
    from publishing_v2.information_text_fit import prepare_text
    d = draft()
    p = run_display(d)
    assert p.returncode == 0, p.stderr
    from pathlib import Path
    settings = json.loads(Path('publishing_v2/design-settings.json').read_text())
    cta = settings['editorial_master']['cta_exact']
    assert p.stdout == prepare_text(d)['display_text'] + '\n\n' + cta + '\n'
    report = json.loads(p.stderr)
    assert report['fit'] and report['receipt']


def test_display_mode_blocks_overflow_even_with_stale_receipt():
    import json
    from publishing_v2.information_text_fit import prepare_text
    d = draft()
    d['receipt'] = prepare_text(d)['receipt']
    d['bullets'][0] = 'على طاري كلام رايان إير عن غلاء التذاكر، هالشركة الأوروبية لها سالفة: كانت تخسر، وقلبت شغلها لطيران اقتصادي.'
    p = run_display(d)
    assert p.returncode == 1
    assert p.stdout == ''
    assert json.loads(p.stderr)['fit'] is False


def test_display_mode_reads_file_without_changing_it(tmp_path):
    import json
    path = tmp_path/'draft.json'
    before = json.dumps(draft(), ensure_ascii=False)
    path.write_text(before)
    p = run_display(None, str(path))
    assert p.returncode == 0, p.stderr
    assert path.read_text() == before
    assert p.stdout.startswith(draft()['headline'])


def test_display_mode_malformed_input_has_no_display_output():
    import subprocess, sys, json
    p = subprocess.run([sys.executable, '-m', 'publishing_v2.information_text_fit', '--display'],
                       input='{bad json', capture_output=True, text=True)
    assert p.returncode == 1
    assert p.stdout == ''
    assert json.loads(p.stderr)['fit'] is False


def test_display_mode_missing_file_has_no_display_output(tmp_path):
    import json
    p = run_display(None, str(tmp_path/'missing.json'))
    assert p.returncode == 1
    assert p.stdout == ''
    assert json.loads(p.stderr)['fit'] is False


def test_display_mode_missing_font_fails_closed(tmp_path, monkeypatch, capsys):
    import io, json, shutil, sys
    import publishing_v2.information_text_fit as fit
    (tmp_path/'publishing_v2').mkdir()
    shutil.copyfile(fit.ROOT/'publishing_v2/design-settings.json',
                    tmp_path/'publishing_v2/design-settings.json')
    monkeypatch.setattr(fit, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['information_text_fit', '--display'])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(draft())))
    assert fit.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert json.loads(captured.err)['fit'] is False


def test_display_mode_missing_cta_fails_closed(tmp_path, monkeypatch, capsys):
    import io, json, sys
    import publishing_v2.information_text_fit as fit
    # Keep real measurement/assets, only omit the master field for handoff.
    original = fit.json.loads
    def without_cta(value, *args, **kwargs):
        data = original(value, *args, **kwargs)
        if isinstance(data, dict) and 'editorial_master' in data:
            data['editorial_master'].pop('cta_exact', None)
        return data
    monkeypatch.setattr(fit.json, 'loads', without_cta)
    monkeypatch.setattr(sys, 'argv', ['information_text_fit', '--display'])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(draft())))
    assert fit.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert original(captured.err)['fit'] is False


def test_legacy_json_success_contract_remains_unchanged():
    import json, subprocess, sys
    from publishing_v2.information_text_fit import prepare_text
    d = draft()
    p = subprocess.run([sys.executable, '-m', 'publishing_v2.information_text_fit'],
                       input=json.dumps(d), capture_output=True, text=True)
    assert p.returncode == 0
    assert p.stderr == ''
    assert json.loads(p.stdout) == prepare_text(d)
