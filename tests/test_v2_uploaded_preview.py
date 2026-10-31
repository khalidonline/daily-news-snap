"""A locally valid preview must not hide missing/corrupt remote bytes."""
import json
import subprocess
import pytest
from test_v2_preview_ready import draft
from publishing_v2 import prepared_information as prep


def test_local_only_preview_is_not_ready(draft, monkeypatch):
    monkeypatch.setattr(prep, 'verify_uploaded_preview', lambda p: (_ for _ in ()).throw(ValueError('not uploaded')), raising=False)
    monkeypatch.setattr('sys.argv', ['prepared_information', 'prepare-preview', '--package', draft.name])
    with pytest.raises(ValueError, match='not uploaded'):
        prep.main()


@pytest.fixture
def remote(draft, tmp_path, monkeypatch):
    prep.prepare_local_preview(draft)
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    subprocess.run(['git','-C',str(tmp_path),'add','.'],check=True)
    subprocess.run(['git','-C',str(tmp_path),'-c','user.name=Test','-c','user.email=test@example.test','commit','-qm','draft'],check=True)
    head=subprocess.check_output(['git','-C',str(tmp_path),'rev-parse','HEAD'],text=True).strip()
    return tmp_path,head


@pytest.mark.parametrize('change', ['none','card.png','source','manifest','settings','missing','prepared'])
def test_uploaded_bytes_must_match(draft,remote,change):
    assert hasattr(prep,'compare_uploaded_preview'), 'uploaded-byte verification missing'
    root,head=remote
    if change!='none':
        target={'card.png':draft/'card.png','source':draft/'newspaper.jpg',
                'manifest':draft/'manifest.json','settings':root/'publishing_v2/design-settings.json',
                'missing':draft/'card.png','prepared':draft/'prepared.json'}[change]
        if change=='missing': target.unlink()
        else: target.write_bytes(target.read_bytes()+b'corrupt')
        subprocess.run(['git','add','-A'],cwd=root,check=True)
        subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.test','commit','-qm','bad upload'],cwd=root,check=True)
        bad=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        subprocess.run(['git','checkout',head,'--','.'],cwd=root,check=True)
        with pytest.raises(ValueError,match='Uploaded'):
            prep.compare_uploaded_preview(draft,root,bad)
    else:
        result=prep.compare_uploaded_preview(draft,root,head)
        assert result['status']=='UPLOADED_PREVIEW_READY_NOT_AUTHORIZED'
        assert result['commit']==head
        assert result['preview_paths']==['approved/radio-school-20261031/card.png']
        assert json.loads((draft/'manifest.json').read_text())['approved'] is False


def test_network_failure_does_not_allow_display(draft,monkeypatch):
    def unavailable(*args,**kwargs):
        raise subprocess.CalledProcessError(1,args[0])
    monkeypatch.setattr(subprocess,'run',unavailable)
    with pytest.raises(ValueError,match='do not display'):
        prep.verify_uploaded_preview(draft)


def test_already_authorized_package_cannot_be_previewed_as_draft(draft,remote):
    m=json.loads((draft/'manifest.json').read_text());m['approved']=True
    (draft/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(ValueError,match='approvals false'):
        prep.compare_uploaded_preview(draft,*remote)
