"""解读服务降级路径测试：不依赖真实 LLM / DB（llm.chat 打桩）。"""
from __future__ import annotations

import asyncio

from app.core.schemas import BirthInfo, InterpretRequest
from app.services import interpret_service as svc

_META = {"model": "qwen-plus", "provider": "dashscope",
         "latency_ms": 100, "prompt_tokens": 10, "completion_tokens": 5}


def _req(modules: list[str]) -> InterpretRequest:
    return InterpretRequest(
        birth=BirthInfo(year=1995, month=8, day=18, hour=9, minute=30,
                        gender="male", birth_place="上海"),
        mode="overview",
        modules=modules,
    )


def _make_fake(*, fail_scenes: set[str], calls: dict):
    """构造替身：指定 scene 抛 RuntimeError，其余成功。捕获每次 user 提示词到 calls。"""
    def fake(system, user, *, scene="overview", **kw):
        calls[scene] = user
        if scene in fail_scenes:
            raise RuntimeError(f"boom:{scene}")
        return ("模块分析ok", dict(_META))
    return fake


def test_overview_single_module_failure(monkeypatch):
    """单模块失败：占位中文、不暴露异常原文、其余模块照常。"""
    calls: dict = {}
    monkeypatch.setattr(svc.llm, "chat", _make_fake(fail_scenes={"overview_module_career"}, calls=calls))
    content, meta, sections = asyncio.run(svc._overview(_req(["career", "wealth"]), "盘面渲染"))
    assert "事业模块本次分析未完成" in content
    assert "模块分析ok" in content
    assert "boom" not in content and "RuntimeError" not in content
    assert meta["model"] == "qwen-plus"
    # 整合提示词不包含失败模块
    assert "【事业】" not in calls["overview_integration"]
    assert "【财运】" in calls["overview_integration"]
    keys = [k for k, _, _ in sections]
    assert keys == ["career", "wealth"]


def test_overview_all_modules_fail(monkeypatch):
    """全部模块失败：整合走兜底句，不抛 500。"""
    calls: dict = {}
    monkeypatch.setattr(svc.llm, "chat", _make_fake(
        fail_scenes={"overview_module_career", "overview_module_wealth", "overview_integration"}, calls=calls))
    content, _, sections = asyncio.run(svc._overview(_req(["career", "wealth"]), "盘面"))
    assert "均未取得有效分析结果" in calls["overview_integration"]  # 兜底句进入整合提示词
    assert "综合速览本次生成失败" in content                      # 整合也失败 → 降级提示
    assert "事业模块本次分析未完成" in content
    assert "财运模块本次分析未完成" in content


def test_overview_integration_failure(monkeypatch):
    """整合调用失败：降级为分模块结果，保留成功模块内容。"""
    calls: dict = {}
    monkeypatch.setattr(svc.llm, "chat", _make_fake(fail_scenes={"overview_integration"}, calls=calls))
    content, meta, _ = asyncio.run(svc._overview(_req(["career"]), "盘面"))
    assert "综合速览本次生成失败" in content
    assert "模块分析ok" in content
    assert meta["model"] == "qwen-plus"


def test_overview_cancelled_error_module_treated_as_failed(monkeypatch):
    """模块返回 CancelledError（BaseException 系）：按失败处理，不崩、不向整合传播。"""

    def cancel(system, user, *, scene="overview", **kw):
        if scene.startswith("overview_module_"):
            raise asyncio.CancelledError()
        return ("整合速览ok", dict(_META))

    monkeypatch.setattr(svc.llm, "chat", cancel)
    content, _, _ = asyncio.run(svc._overview(_req(["career"]), "盘面"))
    assert "事业模块本次分析未完成" in content
    assert "整合速览ok" in content


def test_overview_empty_module_text_filtered(monkeypatch):
    """模块返回空串：不进整合 summaries，整合提示词走兜底句。"""
    calls: dict = {}

    def empty(system, user, *, scene="overview", **kw):
        calls[scene] = user
        if scene == "overview_integration":
            return ("整合速览ok", dict(_META))
        return ("", dict(_META))

    monkeypatch.setattr(svc.llm, "chat", empty)
    content, _, _ = asyncio.run(svc._overview(_req(["career", "wealth"]), "盘面"))
    assert "整合速览ok" in content
    assert "各模块均未取得有效分析结果" in calls["overview_integration"]


if __name__ == "__main__":
    import sys

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"SKIP  {t.__name__}（请用 pytest 运行）")
    sys.exit(0)
