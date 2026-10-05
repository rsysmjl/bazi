"""奇门遁甲排盘引擎：自研时家转盘基础实现。

- 定局：拆补法（节气 + 符头定上中下元）
- 布地盘：三奇六仪 阳顺阴逆
- 值符值使：旬首定星定门
- 天盘：值符随时干转（转盘）
- 人盘：值使随时辰飞宫
- 神盘：八神阳顺阴逆

注意：这是"基础骨架"，局数/飞布请按所用流派校准（README 生产建议第 1 条）。
"""
from __future__ import annotations

from datetime import datetime

from lunar_python import Solar

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = "戊己庚辛壬癸丁丙乙"  # 三奇六仪
YIQI = "乙丙丁"  # 三奇

# 九宫（洛书）
PALACE_NAMES = {1: "坎一", 2: "坤二", 3: "震三", 4: "巽四", 5: "中五", 6: "乾六", 7: "兑七", 8: "艮八", 9: "离九"}
FLY_SEQ = [1, 2, 3, 4, 5, 6, 7, 8, 9]           # 顺飞
RING = [1, 8, 3, 4, 9, 2, 7, 6]                   # 后天八卦环（坎艮震巽离坤兑乾），转盘用

STAR_BY_PALACE = {1: "天蓬", 2: "天芮", 3: "天冲", 4: "天辅", 5: "天禽", 6: "天心", 7: "天柱", 8: "天任", 9: "天英"}
MEN_BY_PALACE = {1: "休门", 2: "死门", 3: "伤门", 4: "杜门", 6: "开门", 7: "惊门", 8: "生门", 9: "景门"}
SHEN_ORDER = ["值符", "腾蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天"]

# 节气象数表（上中下元）：阳遁
YANG_JU = {
    "冬至": (1, 7, 4), "小寒": (2, 8, 5), "大寒": (3, 9, 6),
    "立春": (8, 5, 2), "雨水": (9, 6, 3), "惊蛰": (1, 7, 4),
    "春分": (3, 9, 6), "清明": (4, 1, 7), "谷雨": (5, 2, 8),
    "立夏": (4, 1, 7), "小满": (5, 2, 8), "芒种": (6, 3, 9),
}
# 阴遁
YIN_JU = {
    "夏至": (9, 3, 6), "小暑": (8, 2, 5), "大暑": (7, 1, 4),
    "立秋": (2, 5, 8), "处暑": (1, 4, 7), "白露": (9, 3, 6),
    "秋分": (7, 1, 4), "寒露": (6, 9, 3), "霜降": (5, 8, 2),
    "立冬": (6, 9, 3), "小雪": (5, 8, 2), "大雪": (4, 7, 1),
}

# 地支 → 九宫
ZHI_PALACE = {"子": 1, "丑": 8, "寅": 8, "卯": 3, "辰": 4, "巳": 4,
              "午": 9, "未": 2, "申": 2, "酉": 7, "戌": 6, "亥": 6}

# 用神（议题 → 用神元素/门/星）
USE_GOD = {
    "career": ["开门", "值符"],
    "wealth": ["生门", "戊"],
    "love": ["六合", "乙", "庚"],
    "health": ["天芮", "伤门"],
    "study": ["天辅", "景门"],
    "general": ["值符", "值使"],
    "other": ["值符"],
}


def gz_index(gan: str, zhi: str) -> int:
    gi, zi = GAN.index(gan), ZHI.index(zhi)
    for k in range(5):
        n = zi + 12 * k
        if n % 10 == gi:
            return n
    raise ValueError(f"非法干支: {gan}{zhi}")


def _jieqi_at(dt: datetime) -> tuple[str, bool]:
    """返回 dt 所在节气名，以及是否阳遁（冬至~夏至）。"""
    lunar = Solar.fromYmdHms(dt.year, dt.month, dt.day, 12, 0, 0).getLunar()
    table = lunar.getJieQiTable()
    entries = []
    for name, sol in table.items():
        if sol.getYear() == dt.year:
            entries.append((name, datetime(sol.getYear(), sol.getMonth(), sol.getDay())))
    entries.sort(key=lambda x: x[1])
    prev = entries[-1][0]  # 兜底（若 dt 早于当年首个节气）
    for name, d in entries:
        if d <= dt:
            prev = name
        else:
            break
    # 阳遁：冬至 ≤ 时刻 < 夏至
    yang = True
    dzt = None
    xzt = None
    for name, d in entries:
        if name == "冬至":
            dzt = d
        elif name == "夏至":
            xzt = d
    if dzt and xzt:
        yang = dzt <= dt < xzt
    return prev, yang


def _yuan(day_gz: str) -> str:
    """符头定元。"""
    gan, zhi = day_gz[0], day_gz[1]
    n = gz_index(gan, zhi)
    xu = n - n % 10               # 旬首（甲X）
    if n % 10 < 5:                # 甲乙丙丁戊 → 符头甲X
        fu_tou = xu
    else:                          # 己庚辛壬癸 → 符头己X
        fu_tou = xu + 5
    fu_zhi = ZHI[fu_tou % 12]
    if fu_zhi in "子午卯酉":
        return "上元"
    if fu_zhi in "寅申巳亥":
        return "中元"
    return "下元"


def _place_dipan(ju: int, yang: bool) -> dict[str, int]:
    seq = FLY_SEQ if yang else FLY_SEQ[::-1]
    idx = seq.index(ju)
    seq = seq[idx:] + seq[:idx]
    return {el: seq[i] for i, el in enumerate(ELEMENTS)}


def build_qimen(dt: datetime, question_type: str = "general", place: str = "") -> dict:
    lunar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0).getLunar()
    ec = lunar.getEightChar()
    year_gz, month_gz, day_gz, time_gz = ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()
    day_gan, day_zhi = day_gz[0], day_gz[1]
    time_gan, time_zhi = time_gz[0], time_gz[1]

    jieqi, yang = _jieqi_at(dt)
    yuan = _yuan(day_gz)
    table = YANG_JU if yang else YIN_JU
    ju = table.get(jieqi, (1, 7, 4))[{"上元": 0, "中元": 1, "下元": 2}[yuan]]

    dipan = _place_dipan(ju, yang)
    dipan_rev = {v: k for k, v in dipan.items()}

    # 时辰旬首 → 六仪 → 值符星 / 值使门
    t_n = gz_index(time_gan, time_zhi)
    xu_n = t_n - t_n % 10
    t = t_n % 10
    xun_shou = GAN[xu_n % 10] + ZHI[xu_n % 12]
    xun_yi = {0: "戊", 10: "己", 20: "庚", 30: "辛", 40: "壬", 50: "癸"}[xu_n]
    xun_palace = dipan[xun_yi]
    xun_palace_eff = 2 if xun_palace == 5 else xun_palace
    zhifu_star = STAR_BY_PALACE[xun_palace_eff]
    zhishi_men = MEN_BY_PALACE.get(xun_palace_eff, "死门")

    # 天盘：值符随时干转（转盘）
    shi_gan_palace = dipan[time_gan]
    shi_gan_palace_eff = 2 if shi_gan_palace == 5 else shi_gan_palace
    i0 = RING.index(xun_palace_eff)
    i1 = RING.index(shi_gan_palace_eff)
    shift = (i1 - i0) % 8 if yang else (i0 - i1) % 8
    tianpan: dict[int, str] = {}
    for ip, palace in enumerate(RING):
        src = RING[(ip - shift) % 8] if yang else RING[(ip + shift) % 8]
        tianpan[palace] = STAR_BY_PALACE[src]

    # 人盘：值使随时辰飞宫
    fly = FLY_SEQ if yang else FLY_SEQ[::-1]
    p0 = fly.index(xun_palace if xun_palace != 5 else 2)
    zhishi_palace = fly[(p0 + t) % 9]
    if zhishi_palace == 5:
        zhishi_palace = 2
    renpan: dict[int, str] = {}
    for palace in RING:
        renpan[palace] = None
    renpan[zhishi_palace] = zhishi_men

    # 神盘：八神阳顺阴逆布于后天八卦环，值符起于时干宫
    shen_seq = RING if yang else RING[::-1]
    i2 = shen_seq.index(shi_gan_palace_eff)
    shen_seq = shen_seq[i2:] + shen_seq[:i2]
    shenpan: dict[int, str] = {palace: SHEN_ORDER[ip] for ip, palace in enumerate(shen_seq)}

    # 空亡（日旬）
    d_n = gz_index(day_gan, day_zhi)
    d_xu = d_n - d_n % 10
    kong_zhi = [ZHI[(d_xu + 6) % 12], ZHI[(d_xu + 7) % 12]]
    kong_palaces = sorted({ZHI_PALACE[z] for z in kong_zhi})

    # 宫位汇总（九宫）
    palaces = []
    for p in range(1, 10):
        if p == 5:
            continue
        dipan_el = dipan_rev.get(p)
        palaces.append({
            "palace": PALACE_NAMES[p],
            "num": p,
            "earth": dipan_el,              # 地盘（三奇六仪）
            "heaven": tianpan.get(p),       # 天盘九星
            "human": renpan.get(p),         # 人盘八门（仅值使所在宫非空）
            "spirit": shenpan.get(p),       # 神盘八神
            "empty": p in kong_palaces,     # 是否日旬空亡之宫
        })

    # 用神定位
    gods = {}
    for god in USE_GOD.get(question_type, USE_GOD["general"]):
        if god in ELEMENTS:
            gods[god] = {"type": "element", "palace": dipan[god], "palace_name": PALACE_NAMES[dipan[god]]}
        elif god in ("开门", "生门", "景门", "伤门", "杜门", "死门", "惊门", "休门"):
            src = {v: k for k, v in MEN_BY_PALACE.items()}.get(god)
            gods[god] = {"type": "door", "palace": zhishi_palace if god == zhishi_men else src,
                         "palace_name": PALACE_NAMES[zhishi_palace if god == zhishi_men else src]}
        elif god in ("天芮", "天辅", "天蓬", "天任", "天冲", "天英", "天柱", "天心", "天禽"):
            src = {v: k for k, v in STAR_BY_PALACE.items()}.get(god, 2)
            gods[god] = {"type": "star", "palace": shi_gan_palace_eff if god == zhifu_star else src,
                         "palace_name": PALACE_NAMES[shi_gan_palace_eff if god == zhifu_star else src]}
        elif god == "值符":
            gods[god] = {"type": "star", "name": zhifu_star, "palace": shi_gan_palace,
                         "palace_name": PALACE_NAMES[shi_gan_palace]}
        elif god == "值使":
            gods[god] = {"type": "door", "name": zhishi_men, "palace": zhishi_palace,
                         "palace_name": PALACE_NAMES[zhishi_palace]}

    return {
        "divination_time": f"{dt.year}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}",
        "place": place,
        "pillars": {"year": year_gz, "month": month_gz, "day": day_gz, "time": time_gz},
        "jieqi": jieqi,
        "method": "拆补法（时家转盘）",
        "ju": {"yang": yang, "yang_text": "阳遁" if yang else "阴遁", "yuan": yuan, "ju_number": ju,
               "display": f"{'阳' if yang else '阴'}遁{ju}局"},
        "xun": {"xun_shou": xun_shou, "xun_yi": xun_yi, "time_steps": t},
        "zhifu_zhishi": {"zhifu_star": zhifu_star, "zhishi_men": zhishi_men, "zhishi_palace": zhishi_palace},
        "kong_wang": {"zhi": kong_zhi, "palaces": kong_palaces},
        "palaces": palaces,
        "use_god": gods,
        "question_type": question_type,
        "engine": "self (时家转盘基础实现)",
        "note": "基础骨架实现：定局为拆补法；不同流派（置闰法等）局数可能不同，生产环境请接入专业排盘库校准。",
    }
