"""三盘调度：provider 路由 + 真太阳时校正 + 降级 + 落库。"""
from __future__ import annotations

import uuid
from datetime import datetime

from ..adapters.thirdparty import fetch_thirdparty_chart
from ..core import db
from ..core.config import get_settings
from ..core.schemas import BirthInfo, ChartRequest
from ..core.solar_time import corrected_birth, get_longitude
from ..engines import bazi as bazi_engine
from ..engines import qimen as qimen_engine
from ..engines.ziwei import ZiweiUnavailable, build_ziwei


def _provider(name: str) -> str:
    s = get_settings()
    return getattr(s, f"provider_{name}", "local") or "local"


def _fallback_allowed() -> bool:
    return get_settings().allow_fallback


async def _run(kind: str, local_fn, payload: dict) -> tuple[dict, str, str | None]:
    """local 优先；失败且允许降级时走第三方。返回 (data, provider, warning)。"""
    if _provider(kind) == "local":
        try:
            return local_fn(), "local", None
        except Exception as e:
            warning = f"{kind} 本地引擎失败: {e}"
            if not _fallback_allowed():
                raise
    else:
        warning = f"{kind} 按配置直接走第三方。"
    try:
        data = await fetch_thirdparty_chart(kind, payload)
        return data, "thirdparty", warning
    except Exception as e:
        raise RuntimeError(f"{kind} 排盘失败（本地+第三方）: {e}") from e


def _persist(req: ChartRequest, data: dict) -> None:
    """best-effort 落库：出生信息 + 排盘记录 + 问事。失败只记 warning，不阻塞。"""
    if not get_settings().db_enabled:
        return
    try:
        birth_info_id = db.insert_birth_info(req.birth)
        if not birth_info_id:
            return
        providers = (data.get("meta") or {}).get("providers") or {}
        record_id = db.insert_chart_record(
            user_id=db.DEFAULT_USER_ID,
            birth_info_id=birth_info_id,
            chart_no=f"CH{uuid.uuid4().hex[:12].upper()}",
            providers=providers,
            bazi=data.get("bazi"),
            ziwei=data.get("ziwei"),
            qimen=data.get("qimen"),
            warnings=(data.get("meta") or {}).get("warnings") or [],
        )
        if req.divination:
            db.insert_divination_query(req.divination, db.DEFAULT_USER_ID, record_id)
        if record_id:
            data.setdefault("meta", {})["db_chart_record_id"] = record_id
    except Exception as e:  # 落库失败不影响排盘主流程
        (data.setdefault("meta", {}).setdefault("warnings", [])).append(f"落库失败: {e}")


async def build_charts(req: ChartRequest, reference: datetime | None = None) -> dict:
    """排三盘。返回 {meta, bazi, ziwei, qimen}。"""
    s = get_settings()
    birth: BirthInfo = req.birth

    # 真太阳时校正
    longitude = birth.longitude or get_longitude(birth.birth_place)
    raw_dt = datetime(birth.year, birth.month, birth.day, birth.hour, birth.minute)
    solar_dt = corrected_birth(raw_dt, longitude) if s.true_solar_time else raw_dt

    ref = reference or datetime.now()
    warnings: list[str] = []
    providers: dict[str, str] = {}

    bazi_data = None
    ziwei_data = None
    qimen_data = None

    # ---- 八字 ----
    try:
        bazi_data, providers["bazi"], w = await _run(
            "bazi", lambda: bazi_engine.build_bazi(solar_dt, birth.gender, reference=ref), {})
        if w:
            warnings.append(w)
    except Exception as e:
        warnings.append(str(e))

    # ---- 紫微 ----
    try:
        ziwei_data, providers["ziwei"], w = await _run(
            "ziwei", lambda: build_ziwei(solar_dt, birth.gender, reference=ref), {})
        if w:
            warnings.append(w)
    except ZiweiUnavailable as e:
        warnings.append(f"紫微不可用: {e}（请确认 Node 环境与 node_ziwei 依赖已安装）")
    except Exception as e:
        warnings.append(f"紫微排盘失败: {e}")

    # ---- 奇门（可选）----
    if req.divination:
        div = req.divination
        div_dt = datetime(div.year, div.month, div.day, div.hour, div.minute)
        try:
            qimen_data, providers["qimen"], w = await _run(
                "qimen",
                lambda: qimen_engine.build_qimen(div_dt, div.question_type, div.place),
                {},
            )
            if w:
                warnings.append(w)
        except Exception as e:
            warnings.append(f"奇门排盘失败: {e}")
    else:
        warnings.append("未提供奇门问事时间，奇门盘未起局。")

    if not bazi_data and not ziwei_data and not qimen_data:
        raise RuntimeError("三盘均排盘失败，请检查环境配置。警告：" + "; ".join(warnings))

    data = {
        "meta": {
            "providers": providers,
            "solar_time": {
                "enabled": s.true_solar_time,
                "longitude": longitude,
                "birth_place": birth.birth_place,
                "corrected_time": solar_dt.strftime("%Y-%m-%d %H:%M"),
            },
            "warnings": warnings,
        },
        "bazi": bazi_data,
        "ziwei": ziwei_data,
        "qimen": qimen_data,
    }
    _persist(req, data)
    return data
