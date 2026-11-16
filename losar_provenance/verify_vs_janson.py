#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""Verify phugpa.py against the tables printed in Janson's paper (tibet.tex).

Parses:
  - Table Tlosar (120 Phugpa Losar dates, 1927-2046) directly from the LaTeX source;
  - Table T4Losar (2000-2030, four traditions) for Phugpa + Tsurphu columns;
  - extra text anchors: extremes 4/2/1954, 5/3/1992, 5/2/2019, 7/3/2095; Losar 2000 = 6/2.
"""
import os
import re
import sys
from datetime import date

# phugpa.py лежит рядом; tibet.tex (LaTeX-исходник статьи Янсона, arXiv:1401.6285) в репозиторий не входит —
# скачать e-print с arXiv и положить рядом либо задать путь переменной TIBET_TEX.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from phugpa import PHUGPA, TSURPHU, PHUGPA_E1927

TEX = os.environ.get("TIBET_TEX", os.path.join(HERE, "tibet.tex"))
if not os.path.exists(TEX):
    sys.exit(f"нет {TEX}: скачайте LaTeX-исходник arXiv:1401.6285 (tibet.tex) или задайте TIBET_TEX=/путь/к/tibet.tex")
text = open(TEX, encoding='utf-8').read()
lines = text.splitlines()

# ---- Parse Table Tlosar (lines ~500-529): rows like
# "4/3 1927 & 28/2 1987 & Fire--Rabbit & 2/3 1957 & 27/2 2017 & Fire--Bird\\"
tlosar = {}
block = text.split(r'\caption{Tibetan New Year')[0]
block = block[block.rfind(r'\begin{table}'):]
for m in re.finditer(r'(\d{1,2})/(\d{1,2})\s+(\d{4})', block):
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    tlosar[y] = date(y, mo, d)
print(f"Parsed Tlosar entries: {len(tlosar)} (expect 120), years {min(tlosar)}-{max(tlosar)}")

fails = 0
for y, expected in sorted(tlosar.items()):
    got = PHUGPA.losar_date(y)
    got2 = PHUGPA_E1927.losar_date(y)
    if got != expected or got2 != expected:
        fails += 1
        print(f"  MISMATCH {y}: paper={expected} computed(E806)={got} computed(E1927)={got2}")
print(f"Tlosar check: {len(tlosar) - fails}/{len(tlosar)} match")

# ---- Parse T4Losar (2000-2030): rows like "2003 & \xx{3/3} &  2/2 &  2/2 &  \xx{4/3} \\"
t4 = {}
blk = text.split(r'\caption{%')[0]
blk = blk[blk.rfind(r'\begin{table}'):]
for line in blk.splitlines():
    mm = re.match(r'\s*(\d{4})\s*&(.*)\\\\', line)
    if not mm:
        continue
    y = int(mm.group(1))
    cells = mm.group(2).split('&')
    def parse_cell(c):
        c = c.replace(r'\xx{', '').replace('}', '').strip()
        dd, mo = c.split('/')
        return date(y, int(mo), int(dd))
    t4[y] = (parse_cell(cells[0]), parse_cell(cells[1]))  # Phugpa, Tsurphu
print(f"\nParsed T4Losar entries: {len(t4)} (expect 31), years {min(t4)}-{max(t4)}")

fails4 = 0
for y, (ph, ts) in sorted(t4.items()):
    gp, gt = PHUGPA.losar_date(y), TSURPHU.losar_date(y)
    if gp != ph or gt != ts:
        fails4 += 1
        print(f"  MISMATCH {y}: paper P={ph} T={ts}; computed P={gp} T={gt}")
print(f"T4Losar check: {len(t4) - fails4}/{len(t4)} rows match (both Phugpa and Tsurphu)")

# ---- Text anchors
anchors = {1954: date(1954, 2, 4), 1992: date(1992, 3, 5),
           2019: date(2019, 2, 5), 2095: date(2095, 3, 7), 2000: date(2000, 2, 6)}
for y, expected in sorted(anchors.items()):
    got = PHUGPA.losar_date(y)
    status = 'ok' if got == expected else f'MISMATCH got {got}'
    print(f"Text anchor {y}: paper={expected} -> {status}")

# ---- Consistency: Tlosar vs T4Losar overlap
overlap_bad = [y for y in t4 if y in tlosar and t4[y][0] != tlosar[y]]
print(f"Tlosar/T4Losar overlap consistent: {'YES' if not overlap_bad else overlap_bad}")

# ---- leap month 1 in 2000 (paper: year 2000 began with leap month 1)
print(f"2000 has leap month 1: {PHUGPA.is_leap_month(2000, 1)} (paper says True)")
