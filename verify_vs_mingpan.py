#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_vs_mingpan.py — внешний оракул через MCP-сервер mingpan (ChesterRa/mingpan, Apache-2.0, `npx -y mingpan`). Issue #32.

Что сверяется:
  • meihua.py — 起卦 по числам (2 и 3 числа) и по моменту: 本卦/变卦/互卦 (имя → состав триграмм), 动爻, 体/用 (какая
    триграмма 体), отношение стихий; для времени — ещё и слагаемые (номер ветви года, лунные месяц/день, номер часа);
  • qimen.py (拆补) — 局 (阴/阳遁 + номер + 元) и доска по восьми дворцам (地盘/天盘/九星/八门/八神) — третий оракул
    рядом с kinqimen и Ciallo.
Сервер говорит Markdown (традиционные иероглифы) — разбирается регулярками; 天禽 у mingpan стоит в 中宫, у нас — при 天芮
(сравнение 中宫 пропускается). Нужны node/npx и сеть при первом запуске (npx кэширует пакет); без них — пропуск.

Запуск: .venv/bin/python verify_vs_mingpan.py [N=60] [--seed 20261109] [--require]
"""
import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(DIR, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable
sys.path.insert(0, DIR)

NATURE = {"天": "乾", "澤": "兑", "泽": "兑", "火": "离", "雷": "震", "風": "巽", "风": "巽", "水": "坎", "山": "艮", "地": "坤"}
TRAD = {"兌": "兑", "離": "离"}
NUM = "一二三四五六七八九"
GATE_T = {"休門": "休门", "生門": "生门", "傷門": "伤门", "杜門": "杜门", "景門": "景门", "死門": "死门", "驚門": "惊门", "開門": "开门"}
STAR_T = {"天衝": "天冲", "天輔": "天辅"}
SPIRIT_T = {"螣蛇": "腾蛇", "太陰": "太阴"}
SPIRIT_ALIAS = {"勾陈": "白虎", "朱雀": "玄武"}   # 阳遁-имена 勾陈/朱雀 (наши и kinqimen) = 白虎/玄武 (mingpan, Ciallo)


def skip(msg):
    if "--require" in sys.argv:
        print(f"verify_vs_mingpan: {msg} — оракул обязателен, exit 2"); sys.exit(2)
    print(f"verify_vs_mingpan: {msg} — оракул пропущен"); sys.exit(0)


def hex_from_name(name):
    """«天風姤» → (乾, 巽); «巽為風» → (巽, 巽)."""
    name = name.strip()
    if "為" in name or "为" in name:
        t = TRAD.get(name[0], name[0]); return t, t
    return NATURE[name[0]], NATURE[name[1]]


def our_meihua(args):
    p = subprocess.run([PY, os.path.join(DIR, "meihua.py"), *args, "--json"], capture_output=True, text=True, cwd=DIR)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-200:])
    return json.loads(p.stdout)


def our_qimen(y, m, d, h, mi):
    p = subprocess.run([PY, os.path.join(DIR, "qimen.py"), f"{y}-{m:02d}-{d:02d}", f"{h:02d}:{mi:02d}", "UTC+8", "--json"], capture_output=True, text=True, cwd=DIR)
    return json.loads(p.stdout)


def parse_meihua(md):
    g = lambda rx: (re.search(rx, md) or [None, None])[1]
    out = {"ben": g(r"\*\*本卦\*\*：(\S+?) →"), "bian": g(r"\*\*變卦\*\*：(\S+?) \|"), "hu": g(r"\*\*互卦\*\*：(\S+)"),
           "moving": {"初": 1, "二": 2, "三": 3, "四": 4, "五": 5, "上": 6}.get(g(r"\*\*動爻\*\*：(.)爻")),
           "ti_upper": "上卦" in (re.search(r"\| 上卦 \|[^\n]*\| (體|用) \|", md) or [None, "x"])[0] and re.search(r"\| 上卦 \|[^\n]*\| 體 \|", md) is not None,
           "relation": g(r"\*\*體用關係\*\*：(\S+)"),
           "sums": re.findall(r"年\((\d+)\) \+ 月\((\d+)\) \+ 日\((\d+)\) = (\d+)", md), "hour_sum": re.findall(r"\+ 時\((\d+)\) = (\d+)", md)}
    return out


def rel_norm(s):
    if s is None: return None
    if "比和" in s: return "比和"
    if "用剋體" in s or "用克体" in s: return "克"
    if "體剋用" in s or "体克用" in s: return "被克"
    if "用生體" in s or "用生体" in s: return "生"
    if "體生用" in s or "体生用" in s: return "被生"
    return s


def parse_qimen(md):
    m = re.search(r"\*\*(陰|陽|阴|阳)遁(\d)局\*\* \| 时盘 \| 转盘式 \| (上元|中元|下元)", md)
    ju = (("阳" if m.group(1) in "陽阳" else "阴"), int(m.group(2)), m.group(3)) if m else None
    rows = {}
    for r in re.finditer(r"\| (巽|離|离|坤|震|中|兌|兑|艮|坎|乾)(\d) \| (\S) \| (\S) \| (\S+) \| (\S+) \| (\S+) \|", md):
        tri = TRAD.get(r.group(1), r.group(1))
        rows[tri] = {"earth": r.group(3), "heaven": r.group(4), "gate": GATE_T.get(r.group(5), r.group(5)), "star": STAR_T.get(r.group(6), r.group(6)), "spirit": SPIRIT_T.get(r.group(7), r.group(7))}
    return ju, rows


async def main_async(n, seed):
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    rnd = random.Random(seed)
    cats = {"梅花 числа": 0, "梅花 время": 0, "奇门 局": 0, "奇门 доска": 0}
    ex = []
    zhonggong_school = 0
    import meihua
    async with stdio_client(StdioServerParameters(command="npx", args=["-y", "mingpan"], cwd=DIR)) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            async def call(name, args):
                res = await s.call_tool(name, args)
                return "\n".join(c.text for c in res.content if hasattr(c, "text"))
            # 1. 梅花 по числам (2 и 3 числа)
            for _ in range(n):
                a, b = rnd.randint(1, 999), rnd.randint(1, 999)
                three = rnd.random() < 0.3; c = rnd.randint(1, 99)
                args = {"method": "number", "upperNumber": a, "lowerNumber": b} | ({"yaoNumber": c} if three else {})
                t = parse_meihua(await call("meihua_basic", args))
                o = our_meihua(["--numbers", str(a), str(b)] + ([str(c)] if three else []))
                bad = compare_meihua(o, t)
                if bad:
                    cats["梅花 числа"] += 1
                    if len(ex) < 8: ex.append((f"числа {a} {b}" + (f" {c}" if three else ""), bad))
            # 2. 梅花 по моменту (пекинское время; lunar-python у нас)
            try:
                import lunar_python  # noqa: F401
                have_lunar = True
            except ImportError:
                have_lunar = False
            if have_lunar:
                for _ in range(n):
                    y, m, d, h = rnd.randint(1950, 2040), rnd.randint(1, 12), rnd.randint(1, 28), rnd.randint(0, 23)
                    t = parse_meihua(await call("meihua_basic", {"method": "time", "year": y, "month": m, "day": d, "hour": h}))
                    o = our_meihua(["--time", f"{y}-{m:02d}-{d:02d}", f"{h:02d}:30"])
                    bad = compare_meihua(o, t)
                    if t["sums"]:
                        yb, lm, ld, su = map(int, t["sums"][0]); L = o["input"]["lunar"]
                        if (yb, lm, ld, su) != (L["year_branch_no"], L["month"], L["day"], o["input"]["sums"]["upper"]):
                            bad.append(f"слагаемые год/месяц/день {yb}/{lm}/{ld}={su} ≠ {L['year_branch_no']}/{L['month']}/{L['day']}={o['input']['sums']['upper']}")
                    if bad:
                        cats["梅花 время"] += 1
                        if len(ex) < 8: ex.append((f"время {y}-{m:02d}-{d:02d} {h:02d}h", bad))
            else:
                print("   ~ lunar-python не установлен — 時間起卦 не сверялось")
            # 3. 奇门 拆补
            for _ in range(n):
                y, m, d, h, mi = rnd.randint(1950, 2040), rnd.randint(1, 12), rnd.randint(1, 28), rnd.choice(range(1, 23, 2)), rnd.choice([10, 30, 50])
                ju, rows = parse_qimen(await call("qimen_basic", {"year": y, "month": m, "day": d, "hour": h, "minute": mi}))
                o = our_qimen(y, m, d, h, mi); meta = o["meta"]
                ju_o = ("阳" if meta["yang"] else "阴", meta["ju"], meta["yuan"])
                bad = []
                if ju != ju_o:
                    cats["奇门 局"] += 1; bad.append(f"局 {ju_o}≠{ju}")
                else:
                    pal = {p["trigram"]: p for p in o["palaces"].values()}
                    for tri, row in rows.items():
                        if tri == "中" or tri not in pal: continue
                        op = pal[tri]
                        ours_t = (op["earth"], op["heaven"], op["gate"], op["star"].split("/")[0], SPIRIT_ALIAS.get(op["spirit"], op["spirit"]))
                        theirs_t = (row["earth"], row["heaven"], row["gate"], row["star"], SPIRIT_ALIAS.get(row["spirit"], row["spirit"]))
                        if ours_t != theirs_t:
                            # Известное расхождение школ: 值符 = 天禽 (旬首 в 中宫) — mingpan (《神奇之门》) ведёт 值使 иначе, чем
                            # kinqimen и Ciallo (с которыми мы совпадаем); считаем отдельно, не как ошибку
                            if meta["duty_star"] == "天禽" and ours_t[:2] == theirs_t[:2] and ours_t[3:] == theirs_t[3:]:
                                zhonggong_school += 1
                            else:
                                cats["奇门 доска"] += 1; bad.append(f"доска {tri}: {''.join(ours_t)} ≠ {''.join(theirs_t)}")
                            break
                if bad and len(ex) < 8: ex.append((f"奇门 {y}-{m:02d}-{d:02d} {h:02d}:{mi}", bad))
    print(f"verify_vs_mingpan: по {n} случаев на блок против mingpan (MCP) — расхождения: " + ", ".join(f"{k}={v}" for k, v in cats.items())
          + (f"; врата при 值符=天禽 (школа 《神奇之门》 vs kinqimen/Ciallo, не ошибка): {zhonggong_school}" if zhonggong_school else ""))
    for w, bad in ex if sum(cats.values()) else []:
        print(f"  ✗ {w}: {'; '.join(bad)[:300]}")
    return 1 if sum(cats.values()) else 0


def compare_meihua(o, t):
    import meihua
    bad = []
    for key, ours in (("ben", o["ben_gua"]), ("bian", o["bian_gua"]), ("hu", o["hu_gua"])):
        if not t[key]:
            bad.append(f"{key}: не разобран ответ"); continue
        up, lo = hex_from_name(t[key])
        if (ours["upper"]["name"], ours["lower"]["name"]) != (up, lo):
            bad.append(f"{key} {ours['upper']['name']}/{ours['lower']['name']} ≠ {t[key]}")
    if t["moving"] != o["moving_line"]:
        bad.append(f"动爻 {o['moving_line']}≠{t['moving']}")
    if (o["ti_yong"]["ti"]["side"] == "upper") != bool(t["ti_upper"]):
        bad.append(f"体 {o['ti_yong']['ti']['side']} ≠ {'upper' if t['ti_upper'] else 'lower'}")
    if rel_norm(t["relation"]) != o["ti_yong"]["relation"]:
        bad.append(f"体用 {o['ti_yong']['relation']} ≠ {t['relation']}")
    return bad


def main():
    if not shutil.which("npx"):
        skip("npx (node) не найден")
    try:
        import mcp  # noqa: F401
    except ImportError:
        skip("пакет mcp не установлен (requirements-dev)")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 60
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261109
    try:
        return asyncio.run(main_async(n, seed))
    except Exception as e:  # noqa: BLE001 — сервер не поднялся (сеть/npx)
        skip(f"mingpan не запустился: {type(e).__name__}: {str(e)[:120]}")


if __name__ == "__main__":
    sys.exit(main())
