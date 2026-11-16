#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_vs_kinqimen.py — внешний оракул для qimen.py: доска 时家奇门 (拆补法) против kinqimen (MIT, на sxtwl).
Issue #17/#24.

Сверяется на батарее случайных моментов (UTC+8, часы вне 子): 局 (阴/阳遁 + номер + 元), 地盘, 天盘,
九星, 八门, 八神 по восьми дворцам. Имена духов 勾陈/朱雀 у kinqimen = 白虎/玄武 у нас (转盘-традиция) —
нормализуются.

История: первый прогон 2026-11-09 нашёл в qimen.py две ошибки — 元 считался по дням от 节气 вместо
符头 дня (54/80 неверных 局) и 值使门 сдвигался по кольцу вместо полёта по номерам дворцов.

Режим 置闰 (--method zhirun, issue #24): наш qimen.py --method zhirun против kinqimen.pan(2). ВАЖНО: «置閏»
kinqimen — эвристика (прочитано в его config.qimen_ju_name_zhirun: 元 по 符头, а номера 局 переключаются
на следующий термин, когда с начала текущего прошло ≥ 9 суток), а не 超神接气 по блокам 符头 — поэтому 局
совпадает не всегда (переключение у нас — на 上元-符头, у него — на 9-й день термина; 闰-блоков у него нет).
Расхождение 局 здесь — информация, не FAIL; FAIL — если при одинаковом 局 расходится доска или если 元 разные.

Запуск:  .venv/bin/python verify_vs_kinqimen.py [N=60] [--seed 20261109] [--require] [--method chaibu|zhirun]
Зависимость (вне .venv — kinqimen пинит ephem==4.1.3 и импортирует свой config абсолютно):
  pip install --target /tmp/xval_site --no-deps sxtwl kinqimen && PYTHONPATH=/tmp/xval_site:/tmp/xval_site/kinqimen …
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
    import sxtwl  # noqa: F401
    try:
        from kinqimen import kinqimen
    except ModuleNotFoundError as e:  # `import config` внутри пакета — добавим его папку в путь
        if e.name != "config":
            raise
        import importlib
        import kinqimen as _pkg
        sys.path.insert(0, os.path.dirname(_pkg.__file__))
        kinqimen = importlib.import_module("kinqimen.kinqimen")
except ImportError:
    if "--require" in sys.argv:
        print("verify_vs_kinqimen: kinqimen/sxtwl не установлены — оракул обязателен, exit 2")
        sys.exit(2)
    print("verify_vs_kinqimen: kinqimen/sxtwl не установлены — оракул пропущен")
    sys.exit(0)

TRI = {"坎": "坎", "艮": "艮", "震": "震", "巽": "巽", "离": "離", "坤": "坤", "兑": "兌", "乾": "乾"}
GATE = {"休门": "休", "生门": "生", "伤门": "傷", "杜门": "杜", "景门": "景", "死门": "死", "惊门": "驚", "开门": "開"}
STAR = {"天蓬": "蓬", "天任": "任", "天冲": "沖", "天辅": "輔", "天英": "英", "天芮": "芮", "天柱": "柱", "天心": "心", "天禽": "禽"}
# 阳遁 у kinqimen — 勾陈/朱雀, 阴遁 — 白虎/玄武 (转盘-традиция); у нас всегда 白虎/玄武 → принимаем оба имени
SPIRIT = {"值符": {"符"}, "腾蛇": {"蛇"}, "太阴": {"陰"}, "六合": {"合"}, "白虎": {"勾", "虎"}, "玄武": {"雀", "玄"},
          "九地": {"地"}, "九天": {"天"}, "勾陈": {"勾", "虎"}, "朱雀": {"雀", "玄"}}
NUM = "一二三四五六七八九"


METHOD = sys.argv[sys.argv.index("--method") + 1] if "--method" in sys.argv else "chaibu"


def ours(y, m, d, h, mi):
    p = subprocess.run([PY, os.path.join(DIR, "qimen.py"), f"{y}-{m:02d}-{d:02d}", f"{h:02d}:{mi:02d}", "UTC+8", "--json",
                        "--method", METHOD],
                       capture_output=True, text=True, cwd=DIR)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    return json.loads(p.stdout)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 60
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261109
    rnd = random.Random(seed)
    cats = {"局": 0, "地盘": 0, "天盘": 0, "九星": 0, "八门": 0, "八神": 0}
    ex = []
    zhong_quirk = 0
    heuristic_diff = 0
    for _ in range(n):
        y, m, d = rnd.randint(1960, 2030), rnd.randint(1, 12), rnd.randint(1, 28)
        h, mi = rnd.choice(range(1, 23, 2)), rnd.choice([10, 30, 50])
        o = ours(y, m, d, h, mi)
        r = kinqimen.Qimen(y, m, d, h, mi).pan(1 if METHOD == "chaibu" else 2)   # 1 = 拆补, 2 = «置閏» (эвристика)
        pal = {TRI[p["trigram"]]: p for p in o["palaces"].values() if p["trigram"] in TRI}
        bad = []
        ju_o = f"{'陽' if o['meta']['yang'] else '陰'}遁{NUM[o['meta']['ju'] - 1]}局{o['meta']['yuan']}"
        if ju_o != r["排局"]:
            if METHOD == "zhirun":
                if ju_o[-2:] != r["排局"][-2:]:
                    cats["局"] += 1; bad.append(f"元 {ju_o}≠{r['排局']}")
                else:
                    heuristic_diff += 1
                if bad and len(ex) < 8:
                    ex.append((f"{y}-{m:02d}-{d:02d} {h:02d}:{mi:02d}", bad))
                continue   # доску при разных 局 сравнивать бессмысленно
            cats["局"] += 1; bad.append(f"局 {ju_o}≠{r['排局']}")
        for key, field, mapping in (("地盘", "earth", None), ("天盘", "heaven", None), ("九星", "star", STAR),
                                    ("八门", "gate", GATE), ("八神", "spirit", None)):
            src = {"地盘": "地盤", "天盘": "天盤", "九星": "星", "八门": "門", "八神": "神"}[key]
            for t, p in pal.items():
                v = p[field].split("/")[0] if field == "star" else p[field]
                theirs = r[src].get(t)
                if field == "spirit":
                    if theirs in SPIRIT.get(v, {v}):
                        continue
                    cats[key] += 1; bad.append(f"{key} {t}: {v}≠{theirs}"); break
                v = mapping.get(v, v) if mapping else v
                if field == "star" and v == "芮" and theirs in ("芮", "禽"):
                    continue
                if v != theirs:
                    cats[key] += 1; bad.append(f"{key} {t}: {v}≠{theirs}"); break
        # Известное расхождение оракула: часовой ствол в 中宫 (寄坤) и 值符 уже дома — у нас 伏吟 (天盘 = 地盘,
        # звёзды дома), у kinqimen звёзды тоже дома, но стволы 天盤 повёрнуты — внутренне несогласованно; считаем отдельно.
        hour_stem = o["meta"]["hour"][0]
        stem_pal = next((p["trigram"] for p in o["palaces"].values() if p["earth"] == hour_stem), None)
        fuyin = all(p["heaven"] == p["earth"] for p in pal.values())
        if bad and all(b.startswith("天盘") for b in bad) and stem_pal == "中" and fuyin:
            cats["天盘"] -= 1; zhong_quirk += 1; bad = []
        if bad and len(ex) < 8:
            ex.append((f"{y}-{m:02d}-{d:02d} {h:02d}:{mi:02d}", bad))
    print(f"verify_vs_kinqimen: {n} досок ({'拆补' if METHOD == 'chaibu' else '置闰'}) против kinqimen — расхождения: "
          + ", ".join(f"{k}={v}" for k, v in cats.items())
          + (f"; 局 иной из-за эвристики «день 9» kinqimen (не ошибка, доска не сравнивалась): {heuristic_diff}" if heuristic_diff else "")
          + (f"; часовой ствол в 中宫 при 值符 дома — 天盤 kinqimen повёрнут при звёздах дома (особенность оракула): {zhong_quirk}" if zhong_quirk else ""))
    for when, bad in ex if sum(cats.values()) else []:
        print(f"  ✗ {when}: {'; '.join(bad)[:300]}")
    return 1 if sum(cats.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
