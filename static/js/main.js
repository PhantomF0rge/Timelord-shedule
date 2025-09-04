// Basic stub for saving last selected group in localStorage
window.ScheduleApp = (function(){
  function saveLastGroup(code){ try{ localStorage.setItem('last_group', code); }catch(e){} }
  function getLastGroup(){ try{ return localStorage.getItem('last_group'); }catch(e){ return null; } }
  return { saveLastGroup, getLastGroup };
})();
