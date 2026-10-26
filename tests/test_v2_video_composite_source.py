import copy
import hashlib
import json
import pytest
from publishing_v2.bundle_api import BundleError
from publishing_v2.reviewed_video import validate_reviewed_video
from tests.test_v2_owner_composite import OwnerCompositeTests
from tests.test_v2_reviewed_video import approved_package

@pytest.mark.parametrize('tamper', [False, True])
def test_video_accepts_reviewed_composite_but_rejects_changed_source(tmp_path, tamper):
    fixture = OwnerCompositeTests()
    fixture.setUp()
    try:
        root, video = approved_package()
        source = copy.deepcopy(fixture.data)
        # Copy the reviewed photo and card into the video fixture's repository.
        for name in ('card.png', 'source.png'):
            (tmp_path/name).write_bytes((fixture.root/name).read_bytes())
        for row in video['media'] + video['video_review']['frames'] + [video['video_review']['audio_reference']]:
            dest = tmp_path/row['path']; dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((root/row['path']).read_bytes())
        raw = json.dumps(source).encode()
        (tmp_path/'source-approval.json').write_bytes(raw)
        video['video_review']['source_manifest'] = {'path':'source-approval.json', 'sha256':hashlib.sha256(raw).hexdigest()}
        if tamper:
            (tmp_path/'source.png').write_bytes(b'changed photo')
            with pytest.raises(BundleError, match='Composite: asset changed'):
                validate_reviewed_video(video, tmp_path)
        else:
            assert len(validate_reviewed_video(video, tmp_path)[2]) == 1
    finally:
        fixture.doCleanups()
