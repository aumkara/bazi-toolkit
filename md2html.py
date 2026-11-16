#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""Минимальный, но аккуратный Markdown→HTML для профилей (стдлиб, без зависимостей).
Покрывает ровно то, что есть в файлах: заголовки, **жирный**/*курсив*/`код`,
ссылки, маркир./нумер. списки, GFM-таблицы (|...|), ``` fenced ```, --- hr, > цитаты.
CJK (八字) и эмодзи (⚠️) идут как обычный текст — их рендерит шрифтовой стек в CSS."""
import sys, re, html

SYMBOL_MAP = {
    "✅": "✓",      # ✅ → ✓  (цветное эмодзи не рендерится в headless Chrome)
    "❌": "✗",      # ❌ → ✗
    "⟷": "↔",      # ⟷ → ↔
    "\U0001F525": "",        # 🔥 декор — убрать
    "\U0001F407": "",        # 🐇
    "\U0001F333": "",        # 🌳
}

def normalize_symbols(t):
    """Цветные эмодзи → моно-символы (headless Chrome не встраивает Apple Color Emoji в PDF)."""
    t = t.replace("️", "")          # VS16: ⚠️ → ⚠ (моно-символ, который рендерится)
    for a, b in SYMBOL_MAP.items():
        t = t.replace(a, b)
    return t


def inline(t):
    # защищаем `код` плейсхолдерами, чтобы внутри не сработала разметка
    spans = []
    def stash(m):
        spans.append(m.group(1)); return f"\x00{len(spans)-1}\x00"
    t = re.sub(r"`([^`]+)`", stash, t)
    t = html.escape(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\x00(\d+)\x00", lambda m: "<code>" + html.escape(spans[int(m.group(1))], quote=False) + "</code>", t)
    return t

def cells(line):
    line = line.strip()
    if line.startswith("|"): line = line[1:]
    if line.endswith("|"): line = line[:-1]
    return [c.strip() for c in line.split("|")]

def convert(md):
    lines = md.split("\n")
    out, i, n = [], 0, len(md.split("\n"))
    while i < len(lines):
        ln = lines[i]
        # fenced code; ```svg / ```html — пропускаем СОДЕРЖИМОЕ без экранирования
        # (только блоки, которые мы генерим сами через infographics.py; чужой текст не сюда)
        if ln.lstrip().startswith("```"):
            lang = ln.lstrip()[3:].strip().lower()
            i += 1; buf = []
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            if lang in ("svg", "html"):
                out.append('<figure class="ig">' + "\n".join(buf) + "</figure>")
            else:
                out.append("<pre><code>" + "\n".join(html.escape(x, quote=False) for x in buf) + "</code></pre>")
            continue
        # таблица: строка с | и следующая — разделитель |---|
        if "|" in ln and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i+1]) and "-" in lines[i+1]:
            header = cells(ln); i += 2; rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i])); i += 1
            cls = ' class="wide"' if len(header) >= 6 else ""
            t = [f"<table{cls}><thead><tr>"] + [f"<th>{inline(c)}</th>" for c in header] + ["</tr></thead><tbody>"]
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table>"); out.append("".join(t)); continue
        # заголовки
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1)); out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
        # hr
        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", ln):
            out.append("<hr>"); i += 1; continue
        # цитата
        if ln.lstrip().startswith(">"):
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                buf.append(inline(re.sub(r"^\s*>\s?", "", lines[i]))); i += 1
            out.append("<blockquote>" + "<br>".join(buf) + "</blockquote>"); continue
        # списки (маркир. и нумер., с простыми вложенными по отступу)
        if re.match(r"^\s*([-*+]|\d+\.)\s+", ln):
            tag = "ol" if re.match(r"^\s*\d+\.", ln) else "ul"
            buf = []
            while i < len(lines) and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
                item = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i])
                buf.append(f"<li>{inline(item)}</li>"); i += 1
            out.append(f"<{tag}>" + "".join(buf) + f"</{tag}>"); continue
        # пустая строка
        if not ln.strip():
            i += 1; continue
        # абзац (склеиваем до пустой строки/блочного маркера)
        buf = [ln]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^\s*(#{1,6}\s|```|>|([-*+]|\d+\.)\s)", lines[i]) and "|" not in lines[i]:
            buf.append(lines[i]); i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n".join(out)

CSS = """
@page { margin: 1.8cm 1.8cm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Helvetica Neue", Arial, "Hiragino Sans GB", "STHeiti", "Songti SC", sans-serif;
  font-size: 11pt; line-height: 1.5; color: #1a1a1a; max-width: 720px; margin: 0 auto; }
h1 { font-size: 21pt; margin: 0 0 .2em; font-weight: 700; }
h2 { font-size: 15pt; margin: 1.4em 0 .4em; font-weight: 700; }
h3 { font-size: 12.5pt; margin: 1.1em 0 .3em; font-weight: 700; }
h4 { font-size: 11pt; margin: 1em 0 .3em; font-weight: 700; }
p { margin: .55em 0; }
strong { font-weight: 700; }
hr { border: none; border-top: 1px solid #bbb; margin: 1.3em 0; }
ul, ol { margin: .5em 0; padding-left: 1.5em; }
li { margin: .28em 0; }
code { font-family: "SF Mono", Menlo, monospace; font-size: .9em; background: #f1f1f1;
  padding: 1px 4px; border-radius: 3px; }
pre { background: #f6f6f6; padding: .8em 1em; border-radius: 6px; overflow-x: auto;
  white-space: pre-wrap; word-break: break-word; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3px solid #ccc; margin: .8em 0; padding: .2em 0 .2em 1em; color: #444; }
table { border-collapse: collapse; width: 100%; margin: .9em 0; font-size: 10pt; }
th, td { border: 1px solid #c8c8c8; padding: 6px 9px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; font-weight: 700; }
table.wide { font-size: 8pt; table-layout: fixed; }            /* широкие таблицы (≥6 колонок, напр. 6-систем) — мельче и точно в лист */
table.wide th, table.wide td { padding: 4px 5px; overflow-wrap: anywhere; word-break: break-word; }
tr { break-inside: avoid; }
h1, h2, h3, h4 { break-after: avoid; }
figure.ig { margin: .9em 0 .3em; text-align: center; break-inside: avoid; }   /* инфографика (inline SVG) */
figure.ig svg { max-width: 100%; height: auto; }
"""

if __name__ == "__main__":
    src = normalize_symbols(open(sys.argv[1], encoding="utf-8").read())
    title = html.escape(sys.argv[2] if len(sys.argv) > 2 else "")
    body = convert(src)
    doc = (f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
           f"<title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>")
    sys.stdout.write(doc)
