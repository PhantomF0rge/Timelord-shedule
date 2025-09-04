import { $, show, hide } from "../utils/dom.js";

const API = "/api/v1/suggest";
const input = () => $("#search-input");
const box = () => $("#typeahead");

let timer = null;

async function fetchSuggest(q){
  try{
    const url = `${API}?q=${encodeURIComponent(q)}&limit=10`;
    const r = await fetch(url);
    if(!r.ok) throw new Error("suggest failed");
    const data = await r.json();
    return data.items || [];
  }catch(e){
    return []; // заглушка, пока бэкенд не подключили
  }
}

function render(items){
  const el = box();
  if(!items.length){ hide(el); el.innerHTML=""; return; }
  el.innerHTML = items.map(i => `
    <div class="typeahead-item" data-type="${i.type}" data-id="${i.id}" data-code="${i.code||''}">
      <span class="typeahead-type">${i.type}</span>
      <span class="typeahead-label">${i.label}</span>
    </div>
  `).join("");
  show(el);
}

function bindClicks(){
  box()?.addEventListener("click", (e)=>{
    const item = e.target.closest(".typeahead-item");
    if(!item) return;
    const type = item.dataset.type;
    const code = item.dataset.code;
    if(type==="group" && code){
      localStorage.setItem("last_group", code);
      document.dispatchEvent(new CustomEvent("select-group", { detail: { code } }));
    }
    hide(box());
  });
}

export function initTypeahead(){
  const el = input();
  if(!el) return;
  bindClicks();
  el.addEventListener("input", ()=>{
    const q = el.value.trim();
    if(timer) clearTimeout(timer);
    if(!q){ hide(box()); return; }
    timer = setTimeout(async ()=>{ render(await fetchSuggest(q)); }, 300);
  });
  $("#search-clear")?.addEventListener("click", ()=>{
    el.value=""; hide(box());
  });
}
