import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class SeasonAliasTests(unittest.TestCase):
    def _resolve(self, value):
        with tempfile.TemporaryDirectory() as td:
            seasons = Path(td) / "seasons.txt"
            seasons.write_text(
                "## مؤتمر ليب للتقنية | greg 02-01..02-28 | 10 | 3\n"
                "وش الجديد في مؤتمر ليب؟\n"
                "أبرز تقنيات ليب هذا العام\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "season_aliases.py", value, str(seasons)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def test_english_leap_resolves_to_arabic_canonical_season(self):
        self.assertEqual(self._resolve("LEAP"), "مؤتمر ليب للتقنية")

    def test_arabic_leap_variants_resolve_to_same_season(self):
        for value in ("ليب", "مؤتمر ليب", "مؤتمر ليب للتقنية"):
            with self.subTest(value=value):
                self.assertEqual(self._resolve(value), "مؤتمر ليب للتقنية")

    def test_unknown_season_is_left_unchanged(self):
        self.assertEqual(self._resolve("موسم غير معروف"), "موسم غير معروف")


if __name__ == "__main__":
    unittest.main()
