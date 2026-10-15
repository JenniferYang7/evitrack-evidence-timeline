import json
from pathlib import Path
from engine import (canonical_url, content_hash, detect_conflicts, eligible_evidence,
                    extract_facts, relation_score, event_relation, revision_insert, state_at)

BASE=Path(__file__).resolve().parents[1]
SEED=json.loads((BASE/'sample_evidence.json').read_text(encoding='utf-8'))


def test_time_travel_preannouncement():
    assert state_at(SEED,'2025-05-06')['status']=='证据不足'
    assert eligible_evidence(SEED, '2025-05-06')==[]


def test_announcement_vs_implementation():
    assert state_at(SEED,'2025-05-08')['status']=='已宣布，待确认落地'
    assert state_at(SEED,'2025-05-15')['status']=='已实施（有公开证据）'


def test_verified_source_trace():
    item=next(i for i in SEED if i['id']=='src_gov_0515')
    assert item['verified'] and item['facts']['effective_date']=='2025-05-15'
    assert item['url'].startswith('https://')


def test_no_numeric_conflict_among_verified_inputs():
    assert detect_conflicts(SEED,'2025-05-15')==[]


def test_rumor_conflict_does_not_override_state():
    rumor={'id':'rumor','title':'虚构测试传闻','publisher':'合成测试','published_at':'2025-05-07',
           'occurred_at':'2025-05-07','kind':'传闻','verified':False,'synthetic':True,
           'facts':{'rrr_cut_pp':1.0},'score':0,'stage':'市场解读'}
    all_items=SEED+[rumor]
    conflicts=detect_conflicts(all_items,'2025-05-15')
    assert len(conflicts)==1 and conflicts[0]['id']=='rumor'
    assert state_at(all_items,'2025-05-15')['status']=='已实施（有公开证据）'


def test_extraction_percentage_points_not_percents():
    facts=extract_facts('自2025年5月15日起，下调金融机构存款准备金率0.5个百分点（不含已执行5%准备金率的金融机构）。')
    assert facts['rrr_cut_pp']==.5
    assert facts['effective_date']=='2025-05-15'
    assert extract_facts('降准0.5%，某股票上涨5%。').get('rrr_cut_pp') is None


def test_separate_reverse_repo_rate_from_rrr():
    facts=extract_facts('逆回购利率下调0.1个百分点。降准0.5个百分点。')
    assert facts['rrr_cut_pp']==.5


def test_not_same_event():
    assert relation_score('7天逆回购利率下调0.1个百分点')==0
    assert relation_score('央行决定降准0.5个百分点')>=2


def test_url_normalization_dedup_and_revisions():
    a={'id':'a','url':'https://www.example.com/story?source=abc','excerpt':'首次披露','version':1}
    b={'id':'b','url':'https://example.com/story','excerpt':'首次披露'}
    c={'id':'c','url':'https://example.com/story','excerpt':'正文更新'}
    arr, state=revision_insert([a],b)
    assert state=='duplicate' and len(arr)==1
    arr, state=revision_insert(arr,c)
    assert state=='revised' and len(arr)==2
    assert arr[-1]['revises']=='a' and arr[-1]['version']==2


def test_no_trust_upgrade_for_user_source():
    fake={'id':'fake','title':'新增未核验','kind':'事实','verified':False,'synthetic':False,
          'score':1,'stage':'正式实施','published_at':'2025-05-06','facts':{'rrr_cut_pp':0.5}}
    assert state_at([fake], '2025-05-07')['status']=='证据不足'


def test_published_date_governs_asof_not_event_date():
    retrospective={'id':'ret','kind':'事实','verified':True,'synthetic':False,'score':5,'stage':'正式实施',
                   'published_at':'2025-06-01','occurred_at':'2025-05-15','facts':{'rrr_cut_pp':.5}}
    assert state_at([retrospective], '2025-05-20')['status']=='证据不足'


def test_source_failure_no_fake_good_status():
    assert state_at([], '2025-05-15')['status']=='证据不足'
    assert detect_conflicts([], '2025-05-15')==[]


def test_event_identity_not_just_keyword():
    assert event_relation('2025年5月7日，央行决定降准0.5个百分点')[0]=='match'
    assert event_relation('央行决定降准0.5个百分点')[0]=='needs_review'
    assert event_relation('2025年9月央行降准0.5个百分点')[0]=='different'


def test_authoritative_correction_changes_status():
    revised={'id':'official_correction','title':'假设的官方更正测试，不是真实新闻','kind':'事实',
        'score':5,'verified':True,'synthetic':False,'stage':'更正','published_at':'2025-05-20',
        'facts':{'rrr_cut_pp':.25}}
    assert state_at(SEED+[revised], '2025-05-19')['status']=='已实施（有公开证据）'
    assert state_at(SEED+[revised], '2025-05-20')['status']=='官方信息已更正'


def test_authoritative_denial_changes_status():
    denial={'id':'official_denial','title':'假设的官方否认测试，不是真实新闻','kind':'事实',
        'score':5,'verified':True,'synthetic':False,'stage':'否认','published_at':'2025-05-20',
        'facts':{}}
    assert state_at(SEED+[denial], '2025-05-20')['status']=='已否认或撤回'


def test_correction_updates_current_fact_and_labels_old_claims():
    correction={'id':'later_correction','title':'仅用于单元测试的假设更正',
        'kind':'事实','score':5,'verified':True,'synthetic':False,'stage':'更正',
        'published_at':'2025-05-20','facts':{'rrr_cut_pp':0.25}}
    event=SEED+[correction]
    status=state_at(event,'2025-05-21')
    assert status['rrr_cut_pp']==.25 and status['superseded'] is True
    conflicts=detect_conflicts(event,'2025-05-21')
    assert any(c['interpretation']=='已被后续权威更正替代的旧数值' for c in conflicts)


def test_denial_suppresses_old_current_fact():
    denial={'id':'later_denial','title':'仅用于单元测试的假设撤回',
        'kind':'事实','score':5,'verified':True,'synthetic':False,'stage':'否认',
        'published_at':'2025-05-20','facts':{}}
    status=state_at(SEED+[denial], '2025-05-21')
    assert status['superseded'] is True and status['rrr_cut_pp'] is None
