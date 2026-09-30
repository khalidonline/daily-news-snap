import io
import json
import unittest
from unittest.mock import patch
from publishing_v2.bundle_api import BundleClient

class StoryDurationTests(unittest.TestCase):
    def test_story_creation_requests_one_week_at_provider_boundary(self):
        # Missing/wrong duration silently gives Snapchat's 24-hour default.
        with patch.dict('os.environ', {'BUNDLE_API_KEY':'test-key','BUNDLE_TEAM_ID':'team'}):
            with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"id":"post"}')) as opened:
                self.assertEqual(BundleClient().create('title', 'upload'), 'post')
        payload=json.loads(opened.call_args.args[0].data)
        self.assertEqual(payload['data']['SNAPCHAT'], {
            'type':'STORY','uploadIds':['upload'],'storyDuration':'ONE_WEEK'})
        self.assertEqual(payload['socialAccountTypes'], ['SNAPCHAT'])

if __name__ == '__main__': unittest.main()
