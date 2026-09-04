import os
import subprocess
import sys
import unittest


class StoryModelRoutingTests(unittest.TestCase):
    def test_default_editorial_model_is_sonnet(self):
        env = os.environ.copy()
        env.pop("STORY_MODEL", None)
        output = subprocess.check_output(
            [sys.executable, "-c", "import story_bot; print(story_bot.STORY_MODEL)"],
            env=env,
            text=True,
        )
        self.assertEqual(output.strip().splitlines()[-1], "claude-sonnet-5")


if __name__ == "__main__":
    unittest.main()
