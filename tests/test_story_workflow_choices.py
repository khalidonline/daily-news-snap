import json
import re
import unittest
from pathlib import Path


class StoryWorkflowChoiceTests(unittest.TestCase):
    def setUp(self):
        self.workflow = Path('.github/workflows/story.yml').read_text(encoding='utf-8')
        self.ready = json.loads(Path('state/ready_to_post.json').read_text(encoding='utf-8'))['stories']

    def test_manual_dropdown_matches_ready_pool(self):
        match = re.search(
            r"ready_story:\n(?:.*\n)*?\s+options:\n(?P<options>(?:\s+- .*\n)+)",
            self.workflow,
        )
        self.assertIsNotNone(match, 'ready_story choice input with options is required')
        options = [line.strip()[2:].strip().strip('"') for line in match.group('options').splitlines()]
        self.assertEqual(options, self.ready)

    def test_custom_story_overrides_dropdown_and_post_is_explicit(self):
        self.assertIn('custom_story:', self.workflow)
        self.assertIn("STORY: ${{ inputs.custom_story || inputs.ready_story || '' }}", self.workflow)
        self.assertIn('post:', self.workflow)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.post", self.workflow)


if __name__ == '__main__':
    unittest.main()
