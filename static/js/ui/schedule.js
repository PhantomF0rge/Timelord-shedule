import { $ } from "../utils/dom.js";
import { statusForSlot } from "../utils/time.js";

function lessonView(l){
  if(l.is_break){
    return `<div class="break-item"><strong>Перерыв</strong> · ${l.from}–${l.to}</div>`;
  }
  const status = statusForSlot(l.time_slot.start_time, l.time_slot.end_time, l.is_remote);
  const cls = ["lesson"];
  if(status.includes("now")) cls.push("now");
  else if(status.includes("next")) cls.push("next");
  else if(status.includes("past")) cls.push("past");
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

export function renderSchedule(payload){
  const root = $("#schedule-root");
  if(!root) return;
  if(!payload || !payload.lessons || !payload.lessons.length){
    root.dataset.state="empty";
    root.innerHTML = `<div class="muted">Нет занятий на выбранный день.</div>`;
    return;
  }
  root.dataset.state="filled";
  root.innerHTML = payload.lessons.map(lessonView).join("");
}