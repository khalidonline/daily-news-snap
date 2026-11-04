"""Single explicit replacement of a lost, invalid fixed writer response.

Preserves original research, receipts, identity and audit. This is not a generic
paid retry or an approval bypass. Fresh evidence is checked before writing.
"""
import copy
from datetime import datetime
from .policy import digest


def prepare_recovery(state,request,selection,original_selection,*,now,engine):
    uncertain = isinstance(request,dict) and request.get('kind')=='uncertain_writer'
    if (not isinstance(request,dict) or request.get('version')!=1
            or request.get('kind') not in {'saved_research','uncertain_writer'}
            or request.get('allow_replacement_writer') is not True
            or (uncertain and request.get('allow_new_writer_with_retained_reservation') is not True)):
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
            or audit[-2].get('reason')!=('RuntimeError' if uncertain else 'invalid_fixed_information_text')
            or audit[-2].get('candidate_id')!=state.get('candidate_id')
            or sum(r.get('event')=='saved_research_recovery_authorized' for r in audit)!=(1 if uncertain else 0)
            or any(r.get('event')=='uncertain_writer_recovery_authorized' for r in audit)):
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
    if uncertain:
        prior=state.get('recovery',{})
        if (prior.get('request',{}).get('kind')!='saved_research'
                or prior.get('previous_state',{}).get('research')!=state['research']
                or prior.get('previous_state',{}).get('agent_receipts')!=receipts):
            raise ValueError('original_saved_research_attempt_required')
    recovered=copy.deepcopy(state)
    recovered.update(status='working',reason=None,engine=engine,
                     recovery={'request':copy.deepcopy(request),'previous_state':copy.deepcopy(state)})
    recovered['audit'].append({'event':'uncertain_writer_recovery_authorized' if uncertain else 'saved_research_recovery_authorized','at':now.isoformat(),
                               'previous_state_sha256':digest(state),'request_sha256':digest(request)})
    return recovered


def write_preflight_failure(output, lane, error):
    """Expose bounded diagnostics without changing the held journal or authority."""
    import json
    from pathlib import Path
    from publishing_v2.public_images import atomic_write
    safe = {'selected_source_unverified','planned_image_not_retrieved',
            'insufficient_subject_visuals_before_recovery','saved_research_evidence_changed',
            'saved_research_candidate_no_longer_eligible','saved_research_timing_changed',
            'attention_article_not_retrieved','saved_research_source_drift_requires_opt_in'}
    reason = str(error) if type(error) is ValueError and str(error) in safe else 'preflight_failed'
    row = {'schema_version':1,'status':'blocked','lane':lane,'reason':reason,
           'error_type':type(error).__name__,'preview_allowed':False,'publish_authorized':False}
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    atomic_write(output/'recovery-preflight.json',json.dumps(row,sort_keys=True).encode())
    return row


def verify_evidence(previous,current,request):
    """Compare exact supporting evidence; full-page drift requires fresh review."""
    import re
    old,new=copy.deepcopy(previous),copy.deepcopy(current)
    if not isinstance(old,list) or not isinstance(new,list) or len(old)!=len(new):
        raise ValueError('saved_research_evidence_changed')
    drift=[]
    for a,b in zip(old,new):
        before,after=a.pop('retrieved_text_sha256',None),b.pop('retrieved_text_sha256',None)
        if a!=b or not all(isinstance(h,str) and re.fullmatch('[0-9a-f]{64}',h) for h in (before,after)):
            raise ValueError('saved_research_evidence_changed')
        if before!=after:
            drift.append({'source_id':a['id'],'previous_sha256':before,'current_sha256':after})
    if drift and request.get('allow_source_text_drift_review') is not True:
        raise ValueError('saved_research_source_drift_requires_opt_in')
    return drift


def verify_retained_reservation(state,request,ledger,now):
    """Read-only proof of the specifically authorized unresolved reservation."""
    from daily_budget import day_key
    retained=request.get('retained_reservation',{})
    entry=retained.get('entry',{})
    if (request.get('kind')!='uncertain_writer'
            or request.get('allow_new_writer_with_retained_reservation') is not True
            or retained.get('day')!=day_key(now) or ledger.get('day')!=retained.get('day')
            or ledger.get('version')!=1
            or ledger.get('entries',{}).get(retained.get('id'))!=entry
            or entry.get('status')!='reserved' or entry.get('stage')!='fixed_information_writer'
            or entry.get('bot')!='autopilot:fixed_information_writer'
            or entry.get('package_id')!=state.get('candidate_id')
            or entry.get('run_id')!=str(request.get('original_run_id'))
            or entry.get('run_attempt')!='1' or entry.get('request_attempt')!=3
            or type(entry.get('reserved_micro_usd')) is not int or entry['reserved_micro_usd']<=0
            or entry.get('charged_micro_usd')!=entry['reserved_micro_usd']):
        raise ValueError('retained_writer_reservation_changed')
    rows=[r for r in ledger['entries'].values() if r.get('package_id')==state['candidate_id']]
    if len(rows)!=3 or sorted(r.get('request_attempt',0) for r in rows)!=[1,2,3]:
        raise ValueError('additional_package_attempt_not_authorized')
    for index,receipt in enumerate(state['agent_receipts'],1):
        match=next(r for r in rows if r['request_attempt']==index)
        if (match.get('stage')!=receipt['role'] or match.get('status')!='settled'
                or match.get('charged_micro_usd')!=receipt['cost_micro_usd']):
            raise ValueError('settled_history_changed')
    return 3


def research_source_baseline(state,request):
    # An interrupted reviewer never resolves drift: compare to the source
    # snapshot that originally supported the paid research, not a later fetch.
    if request.get('kind')=='uncertain_writer':
        return state['recovery']['previous_state']['sources']
    return state['sources']
