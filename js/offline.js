/* Talvo · modo sin conexión
   - Guarda en el teléfono lo último que viste (mapa de rutas, lecciones, panel) para poder abrirlo sin internet.
   - Si no hay internet, entra a la app con tu última sesión verificada (solo para ver y practicar).
   - Lo que completes sin internet se queda en una cola y se envía solo al reconectar.
   Nada de esto reemplaza al servidor: el servidor sigue validando todo cuando vuelve la conexión.
   Se carga ANTES de core.js y no depende de él. */
(function(){
'use strict';
const K={snap:'talvo_off_user',idx:'talvo_off_idx',q:'talvo_off_q',pre:'talvo_off_pre',c:'talvo_c:'};
const MAX_KEYS=90,MAX_Q=100,SNAP_DAYS=45,Q_DAYS=14;
let LS=null;try{LS=window.localStorage}catch(e){}
const jget=(k,d)=>{try{const v=JSON.parse(LS.getItem(k));return v==null?d:v}catch(e){return d}};
const jset=(k,v)=>{try{LS.setItem(k,JSON.stringify(v));return true}catch(e){return false}};
const PATHS=/^\/api\/(learning-path|learning-path\/daily-plan|learning-path\/lesson\/[^/?]+\/[^/?]+|dashboard|achievements|vocabulario)$/;
let uid='anon';

const OFF={
  isOff(){return navigator.onLine===false},
  isNetErr(e){return !!e&&(e instanceof TypeError||/failed to fetch|networkerror|load failed|network request failed/i.test(String(e.message||'')))},
  setUser(id){if(id)uid=String(id)},

  /* ---- última sesión verificada (solo datos de pantalla, nunca tokens) ---- */
  snapSave(user,d){
    if(!user||!d)return;
    jset(K.snap,{id:user.id,email:user.email||'',sub:!!d.is_subscribed,trial:!!d.en_prueba,days:d.trial_dias_restantes||0,
                 onboarded:!(d.user&&d.user.onboarded===false),ts:Date.now()});
    OFF.setUser(user.id)
  },
  snap(){
    const s=jget(K.snap,null);
    if(!s||!s.id||!s.sub||!s.onboarded)return null;
    if(Date.now()-(s.ts||0)>SNAP_DAYS*864e5)return null;
    return s
  },

  /* ---- caché de lo que viste (por usuario) ---- */
  cacheable(path){const p=String(path||'').split('?')[0];return PATHS.test(p)&&!/[?&]mode=(review|focus)/.test(path)},
  key(path){return K.c+uid+':'+path},
  put(path,data){
    if(!LS||!OFF.cacheable(path))return;
    const key=OFF.key(path);let idx=jget(K.idx,[]);
    const write=()=>{try{LS.setItem(key,JSON.stringify({t:Date.now(),d:data}));return true}catch(e){return false}};
    if(!write()){ // sin espacio: suelta lo más viejo y reintenta una vez
      idx.slice(0,20).forEach(k=>{try{LS.removeItem(k)}catch(e){}});idx=idx.slice(20);jset(K.idx,idx);
      if(!write())return
    }
    idx=idx.filter(k=>k!==key);idx.push(key);
    while(idx.length>MAX_KEYS){try{LS.removeItem(idx.shift())}catch(e){}}
    jset(K.idx,idx)
  },
  get(path){
    if(!LS)return null;
    const c=jget(OFF.key(path),null);return c&&c.d!==undefined?c.d:null
  },
  clearUser(){ // al cerrar sesión: nada del usuario anterior se queda en el teléfono
    try{
      jget(K.idx,[]).forEach(k=>LS.removeItem(k));LS.removeItem(K.idx);LS.removeItem(K.snap);LS.removeItem(K.q);LS.removeItem(K.pre)
    }catch(e){}
  },

  /* ---- sin internet: qué se puede contestar desde el teléfono ---- */
  handle(path,options){
    const method=String((options&&options.method)||'GET').toUpperCase();
    if(method==='GET'){
      const c=OFF.get(path);
      return c==null?undefined:Object.assign({},c,{__offline:true})
    }
    if(method==='POST'&&String(path).split('?')[0]==='/api/learning-path/complete')return OFF.completeOffline(options)
    return undefined
  },

  /* ---- cola de avances ---- */
  q(){return jget(K.q,[]).filter(i=>i&&Date.now()-(i.ts||0)<Q_DAYS*864e5)},
  qCount(){return OFF.q().length},
  completeOffline(options){
    let body={};try{body=JSON.parse(options.body||'{}')}catch(e){}
    const q=OFF.q();if(q.length>=MAX_Q)throw new Error('Too many lessons waiting to sync. Connect to the internet first.');
    q.push({path:'/api/learning-path/complete',body:options.body,ts:Date.now()});jset(K.q,q);
    let total=Math.max(1,Math.min(40,+body.total||1)),correct=Math.max(0,Math.min(total,+body.correct||0));
    const kind=body.kind||'lesson';
    const score=kind==='sound'?Math.max(0,Math.min(100,+body.score||0)):Math.round(1000*correct/total)/10;
    const passed=score>=60,stars=score>=90?3:score>=75?2:passed?1:0;
    const next=kind==='lesson'?OFF.patchMap(body.unit_code,body.lesson_id,score,passed,stars):null;
    OFF.badge();
    return{ok:true,kind,score,best:score,stars,passed,first_time:false,xp:0,unit_bonus:0,unit_completed:false,
           mistakes:(body.mistakes||[]).length,next,plan_bonus:0,level_change:null,offline:true}
  },
  /* marca la lección como hecha en el mapa guardado y abre la siguiente, para seguir avanzando sin internet */
  patchMap(unitCode,lessonId,score,passed,stars){
    const path='/api/learning-path',d=OFF.get(path);if(!d)return null;
    let next=null;
    const fix=u=>{
      if(!u||u.code!==unitCode||!Array.isArray(u.lessons))return;
      const i=u.lessons.findIndex(l=>l.id===lessonId);if(i<0)return;
      const l=u.lessons[i];
      if(passed||l.completed){l.completed=true;l.state='done';l.score=Math.max(l.score||0,score);l.stars=Math.max(l.stars||0,stars)}
      const n=u.lessons[i+1];
      if(passed&&n&&n.state==='locked'){n.state='available'}
      if(passed&&n){next={unit_code:u.code,lesson_id:n.id,lesson_title:n.title}}
      u.completed_topics=u.lessons.filter(x=>x.completed).length;u.completed=u.completed_topics===u.lessons.length
    };
    (d.units||[]).forEach(fix);(d.sections||[]).forEach(s=>(s.units||[]).forEach(fix));
    try{LS.setItem(OFF.key(path),JSON.stringify({t:Date.now(),d}))}catch(e){}
    return next
  },
  running:false,
  async flush(){
    if(OFF.running||OFF.isOff())return 0;
    const core=window.TalvoCore;if(!core||!core.state||!core.state.user)return 0;
    OFF.running=true;let sent=0;
    try{
      for(;;){
        const q=OFF.q();if(!q.length){jset(K.q,[]);break}
        const it=q[0];let r;
        try{r=await core.authFetch(it.path,{method:'POST',headers:{'Content-Type':'application/json'},body:it.body})}
        catch(e){break} // sin red o sin sesión: se queda en la cola
        if(r.ok||(r.status>=400&&r.status<500&&r.status!==401&&r.status!==429)){q.shift();jset(K.q,q);sent++}
        else break
      }
    }finally{OFF.running=false}
    OFF.badge();
    if(sent){
      try{core.toast('Progress synced ✓')}catch(e){}
      try{if(window.LP&&window.LP.data&&!document.body.classList.contains('lp-open')&&window.loadLearningPath)window.loadLearningPath()}catch(e){}
    }
    return sent
  },

  /* ---- descarga silenciosa de las próximas lecciones (solo con internet y sin ahorro de datos) ---- */
  async prefetch(map){
    try{
      if(OFF.isOff()||!map||!window.TalvoCore)return;
      const c=navigator.connection;if(c&&(c.saveData||/^(slow-2g|2g)$/.test(c.effectiveType||'')))return;
      const last=jget(K.pre,{})[uid]||0;if(Date.now()-last<6*3600e3)return;
      const todo=[];
      (map.units||[]).forEach(u=>(u.lessons||[]).forEach(l=>{if(!l.challenge&&l.state==='available')todo.push([u.code,l.id])}));
      const pre=jget(K.pre,{});pre[uid]=Date.now();jset(K.pre,pre);
      for(const [u,l] of todo.slice(0,8)){
        if(OFF.isOff())break;
        try{await window.TalvoCore.jsonFetch('/api/learning-path/lesson/'+encodeURIComponent(u)+'/'+encodeURIComponent(l))}catch(e){}
        await new Promise(r=>setTimeout(r,500))
      }
    }catch(e){}
  },

  /* ---- aviso en pantalla ---- */
  badge(){
    const n=OFF.qCount(),on=OFF.isOff();
    let b=document.getElementById('off-banner');
    if(!on&&!n){if(b)b.remove();document.body.classList.remove('is-offline');return}
    document.body.classList.toggle('is-offline',on);
    if(!b){b=document.createElement('div');b.id='off-banner';b.setAttribute('role','status');document.body.appendChild(b)}
    b.textContent=on?(n?'Offline · '+n+' lesson'+(n===1?'':'s')+' will sync when you reconnect':'Offline mode: you can practice lessons. Calls and AI tools need internet.'):'Syncing your progress…'
  },
  /* secciones que funcionan sin internet */
  allowed(name){return ['home','learning-path','vocabulario','vocabulary','tutorial','cuenta'].includes(name)}
};

window.TalvoOffline=OFF;
/* el service worker guarda la app para abrirla sin internet (el mismo sw.js de las notificaciones) */
try{if('serviceWorker' in navigator&&(location.protocol==='https:'||location.hostname==='localhost'))window.addEventListener('load',()=>navigator.serviceWorker.register('sw.js').catch(()=>{}))}catch(e){}
window.addEventListener('offline',()=>OFF.badge());
window.addEventListener('online',()=>{OFF.badge();setTimeout(()=>OFF.flush(),1200)});
document.addEventListener('DOMContentLoaded',()=>OFF.badge());
})();
