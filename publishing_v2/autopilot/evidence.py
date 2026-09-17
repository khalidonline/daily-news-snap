"""Deterministic source passages: models select evidence, never transcribe it."""
import re


def passages(sources):
    rows = []
    for source in sources:
        words = list(re.finditer(r'\S+', source['text']))
        for offset in range(0, len(words), 22):
            chunk = words[offset:offset + 22]
            quote = source['text'][chunk[0].start():chunk[-1].end()]
            # Discard tiny final fragments that cannot support a useful claim.
            if len(quote) < 12:
                continue
            rows.append({'id': source['id'] + ':p' + str(offset // 22),
                         'source_id': source['id'], 'quote': quote})
    return rows


def hydrate(data, rows):
    if set(data) != {'event_date', 'event_passage_id', 'sensitive', 'claims'}:
        raise ValueError('unexpected_research_fields')
    known = {row['id']: row for row in rows}
    claims = data['claims']
    if not isinstance(claims, list) or not 1 <= len(claims) <= 8:
        raise ValueError('invalid_claims')
    result = {'event_date': data['event_date'], 'sensitive': data['sensitive'], 'claims': []}
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {'id', 'fact', 'passage_id'}:
            raise ValueError('unexpected_claim_fields')
        if not isinstance(claim['passage_id'], str):
            raise ValueError('invalid_evidence_passage_id')
        row = known.get(claim['passage_id'])
        if row is None:
            raise ValueError('unknown_evidence_passage')
        result['claims'].append({'id': claim['id'], 'fact': claim['fact'],
                                'source_id': row['source_id'], 'quote': row['quote'],
                                'passage_id': row['id']})
    if data['event_passage_id'] is not None:
        if not isinstance(data['event_passage_id'], str):
            raise ValueError('invalid_event_passage_id')
        row = known.get(data['event_passage_id'])
        if row is None:
            raise ValueError('unknown_event_passage')
        result.update(event_source_id=row['source_id'], event_quote=row['quote'])
    return result
