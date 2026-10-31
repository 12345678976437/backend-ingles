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
 {id:'es',badge:'ES',grad:'linear-gradient(135deg,#ff9f43,#ff5c7a)',name:['Spanish','Español'],sub:['For English speakers','Para angloparlantes'],ready:true,landing:'espanol'},
 {id:'zh',badge:'中',grad:'linear-gradient(135deg,#ff5c5c,#ffd166)',name:['Chinese','Chino'],sub:['Mandarin · pinyin and tones','Mandarín · pinyin y tonos'],ready:true,landing:'chino'},
 {id:'chess',badge:'♟',grad:'linear-gradient(135deg,#5ee6a8,#6a7bff)',name:['Chess','Ajedrez'],sub:['Lessons, games and puzzles','Lecciones, partidas y problemas'],ready:true,landing:'ajedrez'}
];
/* secciones comunes a todos los cursos (progreso, cuenta, ajustes) */
const COMMON=['historial','logros','shop','admin','cuenta','notificaciones','configuracion','soporte'];
/* secciones propias de cada curso; el inglés incluye todo lo que no pertenece a otro curso */
const OWN={chess:['ajedrez'],es:['espanol'],zh:['chino']};
const OTHER=Object.values(OWN).reduce((a,b)=>a.concat(b),[]);
function allowed(course,name){
  if(name==='home')return course==='en';
  if(COMMON.includes(name))return true;
  if(course==='en')return !OTHER.includes(name);
  return (OWN[course]||[]).includes(name);
}
function get(){let c='en';try{c=localStorage.getItem('talvo_course')||'en'}catch(e){}return COURSES.find(x=>x.id===c&&x.ready)?c:'en'}
function byId(id){return COURSES.find(c=>c.id===id)||COURSES[0]}
let cur=get();


/* ---------- interfaz propia de cada curso: barra inferior y menú lateral ---------- */
const IC={
 home:'<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
 cards:'<rect x="3" y="6" width="14" height="11" rx="2"/><path d="M7 3h14v11"/>',
 learn:'<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M8 7h7M8 11h5"/>',
 mic:'<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
 chat:'<path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-8l-5 4v-4H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/><path d="M8 10h8M8 13h5"/>',
 play:'<circle cx="12" cy="6" r="3"/><path d="M9 10h6l1 5H8z"/><path d="M7 15h10v3H7zM6 21h12"/>',
 puzzle:'<path d="M9 3h3v3a2 2 0 1 0 4 0V3h3v6h-3a2 2 0 1 0 0 4h3v8H5v-8h3a2 2 0 1 0 0-4H5V3z"/>',
 menu:'<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>'
};
const LC_VIEWS=[['home','home',['Home','Inicio']],['learn','learn',['Lessons','Lecciones']],['speak','mic',['Speak','Hablar'],true],['tutor','chat',['Tutor','Tutor']]];
const VIEWS={es:LC_VIEWS,zh:LC_VIEWS,chess:[['play','play',['Play','Jugar']],['learn','learn',['Learn','Aprender']],['puzzles','puzzle',['Puzzles','Problemas']]]};
const SIDE={es:LC_VIEWS.concat([['vocab','cards',['Vocabulary','Vocabulario']]]),zh:LC_VIEWS.concat([['vocab','cards',['Vocabulary','Vocabulario']]])};
let curView='home',tabOrig=null;
const svg=p=>'<svg viewBox="0 0 24 24" aria-hidden="true">'+p+'</svg>';
function applyTabbar(){
  const tb=document.getElementById('tabbar');if(!tb)return;
  if(tabOrig===null)tabOrig=tb.innerHTML;
  const v=VIEWS[cur];
  if(!v){tb.innerHTML=tabOrig;tb.removeAttribute('data-n');tb.removeAttribute('data-i18n-skip');return}
  const land=byId(cur).landing;
  tb.dataset.n=v.length+1;tb.setAttribute('data-i18n-skip','1');
  tb.innerHTML=v.map(x=>'<button type="button" data-tab="'+land+'" data-view="'+x[0]+'"'+(x[3]?' class="tab-main"><div class="tab-hex">'+svg(IC[x[1]])+'</div>':'>'+svg(IC[x[1]]))+'<span>'+esc(L2(x[2]))+'</span></button>').join('')
    +'<button type="button" data-tab="menu">'+svg(IC.menu)+'<span>'+T('Menu','Menú')+'</span></button>';
  markTabs();
}
function markTabs(){
  const tb=document.getElementById('tabbar');if(!tb||!VIEWS[cur])return;
  const sec=document.querySelector('.section.active'),inCourse=sec&&sec.id==='sec-'+byId(cur).landing;
  tb.querySelectorAll('button').forEach(b=>b.classList.toggle('active',inCourse?(b.dataset.view===curView||(curView==='vocab'&&b.dataset.view==='learn')):b.dataset.tab==='menu'));
}
function applySide(){
  const nav=document.getElementById('main-nav');if(!nav)return;
  nav.querySelectorAll('[data-cnav]').forEach(e=>e.remove());
  const v=SIDE[cur]||VIEWS[cur];if(!v)return;
  const lab=document.createElement('div');lab.className='label';lab.dataset.cnav='1';lab.setAttribute('data-i18n-skip','1');lab.textContent=L2(byId(cur).name);
  const n=document.createElement('nav');n.className='nav';n.dataset.cnav='1';n.setAttribute('data-i18n-skip','1');
  n.innerHTML=v.map(x=>'<button type="button" data-cview="'+x[0]+'">'+svg(IC[x[1]])+'<span>'+esc(L2(x[2]))+'</span></button>').join('');
  n.addEventListener('click',e=>{const b=e.target.closest('[data-cview]');if(!b)return;go(b.dataset.cview);const o=document.getElementById('sidebar-overlay');if(o&&o.classList.contains('show'))o.click()});
  nav.insertBefore(n,nav.firstChild);nav.insertBefore(lab,n);
}
function go(view){
  const core=window.TalvoCore,land=byId(cur).landing,sec=document.querySelector('.section.active');
  if(!sec||sec.id!=='sec-'+land)core.section(land);
  setView(cur,view);
  if(cur==='chess'){window.TalvoChess&&TalvoChess.tab(view)}else if(window.TalvoLang)TalvoLang.view(cur,view);
}
function setView(course,v){if(course!==cur)return;curView=v;markTabs()}

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
    nav.querySelectorAll('button[data-section="ajedrez"]').forEach(b=>b.hidden=true);
    nav.querySelectorAll('button[data-tour]').forEach(b=>{b.hidden=cur!=='en'});
  }
  const home=document.getElementById('home-next');if(home)home.hidden=cur!=='en';
  const nm=L2(c.name);
  document.querySelectorAll('.brand-title span').forEach(s=>s.textContent=nm);
  pill();applyTabbar();applySide();
}
function pill(){
  const c=byId(cur),p=document.getElementById('course-pill');if(!p)return;
  p.innerHTML='<span class="cp-b" style="background:'+c.grad+'">'+c.badge+'</span><b data-i18n-skip>'+esc(L2(c.name))+'</b><i aria-hidden="true">▾</i>';
  p.setAttribute('aria-label',T('Change course. Current: ','Cambiar de curso. Actual: ')+L2(c.name));
}
function setCourse(id,goTo){
  const c=byId(id);if(!c.ready){toast(T('This course is coming soon.','Este curso llegará pronto.'));return}
  cur=c.id;try{localStorage.setItem('talvo_course',cur)}catch(e){}
  applyNav();closeModal();
  if(goTo!==false){
    const core=window.TalvoCore;
    if(goTo&&core&&core.section){core.section(c.landing);if(c.id==='es'||c.id==='zh'){curView='home';window.TalvoLang&&TalvoLang.view(c.id,'home')}}
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
window.TalvoCourses={get:()=>cur,set:setCourse,list:COURSES,allowed,go,setView,syncTabs(id){markTabs()},
  /* si se abre una sección de otro curso (p. ej. desde un enlace), cambia de curso sin mover la pantalla */
  onSection(name){
    if(allowed(cur,name)){markTabs();return}
    if(name==='home'&&cur!=='en'){const l=byId(cur).landing;setTimeout(()=>window.TalvoCore.section(l),0);return}
    const c=COURSES.find(x=>x.ready&&allowed(x.id,name));if(c)setCourse(c.id,false);
  }};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
