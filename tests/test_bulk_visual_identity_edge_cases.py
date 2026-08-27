import json
import unittest
from unittest.mock import patch

from tools.bulk_visual_identity import (
    AMBIGUOUS_ENTITY_CANDIDATES,
    PERSON_ORG_RELATION_UNRESOLVED,
    VERIFIED_IDENTITY,
    diagnose_verified_logo_identity,
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
    def diagnose(self, aliases, entities, searches, *, people=()):
        def fake(url):
            if "wbsearchentities" in url:
                term = next(key for key in searches if key.replace(" ", "%20") in url)
                return {"search": [
                    {"id": qid, "label": entities[qid]["labels"]["en"]["value"],
                     "aliases": [item["value"] for item in
                                 entities[qid].get("aliases", {}).get("en", [])]}
                    for qid in searches[term]
                ]}
            if "Special:EntityData/" in url:
                qid = url.rsplit("/", 1)[-1].removesuffix(".json")
                return {"entities": {qid: entities[qid]}}
            if "sparql" in url:
                return {"results": {"bindings": []}}
            raise AssertionError(url)

        with patch("tools.bulk_visual_identity.sb.story_aliases", return_value=set(aliases)), \
             patch.dict("tools.bulk_visual_identity.sb._STORY_PERSONS",
                        {"story": list(people)} if people else {}, clear=True), \
             patch("tools.bulk_visual_identity.sr.approved_runtime_visuals",
                   return_value=([], [])), \
             patch("tools.bulk_visual_identity.nb.load_local_images", return_value=[]):
            return diagnose_verified_logo_identity("story", fake)

    def test_verified_organization_survives_ambiguous_person_alias(self):
        person = lambda label: {
            "labels": {"en": {"value": label}}, "aliases": {"en": []},
            "claims": {"P31": [claim({"id": "Q5"})]},
        }
        entities = {"QORG": logo_entity("Acme"),
                    "QP1": person("Alex Smith"), "QP2": person("Alex Smith")}
        result = self.diagnose(
            {"Acme", "Alex Smith"}, entities,
            {"Acme": ["QORG"], "Alex Smith": ["QP1", "QP2"]},
            people=("Alex Smith",),
        )
        self.assertEqual(VERIFIED_IDENTITY, result.reason)
        self.assertEqual("example.com", result.logo.domain)

    def test_verified_organization_survives_ambiguous_unrelated_alias(self):
        entities = {"QORG": logo_entity("Acme"),
                    "QX1": logo_entity("Mercury", "one.example"),
                    "QX2": logo_entity("Mercury", "two.example")}
        result = self.diagnose(
            {"Acme", "Mercury"}, entities,
            {"Acme": ["QORG"], "Mercury": ["QX1", "QX2"]},
        )
        self.assertEqual(VERIFIED_IDENTITY, result.reason)
        self.assertEqual("Acme", result.logo.entity_label)

    def test_ambiguous_only_subject_fails_with_bounded_candidate_detail(self):
        entities = {f"Q{i}": logo_entity("Mercury", f"mercury{i}.example")
                    for i in range(10)}
        result = self.diagnose(
            {"Mercury"}, entities, {"Mercury": list(entities)},
        )
        self.assertEqual(AMBIGUOUS_ENTITY_CANDIDATES, result.reason)
        self.assertIsNone(result.logo)
        detail = json.loads(result.detail)
        self.assertEqual("Mercury", detail["ambiguous_terms"][0]["term"])
        self.assertLessEqual(len(detail["ambiguous_terms"][0]["candidates"]), 8)
        self.assertEqual(["Q0", "Q1"], [
            candidate["qid"] for candidate in
            detail["ambiguous_terms"][0]["candidates"][:2]
        ])

    def test_two_distinct_verified_organizations_fail_closed(self):
        entities = {"QONE": logo_entity("One", "one.example"),
                    "QTWO": logo_entity("Two", "two.example")}
        result = self.diagnose(
            {"One", "Two"}, entities, {"One": ["QONE"], "Two": ["QTWO"]},
        )
        self.assertEqual(AMBIGUOUS_ENTITY_CANDIDATES, result.reason)
        self.assertEqual(["QONE", "QTWO"], json.loads(result.detail)["verified_qids"])

    def test_two_aliases_for_same_verified_organization_succeed(self):
        entity = logo_entity("International Business Machines", "ibm.com", aliases=("IBM",))
        result = self.diagnose(
            {"IBM", "International Business Machines"}, {"QIBM": entity},
            {"IBM": ["QIBM"], "International Business Machines": ["QIBM"]},
        )
        self.assertEqual(VERIFIED_IDENTITY, result.reason)
        self.assertEqual("ibm.com", result.logo.domain)

    def test_typed_person_without_unique_corroborated_org_still_fails(self):
        person = {
            "labels": {"en": {"value": "Jane Founder"}}, "aliases": {"en": []},
            "claims": {"P31": [claim({"id": "Q5"})]},
        }
        result = self.diagnose(
            {"Jane Founder"}, {"QPERSON": person},
            {"Jane Founder": ["QPERSON"]}, people=("Jane Founder",),
        )
        self.assertEqual(PERSON_ORG_RELATION_UNRESOLVED, result.reason)

    def test_untyped_person_without_unique_corroborated_org_still_fails(self):
        person = {
            "labels": {"en": {"value": "Jane Founder"}}, "aliases": {"en": []},
            "claims": {"P31": [claim({"id": "Q5"})]},
        }
        result = self.diagnose(
            {"Jane Founder"}, {"QPERSON": person},
            {"Jane Founder": ["QPERSON"]},
        )
        self.assertEqual(PERSON_ORG_RELATION_UNRESOLVED, result.reason)

    def test_typed_person_fallback_survives_ambiguous_unrelated_alias(self):
        person = {
            "labels": {"en": {"value": "Jane Founder"}}, "aliases": {"en": []},
            "claims": {
                "P31": [claim({"id": "Q5"})],
                "P108": [claim({"id": "QORG"})],
            },
        }
        entities = {
            "QPERSON": person,
            "QORG": logo_entity("Acme", "acme.example"),
            "QX1": logo_entity("Mercury", "one.example"),
            "QX2": logo_entity("Mercury", "two.example"),
        }
        result = self.diagnose(
            {"Jane Founder", "Acme", "Mercury"}, entities,
            {"Jane Founder": ["QPERSON"], "Acme": [],
             "Mercury": ["QX1", "QX2"]},
            people=("Jane Founder",),
        )
        self.assertEqual(VERIFIED_IDENTITY, result.reason)
        self.assertEqual("acme.example", result.logo.domain)

    def test_untyped_person_fallback_survives_ambiguous_unrelated_alias(self):
        person = {
            "labels": {"en": {"value": "Jane Founder"}}, "aliases": {"en": []},
            "claims": {
                "P31": [claim({"id": "Q5"})],
                "P108": [claim({"id": "QORG"})],
            },
        }
        entities = {
            "QPERSON": person,
            "QORG": logo_entity("Acme", "acme.example"),
            "QX1": logo_entity("Mercury", "one.example"),
            "QX2": logo_entity("Mercury", "two.example"),
        }
        result = self.diagnose(
            {"Jane Founder", "Acme", "Mercury"}, entities,
            {"Jane Founder": ["QPERSON"], "Acme": [],
             "Mercury": ["QX1", "QX2"]},
        )
        self.assertEqual(VERIFIED_IDENTITY, result.reason)
        self.assertEqual("acme.example", result.logo.domain)

    def test_ambiguous_alias_and_person_without_unique_org_reports_ambiguity(self):
        person = {
            "labels": {"en": {"value": "Jane Founder"}}, "aliases": {"en": []},
            "claims": {"P31": [claim({"id": "Q5"})]},
        }
        ambiguous = {
            "QX1": logo_entity("Mercury", "one.example"),
            "QX2": logo_entity("Mercury", "two.example"),
        }
        zero = self.diagnose(
            {"Jane Founder", "Mercury"}, {"QPERSON": person, **ambiguous},
            {"Jane Founder": ["QPERSON"], "Mercury": ["QX1", "QX2"]},
            people=("Jane Founder",),
        )
        self.assertEqual(AMBIGUOUS_ENTITY_CANDIDATES, zero.reason)
        self.assertEqual("Mercury", json.loads(zero.detail)["ambiguous_terms"][0]["term"])

        person["claims"]["P108"] = [claim({"id": "QX1"}), claim({"id": "QX2"})]
        multiple = self.diagnose(
            {"Jane Founder", "Mercury"}, {"QPERSON": person, **ambiguous},
            {"Jane Founder": ["QPERSON"], "Mercury": ["QX1", "QX2"]},
            people=("Jane Founder",),
        )
        self.assertEqual(AMBIGUOUS_ENTITY_CANDIDATES, multiple.reason)
        self.assertIsNone(multiple.logo)

    def test_declared_aliases_are_verified_individually_before_person_fallback(self):
        story = "Fred Smith biography"
        with patch("tools.bulk_visual_identity.sb.story_aliases",
                   return_value={"Fred Smith", "FedEx"}), \
             patch.dict("tools.bulk_visual_identity.sb._STORY_PERSONS", {}, clear=True), \
             patch("tools.bulk_visual_identity._exact_search_qids",
                   side_effect=lambda terms, get: {"QFEDEX"} if terms == {"FedEx"} else set()), \
             patch("tools.bulk_visual_identity._canonical_entity",
                   return_value=("QFEDEX", logo_entity("FedEx", "fedex.com"))), \
             patch("tools.bulk_visual_identity._exact_human_identity",
                   return_value=(None, set())):
            got = discover_verified_logo_identity(story, lambda url: {})

        self.assertEqual("FedEx", got.entity_label)
        self.assertEqual("fedex.com", got.domain)

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
