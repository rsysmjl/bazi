"""八字排盘引擎：基于 lunar-python。

引擎只输出结构化的盘面事实（四柱/十神/五行分布/大运流年），不做解读。
"""
from __future__ import annotations

from datetime import datetime

from lunar_python import Solar

# 地支藏干（本气、中气、余气）
ZHI_HIDDEN_GAN: dict[str, list[str]] = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
    "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
    "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}

GAN_WUXING: dict[str, str] = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}

PILLAR_KEYS = ["year", "month", "day", "time"]


def _eight_char(dt: datetime) -> tuple:
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)
    lunar = solar.getLunar()
    return lunar, lunar.getEightChar()


def _pillar(ec, key: str, gender: int) -> dict:
    gan = getattr(ec, f"get{key.capitalize()}Gan")()
    zhi = getattr(ec, f"get{key.capitalize()}Zhi")()
    shi_shen_gan = getattr(ec, f"get{key.capitalize()}ShiShenGan")()
    wuxing = getattr(ec, f"get{key.capitalize()}WuXing")()
    return {
        "gan": gan,
        "zhi": zhi,
        "shi_shen_gan": shi_shen_gan,
        "wuxing": wuxing,
        "hidden_gan": ZHI_HIDDEN_GAN.get(zhi, []),
    }


def _wuxing_stats(pillars: dict) -> dict[str, int]:
    counts = {k: 0 for k in ["金", "木", "水", "火", "土"]}
    for key in PILLAR_KEYS:
        p = pillars[key]
        counts[GAN_WUXING[p["gan"]]] += 1
        for hidden in p["hidden_gan"]:
            counts[GAN_WUXING[hidden]] += 1
    return counts


def build_bazi(dt: datetime, gender: str, reference: datetime | None = None) -> dict:
    """排八字。gender: male/female。reference: 用于标注"当前大运/流年"，默认取 dt。"""
    gender_code = 1 if gender == "male" else 0
    lunar, ec = _eight_char(dt)
    ref = reference or datetime.now()

    pillars = {k: _pillar(ec, k, gender_code) for k in PILLAR_KEYS}

    day_master = ec.getDayGan()
    day_master_wuxing = GAN_WUXING[day_master]

    # 用神（简化）：以月令五行 + 日主强弱做粗判，注明是简化逻辑
    month_wuxing = pillars["month"]["wuxing"]
    zhi_tally = {k: 0 for k in ["金", "木", "水", "火", "土"]}
    for key in ["year", "month", "day", "time"]:
        for hidden in pillars[key]["hidden_gan"]:
            zhi_tally[GAN_WUXING[hidden]] += 1
    month_zhi_wx = _zhi_main_wuxing(pillars["month"]["zhi"])
    strong = zhi_tally.get(day_master_wuxing, 0) >= 3 or pillars["month"]["zhi"] in _WX_ZHI_MAP[day_master_wuxing]

    # 大运
    yun = ec.getYun(gender_code, 2)  # sect=2：晚子时日柱按当天
    da_yun_rows = []
    for d in yun.getDaYun():
        if d.getIndex() == 0:
            continue  # 起运前
        da_yun_rows.append({
            "index": d.getIndex(),
            "ganzhi": d.getGanZhi(),
            "start_year": d.getStartYear(),
            "end_year": d.getEndYear(),
            "start_age": d.getStartAge(),
        })

    current_dayun = None
    for row in da_yun_rows:
        if row["start_year"] <= ref.year <= row["end_year"]:
            current_dayun = row
            break

    # 当前流年干支（以立春为界）
    ref_lunar = Solar.fromYmdHms(ref.year, ref.month, ref.day, 12, 0, 0).getLunar()
    ref_year_gz = ref_lunar.getYearInGanZhiByLiChun()
    ref_bazi = ref_lunar.getEightChar()
    ref_month_gz = ref_bazi.getMonth()
    ref_day_gz = ref_bazi.getDay()

    return {
        "solar_birth": f"{dt.year}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}",
        "gender": gender,
        "four_pillars": {
            "year": f"{pillars['year']['gan']}{pillars['year']['zhi']}",
            "month": f"{pillars['month']['gan']}{pillars['month']['zhi']}",
            "day": f"{pillars['day']['gan']}{pillars['day']['zhi']}",
            "time": f"{pillars['time']['gan']}{pillars['time']['zhi']}",
        },
        "pillars_detail": pillars,
        "day_master": day_master,
        "day_master_wuxing": day_master_wuxing,
        "wuxing_distribution": _wuxing_stats(pillars),
        "hidden_gan_tally": zhi_tally,
        "yong_shen": {
            "logic": "简化判定：月令旺衰 + 五行分布（专业排盘请用扶抑/调候/通关/病药细分）",
            "month_wuxing": month_wuxing,
            "day_master_seems": "偏强" if strong else "偏弱",
        },
        "da_yun": da_yun_rows,
        "qi_yun": {
            "start_year": yun.getStartYear(),
            "start_month": yun.getStartMonth(),
            "start_day": yun.getStartDay(),
            "forward": yun.isForward(),
        },
        "current": {
            "year": ref.year,
            "liunian": ref_year_gz,
            "liunian_month": ref_month_gz,
            "liunian_day": ref_day_gz,
            "da_yun": current_dayun,
        },
        "engine": "lunar-python",
        "note": "年柱以立春为界、月柱以节气为界；时辰已按真太阳时校正（由上层完成）。",
    }


_WX_ZHI_MAP = {
    "金": ["申", "酉"],
    "木": ["寅", "卯"],
    "水": ["亥", "子"],
    "火": ["巳", "午"],
    "土": ["辰", "戌", "丑", "未"],
}


def _zhi_main_wuxing(zhi: str) -> str:
    for wx, zhiz in _WX_ZHI_MAP.items():
        if zhi in zhiz:
            return wx
    return ""
