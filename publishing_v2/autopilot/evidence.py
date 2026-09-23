"""Deterministic source passages: models select evidence, never transcribe it."""
import re


def hydrate_editor(choice, candidate):
    """Resolve selected source fields without model-authored titles or quotes."""
    from .policy import validate_editor_binding
    fields = {'id', 'evidence_format', 'why_saudi', 'why_now', 'angle',
              'share_reason', 'research_query', 'subject_evidence'}
    if (not isinstance(choice, dict) or set(choice) != fields
            or choice['evidence_format'] != 'source-fields-v1'
            or choice['id'] != candidate['id']):
        raise ValueError('invalid_editor_source_selection')
    rows = choice['subject_evidence']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2:
        raise ValueError('editor_subject_evidence_required')
    resolved = []
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'subject', 'mention', 'source_field'}
                or not isinstance(row['source_field'], str)):
            raise ValueError('invalid_editor_source_field')
        field = row['source_field']
        if field not in {'title', 'summary'}:
            # Some responses copy the field's value instead of its selector.
            # Recover only an exact full original value, never inferred text.
            matches = [key for key in ('title', 'summary')
                       if field and candidate.get(key) == field]
            if not matches:
                raise ValueError('invalid_editor_source_field')
            field = matches[0]
        # Recover a wrong selector only when the literal mention exists in the
        # other original field. Never translate, infer or fuzzy-match a name.
        mention = row['mention']
        normalize = lambda value: ' '.join(value.split())
        if isinstance(mention, str) and mention.strip():
            if normalize(mention) not in normalize(candidate.get(field, '')):
                for alternate in ('title', 'summary'):
                    if normalize(mention) in normalize(candidate.get(alternate, '')):
                        field = alternate
                        break
        resolved.append({'subject': row['subject'], 'mention': row['mention'],
                         'quote': candidate.get(field, '')})
    result = dict(choice, source_title=candidate['title'],
                  subjects=[row['subject'] for row in resolved], subject_evidence=resolved)
    validate_editor_binding(dict(candidate, editorial=result))
    return result


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


def hydrate_timing(data, rows):
    """Select exact original timing evidence; never accept model-authored evidence."""
    required = {'eligible', 'event_date', 'event_passage_id', 'timing_basis', 'reason'}
    if not isinstance(data, dict) or not required.issubset(data):
        raise ValueError('unexpected_timing_fields')
    extras = set(data) - required
    # Explanatory extras (for example confidence/rationale metadata) cannot
    # influence the decision and are ignored. Evidence-authority fields remain
    # forbidden: the model may select a passage ID but may never supply its own
    # quotation or source identity.
    if extras & {'event_quote', 'event_source_id', 'quote', 'source_id'}:
        raise ValueError('model_authored_timing_evidence')
    result = {key: data[key] for key in required if key != 'event_passage_id'}
    if data.get('eligible') is not True:
        return result
    ident = data.get('event_passage_id')
    if not isinstance(ident, str):
        raise ValueError('invalid_timing_passage_id')
    row = next((row for row in rows if row['id'] == ident), None)
    if row is None:
        raise ValueError('unknown_timing_passage')
    return dict(result, event_source_id=row['source_id'], event_quote=row['quote'])
