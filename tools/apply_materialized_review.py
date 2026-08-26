#!/usr/bin/env python3
"""Apply the 2026-08-26 visual review of all materialized rt-* assets.

Default for an rt-* association is DIRECT only after this script's review pass.
Exceptions below are the visual decisions from the 15 contact sheets. The
runtime still fails closed for any future rt-* file absent from the ledger.
"""
from __future__ import annotations
import json
from pathlib import Path
import news_bot as nb
import story_bot as sb
import story_runtime as sr

OUT = Path("images/relevance.json")

WEAK = {
    "rt-yahoo-2.jpg", "rt-yahoo-3.jpg", "rt-samsung-3.jpg",
    "rt-قصة-أزمة-2008-كيف-بدأت-2.jpg", "rt-pif-2.jpg", "rt-dubai-1.jpg",
    "rt-new-york-2.jpg", "rt-new-york-3.jpg",
    "rt-لماذا-تختلف-أسعار-التذاك-2.jpg", "rt-ghutra-1.jpg",
    "rt-savola-group-1.jpg", "rt-al-othaim-markets-1.jpg", "rt-nadec-1.jpg",
    "rt-saudi-stock-market-crash-1.jpg", "rt-sama-2.jpg", "rt-careem-1.jpg",
    "rt-pif-uber-stake-2.jpg", "rt-قصة-أول-سيارة-تدخل-الجزي-1.jpg",
    "rt-قصة-أول-سيارة-تدخل-الجزي-2.jpg", "rt-first-saudi-banknote-1.jpg",
    "rt-google-1.jpg", "rt-diners-club-1.jpg", "rt-aramco-1.jpg",
}
WRONG = {"rt-pif-1.jpg", "rt-yusuf-bin-ahmed-kanoo-1.jpg", "rt-pif-uber-stake-1.jpg"}
STRONG = {
    "rt-netflix-2.jpg", "rt-aramco-2.jpg", "rt-قصة-أزمة-2008-كيف-بدأت-1.jpg",
    "rt-bitcoin-2.jpg", "rt-كيف-غي-رت-شركات-الطيران-1.jpg",
    "rt-كيف-غي-رت-شركات-الطيران-2.jpg", "rt-لماذا-تختلف-أسعار-التذاك-1.jpg",
    "rt-قصة-جواز-السفر-كيف-بدأت-1.jpg", "rt-قصة-جواز-السفر-كيف-بدأت-2.jpg",
    "rt-jerry-lawson-2.jpg", "rt-muriel-siebert-2.jpg", "rt-muriel-siebert-3.jpg",
    "rt-amancio-ortega-1.jpg", "rt-amancio-ortega-2.jpg", "rt-mcdonald-brothers-1.jpg",
    "rt-madam-c-j-walker-1.jpg", "rt-fred-smith-1.jpg", "rt-fred-smith-2.jpg",
    "rt-abdul-latif-jameel-1.jpg", "rt-abdul-latif-jameel-2.jpg",
    "rt-saudi-coffee-1.jpg", "rt-saudi-coffee-2.jpg",
    "rt-saudi-dates-industry-1.jpg", "rt-saudi-dates-industry-2.jpg",
    "rt-air-conditioning-1.jpg", "rt-air-conditioning-2.jpg", "rt-zamzam-water-1.jpg",
    "rt-starbucks-2.jpg", "rt-ups-1.jpg", "rt-publix-2.jpg", "rt-publix-3.jpg",
}
NOTES = {
    "rt-yusuf-bin-ahmed-kanoo-1.jpg": "Wrong person: Flex CEO Revathi Advaithi, not Yusuf bin Ahmed Kanoo.",
    "rt-pif-1.jpg": "Bad homonym/provenance: the source credit resolves to Italian TV personality Pif, not Saudi PIF.",
    "rt-pif-uber-stake-1.jpg": "Japanese Uber taxi; not evidence of the Saudi PIF investment.",
    "rt-pif-uber-stake-2.jpg": "Generic Uber vehicle; does not document the PIF investment.",
    "rt-قصة-أزمة-2008-كيف-بدأت-2.jpg": "COVID-19 recovery-spending chart from 2021-22, not the 2008 crisis.",
    "rt-aramco-1.jpg": "Unidentified historical Saudi man; not verified as the person in any mapped Aramco story.",
    "rt-first-saudi-banknote-1.jpg": "Later one-riyal note; not verified as the first Saudi paper-money issue.",
    "rt-قصة-أول-سيارة-تدخل-الجزي-2.jpg": "1886 Benz is automobile-history context, not evidence of the first car entering Arabia.",
    "rt-diners-club-1.jpg": "Modern branded arena does not explain the origin of Diners Club.",
}
GRAPHICS = {
    "rt-yahoo-2.jpg", "rt-yahoo-3.jpg", "rt-samsung-3.jpg", "rt-ghutra-1.jpg",
    "rt-savola-group-1.jpg", "rt-al-othaim-markets-1.jpg", "rt-nadec-1.jpg",
    "rt-sama-2.jpg", "rt-careem-1.jpg",
}


def main():
    stories = sb.load_stories()
    assets = {
        "edison-stock-ticker.jpg": {
            "stories": {"Jack Bogle": "WEAK_GENERIC"},
            "note": "Generic market artifact; not a Bogle/Vanguard/index-fund beat.",
        }
    }
    for entry in nb.load_local_images():
        name = entry["path"].name
        if not name.startswith("rt-"):
            continue
        matches = [s for s in stories if sr._matches_story(entry, s)]
        if not matches:
            continue
        verdict = "DIRECT"
        if name in STRONG: verdict = "STRONG_CONTEXT"
        if name in WEAK: verdict = "WEAK_GENERIC"
        if name in WRONG: verdict = "WRONG_ENTITY"
        assets[name] = {"stories": {s: verdict for s in matches}}
        if name in NOTES: assets[name]["note"] = NOTES[name]
        elif name in GRAPHICS:
            assets[name]["note"] = "Graphic/logo/diagram; not counted as one of the four story photos."

    # Story-specific rulings where one tag family matched sibling stories.
    def setv(name, contains, verdict):
        for story in assets.get(name, {}).get("stories", {}):
            if contains in story:
                assets[name]["stories"][story] = verdict

    setv("rt-yahoo-1.jpg", "الطاهي", "WEAK_GENERIC")
    for name in ("rt-riyadh-1.jpg", "rt-riyadh-2.jpg"):
        setv(name, "قصة الرياض", "STRONG_CONTEXT")
        setv(name, "سكة حديد", "WEAK_GENERIC")
    setv("rt-jeddah-1.jpg", "جدة التاريخية", "WEAK_GENERIC")
    setv("rt-jeddah-1.jpg", "أول مطار", "WEAK_GENERIC")
    setv("rt-jeddah-2.jpg", "جدة التاريخية", "STRONG_CONTEXT")
    setv("rt-jeddah-2.jpg", "أول مطار", "WEAK_GENERIC")
    setv("rt-pif-3.jpg", "Uber", "STRONG_CONTEXT")
    assets["rt-pif-3.jpg"]["note"] = "Verified Public Investment Fund Tower, Riyadh (Z thomas / CC BY 4.0)."
    setv("rt-sulaiman-al-rajhi-1.jpg", "صالح الراجحي", "WRONG_ENTITY")
    for name in ("rt-saleh-al-rajhi-1.jpg", "rt-saleh-al-rajhi-2.jpg"):
        setv(name, "سليمان الراجحي", "WRONG_ENTITY")
    # These two are confirmed Saleh Abdulaziz Al Rajhi portraits on Commons.
    # Sulaiman's portrait remains direct only on Sulaiman/Waqf lines.

    doc = {
        "version": 2,
        "policy": "Only DIRECT and STRONG_CONTEXT count. Unreviewed rt-* assets fail closed. Graphics, homonyms, generic filler and wrong entities do not count.",
        "assets": dict(sorted(assets.items())),
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for row in assets.values():
        for verdict in row.get("stories", {}).values():
            counts[verdict] = counts.get(verdict, 0) + 1
    print("materialized relevance ledger:", counts)

if __name__ == "__main__":
    main()
