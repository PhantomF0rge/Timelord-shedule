export function parseTime(hhmm){
  const [h,m]=hhmm.split(':').map(Number);
  const d=new Date();
  d.setHours(h,m,0,0);
  return d;
}
export function now(){ return new Date(); }

export function statusForSlot(start,end, isRemote=false){
  const s=parseTime(start), e=parseTime(end), n=now();
  if(n<s) return isRemote?'remote-next':'next';
  if(n>e) return isRemote?'remote-past':'past';
  return isRemote?'remote':'now';
}

/* Доп. утилиты для дня/недели */
export function isoDate(d){
  const y=d.getFullYear();
  const m=String(d.getMonth()+1).padStart(2,'0');
  const day=String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${day}`;
}
export function startOfWeek(d){
  const dt=new Date(d);
  const wd=dt.getDay(); // 0=Sun .. 6=Sat
  // хотим Понедельник — сдвиг назад: (wd+6)%7
  const shift=(wd+6)%7;
  dt.setDate(dt.getDate()-shift);
  dt.setHours(0,0,0,0);
  return dt;
}
export function weekDates(anchor){
  const mon=startOfWeek(anchor);
  return Array.from({length:7},(_,i)=>{
    const d=new Date(mon);
    d.setDate(mon.getDate()+i);
    return isoDate(d);
  });
}
export function humanDayShort(date){
  // date: Date
  const days=['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];
  return days[date.getDay()];
}
export function humanDateCompact(iso){
  const d=new Date(iso+'T00:00:00');
  const dd=String(d.getDate()).padStart(2,'0');
  const mm=String(d.getMonth()+1).padStart(2,'0');
  return `${dd}.${mm}`;
}
