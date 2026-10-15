"""EviTrack — AI-assisted investment event intelligence and auditable evidence timeline."""
from __future__ import annotations
import json
import os
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from engine import (SOURCE_SCORES, annotate_source, detect_conflicts, eligible_evidence,
                    extract_facts, relation_score, event_relation, revision_insert, state_at)
from ai_assist import classify_with_llm

ROOT = Path(__file__).resolve().parent
with open(ROOT/'sample_evidence.json', encoding='utf-8') as f:
    SEED = json.load(f)

st.set_page_config(page_title='EviTrack｜投资事件证据时间线', page_icon='🧭', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container{padding-top:1.7rem;padding-bottom:3.5rem;max-width:1380px}
[data-testid="stMetric"]{border:1px solid #e5e9f0;border-radius:13px;padding:15px;background:#fcfdff}
h1,h2,h3{letter-spacing:-.025em}
[data-testid="stSidebar"]{background:#f7f9fc}
.mini-label{color:#77849a;font-size:.84rem;text-transform:uppercase;font-weight:700;letter-spacing:.06em}
.hero{background:linear-gradient(110deg,#112e47,#205e69);color:white;border-radius:18px;padding:26px 30px;margin-bottom:18px}
.hero h2{color:white;margin:0 0 9px;font-size:1.65rem}
.hero p{margin:0;color:#dbe9ed;font-size:.94rem}
.disclaimer{border-left:4px solid #76919e;background:#f1f5f7;border-radius:5px;padding:12px 14px;margin:10px 0;font-size:.87rem}
.evidence-dot{color:#18777f}
</style>''', unsafe_allow_html=True)

if 'evidence' not in st.session_state:
    st.session_state['evidence'] = SEED.copy()
if 'synthetic_enabled' not in st.session_state:
    st.session_state['synthetic_enabled'] = False
if 'watchlist' not in st.session_state:
    st.session_state['watchlist'] = []

SYNTHETIC = {
    'id': 'synthetic_test_rumour', 'title': '合成测试：网上传言本次降准1个百分点（虚构案例）',
    'publisher': '合成测试数据，非真实媒体或传闻', 'source_type': '未经证实传闻', 'score': 0,
    'kind': '传闻', 'stage': '市场解读', 'published_at': '2025-05-07', 'occurred_at': '2025-05-07',
    'collected_at': '2026-10-15', 'updated_at': None, 'verified': False, 'synthetic': True,
    'url': '', 'excerpt': '【合成测试材料，非真实新闻】网传央行此次降准1个百分点，尚无官方证实。',
    'facts': {'rrr_cut_pp': 1.0}, 'basis': '仅供冲突检测与传闻降权的测试，不得当作真实新闻。', 'version': 1
}

with st.sidebar:
    st.markdown('### 🧭 EviTrack')
    st.caption('让每一个投资事件，都能回到证据。')
    st.divider()
    st.markdown('**跟踪事件**')
    st.info('2025年5月央行下调金融机构存款准备金率', icon='📌')
    st.caption('样例事件 EVT-PBOC-RRR-202505 | 历史事件演示')
    asof = st.date_input('证据回放截至日期', value=date(2025,5,15), min_value=date(2025,5,1), max_value=date.today(), help='仅纳入截至该日已公开的材料；不使用未来材料提前得出结论。')
    asof_s = asof.isoformat()
    st.caption('可试试 2025-05-08 和 2025-05-15，观察状态变化。')
    st.divider()
    types = st.multiselect('查看哪些证据类型', ['事实','观点','推测','传闻'], default=['事实','观点','推测','传闻'])
    st.toggle('开启合成冲突测试', key='synthetic_enabled', help='额外加入一条明确标注为虚构的1个百分点传闻，仅用于验证冲突提示。')
    st.divider()
    st.markdown('**关注标的（可选）**')
    watch_text = st.text_input('股票/ETF代码或名称', placeholder='如：银行ETF、沪深300')
    if st.button('加入关注', use_container_width=True, disabled=not watch_text.strip()):
        token=watch_text.strip()[:32]
        if token not in st.session_state.watchlist:
            st.session_state.watchlist.append(token)
            st.rerun()
    if st.session_state.watchlist:
        st.caption('、'.join(st.session_state.watchlist))
        if st.button('清空关注', use_container_width=True):
            st.session_state.watchlist=[]
            st.rerun()
    st.divider()
    st.caption('本产品用于公开信息研究，不构成投资建议。样例源在2026-10-15人工核对，**不具备实时新闻同步**。')

all_items = list(st.session_state.evidence)
if st.session_state.synthetic_enabled:
    all_items += [SYNTHETIC]
visible = eligible_evidence(all_items, asof_s)
visible_sorted = sorted(visible, key=lambda it:(it['published_at'], it['occurred_at'],it['id']))
conflicts = detect_conflicts(all_items, asof_s)
status = state_at(all_items, asof_s)
filtered = [x for x in visible_sorted if x.get('kind') in types]

st.markdown('''<div class="hero"><h2>投资事件情报与证据时间线</h2><p>一个事件 · 多种来源 · 四种时间 · 可解释结论 · 版本与冲突追踪</p></div>''', unsafe_allow_html=True)
st.markdown('**2025年央行降准政策**　·　事件编号 `EVT-PBOC-RRR-202505`　·　历史证据演示')
st.caption(f'当前回放时间：{asof_s}｜所有事件判断只使用此日期之前已披露的材料')

c1,c2,c3,c4 = st.columns(4)
c1.metric('事件状态', status['status'])
c2.metric('可见证据', len(visible))
c3.metric('已核验来源', sum(1 for x in visible if x.get('verified') and not x.get('synthetic')))
c4.metric('冲突提示', len(conflicts))
st.info('📍 '+status['explanation'])

summary, timeline, conflict_tab, ingest, audit = st.tabs(['事件总览','证据时间线','冲突与状态变化','添加 / AI处理证据','数据与审计'])

with summary:
    left, right = st.columns([1.45,1])
    with left:
        st.subheader('当前可证实的核心结论')
        if status['status'] == '证据不足':
            st.warning('截至该回放日期，可信证据不足。不得使用事后信息推断公告细节。')
        elif status.get('superseded'):
            st.error(f"**当前权威更新状态**：{status['status']}。之前公告内容已失效或需要重新核实，以下不展示旧公告为当前有效事实。")
            if status.get('rrr_cut_pp') is not None:
                st.markdown(f"- **后续更正值**：{status['rrr_cut_pp']} 个百分点（请以更正来源原文为准）。")
            for evid in visible:
                if evid['id'] in status.get('sources',[]) and evid.get('url'):
                    st.markdown(f"- [最新更正/否认来源：{evid['publisher']}]({evid['url']})")
        else:
            st.markdown(f"- **已核验的降准幅度**：**{status['rrr_cut_pp']} 个百分点**；不含已执行5%准备金率的金融机构。")
            st.markdown('- **首次公开披露**：2025年5月7日；**计划生效日期**：2025年5月15日。')
            st.markdown('- **流动性规模**：公告预计释放约 **1万亿元** 长期流动性，并非实际到账核算。')
            st.markdown(f"- **截至回放日的状态**：{status['status']}。")
            if status['status'] == '已宣布，待确认落地':
                st.warning('截至该回放日，没有足够的公开实施证据，不能将“将实施”写成“已实施”。')
        available_sources=[e for e in visible if e.get('verified') and e.get('kind')=='事实' and e.get('url')]
        if available_sources:
            st.markdown('**截至回放日可见的主要来源**')
            for src in available_sources[:3]:
                st.markdown(f"- [{src['publisher']}（{src['published_at']}）]({src['url']})")
    with right:
        st.subheader('证据判断方法')
        st.markdown('**官方实录 > 官方转载 > 新闻报道 > 分析观点 > 未经证实材料**')
        st.caption('这是产品的可解释优先级规则，并不意味着官方来源绝对不会出错；发生更正时须保留旧版和新版。')
        st.markdown('**事实与观点分开**')
        st.write('“降准0.5个百分点”是公告事实；“某类股票一定上涨”不是政策事实。')
        st.markdown('**同一事件不同阶段**')
        st.write('2025-05-07 宣布 → 2025-05-15 正式实施。')
        st.markdown('**标的关联说明**')
        if st.session_state.watchlist:
            for item in st.session_state.watchlist:
                st.write(f'• {item}：目前只有银行体系流动性的宏观传导背景，未取得该具体标的的直接影响证据。')
        else:
            st.write('银行体系为政策直接涉及环节；具体股票涨跌与此政策的因果关系尚未证明。')
    st.divider()
    st.subheader('证据构成')
    if visible:
        kind_ct = pd.Series([x.get('kind','未知') for x in visible]).value_counts()
        st.bar_chart(kind_ct, horizontal=True, height=200)
    else:
        st.caption('该回放日期前无披露证据。')

with timeline:
    st.subheader('按披露时间排序的证据链')
    st.caption('时间字段不能混用：发生时间是事件发生日期；披露时间是来源公开日期；采集时间是录入产品的日期；更新日期用于版本更正。当前公开材料仅提供日级粒度。')
    if not filtered:
        st.warning('当前时间范围/筛选条件下没有证据。')
    for item in filtered:
        with st.container(border=True):
            header_l, header_r = st.columns([3,1])
            with header_l:
                st.markdown(f"#### {item['title']}")
                st.caption(f"{item['publisher']} · {annotate_source(item)} · 类型：{item['kind']} · 阶段：{item['stage']}")
            with header_r:
                st.markdown(f"**披露** {item['published_at']}")
                st.caption(f"发生：{item.get('occurred_at') or '未披露'}")
            if item.get('synthetic'):
                st.error('这是虚构的测试输入，**不是**现实发生的传闻。')
            if not item.get('verified'):
                st.warning('用户新增内容尚未核验，不能自动升级为已确认事实。')
            st.write(item['excerpt'])
            with st.expander('证据字段、时间与版本（可追溯）'):
                a,b,c = st.columns(3)
                a.write(f"**采集日期**：{item.get('collected_at','未记录')}")
                b.write(f"**更新日期**：{item.get('updated_at') or '未发现更正'}")
                c.write(f"**版本**：v{item.get('version',1)}")
                st.write(f"**事实字段**：{json.dumps(item.get('facts',{}), ensure_ascii=False)}")
                st.write(f"**校验/引用说明**：{item.get('basis','无')}")
                if item.get('revises'):
                    st.write(f"**修订自**：{item['revises']}（旧版未删除）")
                st.code(item['id'])
            if item.get('url') and urlparse(item['url']).scheme in ('http','https'):
                st.link_button('查看原始来源 ↗', item['url'], type='secondary')

with conflict_tab:
    st.subheader('冲突检测与证据优先级')
    if conflicts:
        for c in conflicts:
            st.error(f"⚠️ **{c['title']}** 主张降准 **{c['claimed']} 个百分点**，与已核验证据中的 **{c['accepted']} 个百分点** 不一致。")
            st.caption(f"基准来源：{c['trusted_source_title']}（{c['trusted_source_id']}）。该记录：{'合成测试，非真实消息' if c['synthetic'] else '已核验' if c['verified'] else '待核验'}。类型：{c.get('interpretation','数值存在矛盾')}。保留冲突，不静默覆盖权威数值。")
    else:
        st.success('截至所选日期，尚未发现已录入证据中关于主要降准幅度的数值冲突。此结果不代表市场上不存在其他争议。')
    st.markdown('**点击侧边栏「开启合成冲突测试」**，检查一个虚构的“降准1个百分点”消息是否被正确降权、标记冲突，并且不会覆盖官方结论。')
    st.divider()
    st.subheader('政策状态如何随时间变化')
    transitions = [('2025-05-06','公告前'),('2025-05-08','宣布后'),('2025-05-15','正式实施后')]
    cols=st.columns(3)
    for col, (day, label) in zip(cols,transitions):
        with col:
            st.markdown(f'**{label}**')
            st.markdown(f'`{day}`')
            if day > asof_s:
                st.caption('超出回放日期，未来状态不可见')
            else:
                snapshot=state_at(all_items, day)
                st.info(snapshot['status'])
    st.caption('状态是由当日可见的证据和确定性逻辑推导，并非大模型自由生成。')
    st.subheader('边界与异常处理')
    st.markdown('- **错用未来证据** → 将披露时间晚于回放日期的文档排除。\n- **新闻重复转载** → 按规范化 URL 和文本指纹去重。\n- **同一链接内容修正** → 追加版本，不删除旧证据。\n- **来源有争议** → 显式显示冲突及来源可信程度。\n- **AI模型不可用** → 提示失败，保留原始证据与规则引擎。\n- **未提供行情或个股研究** → 不声称已证明具体股票的价格因果关系。')

with ingest:
    st.subheader('新增一条来源或修订版本')
    st.caption('输入文档后，产品先做本地事件关联与事实字段提取；AI仅帮助分类和总结，不能自动将不明来源提升为可信事实。')
    with st.form('new_source', clear_on_submit=False):
        t=st.text_input('标题', value='', placeholder='如：某机构发布对降准的解读')
        pub=st.text_input('发布机构/媒体', value='', placeholder='如：机构官网')
        url=st.text_input('原始来源链接', placeholder='https://...（可暂不填写，但来源将无法外链追溯）')
        x,y=st.columns(2)
        with x:
            published=st.date_input('公开披露日期',value=date.today(),key='pubdate')
            category=st.selectbox('材料性质', ['事实','观点','推测','传闻'])
        with y:
            happened=st.date_input('所述事件发生日期',value=date.today(),key='eventdate')
            stage=st.selectbox('阶段', ['宣布','正式实施','市场解读','更正','否认','过期'])
        snippet=st.text_area('原始材料内容（请保留可核查的事实和单位）', height=155, placeholder='粘贴来源原文或准确摘录，不要只粘贴结论')
        confirm=st.checkbox('如果缺少事件日期，确认该资料讨论的是2025年5月本次降准（仍标记为待核验）', value=False)
        submit=st.form_submit_button('检查并录入证据', type='primary')
    if submit:
        clean_url=url.strip()
        if not t.strip() or not snippet.strip() or not pub.strip():
            st.error('请填写标题、发布机构和材料内容。')
        elif clean_url and urlparse(clean_url).scheme not in ('http','https'):
            st.error('来源地址必须是 http(s) URL。')
        elif len(snippet)>10000:
            st.error('单条内容请不超过10000字。')
        else:
            relation, explanation=event_relation(t+' '+snippet)
            facts=extract_facts(snippet)
            st.info(f'关联检测：{relation}（{explanation}） | 提取字段：{json.dumps(facts,ensure_ascii=False)}')
            if relation=='different':
                st.error('可能是其他事件，系统拒绝自动合并；请核对事件身份。')
            elif relation=='needs_review' and not confirm:
                st.error('材料事件归属不明确。请先核查并勾选确认，否则不允许合并。')
            else:
                obj={'id':'usr_'+uuid4().hex[:10], 'title':t.strip(), 'publisher':pub.strip(),
                    'source_type':'待核验材料', 'score':1, 'kind':category,'stage':stage,
                    'published_at':published.isoformat(), 'occurred_at':happened.isoformat(),
                    'collected_at':date.today().isoformat(), 'updated_at':date.today().isoformat(),
                    'verified':False,'synthetic':False,'url':clean_url, 'excerpt':snippet.strip(),
                    'facts':facts, 'basis':'用户提交；仅规则提取；尚未由人工对照原文确认。'}
                if category in ('观点','推测','传闻'):
                    obj['facts'] = facts  # retained as claims only; never accepted for state
                new_items, outcome=revision_insert(st.session_state.evidence,obj)
                if outcome=='duplicate':
                    st.warning('识别为重复来源与相同内容，已拦截重复录入。')
                else:
                    st.session_state.evidence = new_items
                    st.success('已添加证据。' if outcome=='added' else '检测到相同来源的不同正文，已保留旧版并添加修订版。')
                    st.warning('重要：新增来源尚未人工核验，仅参与冲突提示，不进入权威事实与状态判定。')
    st.divider()
    st.subheader('AI 分拣助手（可选）')
    st.caption('API Key 仅在服务器环境变量中配置；AI 不作最终投资判断。提交内容将发送到所配置的模型服务。')
    ai_text=st.text_area('待分析文本',height=90,placeholder='粘贴公告/新闻/研报观点... ',key='ai_text')
    if st.button('调用大模型分析', disabled=not ai_text.strip()):
        if relation_score(ai_text)<2:
            st.warning('这段材料与当前事件关联较弱，需人工确认，避免错误合并。')
        try:
            server_key=st.secrets.get('OPENAI_API_KEY')
        except (FileNotFoundError, KeyError, Exception):
            server_key=None
        with st.spinner('正在分析，若未配置Key则会提示...'):
            result,err=classify_with_llm(ai_text, api_key=server_key)
        if err:
            st.warning(err)
        else:
            st.json(result)
            st.caption('以上为AI初步归纳，不是经来源验证的事实；原文与时间字段仍需核验。')

with audit:
    st.subheader('证据原始字段与审计导出')
    rows=[]
    for e in visible_sorted:
        rows.append({k:e.get(k) for k in ('id','title','publisher','source_type','kind','stage','published_at','occurred_at','collected_at','updated_at','verified','synthetic','version','url')})
    if rows:
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else:
        st.info('截至该日尚无证据。')
    st.download_button('导出截至该日的证据 JSON', data=json.dumps(visible_sorted,ensure_ascii=False,indent=2),file_name='evidence_asof_'+asof_s+'.json',mime='application/json')
    st.markdown('**字段和来源说明**')
    st.markdown('- `rrr_cut_pp`：降准幅度，单位是**百分点**，不是百分比。\n- `expected_liquidity_cny_trillion`：预计流动性，单位为**万亿元人民币**。\n- `occurred_at`：事实发生日期；`published_at`：来源披露日期；`collected_at`：产品收录日期；`updated_at`：修订记录日期。\n- `verified`：示例由人工对照网页核查，用户新增材料一律 `false`，禁止由AI擅自确认。\n- `synthetic`：合成测试数据，独立展示，不得伪装为实际新闻。')
    st.warning('本MVP采用人工核验的历史示例材料与用户新增证据。尚未接通实时公告抓取、行情数据、持久化数据库或自动监控提醒。部署者须自行检查数据许可与平台条款。')
    st.caption('验证/测试步骤请参阅 README.md、TEST_PLAN.md 与 AI_USAGE.md。')

st.divider()
st.caption('EviTrack · Research demo · Facts are linked to original sources; interpretations are explicitly marked. No investment advice or return guarantees.')
