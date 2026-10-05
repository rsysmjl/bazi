"""第三方排盘 API 适配层：provider=thirdparty 时使用。

本地引擎失败自动降级时也走这里。按实际第三方接口调整字段映射。
"""
from __future__ import annotations

import httpx

from ..core.config import get_settings


async def fetch_thirdparty_chart(kind: str, payload: dict) -> dict:
    """调用第三方排盘接口。kind: bazi/ziwei/qimen。"""
    s = get_settings()
    if not s.thirdparty_base_url:
        raise RuntimeError("未配置 THIRDPARTY_BASE_URL")
    headers = {"Content-Type": "application/json"}
    if s.thirdparty_api_key:
        headers["Authorization"] = f"Bearer {s.thirdparty_api_key}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{s.thirdparty_base_url.rstrip('/')}/{kind}",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        # 按你实际接口映射到标准结构，此处给出通用兜底
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        data["engine"] = "thirdparty"
        return data
