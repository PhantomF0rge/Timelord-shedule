(async function(){
  try{
    const js = await api.get("/api/v1/admin/dashboard/summary");
    const c = js.counters;
    const cards = document.getElementById("cards");
    cards.innerHTML = [
      ["Группы", c.groups], ["Преподаватели", c.teachers],
      ["Аудитории", c.rooms], ["Предметы", c.subjects]
    ].map(([t,v]) => `<div class="card"><div class="muted">${t}</div><div style="font-size:24px">${v}</div></div>`).join("");

    const byId = (arr, id) => arr.find(x=>x.id===id);
    const tbody = document.querySelector("#week tbody");
    tbody.innerHTML = js.week.map(w => {
      return `<tr>
        <td>${w.date}</td><td>${w.time_slot_id}</td>
        <td>${w.group_id}</td><td>${w.teacher_id}</td>
        <td>${w.room_id}</td><td>${w.subject_id}</td>
      </tr>`;
    }).join("");

    const ul = document.getElementById("conflicts");
    ul.innerHTML = js.conflicts.map(c => `<li>#${c.schedule_id}: ${c.code}</li>`).join("") || "<li>Нет конфликтов</li>";
  }catch(e){
    const t=document.createElement("div");t.className="toast";t.textContent="Ошибка дашборда";document.body.append(t);setTimeout(()=>t.remove(),3000);
  }
})();
