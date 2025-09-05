(function(){
  const form = document.getElementById("form");
  const grid = document.getElementById("grid");
  const df = document.getElementById("df");
  const dt = document.getElementById("dt");
  const loadBtn = document.getElementById("load");

  function toast(msg){ const t=document.createElement("div");t.className="toast";t.textContent=msg;document.body.append(t);setTimeout(()=>t.remove(),3000); }

  let LU = null; // lookup
  async function loadLU(){
    LU = await api.get("/api/v1/admin/schedule/lookup");
    form.innerHTML = `
      <div>Дата: <input type="date" id="c_date"></div>
      <div>Слот: <select id="c_slot">${LU.timeslots.map(t=>`<option value="${t.id}">${t.order_no}</option>`).join("")}</select></div>
      <div>Группа: <select id="c_group">${LU.groups.map(g=>`<option value="${g.id}">${g.code||g.name}</option>`).join("")}</select></div>
      <div>Преп.: <select id="c_teacher">${LU.teachers.map(t=>`<option value="${t.id}">${t.name}</option>`).join("")}</select></div>
      <div>Ауд.: <select id="c_room">${LU.rooms.map(r=>`<option value="${r.id}">${r.number}</option>`).join("")}</select></div>
      <div>Предмет: <select id="c_subject">${LU.subjects.map(s=>`<option value="${s.id}">${s.name}</option>`).join("")}</select></div>
      <div>Тип: <select id="c_lt">${LU.lesson_types.map(s=>`<option value="${s.id}">${s.name}</option>`).join("")}</select></div>
      <button class="btn" id="c_create">Создать (с проверкой)</button>`;
    document.getElementById("c_create").onclick = createPair;
  }

  async function createPair(){
    const body = {
      date: document.getElementById("c_date").value,
      time_slot_id: +document.getElementById("c_slot").value,
      group_id: +document.getElementById("c_group").value,
      teacher_id: +document.getElementById("c_teacher").value,
      room_id: +document.getElementById("c_room").value,
      subject_id: +document.getElementById("c_subject").value,
      lesson_type_id: +document.getElementById("c_lt").value,
      is_remote: false, requires_computers: false,
    };
    // 1) предварительная проверка constraints
    try{
      const check = await api.post("/api/v1/admin/constraints/check", body);
      if(check.ok !== true || (check.errors||[]).length){
        toast("Нарушены ограничения: " + (check.errors||[]).map(e=>e.code).join(", "));
        return;
      }
    }catch(e){ toast("Ошибка /constraints/check"); return; }
    // 2) запись
    try{
      await api.post("/api/v1/admin/schedule", body);
      toast("Создано"); loadGrid();
    }catch(e){
      const codes = (e.response && e.response.errors || []).map(x=>x.code).join(", ");
      toast("Не удалось создать: "+codes);
    }
  }

  async function loadGrid(){
    if(!df.value || !dt.value) return;
    const js = await api.get(`/api/v1/admin/schedule?date_from=${df.value}&date_to=${dt.value}`);
    const items = js.items || [];
    const days = [];
    const d0 = new Date(df.value), d1=new Date(dt.value);
    for(let d=new Date(d0); d<=d1; d.setDate(d.getDate()+1)) days.push(new Date(d));

    const timeslots = LU.timeslots;
    function cellId(d, slotId){ return `${d.toISOString().slice(0,10)}_${slotId}`; }
    const index = new Map();
    items.forEach(it => index.set(cellId(new Date(it.date), it.time_slot_id), it));

    grid.innerHTML = `<table><thead><tr><th>Дата\\Слот</th>${
      timeslots.map(ts=>`<th>#${ts.order_no}</th>`).join("")
    }</tr></thead><tbody>${
      days.map(d=>{
        const dS = d.toISOString().slice(0,10);
        return `<tr><th>${dS}</th>${
          timeslots.map(ts=>{
            const key = `${dS}_${ts.id}`;
            const it = index.get(key);
            return `<td data-key="${key}">${
              it ? `<div class="card" data-id="${it.id}">
                      G${it.group_id}/T${it.teacher_id}/R${it.room_id}/S${it.subject_id}
                      <div><button class="btn flat" data-del="${it.id}">Удалить</button></div>
                    </div>` : `<div class="muted">пусто</div>`
            }</td>`;
          }).join("")
        }</tr>`;
      }).join("")
    }</tbody></table>`;

    // delete
    grid.querySelectorAll("button[data-del]").forEach(b=>{
      b.onclick = async ()=>{
        if(!confirm("Удалить пару?")) return;
        await api.del(`/api/v1/admin/schedule/${b.dataset.del}`);
        toast("Удалено"); loadGrid();
      };
    });
  }

  loadBtn.onclick = loadGrid;
  loadLU().then(()=>{
    const today = new Date().toISOString().slice(0,10);
    df.value = today; dt.value = today;
    loadGrid();
  });
})();
