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
    return { lessons: [] }; // безопасный заглушечный ответ
  }
}

function getQueryFlag(name){
  const p = new URLSearchParams(location.search);
  return p.has(name) && p.get(name) !== "0" && p.get(name) !== "false";
}

async function boot(){
  initTypeahead();

  // демо-режим: если нет сохранённой группы — показываем демо-расписание
  const demoForced = getQueryFlag("demo");             // можно включить/выключить через ?demo=1
  let code = localStorage.getItem("last_group");

  if(!code){
    code = "DEMO"; // ключ для демонстрации; бэкенд мок и так вернёт валидные пары
    const quick = $("#quick-result");
    if(quick){
      quick.innerHTML = `Демо-режим: показываю пример расписания. Выберите свою группу в поиске — мы запомним её и будем показывать автоматически.`;
      show(quick);
    }
    renderSchedule(await fetchGroupSchedule(code));
  }

  // если есть сохранённая группа — показываем её (как раньше)
  if(code && !demoForced && code !== "DEMO"){
    const quick = $("#quick-result");
    if(quick){ quick.innerHTML = `Показываю расписание для группы <strong>${code}</strong>.`; show(quick); }
    renderSchedule(await fetchGroupSchedule(code));
  }

  // выбор из подсказок
  document.addEventListener("select-group", async (e)=>{
    const code = e.detail.code;
    localStorage.setItem("last_group", code);
    renderSchedule(await fetchGroupSchedule(code));
    const quick = $("#quick-result");
    if(quick){ quick.innerHTML = `Показываю расписание для группы <strong>${code}</strong>.`; show(quick); }
  });
}

boot();
