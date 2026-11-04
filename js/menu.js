/* Talvo · Menú: buscador de herramientas y una línea que explica cada una. */
(function(){
'use strict';
const lang=()=>{try{return window.TalvoI18n?TalvoI18n.get():'en'}catch(e){return 'en'}};
const D={
 'home':['Your daily plan and progress','Tu plan diario y tu progreso'],
 'learning-path':['Short lessons that adapt to your level','Lecciones cortas que se adaptan a tu nivel'],
 'lectura':['Read a text and explain it','Lee un texto y explícalo'],
 'escritura':['Write and get feedback','Escribe y recibe correcciones'],
 'escucha':['Listen and write what you hear','Escucha y escribe lo que oyes'],
 'vocabulario':['Build your word bank','Arma tu banco de palabras'],
 'tutor':['Chat with your AI tutor','Conversa con tu tutor IA'],
 'llamada':['Practice like a real phone call','Practica como en una llamada real'],
 'pronunciacion':['Improve your accent and clarity','Mejora tu acento y claridad'],
 'traductor':['Translate live','Traduce en vivo'],
 'escenarios':['Rehearse real conversations','Ensaya conversaciones reales'],
 'voz':['Shadowing, dictionary, meetings','Shadowing, diccionario, reuniones'],
 'clips':['Mini scenes with subtitles','Mini escenas con subtítulos'],
 'presentacion':['Rehearse your slides','Ensaya tus diapositivas'],
 'ajedrez':['Lessons, games and puzzles','Lecciones, partidas y problemas'],
 'historial':['Your stats and history','Tus estadísticas e historial'],
 'logros':['Badges and rewards','Medallas y recompensas'],
 'shop':['Spend your gems','Gasta tus gemas'],
 'cuenta':['Your profile and plan','Tu perfil y plan'],
 'notificaciones':['Reminders and alerts','Recordatorios y avisos'],
 'configuracion':['Language, sound, theme','Idioma, sonido, tema'],
 'soporte':['Report a problem or share an idea','Reporta un problema o comparte una idea'],
 'admin':['Admin panel','Panel de administración']
};
const T=(a)=>lang()==='es'?a[1]:a[0];
function describe(){
  document.querySelectorAll('#main-nav button[data-section]').forEach(b=>{
    const d=D[b.dataset.section];if(!d||b.closest('[data-cnav]'))return;
    let s=b.querySelector('.nv-d');
    if(!s){s=document.createElement('small');s.className='nv-d';s.setAttribute('data-i18n-skip','1');b.appendChild(s)}
    s.textContent=T(d);
  });
}
function filter(q){
  q=(q||'').trim().toLowerCase();
  const nav=document.getElementById('main-nav');if(!nav)return;
  nav.querySelectorAll('button').forEach(b=>{
    const hit=!q||b.textContent.toLowerCase().includes(q);
    if(hit)b.removeAttribute('data-nf');else b.setAttribute('data-nf','1');
  });
  Array.from(nav.children).forEach(el=>{
    if(el.tagName!=='NAV')return;
    const vis=Array.from(el.querySelectorAll('button')).some(b=>!b.hidden&&!b.hasAttribute('data-nf'));
    el.setAttribute('data-nf',vis?'':'1');if(vis)el.removeAttribute('data-nf');
    const lab=el.previousElementSibling;if(lab&&lab.classList.contains('label')){vis?lab.removeAttribute('data-nf'):lab.setAttribute('data-nf','1')}
  });
}
function init(){
  const nav=document.getElementById('main-nav');if(!nav||document.getElementById('nav-search'))return;
  const w=document.createElement('div');w.className='nav-search-w';
  w.innerHTML='<input id="nav-search" type="search" autocomplete="off" data-i18n-skip="1">';
  nav.parentNode.insertBefore(w,nav);
  const i=w.firstChild,ph=()=>{i.placeholder=lang()==='es'?'Buscar herramientas…':'Search tools…'};ph();
  i.addEventListener('input',()=>filter(i.value));
  document.addEventListener('click',e=>{if(e.target.closest&&e.target.closest('.js-lang-toggle'))setTimeout(()=>{ph();describe()},120)});
  new MutationObserver(()=>{describe();filter(i.value)}).observe(nav,{childList:true});
  describe();
  /* grupo "Studio" plegable: menos opciones a la vista */
  const tr=nav.querySelector('button[data-section="traductor"]'),g=tr&&tr.closest('nav.nav'),lab=g&&g.previousElementSibling;
  if(g&&lab&&lab.classList.contains('label')){
    g.classList.add('fold');lab.classList.add('fold-l');lab.setAttribute('role','button');lab.tabIndex=0;
    const tg=()=>{const o=g.classList.toggle('open');lab.classList.toggle('open',o)};
    lab.addEventListener('click',tg);lab.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();tg()}});
    i.addEventListener('input',()=>{const o=!!i.value.trim();g.classList.toggle('srch',o)});
  }
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
window.TalvoMenu={describe,filter};
})();
