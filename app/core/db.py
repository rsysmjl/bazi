"""数据库访问层：业务落库 + 提示词外置查询。

设计原则：所有写操作均为 best-effort —— 连接失败 / SQL 错误只记 warning，
绝不阻塞排盘 / 解读主流程（MVP 容错；生产可改为显式失败）。
"""
from __future__ import annotations

import json
import logging
from typing import Any

import pymysql

from .config import get_settings

logger = logging.getLogger("mingpan.db")

# 匿名用户：未接入登录体系前，业务数据统一挂到该用户（seed 脚本保证存在）
DEFAULT_USER_ID = 1


def _conn() -> "pymysql.connections.Connection | None":
    s = get_settings()
    if not s.db_enabled:
        return None
    try:
        return pymysql.connect(
            host=s.db_host,
            port=s.db_port,
            user=s.db_user,
            password=s.db_password,
            database=s.db_name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=3,
            read_timeout=5,
            write_timeout=5,
        )
    except Exception as e:
        logger.warning("数据库连接失败(%s:%s/%s): %s", s.db_host, s.db_port, s.db_name, e)
        return None


def _run(sql: str, params: tuple | None = None, *, need_id: bool = False) -> int | None:
    """执行一条 SQL。need_id=True 返回自增主键，否则返回影响行数；失败返回 None。"""
    conn = _conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            rid = cur.lastrowid if need_id else None
            conn.commit()
            return rid if need_id else cur.rowcount
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.warning("SQL 执行失败: %s", e)
        return None
    finally:
        conn.close()


def _j(v: Any) -> str | None:
    """dict/list → JSON 字符串（None 透传）。"""
    return json.dumps(v, ensure_ascii=False) if v is not None else None


# ---------- 写入：出生信息 / 问事 / 排盘 ----------

def insert_birth_info(birth: Any, user_id: int = DEFAULT_USER_ID) -> int | None:
    sql = """INSERT INTO birth_info
        (user_id, subject_name, birth_year, birth_month, birth_day, birth_hour, birth_minute,
         gender, birth_place, longitude, timezone, hour_known, solar_time_note, is_default)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)"""
    return _run(
        sql,
        (
            user_id, "本人", birth.year, birth.month, birth.day, birth.hour, birth.minute,
            birth.gender, birth.birth_place, birth.longitude, "Asia/Shanghai",
            1, "由排盘接口自动记录",
        ),
        need_id=True,
    )


def insert_divination_query(div: Any, user_id: int, chart_record_id: int | None) -> int | None:
    sql = """INSERT INTO divination_query
        (user_id, chart_record_id, question_type, ask_year, ask_month, ask_day,
         ask_hour, ask_minute, ask_place, longitude)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    return _run(
        sql,
        (
            user_id, chart_record_id, div.question_type, div.year, div.month, div.day,
            div.hour, div.minute, div.place, None,
        ),
        need_id=True,
    )


def insert_chart_record(
    *,
    user_id: int,
    birth_info_id: int,
    chart_no: str,
    providers: dict[str, str],
    bazi: dict | None,
    ziwei: dict | None,
    qimen: dict | None,
    warnings: list[str],
) -> int | None:
    bazi = bazi or {}
    ziwei = ziwei or {}
    qimen = qimen or {}

    ju = qimen.get("ju") or {}
    zz = qimen.get("zhifu_zhishi") or {}
    cur = bazi.get("current") or {}

    sql = """INSERT INTO chart_record
        (user_id, birth_info_id, chart_no, provider_bazi, provider_ziwei, provider_qimen,
         bazi_pillars, bazi_day_master, bazi_five_elems, bazi_ten_gods, bazi_dayun, bazi_liunian,
         ziwei_palaces, ziwei_soul, ziwei_body, ziwei_five_class,
         qimen_dun, qimen_ju, qimen_zhi_fu, qimen_zhi_shi, qimen_palaces,
         warnings, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)"""
    return _run(
        sql,
        (
            user_id, birth_info_id, chart_no,
            providers.get("bazi", "local"), providers.get("ziwei", "local"), providers.get("qimen", "local"),
            _j(bazi.get("four_pillars")), bazi.get("day_master"), _j(bazi.get("wuxing_distribution")),
            _j(bazi.get("pillars_detail")), _j(bazi.get("da_yun")), _j(cur),
            _j(ziwei.get("houses")), ziwei.get("soulPalaceBranch"), ziwei.get("bodyPalaceBranch"),
            ziwei.get("fiveElementsClass"),
            "阳遁" if ju.get("yang") else ("阴遁" if "yang" in ju else None),
            ju.get("ju_number"), zz.get("zhifu_star"), zz.get("zhishi_men"), _j(qimen.get("palaces")),
            _j(warnings),
        ),
        need_id=True,
    )


# ---------- 写入：解读报告 ----------

def insert_interpret_report(
    *,
    report_no: str,
    chart_record_id: int,
    mode: str,
    question: str | None,
    content: str,
    llm_meta: dict,
    user_id: int = DEFAULT_USER_ID,
) -> int | None:
    overview = content if mode == "overview" else None
    focus_content = content if mode == "focus" else None
    sql = """INSERT INTO interpret_report
        (report_no, user_id, chart_record_id, mode, question, overview, focus_content,
         confidence_note, disclaimer, llm_model, token_input, token_output, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)"""
    return _run(
        sql,
        (
            report_no, user_id, chart_record_id, mode, question, overview, focus_content,
            "本解读基于三盘推演，低置信度结论请谨慎参考。",
            "健康、重大财务、法律事项以现实专业意见为准；本解读作为自我认知参考，不构成决策依据。",
            llm_meta.get("model"),
            llm_meta.get("prompt_tokens") or 0,
            llm_meta.get("completion_tokens") or 0,
        ),
        need_id=True,
    )


def insert_report_module(report_id: int, module_key: str, module_name: str, content_md: str, sort_order: int) -> None:
    sql = """INSERT INTO report_module
        (report_id, module_key, module_name, content_md, sort_order)
        VALUES (%s,%s,%s,%s,%s)"""
    _run(sql, (report_id, module_key, module_name, content_md, sort_order))


# ---------- 写入：LLM 调用日志 ----------

def insert_llm_call_log(
    *,
    scene: str,
    provider: str | None,
    model: str | None,
    request_msgs: str | None,
    response_text: str | None,
    token_input: int,
    token_output: int,
    latency_ms: int,
    status: int = 1,
    error_msg: str | None = None,
    user_id: int = DEFAULT_USER_ID,
    report_id: int | None = None,
) -> None:
    sql = """INSERT INTO llm_call_log
        (user_id, report_id, scene, provider, model, request_msgs, response_text,
         token_input, token_output, latency_ms, status, error_msg)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    _run(
        sql,
        (
            user_id, report_id, scene, provider, model, request_msgs, response_text,
            token_input, token_output, latency_ms, status, error_msg,
        ),
    )


# ---------- 提示词外置 ----------

def get_prompt_template(tpl_key: str) -> dict | None:
    """取当前生效版本的模板。返回 {tpl_key, tpl_name, version, content}。"""
    sql = """SELECT tpl_key, tpl_name, version, content FROM prompt_template
             WHERE tpl_key=%s AND is_active=1 ORDER BY id DESC LIMIT 1"""
    conn = _conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (tpl_key,))
            row = cur.fetchone()
            return row if row else None
    except Exception as e:
        logger.warning("查询提示词模板失败: %s", e)
        return None
    finally:
        conn.close()


def list_module_configs() -> list[dict]:
    """取启用的解读模块配置 [{module_key, module_name, focus_desc, sort_order}]。"""
    sql = """SELECT module_key, module_name, focus_desc, sort_order FROM module_config
             WHERE is_enabled=1 ORDER BY sort_order, id"""
    conn = _conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall()) or []
    except Exception as e:
        logger.warning("查询模块配置失败: %s", e)
        return []
    finally:
        conn.close()
