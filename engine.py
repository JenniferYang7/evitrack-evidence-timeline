"""Auditable, deterministic event/evidence state machine (not investment advice)."""
from __future__ import annotations
from datetime import date
from urllib.parse import urlsplit, urlunsplit
import hashlib
import re

EVENT_KEYWORDS = ('降准', '存款准备金率', 'reserve requirement', 'rrr cut')
SOURCE_SCORES = {'官方原始披露': 5, '权威官方转载': 4, '专业媒体': 3, '分析观点': 2, '待核验材料': 1, '未经证实传闻': 0}


def canonical_url(url: str) -> str:
    if not url: return ''
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower().removeprefix('www.'),p.path.rstrip('/'),'', ''))


def content_hash(text: str) -> str:
    return hashlib.sha256(' '.join(text.strip().split()).encode('utf-8')).hexdigest()


def relation_score(text: str) -> int:
    content = text.lower()
    return sum(2 if kw in content else 0 for kw in EVENT_KEYWORDS)


def event_relation(text: str) -> tuple[str, str]:
    """Conservative event identity: topic similarity alone does not justify auto-merging."""
    if relation_score(text) < 2:
        return 'different', '未识别到降准/存款准备金率主题。'
    other_events = re.findall(r'(20\d{2})年(\d{1,2})月[^。；\n]{0,35}?(?:降准|存款准备金率)', text)
    if any((int(y),int(m)) != (2025,5) for y,m in other_events):
        return 'different', '发现不同年月的降准线索，可能属于另一事件，不得自动合并。'
    if re.search(r'2025年5月|2025[-/]05[-/](?:07|15)|5月(?:7|15)日', text):
        return 'match', '明确出现本事件的2025年5月或关键日期。'
    return 'needs_review', '只识别到同类政策主题，没有足够日期信息证明是同一次降准。'


def _find_r_rrr(text: str):
    # Only recognize values explicitly expressed in *percentage points*, never confuse % with pp.
    # Separate clauses to avoid reading the unrelated 7-day repo-rate cut as an RRR cut.
    for clause in re.split(r'[。；;\n]', text):
        for fragment in re.split(r'[，,]', clause):
            if '降准' not in fragment and '存款准备金率' not in fragment:
                continue
            if '汽车金融公司' in fragment or '金融租赁公司' in fragment:
                continue  # separate target population; do not compare with general-bank RRR
            match = re.search(r'(?:降准|下调|降低)[^。；，,\n]{0,32}?([0-9]+(?:\.[0-9]+)?)\s*个?百分点', fragment)
            if match:
                return float(match.group(1))
    return None


def extract_facts(text: str) -> dict:
    result = {}
    cut = _find_r_rrr(text)
    if cut is not None:
        result['rrr_cut_pp'] = cut
    # Only infer date when sentence specifically mentions RRR and an effective-date verb.
    for sentence in re.split(r'[。；;\n]', text):
        if not ('降准' in sentence or '存款准备金率' in sentence):
            continue
        match = re.search(r'(?:自|从)?\s*(20\d{2})年(\d{1,2})月(\d{1,2})日(?:起|开始|实施|落地)', sentence)
        if match:
            result['effective_date'] = f'{int(match.group(1)):04}-{int(match.group(2)):02}-{int(match.group(3)):02}'
            break
        match = re.search(r'(?:自|从)?\s*(\d{1,2})月(\d{1,2})日(?:起|开始|实施|落地)', sentence)
        if match:
            result['effective_date'] = f'2025-{int(match.group(1)):02}-{int(match.group(2)):02}'
            break
    return result


def eligible_evidence(items: list[dict], as_of: str) -> list[dict]:
    """As-of uses publication time, not underlying event date. Avoid hindsight leaks."""
    return [it for it in items if it.get('published_at', '9999') <= as_of]


def authoritative(items: list[dict]) -> list[dict]:
    return [it for it in items if it.get('verified') and not it.get('synthetic') and it.get('kind') == '事实' and it.get('score', 0) >= 3]


def state_at(items: list[dict], as_of: str) -> dict:
    seen = eligible_evidence(items, as_of)
    strong = authoritative(seen)
    # Later independently verified official corrections / denials override an earlier state.
    updates = [it for it in strong if it.get('score',0) >= 4 and it.get('stage') in ('更正','否认','过期')]
    if updates:
        latest_update = max(updates, key=lambda x: (x['published_at'], x.get('score',0)))
        eligible_prior_stages = [it for it in strong if it.get('stage') in ('宣布','正式实施')]
        if not eligible_prior_stages or latest_update['published_at'] >= max(it['published_at'] for it in eligible_prior_stages):
            stage = latest_update['stage']
            statuses = {'更正': '官方信息已更正', '否认': '已否认或撤回', '过期': '信息已过期，待复核'}
            detail = latest_update.get('facts',{}).get('rrr_cut_pp')
            message = ('后续权威来源已发布'+stage+'信息，不能继续沿用旧结论。' +
                       (f' 当前更正后的指标：{detail}个百分点。' if stage=='更正' and detail is not None else ' 请查看最新原文。'))
            return {'status': statuses[stage], 'explanation':message, 'sources':[latest_update['id']], 'rrr_cut_pp': detail if stage == '更正' else None, 'superseded': True}
    announced = any(it.get('stage') in ('宣布', '正式实施') and it.get('facts', {}).get('rrr_cut_pp') == .5 for it in strong)
    implemented = any(it.get('stage') == '正式实施' and it.get('facts', {}).get('rrr_cut_pp') == .5 for it in strong)
    if implemented:
        return {'status': '已实施（有公开证据）', 'explanation': '截至选定日期，已看到降准实施报道；这是历史事件状态，不代表最新市场走势。', 'sources': [it['id'] for it in strong if it.get('stage')=='正式实施'], 'rrr_cut_pp': 0.5, 'superseded': False}
    if announced:
        return {'status': '已宣布，待确认落地', 'explanation': '已有明确公告，尚无截至所选日期的实施证据；不应提前显示为“已实施”。', 'sources': [it['id'] for it in strong if it.get('stage')=='宣布'], 'rrr_cut_pp': 0.5, 'superseded': False}
    return {'status': '证据不足', 'explanation': '截至选定日期，尚缺少可靠官方/媒体的有效公告证据。', 'sources': [], 'rrr_cut_pp': None, 'superseded': False}


def detect_conflicts(items: list[dict], as_of: str) -> list[dict]:
    seen = eligible_evidence(items, as_of)
    trusted = authoritative(seen)
    baseline = next((it for it in sorted(trusted, key=lambda x:(x.get('score', 0),x['published_at']), reverse=True) if it.get('facts',{}).get('rrr_cut_pp') is not None), None)
    if not baseline:
        return []
    accepted = baseline['facts']['rrr_cut_pp']
    active = state_at(items, as_of)
    is_post_correction = active.get('status') == '官方信息已更正' and active.get('sources') == [baseline['id']]
    conflicts = []
    for it in seen:
        n = it.get('facts', {}).get('rrr_cut_pp')
        if n is not None and abs(n-accepted) > 1e-6:
            conflicts.append({'id': it['id'], 'title': it['title'], 'claimed': n, 'accepted': accepted, 'trusted_source_id': baseline['id'], 'trusted_source_title': baseline['title'], 'verified': it.get('verified', False), 'synthetic': it.get('synthetic', False), 'kind': it.get('kind','未知'), 'publisher':it.get('publisher',''),
                              'interpretation': '已被后续权威更正替代的旧数值' if is_post_correction and it.get('verified') and it.get('published_at','') < baseline.get('published_at','') else '尚待核查的数值矛盾'})
    return conflicts


def revision_insert(items: list[dict], new: dict) -> tuple[list[dict], str]:
    """Same URL and text -> dedup; same URL different text -> versioned revision."""
    items = list(items)
    norm = canonical_url(new.get('url',''))
    existing = [e for e in items if norm and canonical_url(e.get('url','')) == norm]
    fresh = content_hash(new.get('excerpt', ''))
    for e in existing:
        if content_hash(e.get('excerpt','')) == fresh:
            return items, 'duplicate'
    if existing:
        prev = max(existing, key=lambda x: x.get('version',1))
        new = dict(new, revises=prev['id'], version=prev.get('version', 1)+1)
        items.append(new)
        return items, 'revised'
    items.append(dict(new, version=1))
    return items, 'added'


def annotate_source(source: dict) -> str:
    label = f"{source.get('source_type', '未知来源')} | {'已核验' if source.get('verified') else '待人工核验'}"
    if source.get('synthetic'):
        label += ' | 合成测试，不是真实新闻'
    return label
