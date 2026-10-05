"""API 路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.config import get_settings
from ..core.schemas import ChartRequest, ChartResponse, InterpretRequest, InterpretResponse
from ..prompts.templates import MODULE_LABELS
from ..services import llm
from ..services.chart_service import build_charts
from ..services.interpret_service import interpret

router = APIRouter(prefix="/api/v1")


async def require_auth(request: Request) -> None:
    s = get_settings()
    if not s.api_key_list:
        return
    key = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if key not in s.api_key_list:
        raise HTTPException(status_code=401, detail="未授权：请在请求头携带有效 API Key")


@router.get("/health")
async def health():
    s = get_settings()
    return {
        "status": "ok",
        "llm_configured": s.llm_configured,
        "providers": {
            "bazi": s.provider_bazi,
            "ziwei": s.provider_ziwei,
            "qimen": s.provider_qimen,
        },
    }


@router.post("/chart", response_model=ChartResponse, dependencies=[Depends(require_auth)])
async def chart(req: ChartRequest):
    """只排盘，返回结构化三盘数据。"""
    data = await build_charts(req)
    return ChartResponse(
        meta=data["meta"],
        bazi=data.get("bazi") or {},
        ziwei=data.get("ziwei"),
        qimen=data.get("qimen"),
    )


@router.post("/interpret", response_model=InterpretResponse, dependencies=[Depends(require_auth)])
async def interpret_endpoint(req: InterpretRequest):
    """排盘 + LLM 解读。"""
    try:
        result = await interpret(req)
    except llm.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return InterpretResponse(**result)


@router.get("/modules", dependencies=[Depends(require_auth)])
async def modules():
    return {"modules": [{"key": k, "label": v} for k, v in MODULE_LABELS.items()]}
