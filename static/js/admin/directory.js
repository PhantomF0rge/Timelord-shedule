(async function(){
  const entity = window.__DIR_ENTITY__ || "groups";
  // простая карта API (используй уже существующие эндпоинты проекта)
  const map = {
    groups: {list:"/api/v1/admin/groups", create:"/api/v1/admin/groups", item:(id)=>`/api/v1/admin/groups/${id}`},
    teachers:{list:"/api/v1/admin/teachers", create:"/api/v1/admin/teachers", item:(id)=>`/api/v1/admin/teachers/${id}`},
    rooms:   {list:"/api/v1/admin/rooms", create:"/api/v1/admin/rooms", item:(id)=>`/api/v1/admin/rooms/${id}`},
    subjects:{list:"/api/v1/admin/subjects", create:"/api/v1/admin/subjects", item:(id)=>`/api/v1/admin/subjects/${id}`},
    "lesson-types":{list:"/api/v1/admin/lesson-types", create:"/api/v1/admin/lesson-types", item:(id)=>`/api/v1/admin/lesson-types/${id}`},
    timeslots:{list:"/api/v1/admin/time-slots", create:"/api/v1/admin/time-slots", item:(id)=>`/api/v1/admin/time-slots/${id}`},
    buildings:{list:"/api/v1/admin/buildings", create:"/api/v1/admin/buildings", item:(id)=>`/api/v1/admin/buildings/${id}`},
    "room-types":{list:"/api/v1/admin/room-types", create:"/api/v1/admin/room-types", item:(id)=>`/api/v1/admin/room-types/${id}`},
  };
  const cfg = map[entity];
  const root = document.getElementById("dir-root");
  if(!cfg){ root.innerHTML = `<div class="card">Неизвестный справочник</div>`; return; }

  function toast(msg){ const t=document.createElement("div");t.className="toast";t.textContent=msg;document.body.append(t);setTimeout(()=>t.remove(),3000); }

  async function load(){
    try{
      const js = await api.get(cfg.list);
      const items = js.items || js.data || js || [];
      root.innerHTML = `<div class="card">
        <button class="btn" id="add">Добавить</button>
        <table><thead><tr><th>ID</th><th>Название</th><th></th></tr></thead>
        <tbody>${items.map(x=>`<tr><td>${x.id}</td><td>${x.name||x.code||x.number||x.full_name||"-"}</td>
        <td><button class="btn flat" data-id="${x.id}">Удалить</button></td></tr>`).join("")}</tbody></table></div>`;
      root.querySelectorAll("button[data-id]").forEach(b=>{
        b.onclick = async ()=>{
          if(!confirm("Удалить?")) return;
          try{ await api.del(cfg.item(b.dataset.id)); load(); }catch(e){ toast("Ошибка удаления"); }
        };
      });
      root.querySelector("#add").onclick = async ()=>{
        const name = prompt("Название/код:");
        if(!name) return;
        try{ await api.post(cfg.create, {name, code:name, number:name}); load(); }catch(e){ toast("Ошибка создания"); }
      };
    }catch(e){ root.innerHTML = `<div class="card">Ошибка загрузки</div>`; }
  }
  load();
})();
