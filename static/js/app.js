import { $, show } from "./utils/dom.js";
import { initTypeahead } from "./ui/typeahead.js";
import { renderSchedule } from "./ui/schedule.js";

async function fetchGroupSchedule(code){
  try{
    const today = new Date().toISOString().slice(0,10);
    const url = `/api/v1/schedule/group/${encodeURIComponent(code)}?date=${today}&range=day`;
    const r = await fetch(url);
    if(!r.ok) throw new Error("schedule failed");
    return await r.json();
  }catch(e){
    return { lessons: [] }; // заглушка
  }
}

async function boot(){
  initTypeahead();
  const code = localStorage.getItem("last_group");
  if(code){
    const quick = $("#quick-result");
    if(quick){ quick.innerHTML = `Показываю расписание для группы <strong>${code}</strong>.`; show(quick); }
    renderSchedule(await fetchGroupSchedule(code));
  }
  document.addEventListener("select-group", async (e)=>{
    const code = e.detail.code;
    renderSchedule(await fetchGroupSchedule(code));
    const quick = $("#quick-result");
    if(quick){ quick.innerHTML = `Показываю расписание для группы <strong>${code}</strong>.`; show(quick); }
  });
}

boot();
