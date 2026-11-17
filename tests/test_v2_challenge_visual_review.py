"""Synthetic exact-byte fixtures test integrity, never actual editorial judgment."""
import copy
import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess

import pytest
from PIL import Image, ImageChops, ImageStat

from publishing_v2.bundle_api import ApprovedMedia, BundleError, publish
from tests.test_v2_bundle import Client, Journal
from publishing_v2.design_contract import SETTINGS

GEOMETRY = json.loads(SETTINGS.read_bytes())['challenges']['approved_template_v2']['geometry']
BOXES = [GEOMETRY['left_photo'], GEOMETRY['right_photo']]


def test_new_shared_challenge_missing_image_evidence_stops_before_capacity(tmp_path, monkeypatch):
    monkeypatch.setattr('publishing_v2.bundle_api.check_delivery_approval', lambda media: None)
    monkeypatch.setattr('publishing_v2.challenge_contract.validate_challenge', lambda title, media: None)
    client, journal = Client(), Journal()
    client.ensure_capacity = lambda count: pytest.fail('capacity queried before image review')
    media = ApprovedMedia([(tmp_path/'final.mp4', b'movie')], Path.cwd()/'manifest.json',
                          {'content_type': 'challenge'})
    with pytest.raises(BundleError, match='image review'):
        publish(client, journal, 'challenge', media)
    assert client.sent == [] and journal.state == {}


def module():
    return importlib.import_module('publishing_v2.challenge_visual_review')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, data):
    raw = json.dumps(data, ensure_ascii=False).encode()
    Path(path).write_bytes(raw)
    return {'path': str(path), 'sha256': sha(raw)}


@pytest.fixture(scope='module')
def movies(tmp_path_factory):
    root = tmp_path_factory.mktemp('image-review-clips')
    result = {}
    for kind, colors in [('contrast', ('#90c0e0', '#50a030')), ('dark', ('#080808', '#101010')),
                         ('similar', ('#90c0e0', '#90c0e0'))]:
        image = Image.new('RGB', (1080, 1920), 'white')
        image.paste(colors[0], tuple(BOXES[0]))
        image.paste(colors[1], tuple(BOXES[1]))
        image.save(root/(kind+'.png'))
        movie = root/(kind+'.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-loop', '1', '-i', str(root/(kind+'.png')),
                        '-t', '12', '-r', '2', '-c:v', 'libx264', '-threads', '1',
                        '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', str(movie)],
                       check=True, capture_output=True)
        result[kind] = movie.read_bytes()
    return result


def fixture(tmp_path, monkeypatch, movies, kind='contrast'):
    monkeypatch.chdir(tmp_path)
    Path('package').mkdir()
    raw = movies[kind]
    Path('package/final.mp4').write_bytes(raw)
    sources = []
    for i, color in enumerate(('blue', 'green')):
        p = Path(f'package/source-{i}.png')
        Image.new('RGB', (400, 400), color).save(p)
        sources.append({'path': str(p), 'sha256': sha(p.read_bytes())})
    source_manifest = write_json('package/source-approval.json', {'media': [{'source_assets': sources}]})
    frames = []
    decoded = []
    for at in (0.5, 11.5):
        p = Path(f'package/frame-{at}.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(at), '-i', 'package/final.mp4',
                        '-frames:v', '1', '-threads', '1', str(p)], check=True, capture_output=True)
        frames.append({'at': at, 'path': str(p), 'sha256': sha(p.read_bytes())})
        decoded.append(Image.open(p).convert('RGB'))
    photos = []
    crop_pairs = [[], []]
    for i, box in enumerate(copy.deepcopy(BOXES)):
        crops = []
        for frame, at in zip(decoded, (0.5, 11.5)):
            crop = frame.crop(box)
            crop_pairs[i].append(crop)
            gray = crop.convert('L')
            hist = gray.histogram()
            crops.append({'at': at, 'rgb_sha256': sha(crop.tobytes()),
                          'mean_luma': round(ImageStat.Stat(gray).mean[0], 6),
                          'dark_fraction': round(sum(hist[:40])/(crop.width*crop.height), 6)})
        photos.append({'source': sources[i], 'box': box, 'crops': crops, 'assessment': 'passed',
                       'observations': {k: f'Synthetic fixture {i} {k} explicitly describes the visible colored panel for integrity testing only.'
                                        for k in ('subject', 'relevance', 'crop_visibility', 'brightness', 'spoiler_risk')}})
    pair_metrics = []
    for a, b, at in zip(*crop_pairs, (0.5, 11.5)):
        diff = ImageChops.difference(a.resize((32, 32), Image.Resampling.BILINEAR),
                                     b.resize((32, 32), Image.Resampling.BILINEAR))
        pair_metrics.append({'at': at, 'similarity': round(1-sum(ImageStat.Stat(diff).mean)/(3*255), 6)})
    report = {'version': 1, 'video_sha256': sha(raw), 'source_manifest': source_manifest,
              'source_assets': sources, 'reviewer': 'Synthetic test fixture, not an actual visual review',
              'assessment': 'passed', 'mobile_width': 390,
              'mobile_layout': 'Synthetic fixture mobile layout note covers both panels at the required review scale.',
              'photos': photos, 'pair_metrics': pair_metrics,
              'pair': {'assessment': 'passed',
                       'distinct_information': 'The blue and green synthetic panels offer different color information in this integrity fixture.',
                       'answer_spoiler': 'Neither synthetic colored panel contains a written answer or a location label in this fixture.'}}
    data = {'content_type': 'challenge', 'video_review': {'video_sha256': sha(raw),
            'source_manifest': source_manifest, 'frames': frames,
            'image_review': write_json('package/image-review.json', report)}}
    media = ApprovedMedia([(tmp_path/'package/final.mp4', raw)], tmp_path/'package/manifest.json', data)
    return media, report


def seal(media, report):
    media.snapshot['video_review']['image_review'] = write_json('package/image-review.json', report)


def test_valid_contrasting_pair_and_diagnostics(tmp_path, monkeypatch, movies):
    media, report = fixture(tmp_path, monkeypatch, movies)
    module().validate_challenge_images(media)
    diagnostics = module().image_review_diagnostics(media, [{'source': p['source'], 'box': p['box']} for p in report['photos']])
    assert diagnostics == {'photos': [{'source': p['source'], 'box': p['box'], 'crops': p['crops']} for p in report['photos']],
                           'pair_metrics': report['pair_metrics']}
    assert 'assessment' not in diagnostics and 'observations' not in diagnostics['photos'][0]


@pytest.mark.parametrize('fault', ['missing_report','stale_report','video','review_video','source_manifest',
    'source','crop','frame','metric','missing_photo','duplicate_photo','duplicate_source_hash',
    'uncovered_source','missing_observation','generic_observation','copied_observation','false_status',
    'mobile_width','pair_note','spoiler_note','path','absolute_path','symlink','nan_box','bool_box','outside_box',
    'overlap_box','report_type','photos_type','crops_type','source_type','nan_metric','bool_version'])
def test_invalid_evidence_fails_closed(tmp_path, monkeypatch, movies, fault):
    media, report = fixture(tmp_path, monkeypatch, movies)
    if fault == 'missing_report': del media.snapshot['video_review']['image_review']; report = None
    elif fault == 'stale_report': Path('package/image-review.json').write_bytes(b'{}'); report = None
    elif fault == 'video': media[0] = (media[0][0], b'changed')
    elif fault == 'review_video': media.snapshot['video_review']['video_sha256'] = '0'*64
    elif fault == 'source_manifest': Path('package/source-approval.json').write_text('{}')
    elif fault == 'source': Path(report['photos'][0]['source']['path']).write_bytes(b'changed')
    elif fault == 'crop': report['photos'][0]['crops'][0]['rgb_sha256'] = '0'*64
    elif fault == 'frame':
        p = Path(media.snapshot['video_review']['frames'][0]['path'])
        Image.new('RGB', (1080,1920), 'red').save(p)
        media.snapshot['video_review']['frames'][0]['sha256'] = sha(p.read_bytes())
    elif fault == 'metric': report['photos'][0]['crops'][0]['mean_luma'] += 1
    elif fault == 'missing_photo': report['photos'].pop()
    elif fault == 'duplicate_photo': report['photos'][1] = copy.deepcopy(report['photos'][0])
    elif fault == 'duplicate_source_hash':
        sources = report['source_assets']; sources[1]['sha256'] = sources[0]['sha256']
        Path(sources[1]['path']).write_bytes(Path(sources[0]['path']).read_bytes())
        spec = write_json('package/source-approval.json', {'media': [{'source_assets': sources}]})
        media.snapshot['video_review']['source_manifest'] = report['source_manifest'] = spec
    elif fault == 'uncovered_source': report['source_assets'].pop()
    elif fault == 'missing_observation': del report['photos'][0]['observations']['subject']
    elif fault == 'generic_observation': report['photos'][0]['observations']['subject'] = 'passed looks good'
    elif fault == 'copied_observation': report['photos'][1]['observations']['subject'] = report['photos'][0]['observations']['subject']
    elif fault == 'false_status': report['photos'][0]['assessment'] = False
    elif fault == 'mobile_width': report['mobile_width'] = 1080
    elif fault == 'pair_note': report['pair']['distinct_information'] = ''
    elif fault == 'spoiler_note': del report['pair']['answer_spoiler']
    elif fault == 'path': report['photos'][0]['source']['path'] = '../outside.png'
    elif fault == 'absolute_path': media.snapshot['video_review']['image_review']['path'] = str(tmp_path/'package/image-review.json'); report = None
    elif fault == 'symlink':
        p=Path('package/image-review.json'); p.rename('package/real.json'); p.symlink_to('real.json'); report=None
    elif fault == 'nan_box': report['photos'][0]['box'][0] = float('nan')
    elif fault == 'bool_box': report['photos'][0]['box'][0] = True
    elif fault == 'outside_box': report['photos'][0]['box'][2] = 1081
    elif fault == 'overlap_box': report['photos'][1]['box'] = report['photos'][0]['box']
    elif fault == 'report_type': report = []
    elif fault == 'photos_type': report['photos'] = 'invalid'
    elif fault == 'crops_type': report['photos'][0]['crops'] = None
    elif fault == 'source_type': report['photos'][0]['source'] = []
    elif fault == 'nan_metric': report['pair_metrics'][0]['similarity'] = float('nan')
    elif fault == 'bool_version': report['version'] = True
    if report is not None: seal(media, report)
    with pytest.raises(BundleError, match='image review'):
        module().validate_challenge_images(media)


@pytest.mark.parametrize('kind,resolution', [('dark','low_light_resolution'), ('similar','similarity_resolution')])
def test_diagnostic_warning_needs_substantive_resolution(tmp_path, monkeypatch, movies, kind, resolution):
    media, report = fixture(tmp_path, monkeypatch, movies, kind)
    with pytest.raises(BundleError, match='resolution'):
        module().validate_challenge_images(media)
    targets = report['photos'] if kind == 'dark' else [report['pair']]
    for target in targets: target[resolution] = 'pass'
    seal(media, report)
    with pytest.raises(BundleError, match='resolution'):
        module().validate_challenge_images(media)
    # A dark fixture also has similar dark regions; address both diagnostics.
    for i, target in enumerate(targets):
        target[resolution] = f'Synthetic diagnostic resolution {i} records the visible panel limitation rather than asserting semantic approval.'
    if kind == 'dark': report['pair']['similarity_resolution'] = 'Both dark fixture panels are intentionally close in appearance; this is only an integrity test resolution.'
    seal(media, report)
    module().validate_challenge_images(media)


@pytest.mark.parametrize('status', ['POSTED','SENDING'])
def test_known_existing_operation_does_not_need_new_image_review(tmp_path, monkeypatch, status):
    client, journal = Client(), Journal()
    journal.state = {'1': {'status': status, 'post_id': 'known'}}
    monkeypatch.setattr('publishing_v2.bundle_api.check_delivery_approval', lambda media: None)
    media = ApprovedMedia([(tmp_path/'final.mp4', b'old')], Path.cwd()/'manifest.json', {'content_type':'challenge'})
    publish(client, journal, 'challenge', media)
    assert client.sent == [] and journal.state['1']['status'] == 'POSTED'


def test_unknown_intent_still_blocks_without_new_image_evidence(tmp_path, monkeypatch):
    client, journal = Client(), Journal(); journal.state={'1': {'status':'SENDING'}}
    monkeypatch.setattr('publishing_v2.bundle_api.check_delivery_approval', lambda media: None)
    with pytest.raises(BundleError, match='Uncertain'):
        publish(client,journal,'challenge',[(tmp_path/'final.mp4',b'old')])
    assert client.sent == []


def test_offline_validate_requires_image_evidence(tmp_path, monkeypatch):
    delivery = importlib.import_module('publishing_v2.deliver_challenge')
    media = ApprovedMedia([(tmp_path/'final.mp4', b'exact')], Path.cwd()/'manifest.json', {'content_type':'challenge'})
    monkeypatch.setattr(delivery, 'validate_package', lambda *args: ('id','challenge',media,{'not_before':'2099-01-01T00:00:00Z'}))
    monkeypatch.setattr(delivery, 'ChallengeClient', lambda *args: pytest.fail('offline validator initialized provider'))
    with pytest.raises(BundleError, match='image review'):
        delivery.run('sample-package',sha(b'exact'),action='validate')


def test_boolean_diagnostic_is_not_a_numeric_measurement(tmp_path, monkeypatch, movies):
    media, report = fixture(tmp_path, monkeypatch, movies)
    assert report['photos'][0]['crops'][0]['dark_fraction'] == 0
    report['photos'][0]['crops'][0]['dark_fraction'] = False
    seal(media, report)
    with pytest.raises(BundleError, match='diagnostic'):
        module().validate_challenge_images(media)


@pytest.mark.parametrize('placement', ['STORY', 'SPOTLIGHT'])
def test_actual_stale_crop_blocks_each_new_destination_before_mutation(tmp_path, monkeypatch, movies, placement):
    media, report = fixture(tmp_path, monkeypatch, movies)
    media.snapshot['approved_destinations'] = ['STORY','SPOTLIGHT']
    report['photos'][0]['crops'][0]['rgb_sha256'] = '0'*64
    seal(media, report)
    monkeypatch.setattr('publishing_v2.bundle_api.check_delivery_approval', lambda media: None)
    monkeypatch.setattr('publishing_v2.challenge_contract.validate_challenge', lambda title, media: None)
    client, journal = Client(), Journal()
    client.ensure_capacity = lambda count: pytest.fail('capacity before valid review')
    client.upload = lambda item: pytest.fail('upload before valid review')
    with pytest.raises(BundleError, match='crop'):
        publish(client,journal,'challenge',media,placement=placement)
    assert client.sent == [] and journal.state == {}


def test_valid_review_allows_new_shared_send(tmp_path, monkeypatch, movies):
    media, report = fixture(tmp_path, monkeypatch, movies)
    monkeypatch.setattr('publishing_v2.bundle_api.check_delivery_approval', lambda media: None)
    monkeypatch.setattr('publishing_v2.challenge_contract.validate_challenge', lambda title, media: None)
    client, journal = Client(), Journal()
    publish(client, journal, 'challenge', media)
    assert len(client.sent) == 1 and journal.state['1']['status'] == 'POSTED'


def test_bright_template_background_cannot_substitute_for_photo_regions(tmp_path, monkeypatch, movies):
    media, report = fixture(tmp_path, monkeypatch, movies)
    photos = [{'source': p['source'], 'box': box} for p, box in zip(report['photos'],
              ([100, 100, 300, 300], [600, 100, 800, 300]))]
    with pytest.raises(BundleError, match='geometry'):
        module().image_review_diagnostics(media, photos)
