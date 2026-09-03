from pathlib import Path


WORKFLOW = Path('.github/workflows/story-approved-to-telegram.yml')


def test_approval_requires_run_artifact_and_deck_hash():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'artifact_id:' in text
    assert 'deck_hash:' in text
    assert 'APPROVED_STORY_ARTIFACT_ID' in text
    assert 'APPROVED_STORY_DECK_HASH' in text


def test_delivery_downloads_exact_artifact_id_not_name_only():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'actions/artifacts/$APPROVED_STORY_ARTIFACT_ID/zip' in text
    assert '--name "story-review-$APPROVED_STORY_RUN_ID"' not in text


def test_delivery_verifies_artifact_belongs_to_review_run_and_deck_hash():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'workflow_run.id' in text
    assert 'APPROVED_STORY_RUN_ID' in text
    assert 'story-review.json' in text
    assert 'deck_hash' in text
    assert 'APPROVED_STORY_DECK_HASH' in text


def test_legacy_numeric_pointer_fails_closed():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'Legacy numeric-only Story approval pointers are rejected' in text
