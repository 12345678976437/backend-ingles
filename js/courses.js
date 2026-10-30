/* Talvo · Cursos: selector arriba (como Duolingo). Cada curso muestra solo sus secciones en el menú.
   El curso elegido se guarda en este dispositivo (talvo_course). */
(function(){
'use strict';
const lang=()=>{try{return window.TalvoI18n?TalvoI18n.get():'en'}catch(e){return 'en'}};
const T=(en,es)=>lang()==='es'?es:en;
const L2=a=>lang()==='es'?a[1]:a[0];
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const COURSES=[
 {id:'en',badge:'EN',grad:'linear-gradient(135deg,#38e1ff,#6a7bff)',name:['English','Inglés'],sub:['For Spanish speakers','Para hispanohablantes'],ready:true,landing:'home'},
 {id:'es',badge:'ES',grad:'linear-gradient(135deg,#ff9f43,#ff5c7a)',name:['Spanish','Español'],sub:['For English speakers','Para angloparlantes'],ready:false,landing:'espanol'},
 {id:'zh',badge:'中',grad:'linear-gradient(135deg,#ff5c5c,#ffd166)',name:['Chinese','Chino'],sub:['Mandarin · pinyin and tones','Mandarín · pinyin y tonos'],ready:false,landing:'chino'},
 {id:'chess',badge:'♟',grad:'linear-gradient(135deg,#5ee6a8,#6a7bff)',name:['Chess','Ajedrez'],sub:['Lessons, games and puzzles','Lecciones, partidas y problemas'],ready:true,landing:'ajedrez'}
];
/* secciones comunes a todos los cursos (progreso, cuenta, ajustes) */
const COMMON=['home','historial','logros','shop','admin','cuenta','notificaciones','configuracion','soporte'];
/* secciones propias de cada curso; el inglés incluye todo lo que no pertenece a otro curso */
const OWN={chess:['ajedrez'],es:['espanol'],zh:['chino']};
const OTHER=Object.values(OWN).reduce((a,b)=>a.concat(b),[]);
function allowed(course,name){
  if(COMMON.includes(name))return true;
  if(course==='en')return !OTHER.includes(name);
  return (OWN[course]||[]).includes(name);
}
function get(){let c='en';try{c=localStorage.getItem('talvo_course')||'en'}catch(e){}return COURSES.find(x=>x.id===c&&x.ready)?c:'en'}
function byId(id){return COURSES.find(c=>c.id===id)||COURSES[0]}
let cur=get();

function applyNav(){
  const c=byId(cur);
  document.body.dataset.course=cur;
  document.querySelectorAll('#main-nav [data-section]').forEach(b=>{b.hidden=!allowed(cur,b.dataset.section)});
  document.querySelectorAll('[data-section-jump]').forEach(b=>{b.hidden=!allowed(cur,b.dataset.sectionJump)});
  /* oculta los títulos de grupo y los grupos que quedaron vacíos */
  const nav=document.getElementById('main-nav');
  if(nav){
    Array.from(nav.children).forEach(el=>{
      if(el.tagName==='NAV'){const vis=Array.from(el.querySelectorAll('button')).some(b=>!b.hidden);el.hidden=!vis;const lab=el.previousElementSibling;if(lab&&lab.classList.contains('label'))lab.hidden=!vis}
    });
    nav.querySelectorAll('button[data-tour]').forEach(b=>{b.hidden=cur!=='en'});
  }
  const home=document.getElementById('home-next');if(home)home.hidden=cur!=='en';
  const nm=L2(c.name);
  document.querySelectorAll('.brand-title span').forEach(s=>s.textContent=nm);
  pill();
}
function pill(){
  const c=byId(cur),p=document.getElementById('course-pill');if(!p)return;
  p.innerHTML='<span class="cp-b" style="background:'+c.grad+'">'+c.badge+'</span><b data-i18n-skip>'+esc(L2(c.name))+'</b><i aria-hidden="true">▾</i>';
  p.setAttribute('aria-label',T('Change course. Current: ','Cambiar de curso. Actual: ')+L2(c.name));
}
function setCourse(id,go){
  const c=byId(id);if(!c.ready){toast(T('This course is coming soon.','Este curso llegará pronto.'));return}
  cur=c.id;try{localStorage.setItem('talvo_course',cur)}catch(e){}
  applyNav();closeModal();
  if(go!==false){
    const core=window.TalvoCore;
    if(go&&core&&core.section)core.section(c.landing);
  }
}
function toast(m){try{window.TalvoCore.toast(m)}catch(e){}}
function openModal(){
  let m=document.getElementById('course-modal');
  if(!m){m=document.createElement('div');m.id='course-modal';m.className='modal';document.body.appendChild(m);
    m.addEventListener('click',e=>{if(e.target===m){closeModal();return}const b=e.target.closest('[data-course]');if(b)setCourse(b.dataset.course,true);if(e.target.closest('#course-close'))closeModal()})}
  m.innerHTML='<div class="modal-card course-card" data-i18n-skip><h2>'+T('Choose a course','Elige un curso')+'</h2><p class="cc-sub">'+T('Your progress, streak and account are shared across courses.','Tu progreso, racha y cuenta son los mismos en todos los cursos.')+'</p>'
    +COURSES.map(c=>'<button type="button" class="cc-item'+(c.id===cur?' on':'')+(c.ready?'':' soon')+'" data-course="'+c.id+'"><span class="cp-b big" style="background:'+c.grad+'">'+c.badge+'</span><span class="cc-t"><b>'+esc(L2(c.name))+'</b><small>'+esc(L2(c.sub))+'</small></span>'+(c.id===cur?'<em>✓</em>':(c.ready?'':'<em class="sn">'+T('Soon','Pronto')+'</em>'))+'</button>').join('')
    +'<button type="button" class="btn" id="course-close" style="width:100%;margin-top:10px">'+T('Close','Cerrar')+'</button></div>';
  m.style.display='flex';
}
function closeModal(){const m=document.getElementById('course-modal');if(m)m.style.display='none'}

function init(){
  const tb=document.querySelector('.topbar-brand');
  if(tb&&!document.getElementById('course-pill')){
    const b=tb.querySelector('b');if(b)b.remove();
    const p=document.createElement('button');p.type='button';p.id='course-pill';p.className='course-pill';tb.appendChild(p);
    p.addEventListener('click',openModal);
  }
  document.addEventListener('click',e=>{if(e.target.closest&&e.target.closest('.js-lang-toggle'))setTimeout(()=>{pill();applyNav()},80)});
  applyNav();
}
window.TalvoCourses={get:()=>cur,set:setCourse,list:COURSES,allowed,
  /* si se abre una sección de otro curso (p. ej. desde un enlace), cambia de curso sin mover la pantalla */
  onSection(name){
    if(allowed(cur,name))return;
    const c=COURSES.find(x=>x.ready&&allowed(x.id,name));if(c)setCourse(c.id,false);
  }};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
