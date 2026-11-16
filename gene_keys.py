#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
gene_keys.py — Генные Ключи (Ричард Радд). Тонкий слой на hd.py: та же астрономия
и то же колесо И-Цзин (Радд — бывший аналитик Дизайна Человека), но своя «Голограмма»
(Hologenetic Profile) из 11 сфер и спектр Тень → Дар → Сиддхи.

ВЫВЕРКА:
  • Карта сфер «сфера → планета + сторона» взята с официального genekeys.com (docs).
  • Колесо/линии — общие с hd.py (выверены внешней таблицей). КРОСС-ПРОВЕРКА в --test:
    сфера Life's Work обязана дать те же ворота, что Солнце Личности в hd.py (слой 4).
  • Спектр 64 ключей: англ. ярлыки Тень/Дар/Сиддхи 1-64 СВЕРЕНЫ (1-42 ранее; 43-64 —
    по genekeys.com/gene-key-N, 2026-07-01, все 22 совпали дословно). Рус. — перевод.
    Какой ключ.линия у сферы — посчитано точно; слово-ярлык — интерпретация (перевод правится тривиально).
  • ПРОГРАММНЫЕ ПАРТНЁРЫ (2026-07-11): партнёр = ворота строго напротив в колесе (180°,
    «mirror opposites on the wheel» — офиц. формулировка genekeys.com/docs/programming-partners).
    Все 32 пары сверены обходом 64 офиц. страниц genekeys.com — совпали с геометрией 32/32
    (та же оппозиция = построчная инь↔ян инверсия гексаграмм). ВНИМАНИЕ: на самом сайте 2 битые
    текстовые ссылки (у ключей 6 и 8) — наивный скрейпер получил бы «6→2» и «8→8»;
    разрешено взаимными страницами (36→6, 14→8) и офиц. баннерами пар.
  • РУС. КАНОН СПЕКТРА: официальный перевод существует ТОЛЬКО в бумажном издании
    («Генные ключи», Биверсум 2013, ISBN 978-5-9904337-2-4); верифицируемого онлайн-источника
    НЕТ (проверено 2026-07-11: genekeys.com отдаёт ключи только на англ., genekeys.ru таблицы
    не публикует). Поэтому SPECTRUM_RU остаётся НАШИМ переводом — честно помечен.

Конвенция узлов hd.py здесь НЕ влияет: 11 ядровых сфер не используют узлы.
"""
import sys
from datetime import datetime, timezone, timedelta
import ephem_core as ec
import hd

# ── 11 сфер: (ключ_англ, имя_рус, тело, сторона, последовательность) ─────────
SPHERES = [
    ("Life's Work", "Жизненная работа (призвание)", "sun", "personality", "Активация"),
    ("Evolution", "Эволюция (вызов роста)", "earth", "personality", "Активация"),
    ("Radiance", "Сияние (здоровье/витальность)", "sun", "design", "Активация"),
    ("Purpose", "Предназначение (глубинная цель)", "earth", "design", "Активация"),
    ("Attraction", "Притяжение (отношения)", "moon", "design", "Венера"),
    ("IQ", "IQ — ум", "venus", "personality", "Венера"),
    ("EQ", "EQ — эмоции", "mars", "personality", "Венера"),
    ("SQ", "SQ — дух/интуиция", "venus", "design", "Венера"),
    ("Core", "Ядро (ядерная рана)", "mars", "design", "Венера"),
    ("Culture", "Культура (вклад в мир)", "jupiter", "design", "Жемчужина"),
    ("Pearl", "Жемчужина (процветание)", "jupiter", "personality", "Жемчужина"),
]
PRIME_GIFTS = {"Life's Work", "Evolution", "Radiance", "Purpose"}

# Спектр: ворота → (Shadow, Gift, Siddhi). Канонические англ. ярлыки.
SPECTRUM = {
    1: ("Entropy", "Freshness", "Beauty"), 2: ("Dislocation", "Orientation", "Unity"),
    3: ("Chaos", "Innovation", "Innocence"), 4: ("Intolerance", "Understanding", "Forgiveness"),
    5: ("Impatience", "Patience", "Timelessness"), 6: ("Conflict", "Diplomacy", "Peace"),
    7: ("Division", "Guidance", "Virtue"), 8: ("Mediocrity", "Style", "Exquisiteness"),
    9: ("Inertia", "Determination", "Invincibility"), 10: ("Self-Obsession", "Naturalness", "Being"),
    11: ("Obscurity", "Idealism", "Light"), 12: ("Vanity", "Discrimination", "Purity"),
    13: ("Discord", "Discernment", "Empathy"), 14: ("Compromise", "Competence", "Bounteousness"),
    15: ("Dullness", "Magnetism", "Florescence"), 16: ("Indifference", "Versatility", "Mastery"),
    17: ("Opinion", "Far-sightedness", "Omniscience"), 18: ("Judgement", "Integrity", "Perfection"),
    19: ("Co-dependence", "Sensitivity", "Sacrifice"), 20: ("Superficiality", "Self-assurance", "Presence"),
    21: ("Control", "Authority", "Valour"), 22: ("Dishonour", "Graciousness", "Grace"),
    23: ("Complexity", "Simplicity", "Quintessence"), 24: ("Addiction", "Invention", "Silence"),
    25: ("Constriction", "Acceptance", "Universal Love"), 26: ("Pride", "Artfulness", "Invisibility"),
    27: ("Selfishness", "Altruism", "Selflessness"), 28: ("Purposelessness", "Totality", "Immortality"),
    29: ("Half-heartedness", "Commitment", "Devotion"), 30: ("Desire", "Lightness", "Rapture"),
    31: ("Arrogance", "Leadership", "Humility"), 32: ("Failure", "Preservation", "Veneration"),
    33: ("Forgetting", "Mindfulness", "Revelation"), 34: ("Force", "Strength", "Majesty"),
    35: ("Hunger", "Adventure", "Boundlessness"), 36: ("Turbulence", "Humanity", "Compassion"),
    37: ("Weakness", "Equality", "Tenderness"), 38: ("Struggle", "Perseverance", "Honour"),
    39: ("Provocation", "Dynamism", "Liberation"), 40: ("Exhaustion", "Resolve", "Divine Will"),
    41: ("Fantasy", "Anticipation", "Emanation"), 42: ("Expectation", "Detachment", "Celebration"),
    43: ("Deafness", "Insight", "Epiphany"), 44: ("Interference", "Teamwork", "Synarchy"),
    45: ("Dominance", "Synergy", "Communion"), 46: ("Seriousness", "Delight", "Ecstasy"),
    47: ("Oppression", "Transmutation", "Transfiguration"), 48: ("Inadequacy", "Resourcefulness", "Wisdom"),
    49: ("Reaction", "Revolution", "Rebirth"), 50: ("Corruption", "Equilibrium", "Harmony"),
    51: ("Agitation", "Initiative", "Awakening"), 52: ("Stress", "Restraint", "Stillness"),
    53: ("Immaturity", "Expansion", "Superabundance"), 54: ("Greed", "Aspiration", "Ascension"),
    55: ("Victimisation", "Freedom", "Freedom"), 56: ("Distraction", "Enrichment", "Intoxication"),
    57: ("Unease", "Intuition", "Clarity"), 58: ("Dissatisfaction", "Vitality", "Bliss"),
    59: ("Dishonesty", "Intimacy", "Transparency"), 60: ("Limitation", "Realism", "Justice"),
    61: ("Psychosis", "Inspiration", "Sanctity"), 62: ("Intellect", "Precision", "Impeccability"),
    63: ("Doubt", "Inquiry", "Truth"), 64: ("Confusion", "Imagination", "Illumination"),
}
assert len(SPECTRUM) == 64 and set(SPECTRUM) == set(range(1, 65)), "спектр: 64 ключа 1-64"

# Русские ярлыки спектра (Тень → Дар → Сиддхи) — перевод канонических англ. имён.
# Англ. имена сверены для всех 1-64 (43-64 — genekeys.com, 2026-07-01). Рус. — перевод (может быть уточнён).
SPECTRUM_RU = {
    1: ("Энтропия", "Свежесть", "Красота"), 2: ("Смещение", "Ориентация", "Единство"),
    3: ("Хаос", "Новаторство", "Невинность"), 4: ("Нетерпимость", "Понимание", "Прощение"),
    5: ("Нетерпение", "Терпение", "Вневременность"), 6: ("Конфликт", "Дипломатия", "Мир"),
    7: ("Разделение", "Руководство", "Добродетель"), 8: ("Посредственность", "Стиль", "Изысканность"),
    9: ("Инертность", "Целеустремлённость", "Непобедимость"), 10: ("Зацикленность на себе", "Естественность", "Бытие"),
    11: ("Неясность", "Идеализм", "Свет"), 12: ("Тщеславие", "Разборчивость", "Чистота"),
    13: ("Разлад", "Различение", "Эмпатия"), 14: ("Компромисс", "Компетентность", "Щедрость"),
    15: ("Серость", "Магнетизм", "Расцвет"), 16: ("Безразличие", "Разносторонность", "Мастерство"),
    17: ("Мнение", "Дальновидность", "Всеведение"), 18: ("Осуждение", "Целостность", "Совершенство"),
    19: ("Созависимость", "Чувствительность", "Жертвенность"), 20: ("Поверхностность", "Самоуверенность", "Присутствие"),
    21: ("Контроль", "Власть", "Доблесть"), 22: ("Бесчестье", "Любезность", "Благодать"),
    23: ("Усложнение", "Простота", "Квинтэссенция"), 24: ("Зависимость", "Изобретательность", "Тишина"),
    25: ("Зажатость", "Принятие", "Вселенская любовь"), 26: ("Гордыня", "Искусность", "Невидимость"),
    27: ("Эгоизм", "Альтруизм", "Самоотверженность"), 28: ("Бесцельность", "Полнота", "Бессмертие"),
    29: ("Половинчатость", "Приверженность", "Преданность"), 30: ("Желание", "Лёгкость", "Восторг"),
    31: ("Высокомерие", "Лидерство", "Смирение"), 32: ("Провал", "Сохранение", "Почитание"),
    33: ("Забвение", "Осознанность", "Откровение"), 34: ("Напор", "Сила", "Величие"),
    35: ("Голод", "Приключение", "Безграничность"), 36: ("Турбулентность", "Человечность", "Сострадание"),
    37: ("Слабость", "Равенство", "Нежность"), 38: ("Борьба", "Упорство", "Честь"),
    39: ("Провокация", "Динамизм", "Освобождение"), 40: ("Истощение", "Решимость", "Божественная воля"),
    41: ("Фантазия", "Предвкушение", "Эманация"), 42: ("Ожидание", "Отрешённость", "Празднование"),
    43: ("Глухота", "Инсайт", "Озарение"), 44: ("Вмешательство", "Командность", "Синархия"),
    45: ("Доминирование", "Синергия", "Причастие"), 46: ("Серьёзность", "Восхищение", "Экстаз"),
    47: ("Угнетённость", "Трансмутация", "Преображение"), 48: ("Несостоятельность", "Находчивость", "Мудрость"),
    49: ("Реакция", "Революция", "Возрождение"), 50: ("Порча", "Равновесие", "Гармония"),
    51: ("Возбуждение", "Инициатива", "Пробуждение"), 52: ("Напряжение", "Сдержанность", "Покой"),
    53: ("Незрелость", "Расширение", "Сверхизобилие"), 54: ("Жадность", "Устремлённость", "Вознесение"),
    55: ("Виктимность", "Свобода", "Свобода"), 56: ("Отвлечение", "Обогащение", "Опьянение"),
    57: ("Тревога", "Интуиция", "Ясность"), 58: ("Неудовлетворённость", "Витальность", "Блаженство"),
    59: ("Нечестность", "Близость", "Прозрачность"), 60: ("Ограниченность", "Реализм", "Справедливость"),
    61: ("Психоз", "Вдохновение", "Святость"), 62: ("Интеллект", "Точность", "Безупречность"),
    63: ("Сомнение", "Исследование", "Истина"), 64: ("Смятение", "Воображение", "Просветление"),
}
assert set(SPECTRUM_RU) == set(SPECTRUM), "RU-спектр: те же 64 ключа"


def programming_partner(gate):
    """Программный партнёр = ворота строго напротив в колесе (оппозиция 180°).
    Правило и все 32 пары сверены с офиц. genekeys.com (2026-07-11, 32/32)."""
    i = hd.WHEEL.index(gate)
    return hd.WHEEL[(i + 32) % 64]


def build_profile(birth_dt_utc, meta=None):
    jd_p = ec.jd_ut(birth_dt_utc)
    jd_d = ec.design_jd(jd_p)
    lon = {"personality": ec.longitudes(jd_p), "design": ec.longitudes(jd_d)}
    spheres = []
    for key, ru, body, side, seq in SPHERES:
        d = lon[side][body]
        g, ln, wl = hd.gate_line(d["lon"])
        sh, gi, si = SPECTRUM[g]
        shr, gir, sir = SPECTRUM_RU[g]
        pg = programming_partner(g)
        psh, pgi, psi = SPECTRUM[pg]
        pshr, pgir, psir = SPECTRUM_RU[pg]
        spheres.append({
            "sphere": key, "sphere_ru": ru, "sequence": seq, "side": side, "body": body,
            "gate": g, "line": ln, "key_line": f"{g}.{ln}",
            "shadow": sh, "gift": gi, "siddhi": si,
            "shadow_ru": shr, "gift_ru": gir, "siddhi_ru": sir, "is_prime_gift": key in PRIME_GIFTS,
            "programming_partner": {
                "key": pg, "shadow": psh, "gift": pgi, "siddhi": psi,
                "shadow_ru": pshr, "gift_ru": pgir, "siddhi_ru": psir,
                "note": "парный ключ-оппозиция: та же ось, зеркальная тема"},
            "minutes_to_line_change": round(hd._minutes_to_boundary(wl, hd.LINE, d["speed"]), 1),
        })
    fragile = sorted(spheres, key=lambda s: s["minutes_to_line_change"])[:3]
    return {
        "system": "gene_keys", "input": meta or {},
        "prime_gifts": [s for s in spheres if s["is_prime_gift"]],
        "spheres": spheres,
        "sequences": {seq: [s["sphere"] for s in spheres if s["sequence"] == seq]
                      for seq in ("Активация", "Венера", "Жемчужина")},
        "fragile_spheres": [{"sphere": s["sphere_ru"], "key_line": s["key_line"],
                             "minutes": s["minutes_to_line_change"]} for s in fragile],
        "spectrum_provenance": "англ. ярлыки Тень/Дар/Сиддхи 1-64 сверены с genekeys.com (43-64 подтв. 2026-07-01, все совпали); "
                               "рус. — НАШ перевод: офиц. рус. канон существует только в бумажном изд. (Биверсум 2013), "
                               "онлайн не верифицируем (проверено 2026-07-11); номер.линия — расчёт, слово-ярлык — нет; "
                               "программные партнёры — оппозиция колеса, все 32 пары сверены с офиц. genekeys.com (2026-07-11)",
    }


def _test():
    ok = True
    print("gene_keys.py --test"); print("─" * 60)

    # 1) спектр полон
    p1 = len(SPECTRUM) == 64
    ok &= p1
    print(f"[{'PASS' if p1 else 'FAIL'}] спектр: 64 ключа")

    dt = datetime(1990, 3, 3, 12, 0, tzinfo=timezone.utc)
    prof = build_profile(dt, {"birth": "1990-03-03 12:00 UTC"})

    # 2) 11 сфер, 4 главных дара, все ворота 1-64
    p2 = (len(prof["spheres"]) == 11 and len(prof["prime_gifts"]) == 4
          and all(1 <= s["gate"] <= 64 and 1 <= s["line"] <= 6 for s in prof["spheres"]))
    ok &= p2
    print(f"[{'PASS' if p2 else 'FAIL'}] 11 сфер, 4 главных дара, ворота/линии в диапазоне")

    # 3) КРОСС-ПРОВЕРКА (слой 4): Life's Work == HD Солнце Личности
    hd_chart = hd.build_chart(dt)
    hd_sun = next(a for a in hd_chart["activations"]["personality"] if a["body"] == "sun")
    lw = next(s for s in prof["spheres"] if s["sphere"] == "Life's Work")
    p3 = (lw["gate"], lw["line"]) == (hd_sun["gate"], hd_sun["line"])
    ok &= p3
    print(f"[{'PASS' if p3 else 'FAIL'}] кросс-система: Life's Work {lw['key_line']} == "
          f"HD Солнце Личности {hd_sun['gate']}.{hd_sun['line']}")

    # 4) тождество Дизайна: Radiance(Диз.Солнце) = Life's Work(Личн.Солнце) − 88°
    jd_p = ec.jd_ut(dt); jd_d = ec.design_jd(jd_p)
    arc = (ec.longitudes(jd_p)["sun"]["lon"] - ec.longitudes(jd_d)["sun"]["lon"]) % 360
    p4 = abs(arc - 88.0) < 1e-3
    ok &= p4
    print(f"[{'PASS' if p4 else 'FAIL'}] Radiance = Life's Work − 88° (дуга {arc:.4f}°)")

    # 5) программные партнёры: геометрия колеса == офиц. таблица genekeys.com (32/32, 2026-07-11)
    OFFICIAL_PAIRS = {1: 2, 3: 50, 4: 49, 5: 35, 6: 36, 7: 13, 8: 14, 9: 16, 10: 15,
                      11: 12, 17: 18, 19: 33, 20: 34, 21: 48, 22: 47, 23: 43, 24: 44,
                      25: 46, 26: 45, 27: 28, 29: 30, 31: 41, 32: 42, 37: 40, 38: 39,
                      51: 57, 52: 58, 53: 54, 55: 59, 56: 60, 61: 62, 63: 64}
    full_pairs = {**OFFICIAL_PAIRS, **{v: k for k, v in OFFICIAL_PAIRS.items()}}
    pp_bad = [g for g in range(1, 65) if programming_partner(g) != full_pairs[g]]
    p5 = (not pp_bad
          and all(programming_partner(programming_partner(g)) == g for g in range(1, 65))
          and all("programming_partner" in s
                  and s["programming_partner"]["key"] == full_pairs[s["gate"]]
                  for s in prof["spheres"]))
    ok &= p5
    print(f"[{'PASS' if p5 else 'FAIL'}] программные партнёры: 64/64 = офиц. таблица genekeys.com, "
          f"симметрия, поле в сферах" + (f"  ОШИБКИ: {pp_bad}" if pp_bad else ""))

    print("  4 ГЛАВНЫХ ДАРА тест-рождения:")
    for s in prof["prime_gifts"]:
        print(f"    {s['sphere_ru']:32s} ключ {s['key_line']:5s}  "
              f"{s['shadow']} → {s['gift']} → {s['siddhi']}")

    print("─" * 60); print(f"ИТОГ: {'ЗЕЛЁНО ✓' if ok else 'КРАСНОЕ ✗'}")
    return ok


def _cli_tz(args, usage):
    """Оффсет UTC — ОБЯЗАТЕЛЬНЫЙ аргумент: пропавший/незамещённый $OFFSET раньше
    молча давал карту в UTC+0 при exit 0. Мусор/плейсхолдер → stderr + exit 2.
    Формы: «+3», «-5», «+-5», «8.5», «UTC+4»; дробные (Сеул +8.5) законны."""
    cands = [a for a in args if not a.startswith("--")]
    if len(cands) != 1:
        what = ("оффсет UTC не передан" if not cands
                else f"ожидал один оффсет UTC, получил: {' '.join(cands)}")
        sys.stderr.write(f"{usage}\nОШИБКА: {what}\n")
        sys.exit(2)
    try:
        return float(cands[0].upper().replace("UTC", "", 1).replace("+", ""))
    except ValueError:
        sys.stderr.write(f"{usage}\nОШИБКА: не разобрал оффсет UTC из «{cands[0]}» — "
                         "незамещённый плейсхолдер?\n")
        sys.exit(2)


def _cli():
    _USAGE = ("gene_keys.py YYYY-MM-DD HH:MM ОФФСЕТ [--json] | gene_keys.py --test   "
              "(оффсет UTC обязателен: +3, -5, 8.5, UTC+4)")
    if "--test" in sys.argv:
        sys.exit(0 if _test() else 1)
    elif len(sys.argv) >= 4:
        import json
        tz = _cli_tz(sys.argv[3:], _USAGE)
        d = datetime.fromisoformat(f"{sys.argv[1]} {sys.argv[2]}")
        dt_utc = d.replace(tzinfo=timezone(timedelta(hours=tz))).astimezone(timezone.utc)
        prof = build_profile(dt_utc, {"birth_local": f"{sys.argv[1]} {sys.argv[2]} UTC{tz:+g}"})
        if "--json" in sys.argv:
            print(json.dumps(prof, ensure_ascii=False, indent=2))
        else:
            print("ГОЛОГРАММА (Hologenetic Profile)\n")
            for seq in ("Активация", "Венера", "Жемчужина"):
                print(f"  ── Последовательность: {seq} ──")
                for s in prof["spheres"]:
                    if s["sequence"] == seq:
                        star = " ★" if s["is_prime_gift"] else "  "
                        print(f"   {star}{s['sphere_ru']:32s} {s['key_line']:5s}  "
                              f"{s['shadow']} → {s['gift']} → {s['siddhi']}")
                print()
    else:
        sys.stderr.write(_USAGE + "\n")
        sys.exit(2)


if __name__ == "__main__":
    import cli_errors
    cli_errors.run(_cli)
