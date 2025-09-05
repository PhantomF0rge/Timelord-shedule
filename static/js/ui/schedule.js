import { $, show } from "../utils/dom.js";
import { statusForSlot } from "../utils/time.js";

function normalizeLesson(raw) {
  const subjectName =
    raw?.subject?.name ?? raw.subject_name ?? raw.subject_title ?? raw.subject ?? "";
  const teacherFull =
    raw?.teacher?.full_name ?? raw.teacher_full_name ?? raw.teacher_name ?? "";
  const ltypeName =
    raw?.lesson_type?.name ?? raw.lesson_type ?? raw.type ?? "Занятие";
  const time = raw?.time_slot ?? {};
  const start = time.start_time ?? raw.start_time ?? "";
  const end = time.end_time ?? raw.end_time ?? "";
  const orderNo = time.order_no ?? raw.order_no ?? raw.order ?? null;
  const roomNum = raw?.room?.number ?? raw.room_number ?? null;
  const isRemote = !!(raw.is_remote ?? raw.remote ?? raw.online ?? false);
  const homework = raw?.homework?.text ?? raw.homework_text ?? null;

  return {
    is_break: !!raw.is_break,
    from: raw.from,
    to: raw.to,
    subject: { name: subjectName },
    teacher: { full_name: teacherFull },
    lesson_type: { name: ltypeName },
    time_slot: { start_time: start, end_time: end, order_no: orderNo },
    room: roomNum ? { number: roomNum } : null,
    homework: homework ? { text: homework } : null,
    is_remote: isRemote,
  };
}

function lessonView(_l) {
  const l = normalizeLesson(_l);
  if (l.is_break) {
    return `<div class="break-item"><strong>Перерыв</strong> · ${l.from ?? ""}–${l.to ?? ""}</div>`;
  }
  const status = statusForSlot(l.time_slot.start_time, l.time_slot.end_time, l.is_remote);
  const cls = ["lesson"];
  if (status.includes("now")) cls.push("now");
  else if (status.includes("next")) cls.push("next");
  else if (status.includes("past")) cls.push("past");
  if (l.is_remote) cls.push("remote");

  return `
  <article class="${cls.join(" ")}">
    <div class="title">${l.subject.name} <span class="meta">· ${l.lesson_type?.name || "Занятие"}</span></div>
    <div class="meta">
      ${l.time_slot.start_time}–${l.time_slot.end_time}${l.time_slot.order_no ? " · №" + l.time_slot.order_no : ""}
      ${l.room ? " · ауд. " + l.room.number : " · СДО"}
      ${l.teacher?.full_name ? " · " + l.teacher.full_name : ""}
      ${l.homework?.text ? " · ДЗ: " + l.homework.text : ""}
    </div>
  </article>`;
}

export function renderSchedule(payload) {
  const root = $("#schedule-root");
  if (!root) return;

  // week-режим: payload.days[]
  if (payload && Array.isArray(payload.days)) {
    if (!payload.days.length) {
      root.dataset.state = "empty";
      root.innerHTML = `<div class="muted">На этой неделе занятий нет.</div>`;
      return;
    }
    root.dataset.state = "filled";
    root.innerHTML = `
      <div class="week-grid">
        ${payload.days
          .map((d) => {
            const lessons = (d.lessons || []).map(lessonView).join("");
            const dstr = d.date;
            return `
              <section class="glass day-card">
                <header class="day-head">${dstr}</header>
                <div class="day-body">${lessons || '<div class="muted">Нет занятий</div>'}</div>
              </section>`;
          })
          .join("")}
      </div>
    `;
    return;
  }

  // day-режим: payload.lessons[]
  const list = (payload && payload.lessons) || [];
  if (!list.length) {
    root.dataset.state = "empty";
    root.innerHTML = `<div class="muted">Нет занятий на выбранный день.</div>`;
    return;
  }
  root.dataset.state = "filled";
  root.innerHTML = list.map(lessonView).join("");
}
