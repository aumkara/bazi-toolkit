#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""bench/mingli_bench.py — прогон MingLi-Bench (DestinyLinker, MIT; 160 вопросов с выбором из 4 по 32 реальным картам
конкурса 全球算命师大赛 2022–2025) через наш конвейер. Issue #33.

Две условия, один и тот же LLM-агент:
  A  «наш конвейер»: карта от bazi.py (столпы, 十神, сила ХД, 用神/忌神, 调候, столпы удачи с годами, Шэнь Ша,
     для спрошенного года — 流年 и dynamic_interactions) + краткие правила скилла bazi → буква;
  B  «сырая модель»: только данные рождения и вопрос → буква.
Скрипт готовит пакеты промптов (prepare) и считает точность (score); сами ответы агент получает вне скрипта
(Subagent/opencode run) и кладёт в bench/out/answers_<A|B>.json как {"ftb_0001": "A", …}.

Пояс: страна → UTC (中国/china/malaysia/singapore +8, japan +9, usa −5 — допущение, как и у самого бенчмарка,
который берёт время как есть). Данные людей — публичный датасет конкурса, не наши клиенты.

Запуск:  .venv/bin/python bench/mingli_bench.py prepare [--batch 8]   → bench/out/prompts_A.json, prompts_B.json
         .venv/bin/python bench/mingli_bench.py score                 → точность A/B, по категориям, vs 25%
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(DIR, "bench", "out")
PY = os.path.join(DIR, ".venv", "bin", "python")
DATA_URL = "https://raw.githubusercontent.com/DestinyLinker/MingLi-Bench/HEAD/data/data.json"
TZ = {"中国": 8, "china": 8, "malaysia": 8, "singapore": 8, "hong kong": 8, "香港": 8, "taiwan": 8, "japan": 9, "usa": -5}

RULES_A = ("Ты интерпретатор Ба Цзы по правилам проекта: считает код, ты только читаешь карту. Не выдумывай иероглифов — "
           "все столпы, божества, удача и 流年 даны в JSON. Опирайся на: 用神/忌神 года (год на 用神 — поддержка, на 忌神 — "
           "давление), 冲/合/刑 流年 к ветви ДНЯ (дворец супруга — брак/разрыв), к ветви МЕСЯЦА (карьера/родители), к ветви ГОДА "
           "(родители, корни), 七杀/伤官见官 по стволу года (давление, конфликт, болезнь, потери), 财 для мужчины = жена/деньги, "
           "官杀 для женщины = муж/начальство, 印 = мать/учёба/документы, смену столпа удачи (±1 год — перелом рамки жизни). "
           "Выбери ОДИН вариант, который лучше всего согласуется с картой. Отвечай строго JSON: {\"id\": \"буква\", …} без пояснений.")
RULES_B = ("Ты опытный мастер Ба Цзы (四柱八字). По данным рождения определи карту и ответь на вопрос, выбрав ОДИН вариант. "
           "Отвечай строго JSON: {\"id\": \"буква\", …} без пояснений.")


def load_data():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "data.json")
    if not os.path.exists(path):
        with urllib.request.urlopen(urllib.request.Request(DATA_URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
            open(path, "wb").write(r.read())
    d = json.load(open(path, encoding="utf-8"))
    return d if isinstance(d, list) else d.get("questions") or d.get("data")


def chart(bi, as_of=None):
    tz = TZ.get((bi.get("country") or "").lower().strip(), 8)
    args = [PY, os.path.join(DIR, "bazi.py"), f"{bi['year']:04d}-{bi['month']:02d}-{bi['day']:02d}", f"{bi['hour']:02d}:{bi.get('minute') or 0:02d}",
            "М" if bi["gender"] == "男" else "Ж", f"UTC{tz:+d}", "--json"] + (["--as-of", f"{as_of}-07-01"] if as_of else [])
    p = subprocess.run(args, capture_output=True, text=True, cwd=DIR)
    return json.loads(p.stdout)


def compact(c, birth_year):
    """Урезанная карта для промпта: только то, чем пользуется чтение."""
    pil = {k: {"name": v["name"], "ten_god": v.get("ten_god"), "hidden": [(h["name"], h.get("ten_god")) for h in v["branch"].get("hidden_stems", [])]}
           for k, v in c["pillars"].items() if v}
    luck = [{"age": f"{round(l['age_start'])}–{round(l['age_end'])}", "years": f"{birth_year + round(l['age_start'])}–{birth_year + round(l['age_end'])}", "pillar": l["name"], "ten_god": l["ten_god"]}
            for l in (c.get("luck_pillars") or {}).get("pillars", [])]
    return {"day_master": c["day_master"], "pillars": pil, "strength": c["strength"], "yongshen": c["yongshen"], "jishen": c["jishen"],
            "yongshen_borderline": c.get("yongshen_borderline"), "tiaohou": (c.get("tiaohou") or {}).get("primary"),
            "shensha": [s["name"] + s["branch"] for s in c.get("shensha", [])], "interactions": c.get("interactions"),
            "luck_pillars": luck, "luck_start_age": (c.get("luck_pillars") or {}).get("start_age"), "geju": {k: c["geju"].get(k) for k in ("structure", "status")} if c.get("geju") else None}


def year_block(c):
    cy = c.get("current_year") or {}
    return {"year": cy.get("year"), "pillar": cy.get("pillar"), "ten_god": cy.get("ten_god"), "luck_now": (c.get("dynamic_interactions") or {}).get("luck"),
            "dynamic": (c.get("dynamic_interactions") or {}).get("year")}


def prepare(batch):
    items = load_data()
    cache = {}
    prompts = {"A": [], "B": []}
    for q in items:
        bi = q["birth_info"]; cid = q["case_id"]
        if cid not in cache:
            cache[cid] = compact(chart(bi), bi['year'])
        years = sorted({int(y) for y in re.findall(r"(19\d\d|20\d\d)年", q["question"])} |
                       {int(y) for o in q["options"] for y in re.findall(r"(19\d\d|20\d\d)", o["text"])})
        dyn = {}
        for y in years[:6]:
            dyn[y] = year_block(chart(bi, y))
        base = {"id": q["id"], "category": q["category"], "birth": bi["raw"], "question": q["question"], "options": [f"{o['letter']}. {o['text']}" for o in q["options"]]}
        prompts["A"].append(dict(base, chart=cache[cid], years=dyn))
        prompts["B"].append(base)
    for cond in ("A", "B"):
        batches = [prompts[cond][i:i + batch] for i in range(0, len(prompts[cond]), batch)]
        json.dump({"rules": RULES_A if cond == "A" else RULES_B, "batches": batches}, open(os.path.join(OUT, f"prompts_{cond}.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print(f"{cond}: {len(prompts[cond])} вопросов, {len(batches)} пакетов → bench/out/prompts_{cond}.json")


def score():
    items = {q["id"]: q for q in load_data()}
    res = {}
    for cond in ("A", "B"):
        p = os.path.join(OUT, f"answers_{cond}.json")
        if not os.path.exists(p):
            print(f"{cond}: нет bench/out/answers_{cond}.json"); continue
        ans = json.load(open(p, encoding="utf-8"))
        ok = {}; n = {}
        for qid, letter in ans.items():
            q = items.get(qid)
            if not q: continue
            cat = q["category"]; n[cat] = n.get(cat, 0) + 1
            ok[cat] = ok.get(cat, 0) + (1 if str(letter).strip().upper()[:1] == q["answer"] else 0)
        tot_n, tot_ok = sum(n.values()), sum(ok.values())
        res[cond] = (tot_ok, tot_n)
        print(f"{cond}: {tot_ok}/{tot_n} = {100 * tot_ok / max(tot_n, 1):.1f}%  | " + ", ".join(f"{c} {ok[c]}/{n[c]}" for c in sorted(n)))
    if "A" in res and "B" in res:
        print(f"случайный уровень 25%; A−B = {100 * (res['A'][0] / res['A'][1] - res['B'][0] / res['B'][1]):+.1f} п.п.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "prepare":
        prepare(int(sys.argv[sys.argv.index("--batch") + 1]) if "--batch" in sys.argv else 8)
    elif cmd == "score":
        score()
