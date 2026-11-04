"""Real ledger/agent accounting for fixed roles; provider/storage stay offline."""
import json
import pytest
from daily_budget import Ledger, BudgetBlocked, PACKAGE_GROUP_LIMITS
from test_daily_budget import MemoryStore
from publishing_v2.autopilot.agents import Agents


@pytest.mark.parametrize('role,legacy,group',[
    ('fixed_information_writer','writer','writing'),
    ('fixed_information_text_review','text_review','review'),
])
def test_fixed_roles_share_existing_package_cap(role,legacy,group):
    ledger=Ledger(MemoryStore(),limit_micro_usd=None)
    ledger.context={'package_id':'synthetic','stage':legacy}
    ledger.reserve(PACKAGE_GROUP_LIMITS[group]-10,'autopilot:'+legacy)
    ledger.context={'package_id':'synthetic','stage':role}
    ledger.reserve(10,'autopilot:'+role)
    with pytest.raises(BudgetBlocked) as error:
        ledger.reserve(1,'autopilot:'+role)
    assert error.value.diagnostic['code']=='package_stage_limit'


@pytest.mark.parametrize('role',['fixed_information_writer','fixed_information_text_review'])
def test_real_agent_reserves_and_settles_fixed_role(role):
    store=MemoryStore(); ledger=Ledger(store,limit_micro_usd=None);calls=[]
    def transport(method,url,headers,payload):
        calls.append(payload)
        return {'status_code':200,'body':{'id':'offline-fixture', 'stop_reason':'end_turn',
                     'usage':{'input_tokens':10,'output_tokens':10},
                     'content':[{'type':'text','text':'{"fixture":true}'}]}}
    agent=Agents(env={'ANTHROPIC_API_KEY':'offline-fixture'},ledger=ledger,transport=transport)
    agent.package_id='synthetic'
    assert agent.run(role,{'cards':[]})=={'fixture':True}
    entries=next(iter(store.rows.values()))[1]['entries']
    assert len(entries)==1 and len(calls)==1
    row=next(iter(entries.values()))
    assert row['stage']==role and row['package_id']=='synthetic'
    assert row['status']=='settled'
    assert agent.receipts[0]['role']==role


@pytest.mark.parametrize('role,legacy,group',[
    ('fixed_information_writer','writer','writing'),
    ('fixed_information_text_review','text_review','review'),
])
def test_fixed_agent_never_contacts_provider_when_shared_group_exhausted(role,legacy,group):
    ledger=Ledger(MemoryStore(),limit_micro_usd=None)
    ledger.context={'package_id':'synthetic','stage':legacy}
    ledger.reserve(PACKAGE_GROUP_LIMITS[group],'autopilot:'+legacy)
    def forbidden(*a,**kw): pytest.fail('provider contacted after package allowance exhausted')
    agent=Agents(env={'ANTHROPIC_API_KEY':'offline-fixture'},ledger=ledger,transport=forbidden)
    agent.package_id='synthetic'
    with pytest.raises(BudgetBlocked) as error:
        agent.run(role,{'cards':[]})
    assert error.value.diagnostic['code']=='package_stage_limit'
    assert agent.receipts==[]
