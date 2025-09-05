(function () {
  "use strict";

  // ==== helpers ====
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const show = (el) => el && (el.hidden = false);
  const hide = (el) => el && (el.hidden = true);

  function ymd(d) {
    const pad = (n) => (n < 10 ? "0" + n : "" + n);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
  function parseTimeStr(hhmm) {
    if (!hhmm) return null;
    const [h, m] = String(hhmm).split(":").map((x) => parseInt(x, 10));
    if (Number.isNaN(h) || Number.isNaN(m)) return null;
    const d = new Date();
    d.setHours(h, m, 0, 0);
    return d;
  }
  function statusForSlot(startStr, endStr, isRemote) {
    const now = new Date();
    const s = parseTimeStr(startStr);
    const e = parseTimeStr(endStr);
    if (!s || !e) return isRemote ? "remote" : "now";
    if (now < s) return isRemote ? "remote-next" : "next";
    if (now > e) return isRemote ? "remote-past" : "past";
    return isRemote ? "remote" : "now";
  }

  // ==== DOM bootstrap (вставим тулбар если его нет) ====
  function ensureToolbar() {
    let toolbar = $("#schedule-toolbar");
    if (toolbar) return toolbar;

    const container = $(".main, .container") || document.body;
    toolbar = document.createElement("div");
    toolbar.id = "schedule-toolbar";
    toolbar.style.margin = "10px 0 14px";
    toolbar.innerHTML = `
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <div class="segmented" role="tablist" aria-label="Диапазон" style="display:inline-flex;border:1px solid rgba(255,255,255,.15);border-radius:12px;overflow:hidden">
          <button id="btn-day"  class="btn"  style="border:0;border-right:1px solid rgba(255,255,255,.12);padding:8px 12px;background:rgba(255,255,255,.06);cursor:pointer">День</button>
          <button id="btn-week" class="btn"  style="border:0;padding:8px 12px;background:transparent;cursor:pointer">Неделя</button>
        </div>
        <input id="date-input" type="date" style="appearance:none;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.15);border-radius:10px;padding:8px 10px;color:#e9ecf1">
      </div>
    `;
    const anchor = $("#quick-result") || $(".hero") || $(".main") || container;
    (anchor.parentElement || container).insertBefore(toolbar, anchor.nextSibling);
    return toolbar;
  }

  function ensureScheduleRoot() {
    let root = $("#schedule-root");
    if (!root) {
      root = document.createElement("div");
      root.id = "schedule-root";
      root.className = "schedule-grid";
      const main = $(".main, .container") || document.body;
      main.appendChild(root);
    }
    return root;
  }

  function ensureSearch() {
    // если в шапке нет формы поиска — создадим простую
    let input = $("#search-input");
    if (!input) {
      const header = $(".site-header") || document.body;
      const wrap = document.createElement("div");
      wrap.className = "container";
      wrap.innerHTML = `
        <div class="search" style="margin:8px 0 12px">
          <input id="search-input" class="search-input" placeholder="Группа / преподаватель / дисциплина" style="width:100%;appearance:none;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.15);border-radius:12px;padding:10px 12px;color:#e9ecf1;outline:none" />
          <div id="typeahead" class="typeahead" hidden style="position:relative;margin-top:6px"></div>
        </div>
      `;
      header.appendChild(wrap);
    }
  }

  // ==== renderers ====
  function lessonView(l) {
    if (l.is_break) {
      const from = l.from || (l.time_slot && l.time_slot.start_time) || "";
      const to = l.to || (l.time_slot && l.time_slot.end_time) || "";
      return `<div class="break-item" style="border:1px dashed rgba(255,255,255,.25);border-radius:12px;padding:10px;color:#c4ccdb">
        <strong>Перерыв</strong> · ${from}–${to}
      </div>`;
    }
    const start = (l.time_slot && l.time_slot.start_time) || l.start_time || "";
    const end = (l.time_slot && l.time_slot.end_time) || l.end_time || "";
    const orderNo = (l.time_slot && (l.time_slot.order_no || l.time_slot.order)) || l.order_no || l.order || "";
    const subj = (l.subject && (l.subject.name || l.subject.title)) || l.subject_name || "Предмет";
    const type = (l.lesson_type && (l.lesson_type.name || l.lesson_type.title)) || l.type || "Занятие";
    const teacher = (l.teacher && (l.teacher.full_name || l.teacher.name)) || l.teacher_name || "";
    const room = l.room ? (l.room.number || l.room.name) : null;
    const isRemote = !!(l.is_remote || l.remote || l.online);

    const st = statusForSlot(start, end, isRemote);
    const outline =
      st.indexOf("now") >= 0
        ? "outline:2px solid #2dbf7a"
        : st.indexOf("next") >= 0
        ? "outline:2px dashed #c9a227"
        : st.indexOf("past") >= 0
        ? "opacity:.8"
        : "";
    const remoteBorder = isRemote ? "border-color:#5aa2ff" : "";

    const hw = l.homework && (l.homework.text || l.homework) ? ` · ДЗ: ${l.homework.text || l.homework}` : "";

    return `
      <article class="lesson" style="border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px;background:rgba(255,255,255,.04);${outline};${remoteBorder}">
        <div class="title" style="font-weight:600">${subj} <span class="meta" style="color:#a7b0bf;font-size:14px">· ${type}</span></div>
        <div class="meta" style="color:#a7b0bf;font-size:14px">
          ${start}–${end} · №${orderNo}
          ${room ? " · ауд. " + room : " · СДО"}
          ${teacher ? " · " + teacher : ""}${hw}
        </div>
      </article>
    `;
  }

  function renderDay(payload) {
    const root = ensureScheduleRoot();
    const lessons = (payload && payload.lessons) || [];
    if (!lessons.length) {
      root.innerHTML = `<div class="muted" style="color:#a7b0bf">Нет занятий на выбранный день.</div>`;
      return;
    }
    root.innerHTML = lessons.map(lessonView).join("");
  }

  function renderWeek(payload) {
    const root = ensureScheduleRoot();
    const days = (payload && payload.days) || [];
    if (!days.length) {
      root.innerHTML = `<div class="muted" style="color:#a7b0bf">Нет занятий на этой неделе.</div>`;
      return;
    }
    const gridCss = `
      display:grid;gap:12px;
      grid-template-columns: repeat(3,minmax(260px,1fr));
    `;
    root.innerHTML = `
      <div class="week-grid" style="${gridCss}">
        ${days
          .map((d) => {
            const header = new Date(d.date || d.day || d.lesson_date || Date.now());
            const title = header.toLocaleDateString("ru-RU", { weekday: "long", day: "2-digit", month: "2-digit" });
            const items = (d.lessons || []).map(lessonView).join("");
            return `
              <section class="glass" style="background:rgba(255,255,255,.06);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,.12);border-radius:14px;padding:10px 12px">
                <div style="font-weight:600;margin-bottom:6px">${title}</div>
                <div>${items || '<div class="muted" style="color:#a7b0bf">Нет занятий</div>'}</div>
              </section>`;
          })
          .join("")}
      </div>
    `;
  }

  // ==== API ====
  async function fetchJSON(url) {
    const r = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  }

  async function fetchSuggest(q, limit = 10) {
    const url = `/api/v1/suggest?q=${encodeURIComponent(q)}&limit=${limit}`;
    try {
      const data = await fetchJSON(url);
      return data.items || [];
    } catch {
      return [];
    }
  }

  async function fetchSchedule(groupCode, dateStr, range) {
    const url = `/api/v1/schedule/group/${encodeURIComponent(groupCode)}?date=${encodeURIComponent(dateStr)}&range=${encodeURIComponent(range)}`;
    return await fetchJSON(url);
  }

  // ==== Typeahead ====
  function initTypeahead() {
    const input = $("#search-input");
    if (!input) return;
    let box = $("#typeahead");
    if (!box) {
      box = document.createElement("div");
      box.id = "typeahead";
      box.hidden = true;
      input.insertAdjacentElement("afterend", box);
    }
    // box styling if missing
    if (!box.style.position) {
      box.style.position = "absolute";
      box.style.left = "0";
      box.style.right = "0";
      box.style.zIndex = "20";
      box.style.border = "1px solid rgba(255,255,255,.12)";
      box.style.background = "rgba(12,15,22,.92)";
      box.style.backdropFilter = "blur(16px)";
      box.style.borderRadius = "12px";
      box.style.marginTop = "6px";
      box.style.overflow = "hidden";
    }
    let timer = null;

    function render(items) {
      if (!items.length) {
        hide(box);
        box.innerHTML = "";
        return;
      }
      box.innerHTML = items
        .map(
          (i) => `
        <div class="typeahead-item" data-type="${i.type}" data-id="${i.id || ""}" data-code="${i.code || ""}" style="padding:10px 12px;display:flex;gap:10px;align-items:center;cursor:pointer">
          <span class="typeahead-type" style="font-size:12px;color:#c9a227;width:80px">${i.type || ""}</span>
          <span class="typeahead-label" style="flex:1">${i.label || i.name || ""}</span>
        </div>`
        )
        .join("");
      show(box);
    }

    input.addEventListener("input", () => {
      const q = input.value.trim();
      if (timer) clearTimeout(timer);
      if (!q) {
        hide(box);
        return;
      }
      timer = setTimeout(async () => {
        render(await fetchSuggest(q, 10));
      }, 250);
    });

    document.addEventListener("click", (e) => {
      if (!box.contains(e.target) && e.target !== input) hide(box);
    });

    box.addEventListener("click", (e) => {
      const item = e.target.closest(".typeahead-item");
      if (!item) return;
      const type = item.dataset.type;
      const code = item.dataset.code;
      input.value = item.querySelector(".typeahead-label")?.textContent || "";
      hide(box);
      if (type === "group" && code) {
        localStorage.setItem("last_group", code);
        // триггерим загрузку расписания
        const ev = new CustomEvent("select-group", { detail: { code } });
        document.dispatchEvent(ev);
      }
    });
  }

  // ==== Toolbar logic ====
  function initToolbarAndLoad() {
    ensureSearch();
    const toolbar = ensureToolbar();
    const root = ensureScheduleRoot();

    const btnDay = $("#btn-day");
    const btnWeek = $("#btn-week");
    const dateInput = $("#date-input");
    const quick = $("#quick-result");

    // default state
    const today = new Date();
    if (dateInput && !dateInput.value) dateInput.value = ymd(today);

    function setActive(range) {
      if (btnDay) btnDay.style.background = range === "day" ? "rgba(255,255,255,.06)" : "transparent";
      if (btnWeek) btnWeek.style.background = range === "week" ? "rgba(255,255,255,.06)" : "transparent";
    }

    let currentRange = "day";
    setActive(currentRange);

    async function load(groupCode, range, dateStr) {
      try {
        const payload = await fetchSchedule(groupCode, dateStr, range);
        if (range === "week") renderWeek(payload);
        else renderDay(payload);
        if (quick) {
          quick.hidden = false;
          quick.innerHTML = `Показываю расписание для группы <strong>${groupCode}</strong> (${range === "week" ? "неделя" : "день"}: ${dateStr}).`;
        }
      } catch (e) {
        root.innerHTML = `<div class="muted" style="color:#a7b0bf">Не удалось загрузить расписание (${e && e.message ? e.message : "ошибка"}).</div>`;
      }
    }

    function reload() {
      const code = localStorage.getItem("last_group");
      if (!code) {
        root.innerHTML = `<div class="muted" style="color:#a7b0bf">Выберите группу через поиск выше.</div>`;
        return;
      }
      const dateStr = (dateInput && dateInput.value) || ymd(new Date());
      load(code, currentRange, dateStr);
    }

    btnDay && btnDay.addEventListener("click", () => {
      currentRange = "day";
      setActive(currentRange);
      reload();
    });
    btnWeek && btnWeek.addEventListener("click", () => {
      currentRange = "week";
      setActive(currentRange);
      reload();
    });
    dateInput && dateInput.addEventListener("change", reload);

    // авто-загрузка сохранённой группы
    const saved = localStorage.getItem("last_group");
    if (saved) reload();

    // подписка на выбор из подсказок
    document.addEventListener("select-group", reload);
  }

  // ==== boot ====
  document.addEventListener("DOMContentLoaded", function () {
    initTypeahead();
    initToolbarAndLoad();
  });
})();
