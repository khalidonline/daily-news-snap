import unittest
from pathlib import Path


class TopicWorkflowImagePolicyTests(unittest.TestCase):
    def test_topic_brief_prioritizes_relevant_curated_artifacts_over_reuse_rest(self):
        workflow = Path('.github/workflows/topic.yml').read_text(encoding='utf-8')
        self.assertIn('LIBRARY_REUSE_DAYS: "0"', workflow)


if __name__ == '__main__':
    unittest.main()
