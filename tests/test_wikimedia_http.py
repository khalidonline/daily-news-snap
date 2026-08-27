import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.wikimedia_http import (
    SourceRateLimited, require_available, reset_cooldown, terminal_rate_limit,
)


class WikimediaCooldownTests(unittest.TestCase):
    def tearDown(self):
        reset_cooldown()

    def test_retry_after_sixty_remains_blocked_after_thirty_one_seconds(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "cooldown.json"
            created = terminal_rate_limit("download", 60, now=100, path=state)
            self.assertTrue(created.source_cooldown_activated)
            self.assertEqual(created.retry_after_seconds, 30)  # telemetry only

            with self.assertRaises(SourceRateLimited) as suppressed:
                require_available("discovery", now=131, path=state)
            self.assertEqual(suppressed.exception.retry_after_seconds, 29)
            self.assertFalse(suppressed.exception.source_cooldown_activated)

            require_available("discovery", now=160, path=state)
            self.assertFalse(state.exists())

    def test_separately_initialized_process_observes_shared_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "cooldown.json"
            env = {**os.environ, "WIKIMEDIA_COOLDOWN_STATE": str(state)}
            writer = subprocess.run(
                [sys.executable, "-c",
                 "from tools.wikimedia_http import terminal_rate_limit; "
                 "terminal_rate_limit('download', 60)"],
                cwd=Path(__file__).parents[1], env=env, check=False,
            )
            reader = subprocess.run(
                [sys.executable, "-c",
                 "from tools.wikimedia_http import require_available, SourceRateLimited; "
                 "\ntry: require_available('discovery')"
                 "\nexcept SourceRateLimited: raise SystemExit(0)"
                 "\nraise SystemExit(1)"],
                cwd=Path(__file__).parents[1], env=env, check=False,
            )
            self.assertEqual(writer.returncode, 0)
            self.assertEqual(reader.returncode, 0)
            self.assertGreater(json.loads(state.read_text())["blocked_until"], 0)

    def test_malformed_state_blocks_safely_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "cooldown.json"
            state.write_text("not-json", encoding="utf-8")
            with self.assertRaises(SourceRateLimited) as caught:
                require_available("download", now=100, path=state)
            self.assertFalse(caught.exception.source_cooldown_activated)
            self.assertEqual(caught.exception.retry_after_seconds, 30)
            self.assertEqual(state.read_text(encoding="utf-8"), "not-json")
            # A later child still fails closed rather than treating the state
            # as an expired synthetic 30-second cooldown.
            with self.assertRaises(SourceRateLimited):
                require_available("download", now=1000, path=state)

    def test_expired_state_is_removed_and_does_not_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "cooldown.json"
            state.write_text('{"blocked_until": 99}\n', encoding="utf-8")
            require_available("download", now=100, path=state)
            self.assertFalse(state.exists())

    def test_terminal_long_delay_never_sleeps(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "cooldown.json"
            terminal_rate_limit("download", 3600, now=100, path=state)
            self.assertEqual(json.loads(state.read_text())["blocked_until"], 3700)


if __name__ == "__main__":
    unittest.main()
