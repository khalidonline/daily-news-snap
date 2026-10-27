import io
import json
import unittest
from unittest.mock import patch
from publishing_v2.bundle_api import BundleClient

class StoryDurationTests(unittest.TestCase):
    def test_story_creation_requests_one_week_at_provider_boundary(self):
        # Missing/wrong duration silently gives Snapchat's 24-hour default.
        with patch.dict('os.environ', {'BUNDLE_API_KEY':'test-key','BUNDLE_TEAM_ID':'team'}):
            # Payload unit test. Real transport design-gate coverage is in
            # test_v2_design_contract with a valid final-byte review.
            with patch.object(BundleClient, 'call', return_value={'id':'post'}) as opened:
                self.assertEqual(BundleClient().create('title', 'upload'), 'post')
        payload=json.loads(opened.call_args.args[2])
        self.assertEqual(payload['data']['SNAPCHAT'], {
            'type':'STORY','uploadIds':['upload'],'storyDuration':'ONE_WEEK'})
        self.assertEqual(payload['socialAccountTypes'], ['SNAPCHAT'])

if __name__ == '__main__': unittest.main()
