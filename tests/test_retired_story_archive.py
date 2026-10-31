import hashlib
import json
from pathlib import Path


def test_retired_route_is_recoverable_but_not_executable_or_collected():
    root=Path(__file__).resolve().parents[1]
    manifest=root/'archive/retired-story-telegram/manifest.json'
    assert manifest.exists(), 'retired route not archived yet'
    record=json.loads(manifest.read_text())
    expected={
        '.github/workflows-disabled/story-approved-to-telegram.yml',
        '.github/workflows-disabled/story-approval-binding-ci.yml',
        'tests/test_story_approval_artifact_binding.py',
    }
    assert {r['original'] for r in record['files']}==expected
    for row in record['files']:
        assert not (root/row['original']).exists()
        archived=root/row['archived']
        assert archived.suffix=='.txt'
        assert hashlib.sha256(archived.read_bytes()).hexdigest()==row['sha256']
    assert record['base_commit']=='9171af09a10b9faf2051c50bdeace19aaa360054'
    assert record['restore_instructions']


def test_shared_renderer_and_current_template_tests_remain():
    root=Path(__file__).resolve().parents[1]
    assert (root/'news_bot.py').exists()
    assert (root/'tests/test_fixed_information_template.py').exists()
