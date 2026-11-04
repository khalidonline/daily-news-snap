"""Single explicit replacement of a lost, invalid fixed writer response.

Preserves original research, receipts, identity and audit. This is not a generic
paid retry or an approval bypass. Fresh evidence is checked before writing.
"""
import copy
from datetime import datetime
from .policy import digest


def prepare_recovery(state,request,selection,original_selection,*,now,engine):
    if (not isinstance(request,dict) or request.get('version')!=1
            or request.get('kind')!='saved_research' or request.get('allow_replacement_writer') is not True):
        raise ValueError('explicit_saved_research_recovery_required')
    if not isinstance(state,dict) or digest(state)!=request.get('expected_state_sha256'):
        raise ValueError('saved_research_state_changed')
    forbidden={'information_package','package','paths','approval','receipt','working_draft','text_approval'}
    if (forbidden & set(state) or state.get('status')!='held' or state.get('mode')!='fixed-preview'
            or state.get('reason')!='no_package_passed_review' or state.get('engine')!=request.get('original_engine')
            or state.get('lane') not in {'daily','local'} or state['lane']!=request.get('lane')):
        raise ValueError('invalid_saved_research_hold')
    if datetime.fromisoformat(state['expires_at'])<=now:
        raise ValueError('saved_research_expired')
    audit=state.get('audit',[])
    if (len(audit)<3 or [r.get('event') for r in audit[-3:]]!=['researched','candidate_rejected','exhausted_candidates']
            or audit[-2].get('reason')!='invalid_fixed_information_text'
            or audit[-2].get('candidate_id')!=state.get('candidate_id')
            or any(r.get('event')=='saved_research_recovery_authorized' for r in audit)):
        raise ValueError('lost_writer_response_not_proven')
    receipts=state.get('agent_receipts')
    if (not isinstance(receipts,list) or [r.get('role') for r in receipts]!=['researcher','fixed_information_writer']
            or any(not isinstance(r.get('response_id'),str) or not r['response_id']
                   or r.get('stop_reason')!='end_turn' or type(r.get('cost_micro_usd')) is not int
                   or r['cost_micro_usd']<0 or r.get('package_id')!=state.get('candidate_id') for r in receipts)
            or len({r['response_id'] for r in receipts})!=2):
        raise ValueError('exact_settled_research_writer_receipts_required')
    if (not isinstance(state.get('research'),dict) or not state['research'].get('claims')
            or not isinstance(state.get('sources'),list) or not state['sources']):
        raise ValueError('saved_research_missing')
    if (selection!=original_selection or selection!=state.get('free_selection')
            or digest(selection)!=request.get('selection_sha256')
            or digest(original_selection)!=request.get('original_selection_sha256')
            or selection.get('candidate_id')!=state.get('candidate_id')
            or selection.get('candidate_id')!=request.get('candidate_id')
            or selection.get('lane')!=state['lane'] or not isinstance(selection.get('source'),dict)):
        raise ValueError('saved_research_selection_changed')
    recovered=copy.deepcopy(state)
    recovered.update(status='working',reason=None,engine=engine,
                     recovery={'request':copy.deepcopy(request),'previous_state':copy.deepcopy(state)})
    recovered['audit'].append({'event':'saved_research_recovery_authorized','at':now.isoformat(),
                               'previous_state_sha256':digest(state),'request_sha256':digest(request)})
    return recovered
