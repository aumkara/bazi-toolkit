#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_vs_pyhd.py — внешний оракул для hd.py: сверка карты Дизайна Человека с pyhd (MIT, pyswisseph). Issue #17.

Сверяется на батарее случайных рождений (1940–2020, разные пояса): Тип (с учётом подтипов pyhd:
Pure/Manifesting Generator, Energy/Mental/Classic Projector), Авторитет, Профиль, множество активированных
ворот, определённые каналы, ворота/линии Солнца и Земли Личности и Дизайна. Конвенция узлов у pyhd — не
параметризуется, поэтому ворота Узлов из сравнения активаций исключены (сравниваются через общее множество
ворот, где узлы истинные у hd.py; при расхождении только по узлам — предупреждение, не FAIL).

Запуск:  .venv/bin/python verify_vs_pyhd.py [N=60] [--seed 20261109] [--require] [--verbose]
Зависимость (вне .venv): pip install --target /tmp/xval_site "git+https://github.com/ppo/pyhd" && PYTHONPATH=/tmp/xval_site …
Без pyhd — пропуск с exit 0; с --require — exit 2.
"""
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone

DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(DIR, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable

try:
    from pyhd import Chart
except Exception as _e:  # noqa: BLE001 — ImportError, а на Python < 3.13 ещё и AttributeError из enum (pyhd требует 3.13+)
    reason = f"{type(_e).__name__}: {str(_e)[:80]}"
    if "--require" in sys.argv:
        print(f"verify_vs_pyhd: pyhd недоступен ({reason}; нужен Python ≥ 3.13) — оракул обязателен, exit 2")
        sys.exit(2)
    print(f"verify_vs_pyhd: pyhd недоступен ({reason}) — оракул пропущен (pip install git+https://github.com/ppo/pyhd, Python ≥ 3.13)")
    sys.exit(0)

# имена enum у pyhd — человекочитаемые («Pure Generator», «Solar Plexus»); нормализуем в UPPER_SNAKE
def _norm(x):
    return str(getattr(x, "name", x)).upper().replace(" ", "_").replace("-", "_")


def _num(x):
    """Gates._61 / Lines._6 / 61 → 61"""
    try:
        return int(x)
    except (TypeError, ValueError):
        import re as _re
        return int(_re.sub(r"\D", "", str(x)))

TYPE_MAP = {"MANIFESTOR": "Манифестор", "GENERATOR": "Генератор", "PURE_GENERATOR": "Генератор",
            "MANIFESTING_GENERATOR": "Манифестирующий Генератор", "PROJECTOR": "Проектор",
            "MENTAL_PROJECTOR": "Проектор", "ENERGY_PROJECTOR": "Проектор", "CLASSIC_PROJECTOR": "Проектор",
            "REFLECTOR": "Рефлектор"}
AUTH_MAP = {"SOLAR_PLEXUS": "Эмоциональный", "SACRAL": "Сакральный", "SPLENIC": "Селезёночный",
            "EGO_MANIFESTED": "Эго", "EGO_PROJECTED": "Эго", "SELF_PROJECTED": "Самопроецируемый",
            "OUTER_AUTHORITY": "Ментальный", "OUTER": "Ментальный", "LUNAR": "Лунный"}


def ours(date, time, off):
    p = subprocess.run([PY, os.path.join(DIR, "hd.py"), date, time, f"{off:+g}", "--json"],
                       capture_output=True, text=True, cwd=DIR)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    return json.loads(p.stdout)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 60
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261109
    verbose = "--verbose" in sys.argv
    rnd = random.Random(seed)
    cats = {"тип": 0, "авторитет": 0, "профиль": 0, "ворота": 0, "каналы": 0, "Солнце/Земля": 0}
    node_only = 0
    pyhd_sacral_mg = 0
    examples = []
    for _ in range(n):
        y, m, d = rnd.randint(1940, 2020), rnd.randint(1, 12), rnd.randint(1, 28)
        hh, mm = rnd.randint(0, 23), rnd.choice([0, 10, 20, 30, 40, 50])
        off = rnd.choice([-8, -5, 0, 1, 2, 3, 4, 5, 8, 9])
        o = ours(f"{y:04d}-{m:02d}-{d:02d}", f"{hh:02d}:{mm:02d}", off)
        c = Chart(datetime(y, m, d, hh, mm, tzinfo=timezone(timedelta(hours=off))))
        bad = []
        t_type = TYPE_MAP.get(_norm(c.type), _norm(c.type))
        if o["type"] != t_type:
            # Известная ошибка оракула: pyhd проверяет связь Горла только с НЕсакральными моторами
            # (NON_SACRAL_MOTOR_CENTERS), поэтому Сакрал→Горло (34-20 напрямую или через G: 2-14 + 10-20/1-8…)
            # у него «Pure Generator». По канону (Ra Uru Hu; сверка hd.py с Maia Mechanics 2026-06-30) это
            # Манифестирующий Генератор. Считаем отдельно, не как расхождение hd.py.
            if o["type"] == "Манифестирующий Генератор" and _norm(c.type) == "PURE_GENERATOR":
                pyhd_sacral_mg += 1
            else:
                cats["тип"] += 1; bad.append(f"тип {o['type']}≠{_norm(c.type)}")
        t_auth = AUTH_MAP.get(_norm(c.authority), _norm(c.authority))
        if not o["authority"].startswith(t_auth):
            cats["авторитет"] += 1; bad.append(f"авторитет «{o['authority'][:20]}»≠{_norm(c.authority)}")
        if o["profile"] != str(c.profile):
            cats["профиль"] += 1; bad.append(f"профиль {o['profile']}≠{c.profile}")
        o_gates = {a["gate"] for s in ("personality", "design") for a in o["activations"][s]}
        t_gates = {_num(g) for g in c.gates}
        if o_gates != t_gates:
            # расхождение только в воротах Узлов (конвенция true/mean) — предупреждение
            node_bodies = {"north_node", "south_node", "northnode", "southnode", "node_n", "node_s"}
            o_node = {a["gate"] for s in ("personality", "design") for a in o["activations"][s]
                      if "node" in a["body"].lower() or "узел" in a.get("body_ru", "").lower()}
            if (o_gates ^ t_gates) <= o_node:
                node_only += 1
            else:
                cats["ворота"] += 1; bad.append(f"ворота ±{sorted(o_gates ^ t_gates)}")
        o_ch = {frozenset(map(int, ch["gates"].replace("–", "-").split("-"))) for ch in o["defined_channels"]}
        t_ch = {frozenset(_num(x) for x in str(ch).split("-")) for ch in c.channels}
        if o_ch != t_ch:
            cats["каналы"] += 1; bad.append(f"каналы {sorted(map(sorted, o_ch ^ t_ch))}")
        for side, imp in (("personality", c.personality), ("design", c.design)):
            o_sun = next((a["gate"], a["line"]) for a in o["activations"][side] if a["body"] == "sun")
            o_earth = next((a["gate"], a["line"]) for a in o["activations"][side] if a["body"] == "earth")
            acts = {_norm(k).lower(): v for k, v in imp.activations.items()}
            t_sun = (_num(acts["sun"].gate), _num(acts["sun"].line))
            t_earth = (_num(acts["earth"].gate), _num(acts["earth"].line))
            if o_sun != t_sun or o_earth != t_earth:
                cats["Солнце/Земля"] += 1; bad.append(f"{side}: Солнце {o_sun}≠{t_sun}, Земля {o_earth}≠{t_earth}"); break
        if bad and len(examples) < 8:
            examples.append((f"{y}-{m:02d}-{d:02d} {hh:02d}:{mm:02d} UTC{off:+d}", bad))
    print(f"verify_vs_pyhd: {n} карт против pyhd — расхождения: " + ", ".join(f"{k}={v}" for k, v in cats.items())
          + (f"; только узлы (конвенция): {node_only}" if node_only else "")
          + (f"; MG через Сакрал, у pyhd «Pure Generator» (ошибка оракула): {pyhd_sacral_mg}" if pyhd_sacral_mg else ""))
    if sum(cats.values()) or verbose:
        for when, bad in examples:
            print(f"  ✗ {when}: {'; '.join(bad)[:300]}")
    return 1 if sum(cats.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
