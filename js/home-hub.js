/* Talvo · "Mis aprendizajes": acceso a los 4 cursos con su progreso, en el Inicio. */
(function(){
'use strict';
const lang=()=>{try{return window.TalvoI18n&&window.TalvoI18n.get()==='es'?'es':'en'}catch(e){return 'en'}};
const T=(a,b)=>lang()==='es'?b:a;
const ls=(k,d)=>{try{const v=localStorage.getItem(k);return v?JSON.parse(v):d}catch(e){return d}};
const UNITS={es:()=>window.TALVO_COURSE_ES&&TALVO_COURSE_ES.units,zh:()=>window.TALVO_COURSE_ZH&&TALVO_COURSE_ZH.units};
const ICON={
 en:'<svg viewBox="0 0 24 24"><path d="M4 7h9M8.500 5v2M6 7c.6 3 2.500 5.200 5.500 6.800M11.500 7c-.7 3.400-3.200 5.800-6.500 7"/><path d="M13 20l4-9 4 9M14.300 17h5.400"/></svg>',
 es:'<svg viewBox="0 0 24 24"><path d="M5 19V9a4 4 0 0 1 8 0v10M5 14h8M17 19v-6M17 8.500v.01"/></svg>',
 zh:'<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="1.500"/><path d="M12 4v16M4 12h16"/></svg>',
 chess:'<svg viewBox="0 0 24 24"><path d="M9 20h6M8 20c0-3 1-4 1.500-6-2-1-3-3-2-5 1-2 3-3 5-2l1-3 2 3c2 1 3 3 2 5-.5 1.500-1.500 2.500-2.500 3 .5 2 1.500 3 1.500 5"/></svg>'
};
function stat(c){
  if(c.id==='es'||c.id==='zh'){const u=(UNITS[c.id]()||[]),p=ls('talvo_lc_'+c.id,{});const d=u.filter(x=>p[x.id]).length;return{pct:u.length?Math.round(d/u.length*100):0,txt:d+'/'+u.length+' '+T('units','unidades')}}
  if(c.id==='chess'){const s=ls('talvo_chess_stats',{w:0,d:0,l:0}),n=s.w+s.d+s.l;return{pct:null,txt:n?n+' '+T('games · '+s.w+' won','partidas · '+s.w+' ganadas'):T('Play now','Juega ahora')}}
  const lv=(document.getElementById('hs-lv')||{}).textContent||'1',xp=(document.getElementById('hs-xp')||{}).textContent||'0';
  const g=parseInt((document.getElementById('home-goal-pct')||{}).textContent,10)||0;return{pct:g,txt:T('Lv ','Nv ')+lv+' · '+g+'% '+T('today','hoy')}
}
function render(){
  const box=document.getElementById('home-courses');if(!box||!window.TalvoCourses)return;
  const cur=TalvoCourses.get();
  box.innerHTML='<h2 class="sec-h">'+T('My learning','Mis aprendizajes')+'</h2><div class="hc-grid">'+TalvoCourses.list.filter(c=>c.ready).map(c=>{
    const s=stat(c),nm=lang()==='es'?c.name[1]:c.name[0];
    return '<button type="button" class="hc-c" data-hcc="'+c.id+'" data-cc="'+c.id+'"'+(c.id===cur?' aria-current="true"':'')+'><span class="hc-b">'+ICON[c.id]+'</span><span class="hc-x"><b>'+nm+'</b><small>'+s.txt+'</small>'+(s.pct!=null?'<i class="hc-p"><u style="width:'+s.pct+'%"></u></i>':'')+'</span></button>'}).join('')+'</div>';
}
document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('[data-hcc]');if(!b||!window.TalvoCourses)return;TalvoCourses.set(b.dataset.hcc,true)});
function init(){render();const h=document.getElementById('sec-home');if(h)new MutationObserver(()=>{if(h.classList.contains('active'))render()}).observe(h,{attributes:true,attributeFilter:['class']});
  document.addEventListener('talvo:lang',render)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(init,0));else setTimeout(init,0);
window.TalvoHub={render};
})();
