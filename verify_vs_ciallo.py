#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_vs_ciallo.py — внешний оракул для qimen.py --method zhirun (置闰法): движок Ciallo 术数 (cialloshushu.com,
JS, работает под node). Issue #26.

Ciallo реализует 置闰 как 15-дневные блоки от 上元-符头 с 闰 после 芒种/大雪 при «超神 过九日（首尾并数，即实差八日以上）»
и эпохой 1829 — независимо от нашего кода (их астрономия — Meeus низкой точности, ~0.01°). Сверяется: термин блока
(ju_term), 元, 阴/阳遁 + номер 局, 闰-блок; дополнительно — доска (地盘/天盘/九星/八门/八神 по дворцам) при одинаковом 局.
Лицензии у файлов нет, поэтому в репозиторий они не кладутся: скрипт скачивает yi-core.js и yi-shu.js в
~/.cache/bazi-oracles/ciallo/ при первом запуске (нужна сеть) и выполняет их node. Без node/сети — пропуск.

Запуск: .venv/bin/python verify_vs_ciallo.py [N=60] [--seed 20261109] [--require]
"""
import json
import os
import random
import shutil
import subprocess
import sys
import urllib.request

DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(DIR, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "bazi-oracles", "ciallo")
FILES = {"yi-core.js": "https://cialloshushu.com/assets/js/yi-core.js", "yi-shu.js": "https://cialloshushu.com/assets/js/yi-shu.js"}
RUNNER = r"""
const C = require('./yi-core.js'); const S = require('./yi-shu.js');
const out = [];
for (const a of process.argv.slice(2)) {
  const [d, t] = a.split(' '); const [y, m, dd] = d.split('-').map(Number); const [h, mi] = t.split(':').map(Number);
  const R = S.qimen({ date: new Date(Date.UTC(y, m - 1, dd, h - 8, mi)), method: 'zhirun' }, C);
  out.push({ when: a, jieqi: R.jieqi, yuan: R.yuan, dun: R.dun, run: R.note.includes('闰局'), palaces: R.palaces });
}
console.log(JSON.stringify(out));
"""
TRI_NUM = {"坎": 1, "坤": 2, "震": 3, "巽": 4, "乾": 6, "兑": 7, "艮": 8, "离": 9}
SPIRIT_ALIAS = {"勾陈": "白虎", "朱雀": "玄武", "螣蛇": "腾蛇"}


def skip(msg):
    if "--require" in sys.argv:
        print(f"verify_vs_ciallo: {msg} — оракул обязателен, exit 2"); sys.exit(2)
    print(f"verify_vs_ciallo: {msg} — оракул пропущен"); sys.exit(0)


def ensure_files():
    if not shutil.which("node"):
        skip("node не найден")
    os.makedirs(CACHE, exist_ok=True)
    for name, url in FILES.items():
        path = os.path.join(CACHE, name)
        if not os.path.exists(path):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    open(path, "wb").write(r.read())
            except Exception as e:  # noqa: BLE001
                skip(f"не скачать {url}: {type(e).__name__}")
    open(os.path.join(CACHE, "run.js"), "w", encoding="utf-8").write(RUNNER)


def ours(when):
    d, t = when.split()
    p = subprocess.run([PY, os.path.join(DIR, "qimen.py"), d, t, "UTC+8", "--json", "--method", "zhirun"], capture_output=True, text=True, cwd=DIR)
    return json.loads(p.stdout)


def main():
    ensure_files()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 60
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261109
    rnd = random.Random(seed)
    whens = [f"{rnd.randint(1950, 2040)}-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d} {rnd.choice(range(1, 23, 2)):02d}:{rnd.choice([10, 30, 50])}"
             for _ in range(n)] + ["2024-06-15 12:00", "2024-12-21 12:00", "2024-12-26 12:00"]
    theirs = json.loads(subprocess.run(["node", "run.js", *whens], capture_output=True, text=True, cwd=CACHE, check=True).stdout)
    NUM = "一二三四五六七八九"
    cats = {"термин блока": 0, "元": 0, "局": 0, "闰": 0, "доска": 0}
    ex = []
    for w, t in zip(whens, theirs):
        o = ours(w); m = o["meta"]; bad = []
        if m["ju_term"] != t["jieqi"]:
            cats["термин блока"] += 1; bad.append(f"термин {m['ju_term']}≠{t['jieqi']}")
        if m["yuan"] != t["yuan"]:
            cats["元"] += 1; bad.append(f"元 {m['yuan']}≠{t['yuan']}")
        ju_o = f"{'阳' if m['yang'] else '阴'}遁{m['ju']}局"
        if ju_o != t["dun"]:
            cats["局"] += 1; bad.append(f"局 {ju_o}≠{t['dun']}")
        if bool(m["chaojie"]["run_block"]) != bool(t["run"]):
            cats["闰"] += 1; bad.append(f"闰 {m['chaojie']['run_block']}≠{t['run']}")
        if not bad:
            pal = {p["trigram"]: p for p in o["palaces"].values()}
            for tp in t["palaces"]:
                g = tp["gua"].replace("兌", "兑").replace("離", "离")
                op = pal.get(g)
                if not op:
                    continue
                o_star = op["star"].split("/")[0]
                t_star = tp["star"].replace("天衝", "天冲").split("·")[0]     # «天芮·天禽» → 天芮
                t_heaven = (tp["tianGan"] or "")[:1]                           # при 天禽 Ciallo дописывает ствол 中宫 вторым знаком
                if not t_heaven and not tp["star"]:
                    continue                                                  # пустой дворец (伏吟 в 中宫 и т. п.) — нечего сравнивать
                if (op["earth"], op["heaven"], o_star, op["gate"], SPIRIT_ALIAS.get(op["spirit"], op["spirit"])) != \
                        (tp["diGan"], t_heaven, t_star, tp["door"], SPIRIT_ALIAS.get(tp["god"], tp["god"])):
                    cats["доска"] += 1; bad.append(f"доска {g}: {op['earth']}{op['heaven']}{o_star}{op['gate']}{op['spirit']} ≠ {tp['diGan']}{tp['tianGan']}{tp['star']}{tp['door']}{tp['god']}"); break
        if bad and len(ex) < 8:
            ex.append((w, bad))
    print(f"verify_vs_ciallo: {len(whens)} досок (置闰, порог {__import__('qimen').ZHIRUN_THRESHOLD}) против Ciallo — расхождения: "
          + ", ".join(f"{k}={v}" for k, v in cats.items()))
    for w, bad in ex if sum(cats.values()) else []:
        print(f"  ✗ {w}: {'; '.join(bad)[:300]}")
    return 1 if sum(cats.values()) else 0


if __name__ == "__main__":
    sys.path.insert(0, DIR)
    sys.exit(main())
