#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""Сверка школьных таблиц bazi.md (гайд) с bazi.py (код). Разовая, 2026-07-01."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bazi as B

S, BR = B.STEMS, B.BRANCHES
si = {s: i for i, s in enumerate(S)}
bi = {b: i for i, b in enumerate(BR)}
fails, oks = [], 0

def chk(name, got, exp):
    global oks
    if got == exp:
        oks += 1
    else:
        fails.append(f"{name}: код={got} гайд={exp}")

# ── 1.3 Скрытые стволы (гайд) ──
GUIDE_HIDDEN = {
    "子": "癸", "丑": "己辛癸", "寅": "甲丙戊", "卯": "乙", "辰": "戊癸乙",
    "巳": "丙庚戊", "午": "丁己", "未": "己丁乙", "申": "庚壬戊", "酉": "辛",
    "戌": "戊辛丁", "亥": "壬甲",
}
for b, stems in GUIDE_HIDDEN.items():
    code = "".join(S[h] for h in B.HIDDEN_STEMS[bi[b]] if h >= 0)
    chk(f"藏干 {b}", code, stems)

# ── 5.1 На Инь: 30 названий + стихии (гайд) ──
GUIDE_NAYIN = [
    ("海中金", "Металл"), ("炉中火", "Огонь"), ("大林木", "Дерево"), ("路旁土", "Земля"),
    ("剑锋金", "Металл"), ("山头火", "Огонь"), ("涧下水", "Вода"), ("城头土", "Земля"),
    ("白蜡金", "Металл"), ("杨柳木", "Дерево"), ("泉中水", "Вода"), ("屋上土", "Земля"),
    ("霹雳火", "Огонь"), ("松柏木", "Дерево"), ("长流水", "Вода"), ("沙中金", "Металл"),
    ("山下火", "Огонь"), ("平地木", "Дерево"), ("壁上土", "Земля"), ("金箔金", "Металл"),
    ("覆灯火", "Огонь"), ("天河水", "Вода"), ("大驿土", "Земля"), ("钗钏金", "Металл"),
    ("桑柘木", "Дерево"), ("大溪水", "Вода"), ("沙中土", "Земля"), ("天上火", "Огонь"),
    ("石榴木", "Дерево"), ("大海水", "Вода"),
]
for k, (nm, el) in enumerate(GUIDE_NAYIN):
    chk(f"纳音 #{k*2+1}-{k*2+2} имя", B.NAYIN[k], nm)
    chk(f"纳音 #{k*2+1}-{k*2+2} стихия", B.ELEMENTS_RU[B.NAYIN_ELEMENT[k]], el)

# ── 5.2 Шэнь Ша по стволу дня (гайд) ──
G_TIANYI = {"甲": "丑未", "戊": "丑未", "乙": "申子", "己": "申子", "丙": "酉亥",
            "丁": "酉亥", "庚": "丑未", "辛": "寅午", "壬": "卯巳", "癸": "卯巳"}
for s, branches in G_TIANYI.items():
    chk(f"天乙 {s}", "".join(sorted(BR[x] for x in B.TIANYI[si[s]])), "".join(sorted(branches)))
G_WENCHANG = dict(zip("甲乙丙丁戊己庚辛壬癸", "巳午申酉申酉亥子寅卯"))
G_YANGREN = dict(zip("甲乙丙丁戊己庚辛壬癸", "卯寅午巳午巳酉申子亥"))
G_LUSHEN = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅卯巳午巳午申酉亥子"))
for tbl, name, code in [(G_WENCHANG, "文昌", B.WENCHANG), (G_YANGREN, "羊刃", B.YANGREN), (G_LUSHEN, "禄神", B.LUSHEN)]:
    for s, b in tbl.items():
        chk(f"{name} {s}", BR[code[si[s]]], b)

# ── 5.2 Шэнь Ша по группе тройной гармонии (гайд) ──
# группа → (驿马, 桃花, 华盖); ключ = любая ветвь группы
G_GROUPS = {"申": ("寅", "酉", "辰"), "寅": ("申", "卯", "戌"), "巳": ("亥", "午", "丑"), "亥": ("巳", "子", "未")}
for anchor, (yima, taohua, huagai) in G_GROUPS.items():
    g = B.san_he_group(bi[anchor])
    chk(f"驿马 гр.{anchor}", BR[B.YIMA[g]], yima)
    chk(f"桃花 гр.{anchor}", BR[B.TAOHUA[g]], taohua)
    chk(f"华盖 гр.{anchor}", BR[B.HUAGAI[g]], huagai)

# ── 5.3 红鸾/天喜 (гайд: по ветви года) ──
G_HONGLUAN = dict(zip("子丑寅卯辰巳午未申酉戌亥", "卯寅丑子亥戌酉申未午巳辰"))
G_TIANXI = dict(zip("子丑寅卯辰巳午未申酉戌亥", "酉申未午巳辰卯寅丑子亥戌"))
for yb, hl in G_HONGLUAN.items():
    chk(f"红鸾 {yb}", BR[B.HONGLUAN[bi[yb]]], hl)
for yb, tx in G_TIANXI.items():
    chk(f"天喜 {yb}", BR[B.TIANXI_STAR[bi[yb]]], tx)

# ── 4.7 空亡 (гайд: 6 сюней) ──
G_KW = [("甲", "子", "戌亥"), ("甲", "戌", "申酉"), ("甲", "申", "午未"),
        ("甲", "午", "辰巳"), ("甲", "辰", "寅卯"), ("甲", "寅", "子丑")]
for s, b, empt in G_KW:
    kw = B.kong_wang(si[s], bi[b])
    chk(f"空亡 {s}{b}旬", "".join(sorted(BR[x] for x in kw)), "".join(sorted(empt)))

# ── 4.1-4.5 взаимодействия (гайд) ──
G_CLASH = [("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]
for a, b in G_CLASH:
    chk(f"冲 {a}{b}", B.CLASHES.get(bi[a]), bi[b])
G_HE = [("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未")]
code_he = {frozenset(p) for p in B.HE_PAIRS}
chk("六合 набор", code_he, {frozenset((bi[a], bi[b])) for a, b in G_HE})
G_HAI = [("子", "未"), ("丑", "午"), ("寅", "巳"), ("卯", "辰"), ("申", "亥"), ("酉", "戌")]
chk("六害 набор", {frozenset(p) for p in B.HAI_PAIRS}, {frozenset((bi[a], bi[b])) for a, b in G_HAI})
# 刑: гайдовые тройки 寅巳申 / 丑戌未 / 子卯 (без 自刑)
G_XING = {frozenset(x) for x in [("寅", "巳"), ("巳", "申"), ("申", "寅"), ("子", "卯"), ("丑", "戌"), ("戌", "未"), ("未", "丑")]}
chk("刑 набор", {frozenset(BR[a] + BR[b]) - {""} and frozenset((BR[a], BR[b])) for a, b in B.XING_PAIRS},
    G_XING)
# 三合 рамки и стихии
G_TRIADS = {"申子辰": "Вода", "亥卯未": "Дерево", "寅午戌": "Огонь", "巳酉丑": "Металл"}
for tri, el in G_TRIADS.items():
    g = B.san_he_group(bi[tri[0]])
    chk(f"三合 {tri} состав", B.TRIADS[g], {bi[c] for c in tri})
    chk(f"三合 {tri} стихия", B.ELEMENTS_RU[B.TRIAD_ELEMENT[g]], el)

# ── 2.1/2.2/2.4 формулы столпов (гайд, 1-индексные → код 0-индексный) ──
chk("год 1990", tuple(map(lambda x: x, B.year_pillar(1990))), (si["庚"], bi["午"]))
chk("Пять Тигров 庚-год мес.4", B.month_pillar(si["庚"], 4), (si["辛"], bi["巳"]))
chk("Пять Крыс 庚-день 13:04", B.hour_pillar(si["庚"], 13), (si["癸"], bi["未"]))

# ── 3.4 Двенадцать стадий: таблица гайда vs каноническая генерация ──
CHANGSHENG = {"甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申",
              "乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯"}
# колонки гайда: 甲 | 丙戊 | 庚 | 壬 | 乙 | 丁己 | 辛 | 癸
GUIDE_STAGES = [  # 12 строк × 8 колонок
    ("长生", "亥寅巳申午酉子卯"), ("沐浴", "子卯午酉巳申亥寅"), ("冠带", "丑辰未戌辰未戌丑"),
    ("临官", "寅巳申亥卯午酉子"), ("帝旺", "卯午酉子寅巳申亥"), ("衰", "辰未戌丑丑辰未戌"),
    ("病", "巳申亥寅子卯午酉"), ("死", "午酉子卯亥寅巳申"), ("墓", "未戌丑辰戌丑辰未"),
    ("绝", "申亥寅巳酉子卯午"), ("胎", "酉子卯午申亥寅巳"), ("养", "戌丑辰未未戌丑辰"),
]
COLS = ["甲", "丙", "庚", "壬", "乙", "丁", "辛", "癸"]  # 戊≡丙, 己≡丁
for row, (stage_name, cells) in enumerate(GUIDE_STAGES):
    for col, stem in enumerate(COLS):
        start = bi[CHANGSHENG[stem]]
        step = 1 if si[stem] % 2 == 0 else -1  # Ян вперёд, Инь назад
        expected = BR[(start + step * row) % 12]
        chk(f"12стадий {stage_name}/{stem}", cells[col], expected)

print(f"OK: {oks}")
if fails:
    print(f"РАСХОЖДЕНИЯ ({len(fails)}):")
    for f in fails:
        print("  ✗", f)
    sys.exit(1)
print("ВСЕ ТАБЛИЦЫ СХОДЯТСЯ")
