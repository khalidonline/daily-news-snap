import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import logo_fetch as lf


class LogoFetchTests(unittest.TestCase):
    def test_fetch_current_uses_domain_verified_wikidata_p154_after_article_miss(self):
        names = ["McDonald's", "McDonalds", "ماكدونالدز"]
        filename = "McDonald's Golden Arches.svg"
        info = {
            "thumburl": "https://upload.wikimedia.org/example.png",
            "url": "https://upload.wikimedia.org/example.svg",
        }
        with tempfile.TemporaryDirectory() as td, \
             patch.object(lf, "LOGOS_DIR", Path(td)), \
             patch.object(lf, "_article_logo_files", return_value=[]), \
             patch.object(lf, "wikidata_p154_logo", return_value=filename) as wikidata_logo, \
             patch.object(lf, "_commons_fileinfo", return_value=[({"title": f"File:{filename}"}, info)]), \
             patch.object(lf, "_commons_licence_ok", return_value=True), \
             patch.object(lf, "_download") as download, \
             patch.object(lf, "_renders_as_a_mark", return_value=True):
            result = lf.fetch_current(
                "mcdonalds.com",
                names,
                require_domain="mcdonalds.com",
            )

        self.assertEqual(Path(td) / "mcdonalds.com-current.png", result)
        wikidata_logo.assert_called_once_with(names, "mcdonalds.com")
        download.assert_called_once_with(
            "https://upload.wikimedia.org/example.png",
            Path(td) / "mcdonalds.com-current.png",
        )

    def test_fetch_current_never_uses_wikidata_without_declared_domain(self):
        with patch.object(lf, "_article_logo_files", return_value=[]), \
             patch.object(lf, "wikidata_p154_logo") as wikidata_logo:
            result = lf.fetch_current("unverified", ["Unverified Brand"])

        self.assertIsNone(result)
        wikidata_logo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
