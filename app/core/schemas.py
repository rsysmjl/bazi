"""统一数据模型：与提示词工程包的 JSON 规范对齐。

- 输入：出生信息、奇门问事信息（可选）
- 输出：三盘结构化数据 + 解读结果
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------- 输入模型 ----------

class BirthInfo(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    gender: Literal["male", "female"]
    birth_place: str = Field(..., description="出生地，用于真太阳时校正")
    longitude: Optional[float] = Field(None, description="出生地经度（东经），优先于地名查询")


class DivinationInfo(BaseModel):
    """奇门问事信息。缺省则不排奇门。"""
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    place: str = Field(..., description="问事地点")
    question_type: str = Field("general", description="问事类别：career/wealth/love/health/study/other/general")


class ChartRequest(BaseModel):
    birth: BirthInfo
    divination: Optional[DivinationInfo] = None


class InterpretRequest(BaseModel):
    birth: BirthInfo
    divination: Optional[DivinationInfo] = None
    mode: Literal["overview", "focus"] = "overview"
    modules: list[str] = Field(default_factory=list, description="模块列表，overview 模式可用")
    question: Optional[str] = Field(None, description="focus 模式必填：用户具体问题")


# ---------- 输出模型 ----------

class ChartMeta(BaseModel):
    provider: str = "local"
    engine: str = ""
    warnings: list[str] = Field(default_factory=list)
    source: str = ""


class ChartResponse(BaseModel):
    meta: dict[str, Any]
    bazi: dict[str, Any]
    ziwei: Optional[dict[str, Any]] = None
    qimen: Optional[dict[str, Any]] = None


class InterpretResponse(BaseModel):
    mode: str
    question: Optional[str] = None
    content: str = Field(description="Markdown 解读正文")
    charts: dict[str, Any] = Field(description="本次解读所用的盘面快照")
    llm: dict[str, Any] = Field(default_factory=dict, description="模型/耗时等元信息")
    report: dict[str, Any] = Field(default_factory=dict, description="落库信息（报告ID/排盘记录ID，可空）")
