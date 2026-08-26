import unittest
from unittest.mock import patch

from tools.bulk_visual_identity import (
    DiscoveredLogo,
    discover_verified_logo_identity,
    discover_wikidata_logo_for_terms,
)


def claim(value, *, qualifiers=None):
    item = {"mainsnak": {"datavalue": {"value": value}}}
    if qualifiers:
        item["qualifiers"] = qualifiers
    return item


def logo_entity(label, domain="example.com", *, aliases=(), extra_sites=()):
    sites = [claim(f"https://{domain}/")]
    sites.extend(extra_sites)
    return {
        "labels": {"en": {"value": label}},
        "aliases": {"en": [{"value": alias} for alias in aliases]},
        "claims": {
            "P154": [claim(f"{label} logo.svg")],
            "P856": sites,
        },
    }


class BulkVisualIdentityEdgeCaseTests(unittest.TestCase):
    def test_declared_aliases_are_verified_individually_before_person_fallback(self):
        story = "Fred Smith biography"
        fedex = DiscoveredLogo(
            "FedEx", "fedex.com", "FedEx logo.svg",
            "https://www.wikidata.org/wiki/QFEDEX", (),
        )

        def discover(terms, _json_get):
            if terms == {"FedEx"}:
                return fedex
            return None

        with patch("tools.bulk_visual_identity.sb.story_aliases",
                   return_value={"Fred Smith", "FedEx"}), \
             patch.dict("tools.bulk_visual_identity.sb._STORY_PERSONS", {}, clear=True), \
             patch("tools.bulk_visual_identity.discover_wikidata_logo_for_terms",
                   side_effect=discover), \
             patch("tools.bulk_visual_identity._exact_human_identity",
                   return_value=(None, set())):
            got = discover_verified_logo_identity(story, lambda url: {})

        self.assertEqual(fedex, got)

    def test_redirect_qids_collapse_to_one_canonical_identity(self):
        entity = logo_entity("IKEA", "ikea.com", aliases=("Ikea",))

        def fake(url):
            if "wbsearchentities" in url:
                return {"search": [
                    {"id": "QCANON", "label": "IKEA", "aliases": ["Ikea"]},
                    {"id": "QREDIR", "label": "IKEA", "aliases": []},
                ]}
            if "Special:EntityData/QCANON" in url:
                return {"entities": {"QCANON": entity}}
            if "Special:EntityData/QREDIR" in url:
                return {"entities": {"QCANON": entity}}
            raise AssertionError(url)

        got = discover_wikidata_logo_for_terms({"IKEA"}, fake)
        self.assertIsNotNone(got)
        self.assertEqual("ikea.com", got.domain)
        self.assertIn("QCANON", got.source_url)

    def test_disambiguation_item_does_not_compete_with_exact_entity(self):
        bitcoin = logo_entity("Bitcoin", "bitcoin.org")
        disambiguation = {
            "labels": {"en": {"value": "Bitcoin"}},
            "aliases": {"en": []},
            "claims": {"P31": [claim({"id": "Q4167410"})]},
        }

        def fake(url):
            if "wbsearchentities" in url:
                return {"search": [
                    {"id": "QBTC", "label": "Bitcoin", "aliases": []},
                    {"id": "QDAB", "label": "Bitcoin", "aliases": []},
                ]}
            if "Special:EntityData/QBTC" in url:
                return {"entities": {"QBTC": bitcoin}}
            if "Special:EntityData/QDAB" in url:
                return {"entities": {"QDAB": disambiguation}}
            raise AssertionError(url)

        got = discover_wikidata_logo_for_terms({"Bitcoin"}, fake)
        self.assertIsNotNone(got)
        self.assertEqual("bitcoin.org", got.domain)

    def test_unqualified_global_official_site_beats_jurisdiction_site(self):
        canada_qualifier = {
            "P1001": [{"datavalue": {"value": {"id": "Q16"}}}],
        }
        entity = logo_entity(
            "IKEA", "ikea.com",
            extra_sites=(claim("https://ikea.ca/", qualifiers=canada_qualifier),),
        )

        def fake(url):
            if "wbsearchentities" in url:
                return {"search": [{"id": "QIKEA", "label": "IKEA", "aliases": []}]}
            return {"entities": {"QIKEA": entity}}

        got = discover_wikidata_logo_for_terms({"IKEA"}, fake)
        self.assertIsNotNone(got)
        self.assertEqual("ikea.com", got.domain)


if __name__ == "__main__":
    unittest.main()
