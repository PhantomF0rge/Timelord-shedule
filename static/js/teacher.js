(function () {
  const root = document.getElementById('tch-root');
  if (!root) return;

  function iso(d){ return d.toISOString().slice(0,10); }
  function parseISO(s){ const [y,m,d]=s.split('-').map(Number); return new Date(y,m-1,d); }
  function nextDate(cur, range, dir){
    const d = new Date(cur.getTime());
    if (range === 'month') d.setMonth(d.getMonth() + dir);
    else d.setDate(d.getDate() + 7*dir);
    return d;
  }

  const controls = root.querySelector('.controls');
  let range = controls.dataset.range || 'week';
  const url = new URL(location.href);
  let cur = url.searchParams.get('date') ? parseISO(url.searchParams.get('date')) : new Date();

  async function load(){
    const qs = new URLSearchParams({date: iso(cur), range});
    const r = await fetch('/api/v1/teacher/me/aggregate?' + qs.toString());
    if (!r.ok) { console.error('agg failed'); return; }
    const js = await r.json();
    document.getElementById('st-days').textContent  = js.counts.work_days;
    document.getElementById('st-hours').textContent = js.counts.hours;
    document.getElementById('st-pairs').textContent = js.counts.pairs;
    document.getElementById('st-period').textContent = js.period.start + ' — ' + js.period.end;

    const tb = document.querySelector('#lessons tbody');
    tb.innerHTML = '';
    js.lessons.forEach(l => {
      const tr = document.createElement('tr');
      const roomCell = l.is_remote ? `<span class="badge">СДО</span>` : (l.room || '—');
      tr.innerHTML = `
        <td>${l.date}</td>
        <td>${l.slot_order}</td>
        <td>${l.start}–${l.end}</td>
        <td>${l.subject}</td>
        <td>${l.group}</td>
        <td>${l.lesson_type}</td>
        <td>${roomCell}</td>
        <td class="actions">
          <a class="btn-xs" href="/homework/assign?lesson_id=${l.id}">ДЗ</a>
          <button class="btn-xs" data-act="chg-room" data-id="${l.id}" disabled title="скоро">Сменить аудиторию</button>
        </td>
      `;
      tb.appendChild(tr);
    });
  }

  controls.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn');
    if (!btn) return;
    if (btn.dataset.act === 'prev') cur = nextDate(cur, range, -1);
    else if (btn.dataset.act === 'next') cur = nextDate(cur, range, +1);
    else if (btn.dataset.act === 'today') cur = new Date();
    else if (btn.dataset.act === 'toggle-range') {
      range = (range === 'week') ? 'month' : 'week';
      controls.dataset.range = range;
      btn.textContent = (range === 'week') ? 'Месяц' : 'Неделя';
    }
    // отражаем дату в URL (без перезагрузки)
    const u = new URL(location.href);
    u.searchParams.set('date', iso(cur));
    u.searchParams.set('range', range);
    history.replaceState({}, '', u.toString());
    load();
  });

  load();
})();
