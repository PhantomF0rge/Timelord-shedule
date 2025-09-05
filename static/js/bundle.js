(function(){
  // ---- DOM utils ----
  function $(sel, root){ return (root||document).querySelector(sel); }
  function $all(sel, root){ return Array.from((root||document).querySelectorAll(sel)); }
  function show(el){ if(el) el.hidden = false; }
  function hide(el){ if(el) el.hidden = true; }

  // ---- Time utils ----
  function parseTime(hhmm){
    var parts = (hhmm||"").split(":");
    var h = parseInt(parts[0]||"0",10), m = parseInt(parts[1]||"0",10);
    var d = new Date(); d.setHours(h,m,0,0); return d;
  }
  function statusForSlot(start,end,isRemote){
    var s=parseTime(start), e=parseTime(end), n=new Date();
    if(n < s) return isRemote ? "remote-next" : "next";
    if(n > e) return isRemote ? "remote-past" : "past";
    return isRemote ? "remote" : "now";
  }

  // ---- Typeahead ----
  function initTypeahead(){
    var input = $("#search-input");
    var box = $("#typeahead");
    if(!input || !box) return;

    var timer = null;

    function render(items){
      if(!items || !items.length){
        hide(box); box.innerHTML=""; return;
      }
      box.innerHTML = items.map(function(i){
        return '<div class="typeahead-item" data-type="'+(i.type||'')+'" data-id="'+(i.id||'')+'" data-code="'+(i.code||'')+'">'+
                 '<span class="typeahead-type">'+(i.type||'')+'</span>'+
                 '<span class="typeahead-label">'+(i.label||'')+'</span>'+
               '</div>';
      }).join("");
      show(box);
    }

    async function fetchSuggest(q){
      try{
        var url = "/api/v1/suggest?q="+encodeURIComponent(q)+"&limit=10";
        var r = await fetch(url);
        if(!r.ok) throw new Error("suggest failed");
        var data = await r.json();
        return data.items || [];
      }catch(e){
        return [];
      }
    }

    input.addEventListener("input", function(){
      var q = input.value.trim();
      if(timer) clearTimeout(timer);
      if(!q){ hide(box); box.innerHTML=""; return; }
      timer = setTimeout(async function(){
        var items = await fetchSuggest(q);
        render(items);
      }, 300);
    });

    var clearBtn = $("#search-clear");
    if(clearBtn){
      clearBtn.addEventListener("click", function(){
        input.value=""; hide(box); box.innerHTML="";
      });
    }

    box.addEventListener("click", function(e){
      var item = e.target.closest(".typeahead-item");
      if(!item) return;
      var type = item.getAttribute("data-type");
      var code = item.getAttribute("data-code") || "";
      if(type==="group" && code){
        localStorage.setItem("last_group", code);
        document.dispatchEvent(new CustomEvent("select-group", { detail: { code: code } }));
      }
      hide(box);
    });

    document.addEventListener("click", function(e){
      if(!box.contains(e.target) && e.target !== input){ hide(box); }
    });
  }

  // ---- Schedule view ----
  function lessonView(l){
    if(l.is_break){
      return '<div class="break-item"><strong>Перерыв</strong> · '+l.from+'–'+l.to+'</div>';
    }
    var status = statusForSlot(l.time_slot.start_time, l.time_slot.end_time, !!l.is_remote);
    var cls = ["lesson"];
    if(status.indexOf("now")>=0 || status==="remote") cls.push("now");
    else if(status.indexOf("next")>=0) cls.push("next");
    else if(status.indexOf("past")>=0) cls.push("past");
    if(l.is_remote) cls.push("remote");

    var ltype = (l.lesson_type && (l.lesson_type.name||l.lesson_type.title)) || "Занятие";
    var room = l.room ? (" · ауд. " + (l.room.number||"")) : " · СДО";
    var hw   = l.homework ? (" · ДЗ: " + (l.homework.text||"")) : "";

    return '<article class="'+cls.join(" ")+'">'+
             '<div class="title">'+(l.subject.name||l.subject.title||"Предмет")+' <span class="meta">· '+ltype+'</span></div>'+
             '<div class="meta">'+
               l.time_slot.start_time+'–'+l.time_slot.end_time+' · №'+l.time_slot.order_no+
               room+
               ' · '+(l.teacher.full_name || [l.teacher.last_name,l.teacher.first_name,l.teacher.middle_name].filter(Boolean).join(" "))+
               hw+
             '</div>'+
           '</article>';
  }

  function renderSchedule(payload){
    var root = $("#schedule-root");
    if(!root) return;
    if(!payload || !payload.lessons || !payload.lessons.length){
      root.dataset.state="empty";
      root.innerHTML = '<div class="muted">Нет занятий на выбранный день.</div>';
      return;
    }
    root.dataset.state="filled";
    root.innerHTML = payload.lessons.map(lessonView).join("");
  }

  async function fetchGroupSchedule(code){
    try{
      var today = new Date().toISOString().slice(0,10);
      var url = "/api/v1/schedule/group/"+encodeURIComponent(code)+"?date="+today+"&range=day";
      var r = await fetch(url);
      if(!r.ok) throw new Error("schedule failed");
      return await r.json();
    }catch(e){
      return { lessons: [] };
    }
  }

  function boot(){
    initTypeahead();

    var code = localStorage.getItem("last_group");
    if(code){
      var quick = $("#quick-result");
      if(quick){ quick.innerHTML = 'Показываю расписание для группы <strong>'+code+'</strong>.'; show(quick); }
      fetchGroupSchedule(code).then(renderSchedule);
    }

    document.addEventListener("select-group", function(e){
      var code = e.detail.code;
      fetchGroupSchedule(code).then(renderSchedule);
      var quick = $("#quick-result");
      if(quick){ quick.innerHTML = 'Показываю расписание для группы <strong>'+code+'</strong>.'; show(quick); }
    });
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
