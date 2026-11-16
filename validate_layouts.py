#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""Валидатор раскладки инфографики на МНОГИХ рождениях (закрывает «проверено на одном»).
Для каждого рождения: гоняет 6 калькуляторов → JSON, строит все 23 SVG, эвристически
проверяет, не вылезает ли текст/элемент за viewBox. Печатает матрицу проблем.

Запуск: python3 validate_layouts.py [--render]   (--render = ещё и собрать PDF худших)
"""
import sys, os, re, json, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import infographics as ig
from timezones import historical_utc_offset
from geo import resolve

DIR = os.path.dirname(os.path.abspath(__file__))

# Разнообразные рождения (стресс раскладки: разные сезоны/времена/пол/эпохи; города из БД).
BIRTHS = [
    ("1990-03-03", "15:00", "М", "Москва"),
    ("1990-07-22", "23:40", "Ж", "Москва"),   # лето, 子时-граница, ж
    ("1983-08-08", "14:00", "Ж", "Сочи"),      # лето, много Огня/Земли
    ("2002-09-09", "00:20", "М", "Екатеринбург"),  # полночь
    ("1968-11-30", "09:45", "Ж", "Москва"),    # осень, поздние удачи/даши
    ("1995-12-25", "18:10", "М", "Москва"),    # зима
    ("2010-02-03", "11:30", "Ж", "Москва"),    # у 立春 — стресс boundary
    ("1977-06-21", "04:15", "М", "Москва"),    # солнцестояние, раннее утро
]

# JSON-источник -> список функций инфографики, его потребляющих.
CHARTS = {
    "bazi": ["four_pillars_svg", "interactions_svg", "shensha_svg", "nayin_svg", "fragility_svg",
             "five_elements_svg", "wuxing_cycle_svg", "tiaohou_svg", "strength_gauge_svg",
             "ten_gods_svg", "luck_timeline_svg", "annual_year_svg", "dynamic_interactions_svg"],
    "hd": ["bodygraph_svg", "activations_svg", "fragility_hd_svg"],
    "jyotish": ["rashi_chart_svg", "dasha_timeline_svg"],
    "matrix": ["matrix_diamond_svg"],
    "tibetan": ["mewa_square_svg", "forces_svg"],
    "gene_keys": ["spectrum_svg", "spheres_overview_svg"],
}


def run_calcs(date, time, gender, city, outdir):
    """Гоняет 6 калькуляторов, кладёт *.json в outdir. Возвращает {имя: путь|None}."""
    y, m, dd = (int(x) for x in date.split("-"))
    off, _ = historical_utc_offset(city, y, m, dd)
    lat, lon = resolve(city)
    cmds = {
        "bazi": ["bazi.py", date, time, gender, f"UTC+{off}", "--city", city, "--json"],
        "hd": ["hd.py", date, time, f"+{off}", "--json"],
        "jyotish": ["jyotish.py", date, time, str(lat), str(lon), f"+{off}", "--json"],
        "matrix": ["matrix.py", date, "--json"],
        "tibetan": ["tibetan.py", date, "--json"],
        "gene_keys": ["gene_keys.py", date, time, f"+{off}", "--json"],
    }
    out = {}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for name, args in cmds.items():
        try:
            r = subprocess.run(["python3", os.path.join(DIR, args[0])] + args[1:],
                               capture_output=True, text=True, timeout=90, env=env)
            if r.returncode == 0 and r.stdout.strip().startswith("{"):
                p = os.path.join(outdir, f"{name}.json")
                open(p, "w").write(r.stdout)
                out[name] = p
            else:
                out[name] = None
                print(f"    ⚠ {name}: калькулятор не дал JSON ({(r.stderr or r.stdout)[:60].strip()})")
        except Exception as e:
            out[name] = None; print(f"    ⚠ {name}: {e}")
    return out


def overflow(svg):
    """Эвристика: координаты/оценочная ширина текста за пределами viewBox → список проблем."""
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    if not m:
        return ["нет viewBox"]
    W, H = float(m.group(1)), float(m.group(2))
    iss, MAR = [], 3.0

    def num(attrs, name):
        r = re.search(rf'\b{name}="(-?[\d.]+)"', attrs)
        return float(r.group(1)) if r else None

    for tm in re.finditer(r'<text\s([^>]*)>(.*?)</text>', svg, re.S):
        attrs = tm.group(1); content = re.sub(r'<[^>]+>', '', tm.group(2))
        x = num(attrs, "x") or 0.0
        fs = num(attrs, "font-size") or 11.0
        anc = (re.search(r'text-anchor="(\w+)"', attrs) or [None, "start"])[1]
        w = len(content) * fs * 0.58
        lo, hi = (x - w / 2, x + w / 2) if anc == "middle" else (x - w, x) if anc == "end" else (x, x + w)
        y = num(attrs, "y")
        if lo < -MAR or hi > W + MAR:
            iss.append(f"текст «{content[:16]}» x[{lo:.0f}..{hi:.0f}] vs W={W:.0f}")
        if y is not None and (y < -MAR or y > H + MAR):
            iss.append(f"текст «{content[:16]}» y={y:.0f} vs H={H:.0f}")
    for cm in re.finditer(r'<(rect|circle|line|polygon)\s([^>]*?)/?>', svg):
        tag, a = cm.group(1), cm.group(2)
        rx = num(a, "x"); rw = num(a, "width")
        if rx is not None and (rx < -MAR or (rw and rx + rw > W + MAR)):
            iss.append(f"{tag} x={rx:.0f}+{rw or 0:.0f} vs W={W:.0f}")
        ry = num(a, "y"); rh = num(a, "height")
        if ry is not None and (ry < -MAR or (rh and ry + rh > H + MAR)):
            iss.append(f"{tag} y={ry:.0f}+{rh or 0:.0f} vs H={H:.0f}")
        for ax in ("cx", "x1", "x2"):
            v = num(a, ax)
            if v is not None and (v < -MAR or v > W + MAR):
                iss.append(f"{tag} {ax}={v:.0f} vs W={W:.0f}")
        for ay in ("cy", "y1", "y2"):
            v = num(a, ay)
            if v is not None and (v < -MAR or v > H + MAR):
                iss.append(f"{tag} {ay}={v:.0f} vs H={H:.0f}")
    return iss


def main():
    tmp = tempfile.mkdtemp(prefix="validate_")
    total_issues, chart_fail = 0, {}
    for bi, (date, time, gender, city) in enumerate(BIRTHS):
        od = os.path.join(tmp, str(bi)); os.makedirs(od, exist_ok=True)
        print(f"\n=== [{bi}] {date} {time} {gender} {city} ===")
        jsons = run_calcs(date, time, gender, city, od)
        for src, fns in CHARTS.items():
            path = jsons.get(src)
            if not path:
                continue
            d = json.load(open(path, encoding="utf-8"))
            for fn in fns:
                try:
                    svg = getattr(ig, fn)(d)
                except Exception as e:
                    print(f"    ✗ {fn}: ИСКЛЮЧЕНИЕ {e}")
                    chart_fail[fn] = chart_fail.get(fn, 0) + 1
                    continue
                iss = overflow(svg)
                if iss:
                    total_issues += len(iss)
                    chart_fail[fn] = chart_fail.get(fn, 0) + 1
                    print(f"    ⚠ {fn}: " + "; ".join(iss[:4]) + (" …" if len(iss) > 4 else ""))
    print(f"\n══════ ИТОГ: {total_issues} проблем раскладки; "
          f"графики с проблемами: {sorted(chart_fail.items(), key=lambda x:-x[1]) or 'нет — чисто'}")
    print(f"JSON-ы рождений: {tmp}")


if __name__ == "__main__":
    main()
