"""LLM 客户端：OpenAI 兼容格式（DeepSeek/通义/豆包/Kimi/OpenAI 等）。"""
from __future__ import annotations

import json
import time

from openai import OpenAI

from ..core.config import get_settings
from ..core.db import DEFAULT_USER_ID, insert_llm_call_log


class LLMNotConfigured(RuntimeError):
    pass


def _client() -> OpenAI:
    s = get_settings()
    if not s.llm_configured:
        raise LLMNotConfigured("未配置 LLM_API_KEY，请编辑 .env")
    return OpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key, timeout=s.llm_timeout)


def chat(
    system: str,
    user: str,
    *,
    temperature: float = 0.6,
    max_tokens: int = 3000,
    scene: str = "overview",
    user_id: int = DEFAULT_USER_ID,
    report_id: int | None = None,
) -> tuple[str, dict]:
    """调用 LLM，返回 (内容, 元信息)。调用成功/失败均 best-effort 记入 llm_call_log。"""
    s = get_settings()
    client = _client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    started = time.time()
    status, error_msg = 1, None
    content, meta = "", {}
    try:
        resp = client.chat.completions.create(
            model=s.llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or ""
        meta = {
            "model": s.llm_model,
            "provider": s.llm_base_url,
            "latency_ms": int((time.time() - started) * 1000),
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", None) if resp.usage else None,
            "completion_tokens": getattr(resp.usage, "completion_tokens", None) if resp.usage else None,
        }
    except Exception as e:
        status, error_msg = 0, str(e)[:500]
        meta = {
            "model": s.llm_model,
            "provider": s.llm_base_url,
            "latency_ms": int((time.time() - started) * 1000),
            "prompt_tokens": None,
            "completion_tokens": None,
        }
        insert_llm_call_log(
            scene=scene, provider=meta["provider"], model=meta["model"],
            request_msgs=json.dumps(messages, ensure_ascii=False)[:8000],
            response_text=None, token_input=0, token_output=0,
            latency_ms=meta["latency_ms"], status=status, error_msg=error_msg,
            user_id=user_id, report_id=report_id,
        )
        raise
    insert_llm_call_log(
        scene=scene, provider=meta["provider"], model=meta["model"],
        request_msgs=json.dumps(messages, ensure_ascii=False)[:8000],
        response_text=content[:20000],
        token_input=meta["prompt_tokens"] or 0, token_output=meta["completion_tokens"] or 0,
        latency_ms=meta["latency_ms"], status=1,
        user_id=user_id, report_id=report_id,
    )
    return content, meta
