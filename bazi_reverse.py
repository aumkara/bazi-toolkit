#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""bazi_reverse.py — обратный поиск: когда бывают заданные столпы Ба Цзы (год, месяц, день[, час]). Issue #30.

Для ректификации и проверки чтений: «карта 庚午 辛巳 庚辰 癸未 — какие это даты?». Год — каждые 60 лет;
месяц — интервал между двумя 节 (точные моменты, Swiss Ephemeris, в поясе tz); день — 60-дневный цикл внутри
интервала (0–1 попадание); час — двухчасовое окно, ствол часа по правилу bazi.py (夜子时: 23:xx — ствол от
следующего дня). Несогласованные столпы (ствол месяца не следует из ствола года по 五虎遁, ствол часа — из ствола
дня по 五鼠遁) → пустой список с причиной.

Использование:
    python3 bazi_reverse.py 庚午 辛巳 庚辰 [癸未] [--from 1900] [--to 2100] [UTC+8] [--json]
    python3 bazi_reverse.py --test
"""
import json
import sys
from datetime import datetime, timedelta, timezone

import bazi
import cli_errors
from bazi import STEMS, BRANCHES, year_pillar, month_pillar, day_pillar, hour_pillar, get_jie_terms


@cli_errors.parser
def parse_pillar(s):
    if len(s) != 2 or s[0] not in STEMS or s[1] not in BRANCHES:
        raise ValueError(f"столп «{s}» — ожидается ствол+ветвь, например 庚午")
    return STEMS.index(s[0]), BRANCHES.index(s[1])


def find_dates(yp, mp, dp, hp=None, y_from=1900, y_to=2100, tz_off=8):
    ys, yb = parse_pillar(yp); ms, mb = parse_pillar(mp); ds, db = parse_pillar(dp)
    hs_hb = parse_pillar(hp) if hp else None
    mn = (mb - 2) % 12 + 1                         # 寅 → 1 … 丑 → 12
    if month_pillar(ys, mn) != (ms, mb):
        want = STEMS[month_pillar(ys, mn)[0]] + BRANCHES[mb]
        return [], f"столп месяца {mp} не следует из года {yp} (五虎遁 даёт {want})"
    if hs_hb:
        hs, hb = hs_hb
        probe = [h for h in range(24) if ((h + 1) // 2) % 12 == hb]
        if not any(hour_pillar(ds, h) == (hs, hb) for h in probe):
            opts = sorted({STEMS[hour_pillar(ds, h)[0]] + BRANCHES[hb] for h in probe})
            return [], f"столп часа {hp} не следует из дня {dp} (五鼠遁 даёт {'/'.join(opts)})"
    tz = timezone(timedelta(hours=tz_off))
    out = []
    for by in range(y_from, y_to + 1):
        if year_pillar(by) != (ys, yb):
            continue
        jie = sorted([t for y in (by - 1, by, by + 1, by + 2) for t in get_jie_terms(y)], key=lambda t: t[0])
        lichun = [t[0] for t in jie if t[1] == 1 and t[0].astimezone(tz).year == by]
        if not lichun:
            continue
        start_i = next(i for i, t in enumerate(jie) if t[0] == lichun[0])
        idx = next(i for i in range(start_i, len(jie)) if jie[i][1] == mn)
        m_start, m_end = jie[idx][0].astimezone(tz), jie[idx + 1][0].astimezone(tz)
        d = m_start.date()
        while datetime(d.year, d.month, d.day, tzinfo=tz) < m_end:
            if day_pillar(d.year, d.month, d.day) == (ds, db):
                day0 = datetime(d.year, d.month, d.day, tzinfo=tz); day1 = day0 + timedelta(days=1)
                note = None
                if m_start > day0:
                    note = f"节 {jie[idx][2]}-месяца наступает в {m_start:%H:%M} — до этого столп месяца предыдущий"
                elif m_end < day1:
                    note = f"следующий 节 наступает в {m_end:%H:%M} — после этого столп месяца следующий"
                if hs_hb is None:
                    out.append({"date": d.isoformat(), "hours": None, "note": note})
                else:
                    hours = [h for h in range(24) if ((h + 1) // 2) % 12 == hb and hour_pillar(ds, h) == (hs, hb)
                             and m_start <= day0 + timedelta(hours=h, minutes=59) and day0 + timedelta(hours=h) < m_end]
                    if hours:
                        hrs = f"{hours[0]:02d}:00–{hours[-1]:02d}:59" if hours[-1] - hours[0] <= 1 else ", ".join(f"{h:02d}:xx" for h in hours)
                        out.append({"date": d.isoformat(), "hours": hrs, "note": note})
            d += timedelta(days=1)
    return out, None


def _test():
    ok = True
    r, why = find_dates("庚午", "辛巳", "庚辰", "癸未", 1900, 2100, 4)
    hit = [x for x in r if x["date"] == "1990-05-15"]
    p1 = bool(hit) and hit[0]["hours"] == "13:00–14:59" and all(datetime.fromisoformat(x["date"]).year % 60 == 1990 % 60 for x in r)
    ok &= p1; print(f"[{'PASS' if p1 else 'FAIL'}] 庚午 辛巳 庚辰 癸未 (UTC+4) → {[(x['date'], x['hours']) for x in r]} (ожидалось 1990-05-15 13:00–14:59 среди них)")
    r, why = find_dates("庚午", "庚巳", "庚辰", None)
    p2 = r == [] and why and "五虎遁" in why
    ok &= p2; print(f"[{'PASS' if p2 else 'FAIL'}] несогласованный месяц 庚巳 при годе 庚午 → пусто: {why}")
    r, why = find_dates("庚午", "辛巳", "庚辰", "甲未")
    p3 = r == [] and why and "五鼠遁" in why
    ok &= p3; print(f"[{'PASS' if p3 else 'FAIL'}] несогласованный час 甲未 при дне 庚辰 → пусто: {why}")
    # 夜子时: 1990-05-15 23:30 → час 戊子 (ствол от следующего дня); обратный поиск 戊子 должен дать 23:00–23:59 того дня
    r, why = find_dates("庚午", "辛巳", "庚辰", "戊子", 1990, 1990, 8)
    p4 = r and r[0]["date"] == "1990-05-15" and r[0]["hours"] == "23:00–23:59"
    ok &= p4; print(f"[{'PASS' if p4 else 'FAIL'}] 夜子时 戊子 → {r} (ожидалось 1990-05-15 23:00–23:59)")
    r, _ = find_dates("庚午", "辛巳", "庚辰", "丙子", 1990, 1990, 8)
    p5 = r and r[0]["hours"] == "00:00–00:59"
    ok &= p5; print(f"[{'PASS' if p5 else 'FAIL'}] 早子时 丙子 → {r} (ожидалось 00:00–00:59)")
    print("bazi_reverse --test:", "ЗЕЛЁНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1


def main():
    args = sys.argv[1:]
    if not args or "--help" in args:
        print(__doc__); return 0
    if "--test" in args:
        return _test()
    json_mode = "--json" in args
    y_from = int(args[args.index("--from") + 1]) if "--from" in args else 1900
    y_to = int(args[args.index("--to") + 1]) if "--to" in args else 2100
    tz_off = 8
    pillars = []
    skip = False
    for a in args:
        if skip: skip = False; continue
        if a in ("--from", "--to"): skip = True; continue
        if a.upper().startswith("UTC"): tz_off = float(a[3:].replace("+", "") or 0); continue
        if a.startswith("--"): continue
        pillars.append(a)
    if len(pillars) not in (3, 4):
        print("нужно 3 или 4 столпа: год месяц день [час]", file=sys.stderr); return 2
    res, why = find_dates(*pillars[:3], pillars[3] if len(pillars) == 4 else None, y_from, y_to, tz_off)
    if json_mode:
        print(json.dumps({"pillars": pillars, "range": [y_from, y_to], "utc_offset": tz_off, "matches": res, "reason": why,
                          "conventions": {"late_zi": "23:xx — ствол часа от следующего дня (bazi.py)", "month_boundary": "точный момент 节"}},
                         ensure_ascii=False, indent=2))
    else:
        print(f"\n  {' '.join(pillars)}  ({y_from}–{y_to}, UTC{tz_off:+g})")
        if why: print(f"  нет совпадений: {why}")
        for x in res:
            print(f"  {x['date']}  {x['hours'] or ''}  {('— ' + x['note']) if x['note'] else ''}")
        if not res and not why: print("  совпадений нет")
        print()
    return 0


if __name__ == "__main__":
    import cli_errors
    cli_errors.run(main)
