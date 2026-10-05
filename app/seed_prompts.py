"""提示词外置 seed：把内置提示词/模块引导灌入数据库。

用法：python -m app.seed_prompts
幂等：重复执行会更新内容并置为新生效版本，不会产生重复 key+version。
"""
from __future__ import annotations

import sys

from .core import db
from .prompts import templates

# (tpl_key, tpl_name, content, remark)
PROMPTS = [
    ("system", "主系统提示词（角色/原则/红线）", templates.SYSTEM_PROMPT, "内置速用版主系统提示词"),
    ("module_user", "单模块独立分析用户提示词", templates.MODULE_SKELETON, "分模块并行独立分析骨架"),
    ("integration_user", "整合综合速览用户提示词", templates.INTEGRATION_SKELETON, "多模块分析后整合骨架"),
    ("focus_user", "聚焦追问用户提示词", templates.FOCUS_SKELETON, "内置速用版聚焦追问骨架"),
]

# (module_key, module_name, focus_desc, sort_order)
MODULES = [
    (key, templates.MODULE_LABELS[key], templates.MODULES[key], i)
    for i, key in enumerate(
        ["career", "wealth", "love", "health", "study", "family", "luck", "personality"]
    )
]

VERSION = "v1.0.0"


def ensure_default_user() -> int:
    """保证匿名用户 id=1 存在（业务落库统一挂到该用户）。"""
    conn = db._conn()
    if conn is None:
        raise RuntimeError("数据库不可用，请检查 DB_* 配置")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM `user` WHERE id=%s", (db.DEFAULT_USER_ID,))
            if cur.fetchone():
                return db.DEFAULT_USER_ID
            cur.execute(
                "INSERT INTO `user` (id, nickname, status) VALUES (%s, '匿名用户', 1)",
                (db.DEFAULT_USER_ID,),
            )
            conn.commit()
            return db.DEFAULT_USER_ID
    finally:
        conn.close()


def seed_prompts() -> int:
    for tpl_key, name, content, remark in PROMPTS:
        db._run("UPDATE prompt_template SET is_active=0 WHERE tpl_key=%s", (tpl_key,))
        n = db._run(
            """INSERT INTO prompt_template (tpl_key, tpl_name, version, content, is_active, remark)
               VALUES (%s,%s,%s,%s,1,%s)
               ON DUPLICATE KEY UPDATE content=VALUES(content), is_active=1, remark=VALUES(remark)""",
            (tpl_key, name, VERSION, content, remark),
        )
        if n is None:
            print(f"[!] 写入提示词失败: {tpl_key}")
    return len(PROMPTS)


def seed_modules() -> int:
    for mkey, mname, focus, sort_order in MODULES:
        n = db._run(
            """INSERT INTO module_config
                   (module_key, module_name, focus_desc, is_enabled, is_free, sort_order)
               VALUES (%s,%s,%s,1,1,%s)
               ON DUPLICATE KEY UPDATE
                   module_name=VALUES(module_name), focus_desc=VALUES(focus_desc), is_enabled=1""",
            (mkey, mname, focus, sort_order),
        )
        if n is None:
            print(f"[!] 写入模块配置失败: {mkey}")
    return len(MODULES)


def main() -> None:
    uid = ensure_default_user()
    print(f"[ok] 匿名用户 id={uid}")
    p = seed_prompts()
    print(f"[ok] 提示词模板 {p} 条")
    m = seed_modules()
    print(f"[ok] 模块配置 {m} 条")


if __name__ == "__main__":
    sys.exit(main())
