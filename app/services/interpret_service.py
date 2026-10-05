"""解读服务：组装提示词 → LLM → 落库（报告 + 分模块 + 调用日志）。

解读策略：
- overview：每个选中模块先独立并行分析（短调用），再做一次整合生成综合速览，最后拼接全文。
- focus：单事项深挖，一次调用。
"""
from __future__ import annotations

import asyncio
import re
import uuid

from ..core import db
from ..core.schemas import InterpretRequest
from ..prompts import templates
from ..services import llm
from ..services.chart_service import build_charts

_HEADING_RE = re.compile(r"^#{3,4}\s+[【\[]?(.*?)[】\]]?\s*$")

# 默认展开模块（前端未勾选时）
DEFAULT_MODULES = ["career", "wealth", "love", "personality"]


def _extract_modules(content: str) -> list[tuple[str, str, str]]:
    """从 Markdown 解读正文中切出各模块小节。

    返回 [(module_key, module_name, section_md)]；无法识别的标题记为 raw。
    """
    labels = templates.MODULE_LABELS  # key -> 中文名
    by_name = {v: k for k, v in labels.items()}
    sections: list[tuple[str, str, str]] = []
    current: tuple[str, str, list[str]] | None = None

    def flush():
        nonlocal current
        if current and "".join(current[2]).strip():
            key, name, lines = current
            sections.append((key, name, "\n".join(lines).strip()))
        current = None

    for line in content.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m:
            flush()
            title = m.group(1).strip()
            key = by_name.get(title, title if title in labels else "raw")
            name = labels.get(key, title)
            current = (key, name, [])
        elif current is not None:
            current[2].append(line)
    flush()
    return sections


def _merge_meta(metas: list[dict]) -> dict:
    """合并多次 LLM 调用的元信息（token/耗时求和）。"""
    model = next((m.get("model") for m in metas if m.get("model")), None)
    provider = next((m.get("provider") for m in metas if m.get("provider")), None)
    latency = sum(m.get("latency_ms") or 0 for m in metas)
    pt = sum(m.get("prompt_tokens") or 0 for m in metas if m.get("prompt_tokens"))
    ct = sum(m.get("completion_tokens") or 0 for m in metas if m.get("completion_tokens"))
    return {
        "model": model,
        "provider": provider,
        "latency_ms": latency,
        "prompt_tokens": pt,
        "completion_tokens": ct,
    }


async def _overview(req: InterpretRequest, rendered: str) -> tuple[str, dict, list[tuple[str, str, str]]]:
    """综合解读：分模块并行独立分析 → 整合综合速览 → 拼接全文。"""
    modules = list(dict.fromkeys(req.modules or DEFAULT_MODULES))
    guides = templates.get_module_guides()
    system = templates.get_system_prompt()

    def run_module(mkey: str) -> tuple[str, dict]:
        up = templates.build_module_user(rendered, mkey, guides.get(mkey, ""))
        return llm.chat(system, up, scene=f"overview_module_{mkey}", max_tokens=1200)

    # 1) 各模块独立分析（并行短调用）
    results = await asyncio.gather(
        *(asyncio.to_thread(run_module, m) for m in modules),
        return_exceptions=True,
    )
    mod_text: dict[str, str] = {}
    mod_metas: list[dict] = []
    for m, r in zip(modules, results):
        if isinstance(r, BaseException):
            mod_text[m] = f"（{m} 模块本次分析失败：{str(r)[:100]}，可稍后重试）"
            mod_metas.append({})
        else:
            text, meta = r
            mod_text[m] = text
            mod_metas.append(meta)

    # 2) 整合综合速览
    summaries = "\n\n".join(
        f"【{templates.MODULE_LABELS.get(m, m)}】\n{mod_text[m][:600]}" for m in modules
    )
    int_user = templates.build_integration_user(rendered, summaries)
    int_text, int_meta = await asyncio.to_thread(
        llm.chat, system, int_user, scene="overview_integration", max_tokens=1500,
    )

    # 3) 拼接全文：综合速览 + 分模块详解
    parts = ["## 综合速览", int_text.strip(), "## 分模块详解"]
    for m in modules:
        parts.append(f"### 【{templates.MODULE_LABELS.get(m, m)}】")
        parts.append(mod_text[m].strip())
    content = "\n\n".join(parts)

    module_sections = [(m, templates.MODULE_LABELS.get(m, m), mod_text[m]) for m in modules]
    return content, _merge_meta(mod_metas + [int_meta]), module_sections


async def interpret(req: InterpretRequest) -> dict:
    """排盘并调用 LLM 解读。返回 {mode, question, content, charts, llm, report}。"""
    charts = await build_charts(req)

    rendered = templates.render_charts(charts)
    if req.mode == "focus":
        question = req.question or ""
        if not question.strip():
            raise ValueError("focus 模式必须提供 question")
        user_prompt = templates.build_focus_user(rendered, question)
        content, meta = await asyncio.to_thread(
            llm.chat,
            templates.get_system_prompt(), user_prompt,
            scene="focus", max_tokens=2200,
        )
        module_sections = _extract_modules(content)
    else:
        question = req.question
        content, meta, module_sections = await _overview(req, rendered)

    # ---- 落库：报告 + 分模块 ----
    report_id = None
    chart_record_id = (charts.get("meta") or {}).get("db_chart_record_id")
    if chart_record_id:
        report_id = db.insert_interpret_report(
            report_no=f"RP{uuid.uuid4().hex[:12].upper()}",
            chart_record_id=chart_record_id,
            mode=req.mode,
            question=question,
            content=content,
            llm_meta=meta,
        )
        if report_id:
            for i, (mkey, mname, section_md) in enumerate(module_sections):
                db.insert_report_module(report_id, mkey, mname, section_md, i)

    return {
        "mode": req.mode,
        "question": req.question,
        "content": content,
        "charts": charts,
        "llm": meta,
        "report": {"id": report_id, "chart_record_id": chart_record_id},
    }
