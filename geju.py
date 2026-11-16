#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""geju.py — структура карты (格局) по 月令 и школа 格局派 как ВТОРОЙ взгляд на 用神 (issue #29).

Источник правил — geju.md этого репозитория (рамка 子平真诠 в пересказе; провенанс — в шапке файла):
структура по 本气/中气/余气 месячной ветви с учётом прозрачности в стволах; «благоприятное / неблагоприятное»
для восьми 正格 и 建禄/羊刃. 从格 / 专旺格 / 化气格 здесь НЕ определяются (нужна оценка «крайне слаб / абсолютно
доминирует / получает сезон») — выдаётся только пометка-кандидат. Ничего сверх geju.md не добавлено.

Выход — блок `geju` в JSON bazi.py: structure, basis, use (顺/逆), favourable / unfavourable (十神 и стихии),
present (что из них в карте), status (成格 / 破格 / 不成不破 / структура не формируется), comparison —
согласие со школой силы (旺衰): agree / partial / conflict. Школу силы не заменяет: это второй голос.
"""
from bazi import (STEMS, BRANCHES, HIDDEN_STEMS, STEM_ELEMENT, PRODUCES, CONTROLS, ELEMENTS_RU, TEN_GODS,
                  LUSHEN, YANGREN, ten_god)

GROUP = {"财": {4, 5}, "正财": {5}, "偏财": {4}, "官杀": {6, 7}, "官": {7}, "正官": {7}, "七杀": {6},
         "印": {8, 9}, "正印": {9}, "偏印": {8}, "食伤": {2, 3}, "食神": {2}, "伤官": {3}, "比劫": {0, 1}}

# из geju.md: структура → (использование, благоприятное, неблагоприятное, примечание)
RULES = {
    "正官格": ("顺用", ["财", "印"], ["伤官", "七杀"], "财 и 印 не должны конфликтовать; 冲/刑 месячной ветви ломает структуру"),
    "七杀格": ("逆用", ["食神", "印"], ["财"], "食神制杀 — лучший вариант; при 食神 появление 偏印 = 枭神夺食 (破格)"),
    "正财格": ("顺用", ["官", "食神"], ["比劫"], None),
    "偏财格": ("顺用", ["食伤", "官杀"], ["比劫"], None),
    "正印格": ("顺用", ["官杀"], ["财"], "при сильном ХД благоприятен и 食神"),
    "偏印格": ("逆用", ["财", "伤官"], ["食神"], "«Сова» — только когда 食神 в карте полезен; без 食神 работает как Печать"),
    "食神格": ("顺用", ["财"], ["偏印"], "нужен корень ХД; избыток 食神 неблагоприятен"),
    "伤官格": ("逆用", ["印", "财"], ["正官"], "伤官见官 — классическое бедствие"),
    "建禄格": ("—", ["财", "官杀", "食伤"], ["印"], "самостоятельной структуры нет — 用神 ищут среди других столпов: 官 → 杀 → 财 → 食伤; избыток 比劫 неблагоприятен"),
    "羊刃格": ("逆用", ["七杀", "食伤", "财"], ["印"], "杀制刃 — лучший контроль; 冲 к Клинку опасен"),
}


def god_element(dm_si, god_idx):
    """Стихия Десятого Божества относительно ХД."""
    dm_el = STEM_ELEMENT[dm_si]
    if god_idx in (0, 1): return dm_el
    if god_idx in (2, 3): return PRODUCES[dm_el]
    if god_idx in (4, 5): return CONTROLS[dm_el]
    if god_idx in (6, 7): return next(e for e in range(5) if CONTROLS[e] == dm_el)
    return next(e for e in range(5) if PRODUCES[e] == dm_el)


def analyze(dm_si, pillars, yongshen_elements, jishen_elements, strength=None):
    """pillars = [(hs,hb),(ds,db),(ms,mb),(ys,yb)] — как в bazi.py (час может быть (None, None))."""
    (hs, hb), (ds, db), (ms, mb), (ys, yb) = pillars
    transparent = [s for s in (ys, ms, hs) if s is not None]
    hidden = [s for s in HIDDEN_STEMS[mb] if s >= 0]
    ben = hidden[0]
    chosen, god, how, structure, note = ben, ten_god(dm_si, ben), "本气", None, None
    if god in (0, 1):                                   # шаг 4 алгоритма geju.md: 月令 = 禄/刃 ХД → 建禄/羊刃格
        if LUSHEN.get(dm_si) == mb:
            structure = "建禄格"
        elif dm_si % 2 == 0 and YANGREN.get(dm_si) == mb:
            structure = "羊刃格"
        else:
            others = [s for s in hidden[1:] if s in transparent and ten_god(dm_si, s) not in (0, 1)]
            if others:
                chosen, god = others[0], ten_god(dm_si, others[0]); how = "比劫 в 本气 — взят другой прозрачный ствол 月令"
                structure = TEN_GODS[god] + "格"
            else:
                structure = "月劫格 (не формируется)"
                note = "比劫 в 月令 без прозрачного другого ствола — 正格 нет; 用神 по школе силы (geju.md §1, правило деления)"
        borrowed = [STEMS[s] + " (" + TEN_GODS[ten_god(dm_si, s)] + ")" for s in hidden[1:] if s in transparent]
        if structure in ("建禄格", "羊刃格") and borrowed:
            note = "прозрачные 中气/余气 月令 — кандидаты на 用 («用神多借»): " + ", ".join(borrowed)
    else:                                               # шаги 1–3: 本气 透干 → 本气; иначе прозрачные 中气/余气 (не 比劫); иначе 本气
        if ben in transparent:
            how = "本气 прозрачен в стволах"
        else:
            cand = [s for s in hidden[1:] if s in transparent and ten_god(dm_si, s) not in (0, 1)]
            if cand:
                chosen, god = cand[0], ten_god(dm_si, cand[0]); how = ["", "中气", "余气"][hidden.index(cand[0])] + " прозрачен (本气 нет)"
            else:
                how = "本气 (ничего не прозрачно)"
        structure = TEN_GODS[god] + "格"
    rule = RULES.get(structure)
    # что есть в карте: стволы (кроме ХД) + 本气 всех ветвей
    present_gods = set()
    for s in transparent:
        present_gods.add(ten_god(dm_si, s))
    for b in (hb, db, mb, yb):
        if b is not None:
            present_gods.add(ten_god(dm_si, HIDDEN_STEMS[b][0]))
    present_gods.discard(god) if structure not in ("建禄格", "羊刃格") else None
    out = {"structure": structure, "basis": {"stem": STEMS[chosen], "ten_god": TEN_GODS[god], "how": how, "month_branch": BRANCHES[mb]},
           "source": "geju.md (рамка 子平真诠, пересказ; [интерпретация, высокая уверенность] для правил)", "note": note}
    if not rule:
        out.update({"use": None, "favourable": [], "unfavourable": [], "present": {}, "status": "структура не формируется",
                    "comparison": {"verdict": "n/a", "text": "格局 не даёт самостоятельного 用神 — действует школа силы"}})
        return out
    use, fav, unfav, rnote = rule
    def expand(tokens):
        gods = set().union(*(GROUP[t] for t in tokens))
        return {"ten_gods": sorted(TEN_GODS[g] for g in gods), "elements": sorted({ELEMENTS_RU[god_element(dm_si, g)] for g in gods}),
                "element_idx": sorted({god_element(dm_si, g) for g in gods})}
    F, U = expand(fav), expand(unfav)
    fav_present = sorted(TEN_GODS[g] for g in set().union(*(GROUP[t] for t in fav)) & present_gods)
    unfav_present = sorted(TEN_GODS[g] for g in set().union(*(GROUP[t] for t in unfav)) & present_gods)
    if fav_present and not unfav_present: status = "成格 (поддержка есть, разрушителей нет)"
    elif unfav_present and not fav_present: status = "破格 (есть разрушитель, поддержки нет) — проверь 救应 вручную"
    elif fav_present and unfav_present: status = "成破相争 (есть и поддержка, и разрушитель) — решает расположение и 救应, вручную"
    else: status = "不成不破 (ни поддержки, ни разрушителей в карте)"
    # согласие со школой силы: стихии 相神 (благоприятное) против 用神/忌神 旺衰
    fav_el, ys_el, js_el = set(F["element_idx"]), set(yongshen_elements), set(jishen_elements)
    if fav_el & js_el and not (fav_el & ys_el): verdict, text = "conflict", "стихии, полезные по 格局, у школы силы — 忌神"
    elif fav_el & js_el: verdict, text = "partial", "часть стихий 格局 совпадает с 用神 силы, часть — с её 忌神"
    elif fav_el & ys_el: verdict, text = "agree", "благоприятные по 格局 стихии входят в 用神 школы силы"
    else: verdict, text = "partial", "格局 указывает на стихии, которых школа силы не выделяет ни как 用神, ни как 忌神"
    out.update({"use": use, "favourable": F, "unfavourable": U, "present": {"favourable": fav_present, "unfavourable": unfav_present},
                "status": status, "rule_note": rnote,
                "comparison": {"verdict": verdict, "text": text, "yongshen_strength_school": sorted(ELEMENTS_RU[e] for e in ys_el)},
                "special_candidates": _special(dm_si, strength)})
    return out


def _special(dm_si, strength):
    """Пометки-кандидаты на 从格/专旺格 по силе ХД (сами структуры не определяются)."""
    if not strength:
        return []
    out = []
    share = strength.get("support_share")
    if strength.get("label") == "СЛАБЫЙ" and share is not None and share < 0.2:
        out.append("ХД крайне слаб (поддержка < 20%) — возможен 从格: проверить корень и 合 вручную (geju.md §3)")
    if strength.get("label") == "СИЛЬНЫЙ" and share is not None and share > 0.75:
        out.append("ХД доминирует (поддержка > 75%) — возможен 专旺格: проверить чистоту стихии (geju.md §4)")
    return out


def _test():
    ok = True
    def chk(c, m):
        nonlocal ok; ok &= bool(c); print(f"[{'PASS' if c else 'FAIL'}] {m}")
    # 庚-день, месяц 巳 (本气 丙 = 七杀), 丙 прозрачен в стволе года → 七杀格; 食神 (壬) в стволе часа → поддержка
    r = analyze(6, [(8, 7), (6, 4), (7, 5), (2, 6)], [4, 3], [2, 1])   # час 壬未, день 庚辰, месяц 辛巳, год 丙午
    chk(r["structure"] == "七杀格" and r["basis"]["stem"] == "丙" and "食神" in r["present"]["favourable"], f"七杀格 через прозрачный 丙: {r['structure']}, basis {r['basis']}, present {r['present']}, status {r['status']}")
    chk("Вода" in r["favourable"]["elements"] and "Земля" in r["favourable"]["elements"] and r["comparison"]["verdict"] in ("agree", "partial", "conflict"),
        f"相神 七杀格: {r['favourable']['elements']} (ожидались Вода=食神, Земля=印); сравнение со школой силы: {r['comparison']['verdict']}")
    # 甲-день, месяц 寅 (禄 甲) → 建禄格
    r = analyze(0, [(2, 0), (0, 0), (4, 2), (6, 8)], [3, 4], [0, 1])
    chk(r["structure"] == "建禄格" and "偏印" in r["unfavourable"]["ten_gods"] and "丙" in (r["note"] or ""), f"甲 в 寅 (丙 прозрачен) → {r['structure']}; неблагоприятное {r['unfavourable']['ten_gods']}; note: {r['note']}")
    # 甲-день, месяц 亥 (本气 壬 偏印 не прозрачен, 中气 甲 = 比肩 — не годится) → по умолчанию 本气 → 偏印格
    r = analyze(0, [(2, 0), (0, 0), (3, 11), (6, 8)], [3, 4], [0, 1])
    chk(r["structure"] == "偏印格" and "ничего не прозрачно" in r["basis"]["how"], f"甲 в 亥 → {r['structure']} ({r['basis']['how']})")
    # 庚-день, месяц 酉 (羊刃 庚) → 羊刃格
    r = analyze(6, [(0, 0), (6, 4), (1, 9), (4, 2)], [0, 4], [3, 2])
    chk(r["structure"] == "羊刃格", f"庚 в 酉 → {r['structure']}")
    # 乙-день, месяц 卯 (比肩 в 本气, не 禄 — 禄 乙 = 卯? LUSHEN[1]=3 卯 → 建禄)
    r = analyze(1, [(None, None), (1, 3), (5, 3), (3, 1)], [0, 4], [3, 2])
    chk(r["structure"] == "建禄格", f"乙 в 卯 без часа → {r['structure']}")
    print("geju --test:", "ЗЕЛЁНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(_test())
