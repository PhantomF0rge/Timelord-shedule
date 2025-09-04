export function parseTime(hhmm){ const [h,m]=hhmm.split(':').map(Number); const d=new Date(); d.setHours(h,m,0,0); return d; }
export function now(){ return new Date(); }
export function statusForSlot(start,end,isRemote=false){
  const s=parseTime(start), e=parseTime(end), n=now();
  if(n<s) return isRemote?'remote-next':'next';
  if(n>e) return isRemote?'remote-past':'past';
  return isRemote?'remote':'now';
}
