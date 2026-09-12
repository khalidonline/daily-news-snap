"""Manual public-source download evidence; no generation, rendering or delivery."""
import argparse
import json
from pathlib import Path
from .public_images import acquire, search_commons, search_nasa, atomic_write, ImageSourceError


def blocked_source(query):
    raise ImageSourceError('injected_outage')


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cases = [('iphone', 'iPhone 16', [('commons', search_commons)]),
             ('riyadh', 'Riyadh Metro', [('commons', search_commons)]),
             ('voyager', 'Voyager spacecraft', [('commons', search_commons), ('nasa', search_nasa)]),
             ('voyager-source-outage', 'Voyager spacecraft', [('commons', blocked_source), ('nasa', search_nasa)])]
    report = {'getty_enabled': False, 'historical_replay': True, 'production_ready': False, 'results': []}
    for name, query, sources in cases:
        result = {'case': name, 'query': query, **acquire(query, output / name, sources=sources)}
        report['results'].append(result)
        atomic_write(output / 'report.json', json.dumps(report, ensure_ascii=False, indent=2).encode())
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output)
    # Download coverage only. Rights, relevance, crop, six-frame coverage remain unapproved.
    return 0 if all(r['status'] == 'downloaded_review_required' for r in report['results']) else 1

if __name__ == '__main__': raise SystemExit(main())
