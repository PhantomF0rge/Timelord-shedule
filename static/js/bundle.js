// ===== utils =====
const $ = (sel, root=document)=>root.querySelector(sel);
const show = (el)=>{ if(el) el.hidden = false; };
const hide = (el)=>{ if(el) el.hidden = true; };
const todayISO = ()=> new Date().toISOString().slice(0,10);

async function getJSON(url){
  const r = await fetch(url);
  if(!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

// ===== typeahead =====
(function setupTypeahead(){
  const API = "/api/v1/suggest";
  const input = $("#search-input");
  const box = $("#typeahead");
  if(!input || !box) return;

  let timer = null;

  async function fetchSuggest(q){
    try{
      const url = `${API}?q=${encodeURIComponent(q)}&limit=10`;
      const data = await getJSON(url);
      return data.items || [];
    }catch(e){ return []; }
  }

  function render(items){
    if(!items.length){ hide(box); box.innerHTML=""; return; }
    box.innerHTML = items.map(i => `
      <div class="typeahead-item" data-type="${i.type}" data-id="${i.id}" data-code="${i.code||''}">
        <span class="typeahead-type">${i.type}</span>
        <span class="typeahead-label">${i.label}</span>
      </div>
    `).join("");
    show(box);
  }

  box.addEventListener("click", e=>{
    const item = e.target.closest(".typeahead-item");
    if(!item) return;
    const type = item.dataset.type;
    const code = item.dataset.code;
    if(type === "group" && code){
      localStorage.setItem("last_group", code);
      document.dispatchEvent(new CustomEvent("select-group", { detail: { code } }));
      input.value = code;
    }
    hide(box);
  });

  input.addEventListener("input", ()=>{
    const q = input.value.trim();
    if(timer) clearTimeout(timer);
    if(!q){ hide(box); return; }
    timer = setTimeout(async ()=>{ render(await fetchSuggest(q)); }, 250);
  });

  $("#search-clear")?.addEventListener("click", ()=>{ input.value=""; hide(box); });
})();

// ===== schedule render =====
function statusForSlot(start,end,isRemote=false){
  const p = s=>{ const [h,m]=s.split(":").map(Number); const d=new Date(); d.setHours(h,m,0,0); return d; };
  const n = new Date(), S=p(start), E=p(end);
  if(n<S) return isRemote?'remote-next':'next';
  if(n>E) return isRemote?'remote-past':'past';
  return isRemote?'remote':'now';
}

function lessonView(l){
  if(l.is_break){
    return `<div class="break-item"><strong>Перерыв</strong> · ${l.from}–${l.to}</div>`;
  }
  const st = statusForSlot(l.time_slot.start_time, l.time_slot.end_time, l.is_remote);
  const cls = ["lesson"];
  if(st.includes("now")) cls.push("now");
  else if(st.includes("next")) cls.push("next");
  else if(st.includes("past")) cls.push("past");
  if(l.is_remote) cls.push("remote");

  return `
  <article class="${cls.join(' ')}">
    <div class="title">${l.subject.name} <span class="meta">· ${l.lesson_type?.name||"Занятие"}</span></div>
    <div class="meta">
      ${l.time_slot.start_time}–${l.time_slot.end_time} · №${l.time_slot.order_no}
      ${l.room ? " · ауд. " + l.room.number : " · СДО"}
      · ${l.teacher.full_name}
      ${l.homework ? " · ДЗ: " + l.homework.text : ""}
    </div>
  </article>`;
}

function renderDay(payload){
  const root = $("#schedule-root");
  if(!payload || !payload.lessons || !payload.lessons.length){
    root.dataset.state="empty";
    root.innerHTML = `<div class="muted">Нет занятий на выбранный день.</div>`;
    return;
  }
  root.dataset.state="filled";
  root.innerHTML = payload.lessons.map(lessonView).join("");
}

function renderWeek(payload){
  const root = $("#schedule-root");
  if(!payload || !payload.days || !payload.days.length){
    root.dataset.state="empty";
    root.innerHTML = `<div class="muted">Нет занятий за выбранную неделю.</div>`;
    return;
  }
  root.dataset.state="filled";
  root.innerHTML = `
    <div class="week-grid">
      ${payload.days.map(d=>`
        <div class="glass day-card">
          <div class="day-title">${d.date}</div>
          ${d.lessons && d.lessons.length ? d.lessons.map(lessonView).join("") : `<div class="muted">—</div>`}
        </div>
      `).join("")}
    </div>`;
}

// ===== schedule loader (day/week) =====
(async function boot(){
  const quick = $("#quick-result");
  const dateInput = $("#date-input");
  const btnDay = $("#btn-day");
  const btnWeek = $("#btn-week");

  const last = localStorage.getItem("last_group");
  if(last && quick){ quick.innerHTML = `Показываю расписание для группы <strong>${last}</strong>.`; show(quick); }

  function uiRange(){ return btnWeek?.classList.contains("active") ? "week" : "day"; }
  function setRange(r){ 
    btnDay?.classList.toggle("active", r==="day");
    btnWeek?.classList.toggle("active", r==="week");
  }

  async function load(range, dateStr){
    const code = localStorage.getItem("last_group");
    if(!code) return;
    const base = `/api/v1/schedule/group/${encodeURIComponent(code)}?date=${dateStr}&range=${range}`;
    const data = await getJSON(base);
    if(range === "week") renderWeek(data);
    else renderDay(data);
  }

  if(dateInput && !dateInput.value) dateInput.value = todayISO();

  // Первичная загрузка
  await load(uiRange(), dateInput ? dateInput.value : todayISO());

  btnDay?.addEventListener("click", async ()=>{
    setRange("day");
    await load("day", dateInput.value || todayISO());
  });
  btnWeek?.addEventListener("click", async ()=>{
    setRange("week");
    await load("week", dateInput.value || todayISO());
  });
  dateInput?.addEventListener("change", async ()=>{
    await load(uiRange(), dateInput.value || todayISO());
  });

  // Когда выбрали группу в подсказках
  document.addEventListener("select-group", async ()=>{
    await load(uiRange(), dateInput.value || todayISO());
    if(quick){
      const code = localStorage.getItem("last_group");
      quick.innerHTML = `Показываю расписание для группы <strong>${code}</strong>.`; show(quick);
    }
  });
})();
