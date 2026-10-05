"""紫微斗数排盘引擎：通过 Node 桥接调用 iztro。

不支持 Node 或 iztro 缺失时抛出 ZiweiUnavailable，由上层降级处理。
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from ..core.config import get_settings


class ZiweiUnavailable(RuntimeError):
    """紫微排盘不可用（缺 Node / iztro / 桥接脚本）。"""


def _node_bin() -> str:
    s = get_settings()
    return s.ziwei_node_bin or os.environ.get("ZIWEI_NODE_BIN", "node")


def _script_path() -> Path:
    s = get_settings()
    # 相对路径按项目根（mingpan-api/）解析
    base = Path.cwd()
    return (base / s.ziwei_script_path) if not Path(s.ziwei_script_path).is_absolute() else Path(s.ziwei_script_path)


def build_ziwei(dt: datetime, gender: str, reference: datetime | None = None) -> dict:
    """排紫微。gender: male/female。reference 用于标注当前大限/流年。"""
    s = get_settings()
    script = _script_path()
    if not script.exists():
        raise ZiweiUnavailable(f"紫微桥接脚本不存在: {script}（请先在 node_ziwei/ 执行 npm install）")

    payload = {
        "solarDate": f"{dt.year}-{dt.month}-{dt.day}",
        "hour": dt.hour,
        "minute": dt.minute,
        "gender": "男" if gender == "male" else "女",
        "reference": f"{reference.year}-{reference.month}-{reference.day}" if reference else None,
    }

    try:
        proc = subprocess.run(
            [_node_bin(), str(script)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as e:
        raise ZiweiUnavailable(f"找不到 Node 可执行文件（{_node_bin()}），请检查 ZIWEI_NODE_BIN 配置") from e
    except subprocess.TimeoutExpired as e:
        raise ZiweiUnavailable("紫微排盘超时（Node 桥接）") from e

    if proc.returncode != 0:
        raise ZiweiUnavailable(f"Node 桥接失败: {proc.stderr[:500]}")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ZiweiUnavailable(f"Node 桥接输出非 JSON: {proc.stdout[:300]}") from e

    if isinstance(data, dict) and data.get("error"):
        raise ZiweiUnavailable(f"iztro 排盘错误: {data['error']}")

    data["engine"] = "iztro (node bridge)"
    data["note"] = "紫微对出生时辰高度敏感；未提供准确时辰时本盘不可靠。"
    return data
