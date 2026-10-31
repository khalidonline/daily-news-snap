import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw
from publishing_v2.bundle_api import BundleClient, BundleError


def test_cli_validation_preserves_approved_media_type():
    import subprocess, sys, tempfile
    from datetime import datetime, timezone, timedelta
    raw, report=fixture_card()
    digest=hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
        p=Path(folder); (p/'card.png').write_bytes(raw)
        relative=(p/'card.png').relative_to(Path.cwd()).as_posix()
        now=datetime.now(timezone.utc)
        m={'format':'owner-reviewed-composite-v1','approved':True,'account':'executivesaudi',
           'content_type':'information','approved_destinations':['STORY'],'title':'Offline test',
           'expires_at':(now+timedelta(days=1)).isoformat(),
           'owner_review':{'reference':'Offline fixture not publication authority','reviewed_at':now.isoformat(),
                           'approved_media_sha256':[digest],'approved_source_sha256':[digest]},
           'media':[{'kind':'info','path':relative,'sha256':digest,
              'provenance':{'usage':'mixed_editorial_composite','generated_components':False},
              'source_assets':[{'path':relative,'sha256':digest,'source_url':'https://example.com/test',
                 'rights_status':'owner_accepted_editorial_use','description':'Offline test fixture',
                 'owner_reference':'Offline test fixture'}]}]}
        (p/'manifest.json').write_text(json.dumps(m));(p/'design-review.json').write_text(json.dumps(report))
        result=subprocess.run([sys.executable,'-m','publishing_v2.bundle_api','validate','--manifest',str(p/'manifest.json')],capture_output=True,text=True)
        assert result.returncode==0, result.stdout+result.stderr
        assert json.loads(result.stdout)['status']=='validated_not_published'


def test_explicit_approved_typography_does_not_require_regular_claim():
    from publishing_v2.design_contract import validate_design
    raw, report=fixture_card()
    report['review']['regular_font']=False
    report['review']['approved_typography']=True
    validate_design([(Path('card.png'),raw)],report,'STORY')


@pytest.fixture(autouse=True)
def offline_contract_environment(monkeypatch):
    # CI itself sets this flag; only the explicit stale-settings test enables it.
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)


def test_direct_transport_create_cannot_skip_design_gate(monkeypatch):
    monkeypatch.setenv('BUNDLE_API_KEY', 'offline')
    monkeypatch.setenv('BUNDLE_TEAM_ID', 'team')
    with patch('publishing_v2.bundle_api.request', return_value={'id': 'sent'}) as transport:
        with pytest.raises(BundleError, match='Design'):
            BundleClient().create('unreviewed', 'upload')
        transport.assert_not_called()


def test_upload_without_final_report_is_blocked_before_network(tmp_path, monkeypatch):
    monkeypatch.setenv('BUNDLE_API_KEY', 'offline')
    monkeypatch.setenv('BUNDLE_TEAM_ID', 'team')
    with patch('publishing_v2.bundle_api.request', return_value={'id': 'sent'}) as transport:
        with pytest.raises(BundleError, match='Design'):
            BundleClient().upload((tmp_path/'card.png', b'not reviewed'))
        transport.assert_not_called()


def fixture_card():
    settings=json.loads(Path('publishing_v2/design-settings.json').read_text())
    image=Image.new('RGB',(1080,1920),'#F7F7EB'); draw=ImageDraw.Draw(image)
    draw.rectangle((800,130,1000,145),fill='#0C5F46')
    draw.rectangle((60,1665,1020,1730),fill='#FDE5EB')
    blocks=[]
    for role, y, color in [('headline',235,'#B60E32'),('caption',700,'#7A7973'),
                           ('bullet',1140,'#0B3656'),('closing',1580,'#B60E32'),('cta',1680,'#B60E32')]:
        draw.rectangle((100,y,500,y+29),fill=color)
        blocks.append({'role':role,'box':[100,y,501,y+30],'line_count':1,'color':color,
                       'line_boxes':[[100,y,501,y+30]],'font_size':44,
                       'font_weight':'Bold' if role=='bullet' else 'Regular'})
    stream=io.BytesIO(); image.save(stream,format='PNG'); raw=stream.getvalue()
    report={'version':1,'settings_sha256':hashlib.sha256(Path('publishing_v2/design-settings.json').read_bytes()).hexdigest(),
            'settings_revision':settings['canonical_reference']['revision'],'destinations':['STORY'],
            'content_type':'information','review':{'reference':'offline synthetic geometry test',
            'saudi_editorial':True,'approved_wording':True,'regular_font':True,'photos_and_captions':True,
            'cta_visible':True,'overlay_checked':True,'overlay_destinations':{'STORY':'offline Story overlay'},'mobile_width':390},
            'cards':[{'sha256':hashlib.sha256(raw).hexdigest(),'blocks':blocks,
                      'palette_samples':{'green':[810,131,990,144],'background':[100,50,200,70],
                                         'cta_background':[700,1670,800,1680]}}]}
    return raw, report


def test_valid_raster_contract_and_regressions():
    from publishing_v2.design_contract import validate_design
    import copy
    raw, report=fixture_card()
    validate_design([(Path('card.png'),raw)],report,'STORY')
    for field,value in [('settings_revision','old'),('settings_sha256','0'*64),('destinations',['SPOTLIGHT'])]:
        bad=copy.deepcopy(report);bad[field]=value
        with pytest.raises(BundleError):validate_design([(Path('card.png'),raw)],bad,'STORY')
    for change in ['color','lines','safe_area','hash','review']:
        bad=copy.deepcopy(report)
        if change=='color':bad['cards'][0]['blocks'][2]['color']='#003770'
        if change=='lines':bad['cards'][0]['blocks'][2]['line_count']=3
        if change=='safe_area':bad['cards'][0]['blocks'][-1]['box'][3]=1810
        if change=='hash':bad['cards'][0]['sha256']='0'*64
        if change=='review':bad['review']['regular_font']=False
        with pytest.raises(BundleError):validate_design([(Path('card.png'),raw)],bad,'STORY')


def test_zero_exact_core_color_rejected_even_with_claimed_pass():
    from publishing_v2.design_contract import validate_design
    raw, report=fixture_card(); im=Image.open(io.BytesIO(raw));d=ImageDraw.Draw(im)
    d.rectangle((100,1140,500,1169),fill='#003770');buf=io.BytesIO();im.save(buf,format='PNG');raw=buf.getvalue()
    report['cards'][0]['sha256']=hashlib.sha256(raw).hexdigest()
    with pytest.raises(BundleError,match='ink'):validate_design([(Path('card.png'),raw)],report,'STORY')


@pytest.mark.parametrize('placement',['STORY','SPOTLIGHT','SAVED_STORY'])
@pytest.mark.parametrize('endpoint',['/post','/post/','/post/existing'])
def test_all_placements_and_update_endpoints_require_gate(monkeypatch,placement,endpoint):
    monkeypatch.setenv('BUNDLE_API_KEY','offline');monkeypatch.setenv('BUNDLE_TEAM_ID','team')
    with patch('publishing_v2.bundle_api.request',return_value={'id':'unexpected'}) as network:
        with pytest.raises(BundleError,match='Design'):
            BundleClient().call(endpoint,'POST',json.dumps({'data':{'SNAPCHAT':{'type':placement,'uploadIds':['unreviewed']}}}).encode())
        network.assert_not_called()


def test_legacy_helpers_block_before_transport():
    import importlib.util
    spec=importlib.util.spec_from_file_location('publication_gate_legacy',Path('news_bot.py'))
    news_bot=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(news_bot)
    with patch('urllib.request.urlopen') as network:
        for fn,args in [(news_bot._bundle_post,('title','file.png')),
                        (news_bot.post_story,('title',[], 'file.png')),
                        (news_bot._zernio,('posts',{})),(news_bot._ayrshare,('post',{}))]:
            with pytest.raises(BundleError,match='Design'):fn(*args)
        network.assert_not_called()


def approved_package(tmp_path,monkeypatch,placements=None):
    raw,report=fixture_card();placements=placements or ['STORY']
    report['destinations']=placements
    report['review']['overlay_destinations']={p:'offline '+p+' overlay' for p in placements}
    monkeypatch.chdir(tmp_path)
    p=tmp_path/'package';p.mkdir();(p/'card.png').write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    manifest={'format':'owner-generated-design-v1','approved':True,'account':'executivesaudi',
              'expires_at':'2099-01-01T00:00:00+00:00','title':'offline information',
              'content_type':'information','approved_destinations':placements,
              'owner_review':{'reference':'offline fixture approval only','reviewed_at':'2026-01-01T00:00:00+00:00','approved_media_sha256':[digest]},
              'media':[{'kind':'info','path':'package/card.png','sha256':digest,
                        'provenance':{'provider':'openai_imagegen','usage':'illustration','third_party_assets':False,'library_file_id':'libfile_'+'a'*32}}]}
    (p/'manifest.json').write_text(json.dumps(manifest));(p/'design-review.json').write_text(json.dumps(report))
    from publishing_v2.bundle_api import load_package
    return load_package('package/manifest.json')[2]


def test_real_boundary_accepts_review_then_rejects_changed_report(tmp_path,monkeypatch):
    media=approved_package(tmp_path,monkeypatch)
    monkeypatch.setenv('BUNDLE_API_KEY','offline');monkeypatch.setenv('BUNDLE_TEAM_ID','team')
    sent=[]
    def transport(url,headers,method='GET',data=None):
        sent.append((url,data))
        return {'id':'upload' if url.endswith('/upload') else 'post'}
    with patch('publishing_v2.bundle_api.request',side_effect=transport):
        c=BundleClient();u=c.upload(media[0]);assert c.create('title',u)=='post'
        payload=json.loads(sent[-1][1]);assert payload['data']['SNAPCHAT']['storyDuration']=='ONE_WEEK'
        (media.path.parent/'design-review.json').write_text('{}')
        with pytest.raises(BundleError):c.create('title',u)
        assert len(sent)==2


def test_archive_needs_destination_specific_review(tmp_path,monkeypatch):
    media=approved_package(tmp_path,monkeypatch,['STORY','SAVED_STORY'])
    from publishing_v2.saved_story_api import SavedClient
    monkeypatch.setenv('BUNDLE_API_KEY','offline');monkeypatch.setenv('BUNDLE_TEAM_ID','team')
    source={'id':'source-post','teamId':'team','status':'POSTED','data':{'SNAPCHAT':{'type':'STORY','uploadIds':['old-upload']}}}
    with patch('publishing_v2.bundle_api.request',side_effect=lambda url,*a,**k: source if url.endswith('/source-post') else {'id':'archived'}) as transport, \
         patch('publishing_v2.bundle_api.GitHubJournal') as journal:
        journal.return_value.read.return_value={'1':{'status':'POSTED','post_id':'source-post','upload_id':'old-upload'}}
        c=SavedClient()
        with pytest.raises(BundleError):c.create_saved('identity','title',['old-upload'])
        transport.assert_not_called()
        c.authorize_existing(media,['old-upload'],'SAVED_STORY')
        assert c.create_saved('identity','title',['old-upload'])=='archived'


def test_raw_upload_and_wrong_existing_mapping_are_rejected(tmp_path,monkeypatch):
    media=approved_package(tmp_path,monkeypatch,['STORY','SAVED_STORY'])
    monkeypatch.setenv('BUNDLE_API_KEY','offline');monkeypatch.setenv('BUNDLE_TEAM_ID','team')
    with patch('publishing_v2.bundle_api.request',return_value={'id':'unexpected'}) as network, \
         patch('publishing_v2.bundle_api.GitHubJournal') as journal:
        journal.return_value.read.return_value={'1':{'status':'POSTED','post_id':'source','upload_id':'actual'}}
        c=BundleClient()
        with pytest.raises(BundleError):c.call('/upload','POST',b'unreviewed')
        with pytest.raises(BundleError):c.authorize_existing(media,['wrong'],'SAVED_STORY')
        network.assert_not_called()


def test_pending_receipt_can_reconcile_without_current_design_report():
    from publishing_v2.bundle_api import publish
    class Journal:
        def read(self):return {'1':{'post_id':'existing','status':'PENDING'}}
        def save(self,state):assert state['1']['status']=='POSTED'
    class ReadOnlyClient:
        def wait(self,post):assert post=='existing'
    publish(ReadOnlyClient(),Journal(),'title',[(Path('old.png'),b'old')])


def test_wrong_flat_brand_colors_fail_even_when_text_is_correct():
    from publishing_v2.design_contract import validate_design
    for color,box in [('black',(800,130,1000,145)),('white',(60,1665,1020,1679))]:
        raw,report=fixture_card();im=Image.open(io.BytesIO(raw));ImageDraw.Draw(im).rectangle(box,fill=color)
        buf=io.BytesIO();im.save(buf,format='PNG');raw=buf.getvalue()
        report['cards'][0]['sha256']=hashlib.sha256(raw).hexdigest()
        with pytest.raises(BundleError,match='palette'):validate_design([(Path('card.png'),raw)],report,'STORY')


def test_wrong_dominant_ink_cannot_hide_behind_four_correct_pixels():
    from publishing_v2.design_contract import validate_design
    raw,report=fixture_card();im=Image.open(io.BytesIO(raw));d=ImageDraw.Draw(im)
    d.rectangle((104,1140,500,1169),fill='#003770');buf=io.BytesIO();im.save(buf,format='PNG');raw=buf.getvalue()
    report['cards'][0]['sha256']=hashlib.sha256(raw).hexdigest()
    with pytest.raises(BundleError):validate_design([(Path('card.png'),raw)],report,'STORY')


def test_mislabeled_challenge_png_fails_at_upload_boundary(tmp_path,monkeypatch):
    media=approved_package(tmp_path,monkeypatch)
    data=json.loads(media.path.read_text());data['title']='challenge';media.path.write_text(json.dumps(data))
    monkeypatch.setenv('BUNDLE_API_KEY','offline');monkeypatch.setenv('BUNDLE_TEAM_ID','team')
    with patch('publishing_v2.bundle_api.request') as network:
        with pytest.raises(BundleError):BundleClient().upload(media[0])
        network.assert_not_called()


def test_each_destination_needs_its_own_overlay_evidence():
    from publishing_v2.design_contract import validate_design
    raw,report=fixture_card();report['destinations'].append('SAVED_STORY')
    with pytest.raises(BundleError):validate_design([(Path('card.png'),raw)],report,'SAVED_STORY')


def test_empty_approved_destinations_cannot_print_validated(tmp_path,monkeypatch,capsys):
    media=approved_package(tmp_path,monkeypatch)
    data=json.loads(media.path.read_text());data['approved_destinations']=[];media.path.write_text(json.dumps(data))
    monkeypatch.setattr('sys.argv',['bundle_api','validate','--manifest',str(media.path)])
    from publishing_v2.bundle_api import main
    with pytest.raises(SystemExit):main()
    assert 'validated_not_published' not in capsys.readouterr().out


def test_live_settings_change_invalidates_old_report(tmp_path,monkeypatch):
    import base64
    media=approved_package(tmp_path,monkeypatch)
    monkeypatch.setenv('GITHUB_ACTIONS','true');monkeypatch.setenv('GITHUB_TOKEN','offline')
    monkeypatch.setenv('GITHUB_REPOSITORY','khalidonline/daily-news-snap')
    from publishing_v2.design_contract import DeliveryReview
    def response(url,*a,**k):
        raw=b'new master' if 'design-settings.json' in url else media.path.read_bytes()
        return {'encoding':'base64','content':base64.b64encode(raw).decode()}
    with patch('publishing_v2.bundle_api.request',side_effect=response):
        with pytest.raises(BundleError,match='stale'):DeliveryReview(media,'STORY')


def test_decoded_challenge_frame_palette_is_checked(tmp_path):
    from publishing_v2.design_contract import _video_design
    settings=json.loads(Path('publishing_v2/design-settings.json').read_text())
    im=Image.new('RGB',(1080,1920),'#F7F7EB');d=ImageDraw.Draw(im)
    d.rectangle((800,130,1000,145),fill='#0C5F46');d.rectangle((60,1635,1020,1710),fill='#FDE5EB')
    blocks=[]
    for role,y,c in [('headline',280,'#B60E32'),('question',900,'#0C5F46'),('option',1100,'#0B3656'),('option',1200,'#0B3656'),('cta',1650,'#B60E32')]:
        d.rectangle((100,y,500,y+29),fill=c);blocks.append({'role':role,'box':[60,y-1,1020,y+35],'color':c,'line_count':1})
    p=tmp_path/'frame.png';im.save(p)
    design={'at':.5,'sha256':'test','blocks':blocks,'palette_samples':{'green':[810,131,990,144],'background':[100,50,200,70],'cta_background':[700,1640,800,1650]}}
    data={'video_review':{'frames':[{'path':str(p),'at':.5,'sha256':'test'}]}}
    _video_design({'frame_designs':[design]},data,settings)
    d.rectangle((100,1100,500,1129),fill='#003770');im.save(p)
    with pytest.raises(BundleError):_video_design({'frame_designs':[design]},data,settings)


def test_cli_reconciles_expired_pending_without_reupload(tmp_path,monkeypatch,capsys):
    media=approved_package(tmp_path,monkeypatch)
    data=json.loads(media.path.read_text());data['expires_at']='2000-01-01T00:00:00+00:00';media.path.write_text(json.dumps(data))
    monkeypatch.setattr('sys.argv',['bundle_api','publish','--manifest',str(media.path)])
    from publishing_v2.bundle_api import main
    class ReadOnlyClient:
        def check(self):pass
        def wait(self,post):assert post=='pending-post'
    with patch('publishing_v2.bundle_api.BundleClient',return_value=ReadOnlyClient()),patch('publishing_v2.bundle_api.GitHubJournal') as journal:
        journal.return_value.read.return_value={'1':{'post_id':'pending-post','status':'PENDING','placement':'STORY'}}
        main()
        assert journal.return_value.save.call_args.args[0]['1']['status']=='POSTED'
    assert 'reconciled' in capsys.readouterr().out
