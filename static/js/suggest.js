// static/js/suggest.js
(function () {
  const KEY = {UP:38, DOWN:40, ENTER:13, ESC:27};
  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

  function debounce(fn, ms) {
    let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  function highlight(text, query) {
    if (!query) return text;
    const esc = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return text.replace(new RegExp(esc, 'ig'), m => `<mark>${m}</mark>`);
  }

  function createListEl() {
    const el = document.createElement('div');
    el.className = 'tl-suggest';
    el.innerHTML = `<ul class="tl-suggest__list" role="listbox"></ul>`;
    document.body.appendChild(el);
    return el;
  }

  function positionList(input, listEl) {
    const r = input.getBoundingClientRect();
    listEl.style.minWidth = r.width + 'px';
    listEl.style.left = (window.scrollX + r.left) + 'px';
    listEl.style.top = (window.scrollY + r.bottom) + 'px';
  }

  async function fetchSuggest(query, type, limit, signal) {
    const url = `/api/v1/suggest?q=${encodeURIComponent(query)}&type=${encodeURIComponent(type)}&limit=${limit}`;
    const r = await fetch(url, {signal});
    if (!r.ok) throw new Error('Suggest failed');
    return r.json();
  }

  function attachSuggest(input, opts = {}) {
    const type = opts.type || 'group';
    const limit = opts.limit || 10;
    const onSelect = opts.onSelect || (()=>{});
    const listEl = createListEl();
    let items = [];
    let index = -1;
    let ac = null;

    const render = (q) => {
      const ul = listEl.querySelector('.tl-suggest__list');
      ul.innerHTML = items.map((it, i) => {
        const active = i === index ? ' aria-selected="true" class="active"' : '';
        const label = highlight(it.label, q);
        const hint = it.hint ? ` <span class="hint">${highlight(String(it.hint), q)}</span>` : '';
        return `<li role="option"${active} data-idx="${i}">${label}${hint}<span class="type">${it.type}</span></li>`;
      }).join('');
      positionList(input, listEl);
      listEl.style.display = items.length ? 'block' : 'none';

      // click
      ul.querySelectorAll('li').forEach(li => {
        li.addEventListener('mousedown', (e) => {
          e.preventDefault();
          const i = parseInt(li.dataset.idx, 10);
          if (!isNaN(i)) choose(i);
        });
      });
    };

    const choose = (i) => {
      const it = items[i];
      if (!it) return;
      input.value = it.label;
      listEl.style.display = 'none';
      onSelect(it);
    };

    const doSuggest = debounce(async () => {
      const q = input.value.trim();
      if (!q) { items = []; index = -1; render(''); return; }
      if (ac) ac.abort();
      ac = new AbortController();
      try {
        const data = await fetchSuggest(q, type, limit, ac.signal);
        items = data.items || [];
        index = items.length ? 0 : -1;
        render(q);
      } catch(_) {}
    }, 300);

    input.addEventListener('input', doSuggest);
    input.addEventListener('keydown', (e) => {
      if (listEl.style.display !== 'block') return;
      if (e.keyCode === KEY.DOWN) { index = clamp(index + 1, 0, items.length - 1); render(input.value.trim()); e.preventDefault(); }
      else if (e.keyCode === KEY.UP) { index = clamp(index - 1, 0, items.length - 1); render(input.value.trim()); e.preventDefault(); }
      else if (e.keyCode === KEY.ENTER) { if (index >= 0) { choose(index); e.preventDefault(); } }
      else if (e.keyCode === KEY.ESC) { listEl.style.display = 'none'; }
    });

    window.addEventListener('resize', () => positionList(input, listEl));
    window.addEventListener('scroll', () => positionList(input, listEl), true);

    // close on blur (with mousedown protection handled in li listener)
    input.addEventListener('blur', () => setTimeout(()=> (listEl.style.display = 'none'), 120));
    return { destroy(){ listEl.remove(); } };
  }

  // Экспорт в глобалку
  window.TLAttachSuggest = attachSuggest;
})();
