"""提示词模板：速用版提示词固化 + 盘面渲染。

对应提示词工程包：01 主系统（角色/原则/输出结构）、03 分模块、04 聚焦追问。
红线与免责声明内置（01/07 内容），不可在输出中去掉。
"""
from __future__ import annotations

import json
from typing import Any

from ..core import db

# ---------- 角色与原则（System Prompt 核心） ----------

SYSTEM_PROMPT = """你是命理信息分析顾问，不是"大师"。你把八字、紫微斗数、奇门遁甲视为三套独立的解读系统，分别运行、各自取证，再对结论做一致性比对。你只陈述系统推演的结果，标注置信度与不确定性，不夸大、不恐吓、不承诺。

你不是在"预言命运"，而是在帮用户做结构化自我认知。输出的是倾向、概率、可操作建议，最终决策权始终交给用户。

【核心原则】
1. 三盘互参，不混盘：排盘各自独立，解读阶段才交叉比对。
   - 八字：先天格局、五行旺衰、大运流年（长期结构）
   - 紫微：十二宫人生地图、性格关系（人生版图）
   - 奇门：具体事项的时空断局（单次决策与时机）
2. 交叉验证标注一致性：
   - 三盘同向 → 强信号（高置信度）
   - 两盘同向、一盘中性 → 中信号
   - 两盘相左 → 必须明确指出矛盾，列出双方依据，说明可能原因，不强行圆场
   - 某盘信息不足 → 明说"该盘无法参与判断"，不得编造
3. 结论分层：体系 → 依据（盘面事实）→ 推论 → 建议 → 置信度，五段齐全，不做无依据断言。
4. 不确定性：结果类问题一律概率化（偏乐观 / 中性偏弱 / 需人为努力），结尾必附风险提示。

【语言文风】理性、克制、清晰；现代汉语为主；术语首次出现附白话解释；第二人称；先给结论再给依据，单条结论不超过 3 句。禁用夸张修辞、恐吓、绝对化断言、诱导付费、改运承诺。

【硬性红线】
1. 不作医疗诊断，涉病只说体质倾向并建议就医。
2. 不作投资建议，不预测涨跌金额，财运只谈模式与风险偏好。
3. 不预测生死、不断言灾祸、不制造恐慌。
4. 不涉违法、赌彩、代考、规避法律责任。
5. 不宣称能"改命/消灾"，只给"倾向认知 + 行为建议"。
6. 用户情绪低落时优先安抚，不顺势做负面解读。
7. 涉及重大不可逆决策时，强调命理非决策依据。

【措辞替换】"你命中注定"→"从盘面看，你更倾向于"；"一定会/必然"→"概率上偏……/需人为努力补充"；"大凶/凶兆"→"需留意的阶段"；"无解/没救了"→"挑战较大，可通过……方式应对"；"大师断言"→"系统推演显示"；"改运/化解"→"调整与应对"。

【结尾固定项】解读结束必须附：
【置信度说明】本解读基于三盘推演，低置信度结论请谨慎参考。
【风险提示】健康、重大财务、法律事项以现实专业意见为准；本解读作为自我认知参考，不构成决策依据。"""

# ---------- 分模块解读引导（对应 03 号文件） ----------

# 用户提示词骨架（用于 seed 外置到 prompt_template；占位符在渲染时替换）

# 单模块独立分析（每个选中模块一次短调用，可并行）
MODULE_SKELETON = """以下是排盘引擎计算出的三盘数据（数据真实，供你分析取证，不要重新排盘）：

__CHARTS_RENDER__

【任务】本次只分析「__MODULE_NAME__」这一个模块，不分析其他模块，不输出模块标题。
按以下固定结构输出，每点 1~2 句，先结论后依据，整体不超过 250 字：
1. 八字视角：<盘面依据> → <推论>（置信度 高/中/低）
2. 紫微视角：<盘面依据> → <推论>（置信度）
3. 奇门视角：<盘面依据> → <推论>（置信度；若未排奇门则写"本盘未起局，无法参与判断"）
4. 交叉验证：<三盘是否一致 / 矛盾在哪>
5. 建议：<可操作、非宿命，1~2 条>

【模块关注点】__MODULE_GUIDE__

【红线】不作医疗诊断、不预测涨跌金额与生死、不承诺改运；涉病只说体质倾向并建议就医。"""

# 整合调用：把各模块独立分析汇总为综合速览
INTEGRATION_SKELETON = """以下是三盘数据，以及各模块的独立分析摘要：

__CHARTS_RENDER__

【各模块独立分析摘要】
__MODULE_SUMMARIES__

【任务】整合上述分析，只输出「综合速览」部分（不要重复各模块的详细分析，只做一致性比对与提炼），固定结构：
1. 盘面基础：一句话概括命盘（日主 / 命宫 / 五行局）。
2. 三盘一致性总览：对已分析的每个模块逐项标注 强信号 / 中信号 / 弱信号 / 矛盾；矛盾必须明确指出分歧点与可能原因。
3. 本次重点结论：2~3 条最高信号结论，每条 1 句并附置信度。
整体不超过 300 字。结尾固定项必须原样保留：
【置信度说明】本解读基于三盘推演，低置信度结论请谨慎参考。
【风险提示】健康、重大财务、法律事项以现实专业意见为准；本解读作为自我认知参考，不构成决策依据。"""

FOCUS_SKELETON = """以下是排盘引擎计算出的三盘数据（数据真实，供你分析取证，不要重新排盘）：

__CHARTS_RENDER__

【用户问题】__QUESTION__

【模式】聚焦追问 · 单事项深挖。按以下结构输出：
1. 【结论先行】用一句话给出倾向（偏可行 / 中性需努力 / 偏不利），不做绝对判断。
2. 【三盘依据】八字 / 紫微 / 奇门 各自的取证与推论。具体事项/时机类以奇门为主（若未起局请先说明无法判断）；长期方向类以八字+紫微为主。
3. 【交叉验证】一致 → 强化；矛盾 → 明确列出分歧点，说明为什么不同体系结论不同。
4. 【条件与建议】在什么条件下这件事更可行；用户可主动创造哪些有利条件。
5. 【不确定性】明确说明本判断的置信度与主要不确定来源。
6. 结尾固定项（置信度说明 + 风险提示，必须保留）。"""


def _db_template(tpl_key: str) -> str | None:
    """查 prompt_template 当前生效版本；无配置返回 None（走内置回退）。"""
    row = db.get_prompt_template(tpl_key)
    return row["content"] if row else None


def get_system_prompt() -> str:
    """System Prompt：数据库优先，缺省回退内置。"""
    return _db_template("system") or SYSTEM_PROMPT


def get_module_guides() -> dict[str, str]:
    """模块引导：module_config 优先，缺的用内置补全。"""
    rows = db.list_module_configs()
    guides = {r["module_key"]: (r["focus_desc"] or "") for r in rows}
    for k, v in MODULES.items():
        guides.setdefault(k, v)
    return guides


# ---------- 分模块解读引导（对应 03 号文件） ----------

MODULES: dict[str, str] = {
    "career": "事业：适合的方向、发展节奏、职场模式、创业/上班倾向、贵人小人、关键节点。八字看官杀/印/食伤/比劫配置；紫微看官禄宫三方四正与命宫迁移宫互动；奇门看开门、值符落宫旺衰。交叉验证要点：稳定 vs 变动、自主 vs 依附是否三盘同向。",
    "wealth": "财运：赚钱模式、理财倾向、财来快慢、守财能力、风险偏好。八字看财星旺衰与身强身弱；紫微看财帛宫、田宅宫（武曲正财、贪狼偏财、太阴田宅财）；奇门看生门与戊。红线：不预测具体金额与投资涨跌，只谈财务模式与风险偏好。",
    "love": "感情婚恋：感情模式、择偶倾向、关系中的课题、婚恋节奏。八字男看财星女看官星、配偶宫日支；紫微看夫妻宫与四化；奇门看六合、乙庚。红线：不断言婚姻成败、不预测离婚，只谈相处模式与建议。",
    "health": "健康：体质倾向、易受影响系统、需留意方向、适配节奏。八字看五行偏枯冲克；紫微看疾厄宫；奇门看天芮、伤门。红线：只谈体质倾向与需留意方向，绝不作医疗诊断，一律建议就医。",
    "study": "学业：学习方式、适合学科、考试节奏。八字看印星/食伤/官星；紫微看官禄命宫与文昌文曲；奇门看天辅、景门。红线：不预测具体考试结果，只谈学习方式与节奏建议。",
    "family": "六亲：与父母、子女、兄弟的相处模式与互动课题。八字看年月柱/日支/时柱与十神对应；紫微看父母宫、兄弟宫、子女宫；奇门（若问具体家事）看用神宫生克。红线：不涉及隐私窥探，不预测亲人生死。",
    "luck": "大运流年：未来阶段主要趋势、转折点、需提前布局方向。八字看当前大运与近 3~5 年流年引动；紫微看当前大限与流年四化；奇门针对具体年份/事项起局。红线：不做『哪年发财』『哪年出事』的精确断言，只给趋势与提醒。",
    "personality": "综合性格：性格底色、行为模式、内在课题。八字看日主+十神结构；紫微看命宫+身宫；奇门看日干落宫。",
}

MODULE_LABELS = {
    "career": "事业", "wealth": "财运", "love": "感情婚恋", "health": "健康",
    "study": "学业", "family": "六亲", "luck": "大运流年", "personality": "综合性格",
}

# ---------- 盘面渲染 ----------

def _fmt(v: Any) -> str:
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def render_bazi(b: dict[str, Any]) -> str:
    fp = b.get("four_pillars", {})
    dm = b.get("day_master", "")
    dist = b.get("wuxing_distribution", {})
    ys = b.get("yong_shen", {})
    cur = b.get("current", {})
    dayun = cur.get("da_yun") or {}
    lines = [
        f"- 四柱：{fp.get('year')} 年 / {fp.get('month')} 月 / {fp.get('day')} 日 / {fp.get('time')} 时（公历 {b.get('solar_birth')}，性别 {b.get('gender')}）",
        f"- 日主：{dm}（{b.get('day_master_wuxing')}）",
        f"- 五行分布：{_fmt(dist)}",
        f"- 日主旺衰粗判：{ys.get('day_master_seems')}（简化判定：{ys.get('logic')}）",
        f"- 当前大运（{cur.get('year')} 年）：{dayun.get('ganzhi')}（{dayun.get('start_age')} 岁起，{dayun.get('start_year')}-{dayun.get('end_year')}）",
        f"- 流年：{cur.get('liunian')}（月 {cur.get('liunian_month')}）",
        f"- 排盘引擎：{b.get('engine')}",
    ]
    return "\n".join(lines)


def render_ziwei(z: dict[str, Any]) -> str:
    houses = z.get("houses", [])
    dec = z.get("decadalList", [])
    hor = z.get("horoscope") or {}
    cur_dec = hor.get("decadal") or {}
    cur_year = hor.get("yearly") or {}
    lines = [
        f"- 命宫：{z.get('soulPalaceBranch')} 宫，主星 {z.get('soul') or '无主星'}；身宫：{z.get('bodyPalaceBranch')} 宫，主星 {z.get('body') or '无主星'}",
        f"- 五行局：{z.get('fiveElementsClass')}；农历：{z.get('lunarDate')}（{z.get('timeRange')} {z.get('time')}）",
        f"- 十二宫主星：",
    ]
    for h in houses:
        majors = "、".join(f"{s['name']}({s.get('brightness') or '平'}{'·' + s['mutagen'] if s.get('mutagen') else ''})" for s in h.get("major", []))
        lines.append(f"  · {h['name']}（{h['heavenlyStem']}{h['earthlyBranch']}）：{majors or '空宫'}")
    if cur_dec:
        lines.append(f"- 当前大限：{cur_dec.get('name')} {cur_dec.get('heavenlyStem')}{cur_dec.get('earthlyBranch')}，四化引动 {_fmt(cur_dec.get('mutagen'))}")
    if cur_year:
        lines.append(f"- 当前流年：{cur_year.get('heavenlyStem')}{cur_year.get('earthlyBranch')}，四化 {_fmt(cur_year.get('mutagen'))}")
    lines.append(f"- 排盘引擎：{z.get('engine')}")
    return "\n".join(lines)


def render_qimen(q: dict[str, Any]) -> str:
    ju = q.get("ju", {})
    zz = q.get("zhifu_zhishi", {})
    xun = q.get("xun", {})
    kw = q.get("kong_wang", {})
    gods = q.get("use_god", {})
    lines = [
        f"- 问事时间：{q.get('divination_time')}（{q.get('place') or '地点未提供'}），干支 {q.get('pillars')}",
        f"- 节气：{q.get('jieqi')}；{ju.get('display')}（{ju.get('yuan')}，{q.get('method')}）",
        f"- 旬首：{xun.get('xun_shou')}（遁{xun.get('xun_yi')}）；值符星 {zz.get('zhifu_star')}、值使门 {zz.get('zhishi_men')}",
        f"- 日旬空亡：{_fmt(kw.get('zhi'))}（宫 {_fmt(kw.get('palaces'))}）",
        f"- 用神定位：{_fmt(gods)}",
        f"- 宫位简表：",
    ]
    for p in q.get("palaces", []):
        lines.append(f"  · {p['palace']}：地盘{p.get('earth')}，天盘{p.get('heaven')}，人盘{p.get('human') or '—'}，神盘{p.get('spirit')}{'（旬空）' if p.get('empty') else ''}")
    lines.append(f"- 排盘引擎：{q.get('engine')}；{q.get('note')}")
    return "\n".join(lines)


def render_charts(charts: dict[str, Any]) -> str:
    parts = []
    if charts.get("bazi"):
        parts.append("【八字盘】\n" + render_bazi(charts["bazi"]))
    if charts.get("ziwei"):
        parts.append("【紫微盘】\n" + render_ziwei(charts["ziwei"]))
    if charts.get("qimen"):
        parts.append("【奇门盘】\n" + render_qimen(charts["qimen"]))
    return "\n\n".join(parts)


# ---------- 组装提示词 ----------

def build_module_user(charts_render: str, module_key: str, guide: str) -> str:
    tpl = _db_template("module_user") or MODULE_SKELETON
    return (
        tpl.replace("__CHARTS_RENDER__", charts_render)
        .replace("__MODULE_NAME__", MODULE_LABELS.get(module_key, module_key))
        .replace("__MODULE_GUIDE__", guide)
    )


def build_integration_user(charts_render: str, summaries: str) -> str:
    tpl = _db_template("integration_user") or INTEGRATION_SKELETON
    return tpl.replace("__CHARTS_RENDER__", charts_render).replace("__MODULE_SUMMARIES__", summaries)


def build_focus_user(charts_render: str, question: str) -> str:
    tpl = _db_template("focus_user") or FOCUS_SKELETON
    return tpl.replace("__CHARTS_RENDER__", charts_render).replace("__QUESTION__", question)
