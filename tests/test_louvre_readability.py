import copy
import json
from pathlib import Path

import pytest

from publishing_v2.readability import validate_readability, ReadabilityError

ROOT = Path(__file__).resolve().parents[1]
HASH = 'd42468017c71bd3000079f46896a5ac3e231c26774dddac893f18db42593be91'


@pytest.fixture
def approved():
    image = ROOT / 'approved/louvre-20261024/card.png'
    report = {
        'version': 1, 'typography_profile': 'owner-reviewed-louvre-20261024',
        'visual_review': {'approved': True, 'reference': 'Khalid approved exact final preview and five-point exception'},
        'cards': [{'sha256': HASH, 'bullet_line_counts': [2, 2, 2, 2, 2]}],
    }
    return report, [(image, image.read_bytes())]


def check(tmp_path, report, media):
    path = tmp_path / 'readability.json'
    path.write_text(json.dumps(report))
    return validate_readability(path, media)


def test_exact_owner_reviewed_five_point_raster_is_accepted(tmp_path, approved):
    report, media = approved
    assert check(tmp_path, report, media)['card_count'] == 1


@pytest.mark.parametrize('mutation', ['bytes', 'approval', 'hash', 'lines', 'second_card'])
def test_exception_cannot_authorize_changed_or_unreviewed_art(tmp_path, approved, mutation):
    report, media = copy.deepcopy(approved)
    if mutation == 'bytes': media[0] = (media[0][0], media[0][1] + b'changed')
    if mutation == 'approval': report['visual_review']['approved'] = False
    if mutation == 'hash': report['cards'][0]['sha256'] = '0' * 64
    if mutation == 'lines': report['cards'][0]['bullet_line_counts'][0] = 3
    if mutation == 'second_card':
        media *= 2
        report['cards'] *= 2
    with pytest.raises(ReadabilityError): check(tmp_path, report, media)
