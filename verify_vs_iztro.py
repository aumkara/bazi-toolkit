#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_vs_iztro.py — внешний оракул для ziwei.py: сверка карты 紫微斗数 с x-iztro (порт iztro,
716 314 golden-кейсов поле-в-поле; MIT). Issue #17.

Что сверяется на батарее случайных лунных дат/часов/полов: 命宫, 身宫, 五行局, стволы дворцов,
14 главных звёзд по дворцам, 四化 (禄/权/科/忌) главных звёзд, общие вспомогательные звёзды
(左辅 右弼 文昌 文曲 天魁 天钺 禄存 擎羊 陀罗 火星 铃星 地空 地劫 — те, что считает ziwei.py).
Час 子 (23–01) исключён: разные конвенции 早/晚子时 — сравнивается отдельно вручную.

История: первый прогон 2026-11-09 нашёл две ошибки ziwei.py — формула 安紫微 была верна только
для дня 1 (42/60 карт с неверным 紫微), 破军 стоял на 天府+7 вместо +10. После фикса: 120/120.

Запуск:  .venv/bin/python verify_vs_iztro.py [N=80] [--seed 20261109] [--require] [--verbose]
Зависимость (вне .venv проекта): pip install --target /tmp/xval_site x-iztro && PYTHONPATH=/tmp/xval_site …
Без x_iztro — пропуск с exit 0; с --require — exit 2.
"""
import json
import os
import random
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(DIR, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable

try:
    from x_iztro import Astro
except ImportError:
    if "--require" in sys.argv:
        print("verify_vs_iztro: x_iztro не установлен (pip install x-iztro) — оракул обязателен, exit 2")
        sys.exit(2)
    print("verify_vs_iztro: x_iztro не установлен — оракул пропущен (pip install x-iztro, чтобы включить)")
    sys.exit(0)

MUT = {"化禄": "禄", "化权": "权", "化科": "科", "化忌": "忌"}


def ours(y, m, d, h, g):
    p = subprocess.run([PY, os.path.join(DIR, "ziwei.py"), "--lunar", str(y), str(m), str(d), str(h), g, "--json"],
                       capture_output=True, text=True, cwd=DIR)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    return json.loads(p.stdout)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 80
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261109
    verbose = "--verbose" in sys.argv
    rnd = random.Random(seed)
    astro = Astro()
    cats = {"命宫": 0, "身宫": 0, "五行局": 0, "стволы": 0, "главные звёзды": 0, "四化": 0, "вспомогательные": 0}
    examples = []
    for _ in range(n):
        y, m, d = rnd.randint(1920, 2030), rnd.randint(1, 12), rnd.randint(1, 29)
        h = rnd.choice([1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21])
        g = rnd.choice(["М", "Ж"])
        o = ours(y, m, d, h, g)
        c = astro.by_lunar(f"{y}-{m}-{d}", ((h + 1) // 2) % 12, "male" if g == "М" else "female", language="zh-CN")
        t_pal = {p.earthly_branch: p for p in c.palaces}
        o_pal = {p["branch"]: p for p in o["palaces"].values()}
        ming_t = next(p.earthly_branch for p in c.palaces if p.name == "命宫")
        shen_t = next(p.earthly_branch for p in c.palaces if p.is_body_palace)
        bad = []
        if o["ming_gong"]["branch"] != ming_t:
            cats["命宫"] += 1; bad.append(f"命宫 {o['ming_gong']['branch']}≠{ming_t}")
        if o["shen_gong"]["branch"] != shen_t:
            cats["身宫"] += 1; bad.append(f"身宫 {o['shen_gong']['branch']}≠{shen_t}")
        if o["ju"]["name"] != c.five_elements_class:
            cats["五行局"] += 1; bad.append(f"局 {o['ju']['name']}≠{c.five_elements_class}")
        if any(o_pal[b]["stem"] != t_pal[b].heavenly_stem for b in t_pal):
            cats["стволы"] += 1; bad.append("стволы дворцов")
        for b, tp in t_pal.items():
            om = sorted(s["name"] for s in o_pal[b]["stars"] if s["type"] == "main")
            tm = sorted(s.name for s in tp.major_stars)
            if om != tm:
                cats["главные звёзды"] += 1; bad.append(f"{b}: {om}≠{tm}"); break
        for b, tp in t_pal.items():
            omu = sorted((s["name"], MUT.get(s.get("transformation") or "", s.get("transformation") or ""))
                         for s in o_pal[b]["stars"] if s["type"] == "main" and s.get("transformation"))
            tmu = sorted((s.name, str(s.mutagen)) for s in tp.major_stars if s.mutagen)
            if omu != tmu:
                cats["四化"] += 1; bad.append(f"四化 {b}: {omu}≠{tmu}"); break
        # вспомогательные: сравниваем только звёзды, которые есть у нас
        o_minor = {s["name"]: b for b, p in o_pal.items() for s in p["stars"] if s["type"] != "main"}
        t_minor = {s.name: b for b, tp in t_pal.items() for s in list(tp.minor_stars) + list(tp.adjective_stars)}
        diff = [(name, b, t_minor.get(name)) for name, b in o_minor.items() if name in t_minor and t_minor[name] != b]
        if diff:
            cats["вспомогательные"] += 1; bad.append(f"вспом.: {diff[:3]}")
        if bad and len(examples) < 8:
            examples.append((f"{y}-{m}-{d} ч{h} {g}", bad))
    total_bad = sum(1 for _ in examples)  # число карт с ошибками ограничено примерами; считаем по категориям
    print(f"verify_vs_iztro: {n} карт против x-iztro — расхождения по категориям: "
          + ", ".join(f"{k}={v}" for k, v in cats.items()))
    for when, bad in examples if verbose or sum(cats.values()) else []:
        print(f"  ✗ {when}: {'; '.join(bad)[:300]}")
    return 1 if sum(cats.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
