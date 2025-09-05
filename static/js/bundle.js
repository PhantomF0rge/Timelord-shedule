/* ========= utils ========= */
const $  = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));
const show = (el) => el && (el.hidden = false);
const hide = (el) => el && (el.hidden = true);

function todayISO() {
  const d = new Date();
  const m = String(d.getMonth()+1).padStart(2,'0');
  const day = String(d.getDate()).padStart(2,'0');
  return `${d.getFullYear()}-${m}-${day}`;
}
function parseTimeToDate(hhmm) {
  if (!hhmm) return null;
  const [h, m] = String(hhmm).split(':').map(Number);
  const d = new Date();
  d.setHours(h||0, m||0, 0, 0);
  return d;
}
function statusForSlot(start, end, isRemote=false) {
  const s = parseTimeToDate(start), e = parseTimeToDate(end), n = new Date();
  if (!s || !e) return 'past';
  if (n < s) return isRemote ? 'remote-next' : 'next';
  if (n > e) return isRemote ? 'remote-past' : 'past';
  return isRemote ? 'remote' : 'now';
}

/* ========= API ========= */
const API_PREFIX = '/api/v1';

async function apiGet(url) {
  const r = await fetch(url, { headers: { 'Accept': 'application/json' }});
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
async function fetchSuggest(q, limit=10) {
  if (!q) return [];
  try {
    const data = await apiGet(`${API_PREFIX}/suggest?q=${encodeURIComponent(q)}&limit=${limit}`);
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}
async function fetchGroupSchedule(code, dateISO, range='day') {
  try {
    const url = `${API_PREFIX}/schedule/group/${encodeURIComponent(code)}?date=${encodeURIComponent(dateISO)}&range=${encodeURIComponent(range)}`;
    return await apiGet(url);
  } catch {
    return range === 'week' ? { days: [] } : { lessons: [] };
  }
}

/* ========= Typeahead ========= */
function mountTypeahead() {
  const input = $('#search-input');
  const box   = $('#typeahead');
  const clearBtn = $('#search-clear');

  if (!input || !box) return;

  let timer = null;

  function render(items) {
    if (!items.length) {
      box.innerHTML = '';
      hide(box);
      return;
    }
    box.innerHTML = items.map(i => `
      <div class="typeahead-item" data-type="${i.type||''}" data-id="${i.id||''}" data-code="${i.code||''}">
        <span class="typeahead-type">${i.type||''}</span>
        <span class="typeahead-label">${i.label||i.code||''}</span>
      </div>
    `).join('');
    show(box);
  }

  input.addEventListener('input', () => {
    const q = input.value.trim();
    if (timer) clearTimeout(timer);
    if (!q) { render([]); return; }
    timer = setTimeout(async () => {
      render(await fetchSuggest(q));
    }, 200);
  });

  box.addEventListener('click', (e) => {
    const item = e.target.closest('.typeahead-item');
    if (!item) return;
    const type = item.dataset.type;
    const code = item.dataset.code;
    if (type === 'group' && code) {
      localStorage.setItem('last_group', code);
      document.dispatchEvent(new CustomEvent('select-group', { detail: { code } }));
    }
    hide(box);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { hide(box); }
  });

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      input.value = '';
      hide(box);
      input.focus();
    });
  }
}

/* ========= Schedule render ========= */
function lessonCard(l) {
  if (l.is_break) {
    return `<div class="break-item"><strong>Перерыв</strong> · ${l.from||''}–${l.to||''}</div>`;
  }
  const isRemote = !!(l.is_remote || l.remote || l.online);
  const t = l.time_slot || {};
  const status = statusForSlot(t.start_time, t.end_time, isRemote);
  const cls = ['lesson'];
  if (status.includes('now'))  cls.push('now');
  if (status.includes('next')) cls.push('next');
  if (status.includes('past')) cls.push('past');
  if (isRemote) cls.push('remote');

  const subj = l.subject || {};
  const lt   = l.lesson_type || {};
  const teach= l.teacher || {};
  const room = l.room;

  const hw = l.homework && (l.homework.text || l.homework.title) ? ` · ДЗ: ${l.homework.text || l.homework.title}` : '';

  return `
    <article class="${cls.join(' ')}">
      <div class="title">${subj.name || subj.title || 'Предмет'} <span class="meta">· ${lt.name || lt.title || 'Занятие'}</span></div>
      <div class="meta">
        ${(t.start_time||'')}${t.end_time?'–'+t.end_time:''}
        ${t.order_no ? ` · №${t.order_no}` : ''}
        ${room ? ` · ауд. ${room.number||room.name||''}` : ' · СДО'}
        ${teach.full_name ? ` · ${teach.full_name}` : ''}
        ${hw}
      </div>
    </article>
  `;
}

function renderDay(payload) {
  const root = $('#schedule-root');
  if (!root) return;
  const lessons = (payload && payload.lessons) || [];
  if (!lessons.length) {
    root.dataset.state = 'empty';
    root.innerHTML = `<div class="muted">Нет занятий на выбранный день.</div>`;
    return;
  }
  root.dataset.state = 'filled';
  root.innerHTML = lessons.map(lessonCard).join('');
}

function renderWeek(payload) {
  const root = $('#schedule-root');
  if (!root) return;
  const days = (payload && payload.days) || [];
  if (!days.length) {
    root.dataset.state = 'empty';
    root.innerHTML = `<div class="muted">Нет занятий на выбранную неделю.</div>`;
    return;
  }
  root.dataset.state = 'filled';
  // 3 карточки в строку
  root.style.display = 'grid';
  root.style.gridTemplateColumns = 'repeat(auto-fill, minmax(300px, 1fr))';
  root.style.gap = '12px';
  root.innerHTML = days.map(d => {
    const dateStr = d.date || '';
    const list = (d.lessons||[]).map(lessonCard).join('') || `<div class="muted">Нет занятий</div>`;
    return `
      <section class="glass" style="padding:12px;border-radius:12px">
        <div class="meta" style="margin-bottom:8px">${dateStr}</div>
        ${list}
      </section>
    `;
  }).join('');
}

/* ========= Controls (date/range) ========= */
function mountControls() {
  const btnDay  = $('#btn-range-day')   || $('#view-day')   || $('[data-view="day"]');
  const btnWeek = $('#btn-range-week')  || $('#view-week')  || $('[data-view="week"]');
  const inputDate = $('#date-input')    || $('#date-picker')|| $('input[type="date"]');

  function currentGroup() {
    return localStorage.getItem('last_group') || '';
  }

  async function loadAndRender(range) {
    const code = currentGroup();
    const dateISO = (inputDate && inputDate.value) || todayISO();
    const payload = await fetchGroupSchedule(code, dateISO, range);
    if (range === 'week') renderWeek(payload); else renderDay(payload);
  }

  if (inputDate) {
    if (!inputDate.value) inputDate.value = todayISO();
    inputDate.addEventListener('change', async () => {
      const isWeek = (btnWeek && btnWeek.classList.contains('active')) || (btnWeek && btnWeek.getAttribute('aria-pressed')==='true');
      await loadAndRender(isWeek ? 'week' : 'day');
    });
  }

  if (btnDay) {
    btnDay.addEventListener('click', async () => {
      btnDay.classList.add('active');
      if (btnWeek) btnWeek.classList.remove('active');
      await loadAndRender('day');
    });
  }

  if (btnWeek) {
    btnWeek.addEventListener('click', async () => {
      btnWeek.classList.add('active');
      if (btnDay) btnDay.classList.remove('active');
      await loadAndRender('week');
    });
  }

  // первичная загрузка, если есть сохранённая группа
  document.addEventListener('select-group', async (e) => {
    const isWeek = (btnWeek && btnWeek.classList.contains('active')) || (btnWeek && btnWeek.getAttribute('aria-pressed')==='true');
    await loadAndRender(isWeek ? 'week' : 'day');
  });

  // если группа уже сохранена — показать сразу
  if (localStorage.getItem('last_group')) {
    loadAndRender('day');
  }
}

/* ========= Boot ========= */
(function boot() {
  // инициализация подсказок
  mountTypeahead();

  // быстрый баннер с выбранной группой (если есть)
  const code = localStorage.getItem('last_group');
  const quick = $('#quick-result');
  if (code && quick) {
    quick.innerHTML = `Показываю расписание для группы <strong>${code}</strong>.`;
    show(quick);
  }

  // инициализация контролов и первичная отрисовка
  mountControls();
})();
