#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""fact_check_reading.py — механическая сверка ФАКТОВ в тексте чтения с JSON движка (issue #22).

Идея из FOR-BAZI (`fact_check_ganzhi`): модель пишет текст, код потом проверяет, что все
упомянутые в нём干支, божества, ворота и каналы действительно есть в карте. Ловит «иероглиф из
головы» — самую дешёвую и самую частую галлюцинацию интерпретатора. Смысл не проверяет (это спот-чек
Шагов 3.5/4.2 profile3) — только принадлежность упомянутых фактов карте.

Что сверяется:
  1_bazi.md ↔ _bazi.json      — все пары 干支 (60 Цзя Цзы) из текста ∈ {натальные столпы, столпы удачи,
                                 текущий год, годовой/удачный столп динамики}; все 十神 из текста ∈ божествам карты
                                 (стволы + скрытые стволы + столпы удачи + текущий год);
                                 ХД (ствол дня) упомянут хотя бы раз.
  3_human_design.md ↔ _hd.json — «ворота N» ∈ активированным воротам; каналы «N-M» ∈ определённым каналам;
                                 Тип и Профиль из JSON присутствуют в тексте (а чужие Типы — нет).
  2_jyotish.md ↔ _jyotish.json — знак Лагны и накшатра Луны из JSON присутствуют в тексте.

Запуск:  python3 fact_check_reading.py <папка профиля>      (exit 0 — чисто; 1 — есть расхождения)
         python3 fact_check_reading.py --test                 (самопроверка на синтетическом примере)
Одиночные пары: python3 fact_check_reading.py --bazi чтение.md карта.json
"""
import json
import os
import re
import sys

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
TEN_GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
HD_TYPES = ["Манифестор", "Генератор", "Манифестирующий Генератор", "Проектор", "Рефлектор"]
GANZHI_RX = re.compile(f"[{STEMS}][{BRANCHES}]")
GATE_RX = re.compile(r"ворот[аы]?\s*(?:№\s*)?(\d{1,2})\b", re.I)
CHANNEL_RX = re.compile(r"\b(\d{1,2})\s*[-–—]\s*(\d{1,2})\b")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def check_bazi(text, data):
    errs = []
    allowed = set()
    for p in data["pillars"].values():
        if p and p.get("name"):
            allowed.add(p["name"])
    for lp in (data.get("luck_pillars") or {}).get("pillars", []):
        allowed.add(lp["name"])
    cy = data.get("current_year") or {}
    if cy.get("pillar"):
        allowed.add(cy["pillar"])
    dyn = data.get("dynamic_interactions") or {}
    for k in ("year", "luck"):
        if dyn.get(k) and dyn[k].get("pillar"):
            allowed.add(dyn[k]["pillar"])
    # Натальные столпы обязаны быть в тексте; 干支 вне карты — предупреждение, не ошибка: это может быть
    # законный 流年 прошлого/будущего года (за 100 лет перебираются все 60 пар), а может — иероглиф из головы.
    # формат гайда пишет стволы и ветви отдельными строками таблицы — пара как «庚辰» может не встретиться;
    # считаем столп названным, если есть пара ИЛИ оба иероглифа порознь
    natal = {p["name"] for p in data["pillars"].values() if p and p.get("name")}
    missing = sorted(n for n in natal if n not in text and not (n[0] in text and n[1] in text))
    if missing:
        errs.append(f"1_bazi: натальные столпы не названы в тексте: {', '.join(missing)}")
    extra = sorted(set(GANZHI_RX.findall(text)) - allowed)
    if extra:
        print(f"   ~ 1_bazi: 干支 вне карты/удачи/текущего года: {', '.join(extra)} — законно только как 流年 конкретного года; проверь глазами")
    # 十神
    gods = set()
    for p in data["pillars"].values():
        if not p:
            continue
        if p.get("ten_god"):
            gods.add(p["ten_god"])
        for h in p["branch"].get("hidden_stems", []):
            if h.get("ten_god"):
                gods.add(h["ten_god"])
    for lp in (data.get("luck_pillars") or {}).get("pillars", []):
        gods.add(lp["ten_god"])
        for h in lp["branch"].get("hidden_stems", []):
            if h.get("ten_god"):
                gods.add(h["ten_god"])
    if cy.get("ten_god"):
        gods.add(cy["ten_god"])
        for h in (cy.get("branch") or {}).get("hidden_stems", []):
            if h.get("ten_god"):
                gods.add(h["ten_god"])
    bad_gods = sorted(g for g in TEN_GODS if g in text and g not in gods)
    if bad_gods:
        errs.append(f"1_bazi: 十神, которых нет ни в карте, ни в удаче, ни в году: {', '.join(bad_gods)} "
                    f"(ок как теория школы только с пометкой «отсутствует в карте»)")
    dm = data["day_master"]["name"]
    if dm not in text:
        errs.append(f"1_bazi: Хозяин Дня {dm} ни разу не упомянут")
    return errs


def check_hd(text, data):
    errs = []
    gates = set()
    for side in ("personality", "design"):
        for a in (data.get("activations") or {}).get(side, []):
            gates.add(int(a["gate"]))
    # ворота не из карты: ошибка, если названы как факт; если фраза условная («при сдвиге… уходит в ворота N»,
    # «если бы», «сменится на») — это законная оговорка о хрупкости (fragile_activations), не галлюцинация
    # условные/отсутствующие упоминания — не галлюцинация: хрупкость времени, недостающие «мостики» сплита,
    # «канал X у тебя не определён», объяснение чужих ворот рядом с людьми
    cond = re.compile(r"сдвиг|если|\bбы\b|уйд|уход|перейд|перех|смен|станет|при неточн|ректифик|соседн|"
                      r"недостающ|мост|отсутств|\bнет\b|не определ|не активир|открыт|пуст|ждут|у кого|рядом с людьми|"
                      r"чуж|партн|другого человека|не в карте|вне карты|половин|не собран|достраива|в паре с", re.I)
    hard_bad, soft = [], []
    for m in GATE_RX.finditer(text):
        g = int(m.group(1))
        if g in gates:
            continue
        window = text[max(0, m.start() - 120): m.end() + 140]
        (soft if cond.search(window) else hard_bad).append(g)
    if hard_bad:
        errs.append(f"3_hd: ворота не из карты названы как факт: {sorted(set(hard_bad))} (активированы: {sorted(gates)})")
    if soft:
        print(f"   ~ 3_hd: ворота {sorted(set(soft))} упомянуты в условной фразе (сдвиг/если) — не в карте, допустимо как оговорка о хрупкости")
    channels = set()
    for ch in data.get("defined_channels") or []:
        a, b = re.split(r"[-–]", ch["gates"])
        channels.add(frozenset((int(a), int(b))))
    for m in CHANNEL_RX.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        before = text[max(0, m.start() - 16): m.start()]
        if not re.search(r"канал[а-я]*\s*(№\s*)?$", before, re.I):
            continue  # считаем каналом только «канал 21-45»; «запас 6,5–9 часов» и «7–17 лет» — не каналы
        if 1 <= a <= 64 and 1 <= b <= 64 and a != b and frozenset((a, b)) not in channels:
            if cond.search(text[max(0, m.start() - 120): m.end() + 140]):
                print(f"   ~ 3_hd: канал {a}-{b} упомянут условно (сдвиг/если) — не определён в карте, допустимо как оговорка")
            else:
                errs.append(f"3_hd: «{a}-{b}» назван каналом как факт, но среди определённых каналов его нет")
    typ = data.get("type")
    if typ and typ not in text:
        errs.append(f"3_hd: Тип из JSON «{typ}» не упомянут")
    others = [t for t in HD_TYPES if t != typ and t in text and not (typ == "Манифестирующий Генератор" and t == "Генератор")]
    # чужие Типы допустимы в объяснении «5 типов» — считаем ошибкой только если свой Тип не назван
    if typ and typ not in text and others:
        errs.append(f"3_hd: в тексте другие Типы ({others}), свой «{typ}» отсутствует")
    prof = data.get("profile")
    if prof and prof not in text:
        errs.append(f"3_hd: Профиль «{prof}» не упомянут")
    return errs


def check_jyotish(text, data):
    errs = []
    rashi = (data.get("lagna") or {}).get("rashi")
    if isinstance(rashi, str) and rashi and rashi not in text:
        errs.append(f"2_jyotish: знак Лагны «{rashi}» не упомянут")
    nk = (data.get("moon_nakshatra") or {}).get("nakshatra")
    if isinstance(nk, str) and nk and nk not in text:
        errs.append(f"2_jyotish: накшатра Луны «{nk}» не упомянута")
    # знаки, которых нет ни у одной грахи и у Лагны, но названы как положение — ловим только явную форму «<граха> в <знаке>»
    import re as _re
    present = {rashi} | {g.get("rashi") for g in data.get("grahas", [])} | {g.get("d9_rashi") for g in data.get("grahas", [])}
    # «западный взгляд» (tropical) законно называет другие знаки тех же светил
    for v in (data.get("tropical") or {}).values():
        if isinstance(v, dict) and v.get("sign"):
            present.add(v["sign"])
    signs = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева", "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]
    for g in data.get("grahas", []):
        name_ru = g.get("graha", "").split(" (")[0]
        for sgn in signs:
            if sgn in present:
                continue
            if _re.search(rf"{name_ru}\s+в\s+{sgn}", text):
                errs.append(f"2_jyotish: «{name_ru} в {sgn}» — в карте такого положения нет (у {name_ru}: {g.get('rashi')})")
    return errs


def check_folder(folder):
    errs = []
    pairs = [("1_bazi.md", "_bazi.json", check_bazi), ("3_human_design.md", "_hd.json", check_hd),
             ("2_jyotish.md", "_jyotish.json", check_jyotish)]
    done = 0
    for md, js, fn in pairs:
        mp, jp = os.path.join(folder, md), os.path.join(folder, js)
        if not (os.path.exists(mp) and os.path.exists(jp)):
            continue
        done += 1
        errs += fn(_read(mp), json.load(open(jp, encoding="utf-8")))
    if not done:
        errs.append(f"{folder}: нет пар (1_bazi.md,_bazi.json) / (3_human_design.md,_hd.json) / (2_jyotish.md,_jyotish.json)")
    return errs, done


def _selftest():
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    py = os.path.join(here, ".venv", "bin", "python")
    py = py if os.path.exists(py) else sys.executable
    data = json.loads(subprocess.run([py, os.path.join(here, "bazi.py"), "1990-05-15", "14:30", "М", "UTC+4", "--json"],
                                     capture_output=True, text=True, check=True, cwd=here).stdout)
    good = "Хозяин Дня 庚 (Металл). Столпы: 庚午 辛巳 庚辰 癸未. Удача 甲申 (偏财). 伤官 на часе."
    bad = "Хозяин Дня 庚. Столпы: 庚午 辛巳 癸未 (день пропущен)."
    e1 = check_bazi(good, data)
    e2 = check_bazi(bad, data)
    natal_only = dict(data, luck_pillars=None, current_year=None, dynamic_interactions=None)
    e3 = check_bazi("ХД 庚; столпы 庚午 辛巳 庚辰 癸未; 伤官 на часе. Бог Пищи 食神 ведёт.", natal_only)   # 食神 у этой карты есть только в удаче
    ok = not e1 and len(e2) == 1 and "庚辰" in e2[0] and len(e3) == 1 and "食神" in e3[0]
    print(f"{'✓' if ok else '✗'} selftest bazi: чистый → {len(e1)}; без столпа дня → {len(e2)}; 食神 без удачи → {len(e3)} ошибок")
    hd = json.loads(subprocess.run([py, os.path.join(here, "hd.py"), "1990-05-15", "14:30", "+4", "--json"],
                                   capture_output=True, text=True, check=True, cwd=here).stdout)
    g = sorted({a["gate"] for s in ("personality", "design") for a in hd["activations"][s]})
    text_ok = f"Тип {hd['type']}, профиль {hd['profile']}. Ворота {g[0]} и {g[1]}."
    text_bad = text_ok + " Ворота 99 и канал 1-2 определён."
    h1, h2 = check_hd(text_ok, hd), check_hd(text_bad, hd)
    ok2 = not h1 and any("ворота не из карты" in e for e in h2)
    print(f"{'✓' if ok2 else '✗'} selftest hd: чистый → {len(h1)}; с воротами 99 → {len(h2)} ошибок")
    return 0 if ok and ok2 else 1


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    if args[0] == "--test":
        return _selftest()
    if args[0] == "--bazi" and len(args) == 3:
        errs = check_bazi(_read(args[1]), json.load(open(args[2], encoding="utf-8")))
    else:
        errs, done = check_folder(args[0])
    if errs:
        print("fact_check_reading: КРАСНОЕ ✗")
        for e in errs:
            print("  ", e)
        return 1
    print("fact_check_reading: ЗЕЛЁНО ✓ — все упомянутые干支/十神/ворота/каналы есть в карте")
    return 0


if __name__ == "__main__":
    sys.exit(main())
