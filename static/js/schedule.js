(function () {
  function iso(d){ return d.toISOString().slice(0,10) }
  function parseISO(s){ const [y,m,d]=s.split('-').map(Number); return new Date(y,m-1,d) }

  function nextDate(cur, range, dir){
    const d = new Date(cur.getTime());
    if (range === 'week') d.setDate(d.getDate() + 7*dir);
    else d.setDate(d.getDate() + 1*dir);
    return d;
  }

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.controls .btn');
    if (!btn) return;
    const box = btn.closest('.controls');
    const type = box.dataset.entity;
    const id = box.dataset.entityId;
    let range = box.dataset.range;
    const url = new URL(location.href);
    const d = url.searchParams.get('date');
    const cur = d ? parseISO(d) : new Date();
    if (btn.dataset.act === 'prev') {
      url.searchParams.set('date', iso(nextDate(cur, range, -1)));
    } else if (btn.dataset.act === 'next') {
      url.searchParams.set('date', iso(nextDate(cur, range, +1)));
    } else if (btn.dataset.act === 'today') {
      url.searchParams.set('date', iso(new Date()));
    } else if (btn.dataset.act === 'toggle-range') {
      range = range === 'day' ? 'week' : 'day';
      box.dataset.range = range;
      url.searchParams.set('range', range);
    }
    location.href = `/schedule/${type === 'group' ? 'group/'+encodeURIComponent(id) : 'teacher/'+encodeURIComponent(id)}?` + url.searchParams.toString();
  });
})();
