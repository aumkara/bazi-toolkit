#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""Phugpa (and Tsurphu) Tibetan calendar: New Year (Losar) dates.

Implementation strictly follows:
  Svante Janson, "Tibetan calendar mathematics", arXiv:1401.6285 (v2 of 0710.0520),
  LaTeX source tibet.tex (downloaded from arXiv e-print, 2014-01-24).

Key equations (labels = \label{} names in the paper):
  (MM)          MM = 12*(Y - Y0) + M - M0,  with M0 = 3
  (tm0)         true_month = (67*MM + beta*) / 65        [beta* = gbx, epoch constant]
  (ix)          ix = (2*MM + gbx) mod 65
  (leaprule-P)  Phugpa: leap month iff ix in {48, 49}
  (mcrule-P)/(c2)  n = floor((67*MM + gbx + 17)/65) - [leap]   [Phugpa rounding]
  Tsurphu (leaprule-T): leap iff ix in {0, 1}; n = floor((67*MM+gbx)/65) - [leap]
  (meandate)    mean_date(d,n) = n*m1 + d*m2 + m0
  (meansun)     mean_sun(d,n)  = n*s1 + d*s2 + s0
  (anomalymoon) anomaly_moon(d,n) = n*a1 + d*a2 + a0
  (moonequ)     moon_equ = moon_tab(28*anomaly_moon), moon_tab = 0,5,10,15,19,22,24,25
                symmetry: tab(14-i)=tab(i), tab(14+i)=-tab(i); linear interpolation
  (anosun)      anomaly_sun = mean_sun - 1/4
  (sunequ)      sun_equ = sun_tab(12*anomaly_sun), sun_tab = 0,6,10,11
                symmetry: tab(6-i)=tab(i), tab(6+i)=-tab(i); linear interpolation
  (truedate)    true_date = mean_date + moon_equ/60 - sun_equ/60
  (jd)          JD = floor(true_date)
  New Year (section "Tibetan New Year"): JD(Losar of year Y) =
                1 + JD(lunar day 30, regular month 12, year Y-1).

Epoch E806 (Phugpa):  Y0=806, gbx=61,
  m1 = 167025/5656, m2 = m1/30 = 11135/11312, m0 = 2015501 + 4783/5656
  s1 = 65/804, s2 = s1/30 = 13/4824, s0 = 743/804
  a1 = 253/3528, a2 = 1/28, a0 = 475/3528
Epoch E1927 (Phugpa, Henning): n differs by 13866; m0 = 2424972 + 5457/5656,
  s0 = 749/804, a0 = 1741/3528  (used as self-check)
Tsurphu epoch E1732: Y0=1732, gbx=59, m0 = 2353745 + 1795153/7635600,
  s0 = -5983/108540, a0 = 207/392, leap iff ix in {0,1}.

JD -> Gregorian: JD 2440588 = 1970-01-01 (paper: JD 2454102 = 2007-01-01, checked).
"""
from fractions import Fraction as F
from datetime import date, timedelta

JD_19700101 = 2440588

MOON_TAB_BASE = [0, 5, 10, 15, 19, 22, 24, 25]  # i = 0..7
SUN_TAB_BASE = [0, 6, 10, 11]                   # i = 0..3


def moon_tab(i_int):
    """moon_tab at integer argument, period 28."""
    i = i_int % 28
    if i <= 7:
        return MOON_TAB_BASE[i]
    if i <= 14:
        return MOON_TAB_BASE[14 - i]
    if i <= 21:
        return -MOON_TAB_BASE[i - 14]
    return -MOON_TAB_BASE[28 - i]


def sun_tab(i_int):
    """sun_tab at integer argument, period 12."""
    i = i_int % 12
    if i <= 3:
        return SUN_TAB_BASE[i]
    if i <= 6:
        return SUN_TAB_BASE[6 - i]
    if i <= 9:
        return -SUN_TAB_BASE[i - 6]
    return -SUN_TAB_BASE[12 - i]


def interp(tab_func, x):
    """Linear interpolation of tab_func (integer table) at rational x."""
    lo = x.numerator // x.denominator  # floor
    frac = x - lo
    a, b = tab_func(lo), tab_func(lo + 1)
    return a + (b - a) * frac


class Tradition:
    def __init__(self, name, Y0, gbx, m0, s0, a0, leap_ix, rounding):
        self.name = name
        self.Y0 = Y0
        self.gbx = gbx
        self.m1 = F(167025, 5656)
        self.m2 = self.m1 / 30            # = 11135/11312
        self.m0 = m0
        self.s1 = F(65, 804)
        self.s2 = self.s1 / 30            # = 13/4824
        self.s0 = s0
        self.a1 = F(253, 3528)
        self.a2 = F(1, 28)
        self.a0 = a0
        self.leap_ix = leap_ix            # set of ix values marking a leap month
        self.rounding = rounding          # 'phugpa' or 'tsurphu'

    def true_month_count(self, Y, M, leap=False):
        """Integer true-month count n for month M of Tibetan year Y.
        Eq. (MM), (c2) for Phugpa; Tsurphu rule per App. A.2."""
        MM = 12 * (Y - self.Y0) + M - 3   # M0 = 3
        if self.rounding == 'phugpa':
            n = (67 * MM + self.gbx + 17) // 65
        else:  # tsurphu: round true month (67*MM+gbx)/65 down
            n = (67 * MM + self.gbx) // 65
        if leap:
            n -= 1
        return n

    def is_leap_month(self, Y, M):
        MM = 12 * (Y - self.Y0) + M - 3
        ix = (2 * MM + self.gbx) % 65
        return ix in self.leap_ix

    def true_date(self, d, n):
        """End of lunar day d in true-month n, as exact rational 'local JD'."""
        mean_date = n * self.m1 + d * self.m2 + self.m0
        mean_sun = n * self.s1 + d * self.s2 + self.s0
        anomaly_moon = n * self.a1 + d * self.a2 + self.a0
        moon_equ = interp(moon_tab, (28 * anomaly_moon) % 28)
        anomaly_sun = (mean_sun - F(1, 4)) % 1
        sun_equ = interp(sun_tab, (12 * anomaly_sun) % 12)
        return mean_date + F(moon_equ, 60) - F(sun_equ, 60)

    def jd_of_lunar_day(self, Y, M, d, leap=False):
        n = self.true_month_count(Y, M, leap)
        td = self.true_date(d, n)
        return td.numerator // td.denominator  # floor -> JD

    def losar_jd(self, Y):
        """JD of first day of Tibetan year Y = 1 + JD(day 30, regular month 12, Y-1)."""
        return 1 + self.jd_of_lunar_day(Y - 1, 12, 30, leap=False)

    def losar_date(self, Y):
        return date(1970, 1, 1) + timedelta(days=self.losar_jd(Y) - JD_19700101)


PHUGPA = Tradition(
    'phugpa', Y0=806, gbx=61,
    m0=2015501 + F(4783, 5656),
    s0=F(743, 804),
    a0=F(475, 3528),
    leap_ix={48, 49}, rounding='phugpa',
)

# Self-check epoch E1927 (must give identical calendar):
PHUGPA_E1927 = Tradition(
    'phugpa-E1927', Y0=1927, gbx=55,
    m0=2424972 + F(5457, 5656),
    s0=F(749, 804),
    a0=F(1741, 3528),
    leap_ix={48, 49}, rounding='phugpa',
)

TSURPHU = Tradition(
    'tsurphu', Y0=1732, gbx=59,
    m0=2353745 + F(1795153, 7635600),
    s0=F(-5983, 108540),
    a0=F(207, 392),
    leap_ix={0, 1}, rounding='tsurphu',
)


if __name__ == '__main__':
    import sys
    y1, y2 = 1900, 2100
    if len(sys.argv) == 3:
        y1, y2 = int(sys.argv[1]), int(sys.argv[2])
    for y in range(y1, y2 + 1):
        p = PHUGPA.losar_date(y)
        p2 = PHUGPA_E1927.losar_date(y)
        t = TSURPHU.losar_date(y)
        flag = '' if p == p2 else '  EPOCH-MISMATCH!'
        print(f"{y}  phugpa={p}  tsurphu={t}{flag}")
