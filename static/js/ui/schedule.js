import { $, show } from "../utils/dom.js";
import { statusForSlot, humanDayShort, humanDateCompact } from "../utils/time.js";

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
      ${l.time_slot.start_time}–${l.time_slot.end_time} · №${l.time_slot.order_no ?? ""}
      ${l.room ? " · ауд. " + l.room.number : " · СДО"}
      · ${l.teacher.full_name}
      ${l.homework ? " · ДЗ: " + l.homework.text : ""}
    </div>
  </article>`;
}

export function renderScheduleDay(payload){
  const root = $("#schedule-root");
  if(!root) return;
  if(!payload || !payload.lessons || !payload.lessons.length){
    root.dataset.state="empty";
    root.innerHTML = `<div class="muted">Нет занятий на выбранный день.</div>`;
    return;
  }
  root.dataset.state="filled";
  root.classList.remove("week-grid");
  root.innerHTML = payload.lessons.map(lessonView).join("");
}

export function renderScheduleWeek(week){
  // week = { days: [ {date:"YYYY-MM-DD", lessons:[...]}, ... ] }
  const root = $("#schedule-root");
  if(!root) return;
  const days = (week?.days||[]);
  root.dataset.state = days.length ? "filled":"empty";
  if(!days.length){
    root.classList.remove("week-grid");
    root.innerHTML = `<div class="muted">Нет занятий на выбранную неделю.</div>`;
    return;
  }
  root.classList.add("week-grid");
  root.innerHTML = days.map(d=>{
    const dateObj = new Date(d.date+'T00:00:00');
    const hdr = `<div class="day-header">
      <div class="day-title">${humanDayShort(dateObj)}</div>
      <div class="day-date">${humanDateCompact(d.date)}</div>
    </div>`;
    const content = (d.lessons && d.lessons.length)
      ? d.lessons.map(lessonView).join("")
      : `<div class="muted">Нет занятий</div>`;
    return `<div class="day-card">${hdr}${content}</div>`;
  }).join("");
}
