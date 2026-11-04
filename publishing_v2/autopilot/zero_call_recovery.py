"""Explicit, single-use recovery of an exact pre-selection zero-call hold.

Never clears a journal or resumes ambiguous/paid generation. The original state,
immutable source revision and approval request remain in the same slot's audit.
"""
import base64
import copy
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from .policy import digest


REASON = 'free_selection_not_in_current_pool'


def prepare_recovery(state, request, selection, original_selection, *, now, engine):
    if not isinstance(request, dict) or request.get('version') != 1:
        raise ValueError('invalid_zero_call_recovery_request')
    if not isinstance(state, dict) or digest(state) != request.get('expected_state_sha256'):
        raise ValueError('zero_call_recovery_state_changed')
    permitted = {'version','engine','lane','mode','status','started_at','expires_at',
                 'reason','agent_receipts','pool','audit','eligibility_rejections'}
    if (set(state) - permitted or state.get('status') != 'held'
            or state.get('mode') != 'fixed-preview' or state.get('reason') != REASON
            or state.get('agent_receipts') != [] or state.get('engine') != request.get('original_engine')):
        raise ValueError('only_preselection_zero_call_hold_recoverable')
    audit = state.get('audit')
    if (not isinstance(audit,list) or not 3 <= len(audit) <= 4
            or [row.get('event') for row in audit] not in
               (['started','pool','stopped'], ['started','pool','triggers_filtered','stopped'])
            or audit[-1].get('reason') != REASON):
        raise ValueError('zero_call_recovery_audit_not_proven')
    if datetime.fromisoformat(state['expires_at']) <= now:
        raise ValueError('zero_call_recovery_expired')
    if (request.get('lane') not in {'daily','local'} or request['lane'] != state.get('lane')
            or request['lane'] != selection.get('lane')
            or request.get('candidate_id') != selection.get('candidate_id')
            or selection.get('candidate_id') != original_selection.get('candidate_id')
            or digest(selection) != request.get('selection_sha256')
            or digest(original_selection) != request.get('original_selection_sha256')):
        raise ValueError('zero_call_recovery_selection_changed')
    # The only permitted editorial change is adding the missing exact source pin.
    if ('source' in original_selection
            and original_selection['source'] != selection.get('source')):
        raise ValueError('zero_call_recovery_original_source_changed')
    old, current = copy.deepcopy(original_selection), copy.deepcopy(selection)
    old.pop('source',None); current.pop('source',None)
    if old != current or not isinstance(selection.get('source'),dict):
        raise ValueError('zero_call_recovery_original_content_changed')
    recovered = copy.deepcopy(state)
    recovered.update(status='working',engine=engine,reason=None,
                     recovery={'request':copy.deepcopy(request),'previous_state':copy.deepcopy(state)})
    recovered['audit'].append({'event':'zero_call_recovery_authorized','at':now.isoformat(),
                               'previous_state_sha256':digest(state),'request_sha256':digest(request)})
    return recovered


def load_recovery(path, journal, *, mode, lane):
    """Verify the explicit request against immutable GitHub run/source metadata."""
    if mode != 'fixed-preview':
        raise ValueError('recovery_requires_fixed_preview')
    root=Path.cwd().resolve(); source=Path(path)
    if (source.is_symlink() or not source.resolve().is_relative_to(root/'editorial/recovery')
            or not source.is_file() or source.stat().st_size > 64000):
        raise ValueError('repository_recovery_request_required')
    request=json.loads(source.read_text())
    run_id=request.get('original_run_id'); head=request.get('original_head_sha','')
    original_path=request.get('original_selection_path','')
    if (type(run_id) is not int or run_id <= 0 or not re.fullmatch('[0-9a-f]{40}',head)
            or not re.fullmatch(r'editorial/selected/[A-Za-z0-9_-]+\.json',original_path)
            or request.get('lane') != lane):
        raise ValueError('invalid_recovery_source_identity')
    run=journal.call('/actions/runs/'+str(run_id))
    if (run.get('head_sha') != head or run.get('event') != 'workflow_dispatch'
            or run.get('status') != 'completed' or run.get('conclusion') != 'failure'
            or run.get('path') != '.github/workflows/publishing-v2-fixed-preview.yml'
            or run.get('repository',{}).get('full_name') != 'khalidonline/daily-news-snap'):
        raise ValueError('original_failed_preview_run_required')
    response=journal.call('/contents/'+quote(original_path,safe='/')+'?ref='+head)
    raw=base64.b64decode(response['content'])
    if len(raw)>64000:
        raise ValueError('original_selection_too_large')
    original=json.loads(raw)
    if digest(original)!=request.get('original_selection_sha256'):
        raise ValueError('immutable_original_selection_changed')
    return request, original
