"""冒烟测试：排盘引擎 + API 链路（不依赖 LLM Key）。"""
from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi.testclient import TestClient

from app.core.schemas import BirthInfo, ChartRequest, DivinationInfo
from app.engines.bazi import build_bazi
from app.engines.qimen import build_qimen
from app.engines.ziwei import build_ziwei
from app.main import app


def test_bazi_engine():
    r = build_bazi(datetime(1995, 8, 18, 9, 30), "male", reference=datetime(2026, 3, 19))
    assert r["four_pillars"]["day"] == "辛巳"
    assert r["day_master"] == "辛"
    assert len(r["da_yun"]) >= 5
    assert r["current"]["liunian"]


def test_ziwei_engine():
    r = build_ziwei(datetime(1995, 8, 18, 9, 30), "male", reference=datetime(2026, 3, 19))
    assert r["soulPalaceBranch"] == "卯"
    assert len(r["houses"]) == 12
    assert r["fiveElementsClass"] == "土五局"


def test_qimen_engine():
    r = build_qimen(datetime(2026, 3, 19, 21, 30), "career", "上海")
    assert r["ju"]["display"] == "阳遁4局"
    assert r["zhifu_zhishi"]["zhifu_star"] == "天任"
    assert r["kong_wang"]["zhi"] == ["寅", "卯"]
    assert len(r["palaces"]) == 8


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_chart_endpoint():
    client = TestClient(app)
    req = ChartRequest(
        birth=BirthInfo(year=1995, month=8, day=18, hour=9, minute=30,
                        gender="male", birth_place="上海"),
        divination=DivinationInfo(year=2026, month=3, day=19, hour=21, minute=30,
                                  place="上海", question_type="career"),
    )
    resp = client.post("/api/v1/chart", json=req.model_dump())
    assert resp.status_code == 200
    body = resp.json()
    assert body["bazi"]["four_pillars"]["day"] == "辛巳"
    assert body["ziwei"]["houses"]
    assert body["qimen"]["ju"]["display"] == "阳遁4局"


def test_chart_service_async():
    """直接走异步调度。"""
    req = ChartRequest(
        birth=BirthInfo(year=1995, month=8, day=18, hour=9, minute=30,
                        gender="male", birth_place="上海"),
    )
    from app.services.chart_service import build_charts
    data = asyncio.run(build_charts(req))
    assert data["bazi"]["four_pillars"]["day"] == "辛巳"
    assert data["qimen"] is None  # 未提供问事时间，不排奇门


if __name__ == "__main__":
    import sys

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    sys.exit(0)
