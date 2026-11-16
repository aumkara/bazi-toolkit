/* SPDX-License-Identifier: AGPL-3.0-or-later · Copyright (C) 2026 Tim */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const ORDER = ["hour", "day", "month", "year"];
  const HEAD = { hour: ["Час", "时"], day: ["День", "日"], month: ["Месяц", "月"], year: ["Год", "年"] };
  const POLARITY = { yang: "ян", yin: "инь" };
  const SEVERITY = { high: "‼", medium: "⚠", info: "ℹ" };
  const STORE = "bazi-report-sections-v1";   // хранится только выбор разделов, не данные рождения

  const state = { meta: null, result: null, selected: new Set(), charts: false };

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === "class") node.className = v; else node.setAttribute(k, v === true ? "" : v);
    }
    for (const c of [].concat(children == null ? [] : children)) node.append(c);
    return node;
  }

  const names = (items) => (items || []).map((x) => x.element).join(", ") || "—";
  const num = (x, digits = 1) => (typeof x === "number" ? String(Math.round(x * 10 ** digits) / 10 ** digits) : "—");

  // ── форма ──────────────────────────────────────────────────────────────────────────────────

  function placeMode() {
    return document.querySelector('input[name="place"]:checked').value;
  }

  function syncForm() {
    $("f-time").disabled = $("f-notime").checked;
    const city = placeMode() === "city";
    $("place-city").hidden = !city;
    $("place-utc").hidden = city;
  }

  function readForm() {
    const body = {
      date: $("f-date").value,
      time: $("f-notime").checked ? null : $("f-time").value || null,
      gender: document.querySelector('input[name="gender"]:checked').value,
      as_of: $("f-asof").value || null,
    };
    if (!body.date) return { error: "Укажите дату рождения." };
    if (!$("f-notime").checked && !body.time) return { error: "Укажите время или отметьте «время неизвестно»." };
    if (placeMode() === "city") {
      body.city = $("f-city").value.trim();
      if (!body.city) return { error: "Выберите город из списка или переключитесь на «пояс вручную»." };
    } else {
      const raw = $("f-utc").value.trim().replace(",", ".");
      body.utc_offset = Number(raw);
      if (raw === "" || Number.isNaN(body.utc_offset)) return { error: "Укажите смещение от UTC в часах, например 3 или 5.5." };
    }
    return { body };
  }

  function showError(text) {
    $("form-error").textContent = text || "";
    $("form-error").hidden = !text;
  }

  async function submit(event) {
    event.preventDefault();
    const { body, error } = readForm();
    if (error) return showError(error);
    showError("");
    const button = $("submit");
    button.disabled = true;
    button.textContent = "Считаю…";
    try {
      const resp = await fetch("/api/bazi", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (!resp.ok) return showError(data.error || `Ошибка ${resp.status}`);
      state.result = data;
      render();
    } catch (e) {
      showError("Сервер не отвечает. Проверьте, что web.py запущен.");
    } finally {
      button.disabled = false;
      button.textContent = "Рассчитать карту";
    }
  }

  // ── карта ──────────────────────────────────────────────────────────────────────────────────

  function pillarCard(key, p) {
    const card = el("div", { class: "pillar" + (key === "day" ? " is-day" : "") });
    card.append(el("div", { class: "p-head" }, [HEAD[key][0], el("span", { lang: "zh" }, HEAD[key][1])]));
    if (!p || !p.name) {
      card.append(el("div", { class: "p-empty" }, "время не указано — столп не рассчитан"));
      return card;
    }
    card.append(el("div", { class: "p-god" }, key === "day"
      ? "Хозяин Дня"
      : [p.ten_god_ru, el("small", { lang: "zh" }, p.ten_god)]));
    card.append(el("div", { class: `glyph el-${p.stem.element_index}`, lang: "zh" }, p.stem.name));
    card.append(el("div", { class: "p-cap" }, `${p.stem.element}, ${POLARITY[p.stem.polarity] || p.stem.polarity}`));
    card.append(el("div", { class: `glyph el-${p.branch.element_index}`, lang: "zh" }, p.branch.name));
    card.append(el("div", { class: "p-cap" }, `${p.branch.animal} · ${p.branch.element}`));
    const hidden = el("ul", { class: "p-hidden", "aria-label": "Скрытые стволы" });
    for (const h of p.branch.hidden_stems || []) {
      hidden.append(el("li", {}, [el("b", { class: `el-${h.element_index}`, lang: "zh" }, h.name), h.ten_god_ru || h.element]));
    }
    card.append(hidden);
    card.append(el("div", { class: "p-nayin" }, ["На Инь: ", el("span", { lang: "zh" }, p.nayin), ` (${p.nayin_element})`]));
    return card;
  }

  function fact(term, value) {
    return el("div", {}, [el("dt", {}, term), el("dd", {}, value)]);
  }

  function renderChart(chart) {
    const i = chart.input;
    const minutes = Math.round(Math.abs(i.utc_offset) * 60);
    const place = i.city ? i.city
      : `UTC${i.utc_offset >= 0 ? "+" : "−"}${Math.floor(minutes / 60)}${minutes % 60 ? ":" + String(minutes % 60).padStart(2, "0") : ""}`;
    const time = (i.city ? i.wall_time : i.time) || "время неизвестно";
    $("chart-sub").textContent = `${i.date}, ${time} · ${place} · ${i.gender}`;
    $("pillars").replaceChildren(...ORDER.map((k) => pillarCard(k, chart.pillars[k])));

    const dm = chart.day_master, st = chart.strength, g = chart.geju || {}, cy = chart.current_year || {};
    const luck = (chart.dynamic_interactions || {}).luck || {};
    const facts = [
      fact("Хозяин Дня", `${dm.name} — ${dm.element}, ${POLARITY[dm.polarity] || dm.polarity}`),
      fact("Сила", `${st.label} (балл ${num(st.score)}${st.borderline ? ", погранично" : ""})`),
      fact("用神 — полезные", names(chart.yongshen) + (chart.yongshen_borderline ? " (трактуемо)" : "")),
      fact("忌神 — неблагоприятные", names(chart.jishen)),
      fact("Структура 格局", g.structure ? `${g.structure} — ${g.status || "статус не определён"}` : "—"),
      fact("Сейчас", `год ${cy.pillar || "—"}` + (luck.pillar ? `, столп удачи ${luck.pillar}` : ", столпа удачи нет")),
    ];
    $("facts").replaceChildren(...facts);
  }

  function renderCaveats(list) {
    const items = list.map((c) => el("li", { class: `sev-${c.severity}` },
      [el("span", { "aria-hidden": "true" }, SEVERITY[c.severity] || "⚠"), el("span", {}, [el("b", {}, `${c.topic}: `), c.text])]));
    if (!items.length) items.push(el("li", { class: "none" }, [el("span", {}, "✓"), "Калькулятор не выдал оговорок для этой карты."]));
    $("caveats").replaceChildren(...items);
  }

  // ── отчёт ──────────────────────────────────────────────────────────────────────────────────

  function loadSelection() {
    const defaults = state.meta.sections.filter((s) => s.default).map((s) => s.id);
    try {
      const saved = JSON.parse(localStorage.getItem(STORE) || "null");
      if (saved && Array.isArray(saved.ids)) {
        const known = new Set(state.meta.sections.map((s) => s.id));
        state.selected = new Set(saved.ids.filter((id) => known.has(id)));
        state.charts = Boolean(saved.charts);
        return;
      }
    } catch (e) { /* хранилище недоступно — берём умолчания */ }
    state.selected = new Set(defaults);
  }

  function saveSelection() {
    try { localStorage.setItem(STORE, JSON.stringify({ ids: [...state.selected], charts: state.charts })); } catch (e) { /* не критично */ }
  }

  function renderSections() {
    const boxes = state.meta.sections.map((s) => {
      const input = el("input", { type: "checkbox", value: s.id, checked: s.locked || state.selected.has(s.id), disabled: s.locked });
      input.checked = s.locked || state.selected.has(s.id);
      input.addEventListener("change", () => {
        if (input.checked) state.selected.add(s.id); else state.selected.delete(s.id);
        saveSelection();
        renderReport();
      });
      return el("label", { class: "sec" + (s.locked ? " locked" : "") }, [input, el("strong", {}, s.title), el("small", {}, s.hint)]);
    });
    $("sections").replaceChildren(...boxes);
    $("opt-charts").checked = state.charts;
  }

  function chosenParts() {
    return state.result.parts.filter((p) => p.locked || state.selected.has(p.id));
  }

  // Та же сборка, что bazi_report.assemble: сервер отдал готовые разделы, страница их только склеивает.
  function buildMarkdown() {
    const out = [];
    for (const p of chosenParts()) {
      out.push(p.md);
      if (state.charts && p.charts_md) out.push(p.charts_md);
    }
    return out.join("\n\n").replace(/\s+$/, "") + "\n";
  }

  function renderReport() {
    if (!state.result) return;
    const parts = chosenParts();
    // HTML разделов собран сервером (md2html экранирует текст); чужого ввода в нём нет.
    $("doc").innerHTML = parts.map((p) => p.html + (state.charts && p.charts_html ? p.charts_html : "")).join("\n");
    $("src").textContent = buildMarkdown();
    const optional = parts.filter((p) => !p.locked).length;
    $("export-note").textContent = `${optional} из ${state.meta.sections.filter((s) => !s.locked).length} разделов по выбору`
      + (state.charts ? ", с графиками" : "");
  }

  function render() {
    renderCaveats(state.result.caveats);
    renderChart(state.result.chart);
    renderSections();
    renderReport();
    $("result").hidden = false;
    $("result").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function download(text, filename, type) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = el("a", { href: url, download: filename });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function flash(text) {
    const note = $("export-note");
    const before = note.textContent;
    note.textContent = text;
    setTimeout(() => { if (note.textContent === text) note.textContent = before; }, 2200);
  }

  async function copyMarkdown() {
    const text = buildMarkdown();
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      const area = el("textarea", { "aria-hidden": "true" });
      area.value = text;
      document.body.append(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    flash("Скопировано");
  }

  function setTab(source) {
    $("tab-preview").setAttribute("aria-selected", String(!source));
    $("tab-source").setAttribute("aria-selected", String(source));
    $("doc").hidden = source;
    $("src").hidden = !source;
  }

  function preset(kind) {
    const pick = { all: () => true, none: () => false, default: (s) => s.default }[kind];
    state.selected = new Set(state.meta.sections.filter((s) => !s.locked && pick(s)).map((s) => s.id));
    saveSelection();
    renderSections();
    renderReport();
  }

  // ── запуск ─────────────────────────────────────────────────────────────────────────────────

  async function init() {
    document.querySelectorAll('input[name="place"]').forEach((r) => r.addEventListener("change", syncForm));
    $("f-notime").addEventListener("change", syncForm);
    $("birth-form").addEventListener("submit", submit);
    $("opt-charts").addEventListener("change", (e) => { state.charts = e.target.checked; saveSelection(); renderReport(); });
    $("btn-download").addEventListener("click", () => download(buildMarkdown(), state.result.filename, "text/markdown;charset=utf-8"));
    $("btn-json").addEventListener("click", () => download(JSON.stringify(state.result.chart, null, 1) + "\n",
      state.result.filename.replace(/\.md$/, ".json"), "application/json;charset=utf-8"));
    $("btn-copy").addEventListener("click", copyMarkdown);
    $("tab-preview").addEventListener("click", () => setTab(false));
    $("tab-source").addEventListener("click", () => setTab(true));
    document.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => preset(b.dataset.preset)));

    try {
      state.meta = await (await fetch("/api/meta")).json();
    } catch (e) {
      return showError("Сервер не отвечает. Проверьте, что web.py запущен.");
    }
    $("cities").replaceChildren(...state.meta.cities.map((c) => el("option", { value: c })));
    loadSelection();
    syncForm();
  }

  init();
})();
