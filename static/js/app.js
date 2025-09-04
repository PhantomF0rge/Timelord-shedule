import { $, show } from "./utils/dom.js";
import { initTypeahead } from "./ui/typeahead.js";
import { renderScheduleDay, renderScheduleWeek } from "./ui/schedule.js";
import { isoDate } from "./utils/time.js";

async function fetchGroupScheduleDay(code, dateIso){
  try{
    const url = `/api/v1/schedule/group/${encodeURIComponent(code)}?date=${dateIso}&range=day`;
    const r = await fetch(url);
    if(!r.ok) throw new Error("schedule failed");
    return await r.json();
  }catch(e){
    return { lessons: [] };
  }
}

async function fetchGroupScheduleWeek(code, anchorIso){
  try{
    const url = `/api/v1/schedule/group/${encodeURIComponent(code)}?date=${anchorIso}&range=week`;
    const r = await fetch(url);
    if(!r.ok) throw new Error("week schedule failed");
    return await r.json(); // ожидаем { days:[{date,lessons}], from, to, ... }
  }catch(e){
    return { days: [] };
  }
}

function bindControls(state){
  const dateEl = $("#date-input");
  const segs = Array.from(document.querySelectorAll(".segmented .seg"));

  const todayIso = isoDate(new Date());
  state.date = state.date || todayIso;
  if(dateEl){
    dateEl.value = state.date;
    dateEl.addEventListener("change", ()=>{
      state.date = dateEl.value || todayIso;
      refresh(state);
    });
  }
  if(segs.length){
    segs.forEach(btn=>{
      btn.addEventListener("click", ()=>{
        segs.forEach(b=>b.classList.remove("active"));
        btn.classList.add("active");
        state.range = btn.dataset.range || "day";
        refresh(state);
      });
    });
  }
}

async function refresh(state){
  if(!state.group) return;
  const quick = $("#quick-result");
  if(quick){
    quick.innerHTML = `Показываю расписание для группы <strong>${state.group}</strong> (${state.range === "week" ? "неделя" : "день"}).`;
    show(quick);
  }
  if(state.range === "week"){
    const week = await fetchGroupScheduleWeek(state.group, state.date);
    renderScheduleWeek(week);
  }else{
    const day = await fetchGroupScheduleDay(state.group, state.date);
    renderScheduleDay(day);
  }
}

async function boot(){
  initTypeahead();

  const state = {
    group: localStorage.getItem("last_group"),
    date: isoDate(new Date()),
    range: "day",
  };
  bindControls(state);

  if(state.group){
    refresh(state);
  }

  document.addEventListener("select-group", async (e)=>{
    const code = e.detail.code;
    state.group = code;
    state.date = state.date || isoDate(new Date());
    refresh(state);
  });
}

boot();
