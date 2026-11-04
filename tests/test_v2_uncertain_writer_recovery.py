import copy
from datetime import datetime,timezone
import pytest
from publishing_v2.autopilot.policy import digest
from test_v2_saved_research_recovery import fixture,NOW


def data():
    old,req,selection,original=fixture()
    state=copy.deepcopy(old)
    state['audit'].insert(1,{'event':'saved_research_recovery_authorized'})
    state['audit'][-2]['reason']='RuntimeError'
    state['recovery']={'request':dict(req,kind='saved_research'),'previous_state':copy.deepcopy(old)}
    entry={'package_id':'a','stage':'fixed_information_writer','bot':'autopilot:fixed_information_writer',
           'request_attempt':3,'status':'reserved','reserved_micro_usd':200,'charged_micro_usd':200,
           'run_id':'123','run_attempt':'1','reserved_at':NOW.isoformat()}
    request=dict(req,kind='uncertain_writer',allow_new_writer_with_retained_reservation=True,
        original_run_id=123,writing_limit_micro_usd=1_100_000,expected_state_sha256=digest(state),
        retained_reservation={'id':'reservation','day':'2026-11-04','entry':entry})
    ledger={'version':1,'day':'2026-11-04','entries':{'reservation':copy.deepcopy(entry)}}
    for i,r in enumerate(state['agent_receipts'],1):
        ledger['entries'][str(i)]={'package_id':'a','stage':r['role'],'request_attempt':i,'status':'settled',
                                 'charged_micro_usd':r['cost_micro_usd']}
    return state,request,selection,original,ledger


def test_authorized_new_attempt_retains_all_prior_state_and_reservation():
    from publishing_v2.autopilot.saved_research_recovery import prepare_recovery,verify_retained_reservation
    state,req,sel,orig,ledger=data();before=copy.deepcopy(ledger)
    assert verify_retained_reservation(state,req,ledger,NOW)==3
    out=prepare_recovery(state,req,sel,orig,now=NOW,engine='new')
    assert out['recovery']['previous_state']==state and ledger==before
    assert out['audit'][-1]['event']=='uncertain_writer_recovery_authorized'
    with pytest.raises(ValueError):prepare_recovery(out,req,sel,orig,now=NOW,engine='new')


@pytest.mark.parametrize('change',[{'status':'settled'},{'charged_micro_usd':0},{'request_attempt':4},
 {'run_id':'other'},{'package_id':'b'},{'stage':'researcher'}])
def test_changed_or_reconciled_reservation_is_not_retry_authority(change):
    from publishing_v2.autopilot.saved_research_recovery import verify_retained_reservation
    state,req,_,_,ledger=data();ledger['entries']['reservation'].update(change)
    with pytest.raises(ValueError):verify_retained_reservation(state,req,ledger,NOW)


def test_extra_package_attempt_or_missing_opt_in_blocks():
    from publishing_v2.autopilot.saved_research_recovery import verify_retained_reservation,prepare_recovery
    state,req,sel,orig,ledger=data();ledger['entries']['extra']=dict(ledger['entries']['reservation'],request_attempt=4)
    with pytest.raises(ValueError):verify_retained_reservation(state,req,ledger,NOW)
    req.pop('allow_new_writer_with_retained_reservation')
    with pytest.raises(ValueError):prepare_recovery(state,req,sel,orig,now=NOW,engine='new')


def test_unreviewed_source_drift_cannot_disappear_on_next_attempt():
    from publishing_v2.autopilot.saved_research_recovery import research_source_baseline,verify_evidence
    state,req,_,_,_=data()
    original=[{'id':'a','url':'https://example.org/a','text':'exact','retrieved_text_sha256':'a'*64}]
    state['recovery']['previous_state']['sources']=original
    state['sources']=copy.deepcopy(original);state['sources'][0]['retrieved_text_sha256']='b'*64
    req['allow_source_text_drift_review']=True
    drift=verify_evidence(research_source_baseline(state,req),state['sources'],req)
    assert drift[0]['previous_sha256']=='a'*64 and drift[0]['current_sha256']=='b'*64


def test_pipeline_new_attempt_sequence_preserves_old_reserved_charge():
    from test_v2_saved_research_recovery import pipeline_fixture
    from daily_budget import day_key
    from types import SimpleNamespace
    case,p,old,seen=pipeline_fixture()
    try:
        prior=copy.deepcopy(old)
        old['audit'].insert(1,{'event':'saved_research_recovery_authorized'})
        old['audit'][-2]['reason']='RuntimeError'
        old['recovery']={'request':dict(p.saved_research_recovery[0],kind='saved_research'),'previous_state':prior}
        _,req,_,_,ledger=data();req.update(expected_state_sha256=digest(old),original_engine=old['engine'],
            selection_sha256=digest(p.free_selection),original_selection_sha256=digest(p.free_selection))
        day=day_key(p.now());req['retained_reservation']['day']=day;ledger['day']=day
        for i,r in enumerate(old['agent_receipts'],1):ledger['entries'][str(i)]['charged_micro_usd']=r['cost_micro_usd']
        before=copy.deepcopy(ledger)
        p.store.save(old);p.saved_research_recovery=(req,copy.deepcopy(p.free_selection))
        p.agent.estimate_fixed_writer=lambda data:100
        p.agent.ledger=SimpleNamespace(store=SimpleNamespace(read=lambda day:('sha',copy.deepcopy(ledger))))
        result=p.run('daily','fixed-preview')
        assert result['status']=='awaiting_information_review',result
        assert p.agent.request_attempt_offset==3 and p.agent.fixed_writer_recovery_once is True
        assert result['recovery']['previous_state']==old and ledger==before and case.agent.calls==[]
        with pytest.raises(ValueError):p.run('daily','fixed-preview')
    finally:case.doCleanups()


def test_trial_cap_is_one_package_writer_attempt_and_preserves_reservation():
    from daily_budget import Ledger,BudgetBlocked
    from test_daily_budget import MemoryStore
    state,req,_,_,row=data();store=MemoryStore()
    row['entries']['reservation'].update(reserved_micro_usd=329825,charged_micro_usd=329825)
    row['entries']['1']['charged_micro_usd']=162520;row['entries']['2']['charged_micro_usd']=75285
    row['limit_micro_usd']=None;store.write('2026-11-04',0,copy.deepcopy(row))
    ledger=Ledger(store,now=lambda:NOW,limit_micro_usd=None)
    ledger.context={'package_id':'a','stage':'fixed_information_writer','request_attempt':4}
    with pytest.raises(BudgetBlocked):ledger.reserve(329825,'autopilot:fixed_information_writer')
    ledger.package_writing_authorization={'package_id':'a','day':'2026-11-04','limit_micro_usd':1100000,
        'request_sha256':'a'*64,'retained_entry_id':'reservation','retained_entry':copy.deepcopy(row['entries']['reservation'])}
    token=ledger.reserve(329825,'autopilot:fixed_information_writer')
    _,out=store.read('2026-11-04')
    assert out['entries']['reservation']==row['entries']['reservation']
    assert out['entries'][token[1]]['writing_authorization']['limit_micro_usd']==1100000
    with pytest.raises(BudgetBlocked):ledger.reserve(329825,'autopilot:fixed_information_writer')
    ledger.settle(token,1)
    with pytest.raises(BudgetBlocked):ledger.reserve(1,'autopilot:fixed_information_writer')
    ledger.context['request_attempt']=5
    with pytest.raises(BudgetBlocked):ledger.reserve(1,'autopilot:fixed_information_writer')
    ledger.context.update(package_id='other',request_attempt=4)
    with pytest.raises(BudgetBlocked):ledger.reserve(1,'autopilot:fixed_information_writer')


def test_concurrent_same_trial_grant_consumed_once_atomically():
    from daily_budget import Ledger,BudgetBlocked
    from test_daily_budget import MemoryStore
    from concurrent.futures import ThreadPoolExecutor
    state,req,_,_,row=data();row['limit_micro_usd']=None
    store=MemoryStore();store.write('2026-11-04',0,copy.deepcopy(row))
    auth={'package_id':'a','day':'2026-11-04','limit_micro_usd':1100000,'request_sha256':'b'*64,
          'retained_entry_id':'reservation','retained_entry':copy.deepcopy(row['entries']['reservation'])}
    def reserve():
        ledger=Ledger(store,now=lambda:NOW,limit_micro_usd=None)
        ledger.context={'package_id':'a','stage':'fixed_information_writer','request_attempt':4}
        ledger.package_writing_authorization=copy.deepcopy(auth)
        try:return ledger.reserve(100,'autopilot:fixed_information_writer')
        except BudgetBlocked:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:reserve(),range(2)))
    assert sum(r is not None for r in results)==1
    assert len(store.read('2026-11-04')[1]['entries'])==4
