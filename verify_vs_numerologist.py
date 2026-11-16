#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_vs_numerologist.py — второй, независимый от iztro оракул для ziwei.py: `ziwei_cli.py` из
FANzR-arch/Numerologist_skills (Python, только lunar_python; свои таблицы 安星 по 三合-школе, ruleset ziwei-sanhe-v1).
Issue #31. Контекст: все найденные JS-проекты (iztro, ziwei-doushu, mingpan) делят одно ядро iztro — это первая
реализация с другим кодом.

Сверяется по батарее лунных дат (без 子-часа и без 闰月 — там школы расходятся): 命宫, 身宫, 五行局, стволы дворцов,
14 главных звёзд, 四化 года, вспомогательные звёзды из числа тех, что считает ziwei.py (左辅 右弼 文昌 文曲 天魁 天钺
禄存 擎羊 陀罗). Имя дворца 事业 ≡ 官禄.
Лицензии у репозитория нет → файл не вендорится: скачивается в ~/.cache/bazi-oracles/numerologist/ при первом запуске
(нужна сеть), lunar-python берётся из .venv (requirements-dev). Без них — пропуск.

Запуск: .venv/bin/python verify_vs_numerologist.py [N=60] [--seed 20261109] [--require]
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import urllib.request

DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(DIR, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "bazi-oracles", "numerologist")
URL = "https://raw.githubusercontent.com/FANzR-arch/Numerologist_skills/HEAD/ziwei-doushu/scripts/ziwei_cli.py"
PALACE_ALIAS = {"官禄": "事业"}
MINOR_WE_HAVE = {"左辅", "右弼", "文昌", "文曲", "天魁", "天钺", "禄存", "擎羊", "陀罗"}


def skip(msg):
    if "--require" in sys.argv:
        print(f"verify_vs_numerologist: {msg} — оракул обязателен, exit 2"); sys.exit(2)
    print(f"verify_vs_numerologist: {msg} — оракул пропущен"); sys.exit(0)


def ensure():
    try:
        subprocess.run([PY, "-c", "import lunar_python"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        skip("lunar-python не установлен в .venv")
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "ziwei_cli.py")
    if not os.path.exists(path):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                open(path, "wb").write(r.read())
        except Exception as e:  # noqa: BLE001
            skip(f"не скачать ziwei_cli.py: {type(e).__name__}")
    return path


def theirs(cli, y, m, d, h, male):
    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "in.json"); out = os.path.join(td, "out.json")
        json.dump({"calendar_type": "lunar", "birth_time": {"year": y, "month": m, "day": d, "hour": h, "minute": 0},
                   "gender": "male" if male else "female"}, open(inp, "w"))
        p = subprocess.run([PY, cli, "--input", inp, "--output", out], capture_output=True, text=True)
        data = json.load(open(out, encoding="utf-8"))
        if "error" in data:
            raise RuntimeError(data["error"])
        return data["chart"]


def ours(y, m, d, h, male):
    p = subprocess.run([PY, os.path.join(DIR, "ziwei.py"), "--lunar", str(y), str(m), str(d), str(h), "М" if male else "Ж", "--json"],
                       capture_output=True, text=True, cwd=DIR)
    return json.loads(p.stdout)


def main():
    cli = ensure()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 60
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261109
    rnd = random.Random(seed)
    cats = {"命宫": 0, "身宫": 0, "五行局": 0, "стволы": 0, "главные": 0, "四化": 0, "вспомогательные": 0, "имена дворцов": 0}
    ex = []; done = 0
    nm = lambda s: s if isinstance(s, str) else s.get("name")
    while done < n:
        y, m, d = rnd.randint(1930, 2030), rnd.randint(1, 12), rnd.randint(1, 29)
        h = rnd.choice([1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]); male = rnd.random() < 0.5
        try:
            t = theirs(cli, y, m, d, h, male)
        except Exception:  # дата не существует в лунном календаре (29-е) — пропускаем
            continue
        o = ours(y, m, d, h, male); done += 1; bad = []
        if o["ming_gong"]["branch"] != t["ming_gong"]["branch"]: cats["命宫"] += 1; bad.append(f"命宫 {o['ming_gong']['branch']}≠{t['ming_gong']['branch']}")
        if o["shen_gong"]["branch"] != t["shen_gong"]["branch"]: cats["身宫"] += 1; bad.append(f"身宫 {o['shen_gong']['branch']}≠{t['shen_gong']['branch']}")
        if o["ju"]["name"] != t["wuxing_ju"]["name"]: cats["五行局"] += 1; bad.append(f"局 {o['ju']['name']}≠{t['wuxing_ju']['name']}")
        tp = {p["branch"]: p for p in t["palaces"]}
        for p in o["palaces"].values():
            q = tp[p["branch"]]
            if p["stem"] != q["stem"]: cats["стволы"] += 1; bad.append(f"ствол {p['branch']}"); break
        for p in o["palaces"].values():
            q = tp[p["branch"]]
            if PALACE_ALIAS.get(q["name"], q["name"]) != PALACE_ALIAS.get(p["name"], p["name"]): cats["имена дворцов"] += 1; bad.append(f"дворец {p['branch']}: {p['name']}≠{q['name']}"); break
        for p in o["palaces"].values():
            q = tp[p["branch"]]
            om = sorted(s["name"] for s in p["stars"] if s["type"] == "main"); tm = sorted(nm(s) for s in q["major_stars"])
            if om != tm: cats["главные"] += 1; bad.append(f"{p['branch']}: {om}≠{tm}"); break
        osh = sorted((s["name"], s.get("transformation")) for p in o["palaces"].values() for s in p["stars"] if s.get("transformation"))
        tsh = sorted((x["star"], x["type"]) for x in t["year_sihua"])
        if osh != tsh: cats["四化"] += 1; bad.append(f"四化 {osh}≠{tsh}")
        for p in o["palaces"].values():
            q = tp[p["branch"]]
            omi = sorted(s["name"] for s in p["stars"] if s["type"] != "main" and s["name"] in MINOR_WE_HAVE)
            tmi = sorted(nm(s) for s in q["minor_stars"] if nm(s) in MINOR_WE_HAVE)
            if omi != tmi: cats["вспомогательные"] += 1; bad.append(f"вспом. {p['branch']}: {omi}≠{tmi}"); break
        if bad and len(ex) < 8: ex.append((f"лунная {y}-{m}-{d} ч{h} {'М' if male else 'Ж'}", bad))
    print(f"verify_vs_numerologist: {done} карт против ziwei_cli.py (Numerologist_skills, без iztro) — расхождения: "
          + ", ".join(f"{k}={v}" for k, v in cats.items()))
    for w, bad in ex if sum(cats.values()) else []:
        print(f"  ✗ {w}: {'; '.join(bad)[:300]}")
    return 1 if sum(cats.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
