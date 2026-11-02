/* Talvo · Palanqueta con más expresiones (celebrando, sorprendida, confundida, motivando, enseñando).
   Se dibujan con animaciones y un globo de emoji sobre la mascota actual: sin imágenes nuevas. */
(function(){
'use strict';
const FX={pensando:'',celebrando:'',sorprendida:'',confundida:'',motivando:'',ensenando:'',feliz:'',triste:''};
const POSES=['normal','feliz','triste','pensando','celebrando','sorprendida','confundida','motivando','ensenando','habla-abierta','habla-cerrada'];
const POSE_OF={idle:'normal',normal:'normal',feliz:'feliz',triste:'triste',pensando:'pensando',celebrando:'celebrando',sorprendida:'sorprendida',confundida:'confundida',motivando:'motivando',ensenando:'ensenando'};
let curPose='normal',talkT=null;
const src=n=>'img/pq/pq-'+n+'.webp';
function pose(n){const i=document.getElementById('mascot-pose');if(i&&n&&curPose!==n){curPose=n;i.src=src(n)}}
function stateOf(m){const c=(m.className.match(/state-(\w+)/)||[])[1];return POSE_OF[c]||'normal'}
function setup(){
  const m=document.getElementById('mascot'),layer=m&&m.querySelector('.layer');if(!layer||document.getElementById('mascot-pose'))return;
  POSES.forEach(n=>{const p=new Image();p.src=src(n)});
  const i=document.createElement('img');i.id='mascot-pose';i.alt='';i.draggable=false;i.src=src('normal');layer.insertBefore(i,layer.firstChild);m.classList.add('pq-poses');
  new MutationObserver(()=>{if(!m.classList.contains('pq-poses'))m.classList.add('pq-poses');if(!talkT)pose(stateOf(m))}).observe(m,{attributes:true,attributeFilter:['class']});
  const mouth=document.getElementById('mascot-mouth');
  if(mouth)new MutationObserver(()=>{
    if(mouth.classList.contains('talk')){if(!talkT){let o=true;pose('habla-abierta');talkT=setInterval(()=>{o=!o;pose(o?'habla-abierta':'habla-cerrada')},190)}}
    else if(talkT){clearInterval(talkT);talkT=null;pose(stateOf(m))}
  }).observe(mouth,{attributes:true,attributeFilter:['class']});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);else setup();
let t=null;
function react(kind,ms){
  if(!(kind in FX))return;
  const face=document.querySelector('#sec-tutor.active .coach .face');
  if(face){face.className='face pq-'+kind;const fi=face.querySelector('img');if(fi)fi.src=src(POSE_OF[kind]||'normal');setTimeout(()=>{face.className='face';const g=face.querySelector('img');if(g)g.src=src('normal')},ms||2800)}
  const m=document.getElementById('mascot');if(!m)return;
  const C=window.TalvoCore;
  if(C&&C.setMascotState)C.setMascotState(kind,ms||2800);else m.className='mascot-widget state-'+kind;
  clearTimeout(t);
}
window.PQ={react,pose};
function faceInit(){const fi=document.querySelector('#sec-tutor .coach .face img');if(fi)fi.src=src('normal')}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',faceInit);else faceInit();
/* ---------- momentos: Palanqueta aparece solo cuando importa ---------- */
const lang=()=>{try{return window.TalvoI18n&&window.TalvoI18n.get()==='es'?'es':'en'}catch(e){return 'en'}};
const TT=(en,es)=>lang()==='es'?es:en;
let mEl=null,mT=null,lastM=0,calls=false;
function moment(kind,text,ms){
  const now=Date.now();if(now-lastM<4500&&kind!=='force')return;
  if(document.body.classList.contains('in-call')||document.querySelector('.section.active#sec-llamada'))return;
  lastM=now;if(!mEl){mEl=document.createElement('div');mEl.className='pq-moment';mEl.setAttribute('role','status');mEl.innerHTML='<img alt="" draggable="false"><p></p>';document.body.appendChild(mEl);mEl.addEventListener('click',()=>mEl.classList.remove('on'))}
  mEl.querySelector('img').src=src(POSE_OF[kind]||'normal');mEl.querySelector('p').textContent=text;mEl.dataset.k=kind;
  mEl.classList.remove('on');void mEl.offsetWidth;mEl.classList.add('on');clearTimeout(mT);mT=setTimeout(()=>mEl.classList.remove('on'),ms||3600);
}
function scoreMoment(n){n=Number(n)||0;
  if(n>=90)moment('celebrando',TT('Excellent pronunciation!','¡Excelente pronunciación!'));
  else if(n>=75)moment('feliz',TT('Nice! Clear and natural.','¡Bien! Se entiende clarito.'));
  else if(n>=50)moment('motivando',TT('Close! Listen once more and try again.','¡Cerca! Escucha otra vez e inténtalo.'));
  else moment('confundida',TT('Hmm, that one was tough. Slow it down.','Hmm, esa estuvo difícil. Ve más despacio.'))}
const MAP={
  leccion_fin:(sec,meta)=>{const ok=!(meta&&meta.ok===false);react(ok?'celebrando':'motivando');moment(ok?'celebrando':'motivando',ok?TT('Lesson complete!','¡Lección completada!'):TT('Not yet. Try it again, you can do it.','Aún no. Inténtalo otra vez, tú puedes.'))},
  unidad_fin:()=>{react('celebrando');moment('celebrando',TT('Unit complete!','¡Unidad completada!'))},
  pronunciacion:sec=>scoreMoment(sec),
  ajedrez_fin:(sec,meta)=>{const r=meta&&meta.res;if(r==='gano')moment('celebrando',TT('Checkmate! Great game.','¡Jaque mate! Gran partida.'));else if(r==='perdio')moment('motivando',TT('Good fight. Review it in Learn.','Buena pelea. Repásala en Aprender.'));else moment('pensando',TT('A draw. Balanced game.','Tablas. Partida equilibrada.'))},
  examen_fin:()=>moment('sorprendida',TT('Exam finished! Let’s see your result.','¡Examen terminado! Veamos tu resultado.')),
  tutor:()=>{}
};
const orig=window.track;
if(typeof orig==='function'){
  window.track=function(n,sec,meta){try{const f=MAP[n];if(f)f(sec,meta)}catch(e){}return orig.apply(this,arguments)};
}
/* el tutor piensa mientras llega la respuesta */
const _f=window.fetch;
if(_f)window.fetch=function(u){try{if(/\/api\/(tutor|idioma\/tutor)/.test(String(u&&u.url||u)))react('pensando',9000)}catch(e){}return _f.apply(this,arguments)};
/* bienvenida según la última visita */
setTimeout(()=>{try{const C=window.TalvoCore;if(!C||!C.state||!C.state.user)return;const k='talvo_lastvisit',last=+localStorage.getItem(k)||0,now=Date.now();localStorage.setItem(k,String(now));
  if(!last)return;const d=(now-last)/864e5;
  if(d>=3)moment('sorprendida',TT('You’re back! I missed you. Let’s pick up where you left off.','¡Volviste! Te extrañé. Sigamos donde te quedaste.'),5000);
  else if(d>=0.5)moment('motivando',TT('Ready for a quick session today?','¿Listo para una sesión rápida hoy?'),4200)}catch(e){}},4500);
window.PQ.moment=moment;window.PQ.score=scoreMoment;
const css=document.createElement('style');
css.textContent='#sec-tutor .coach .face{overflow:hidden;border-radius:50%}#sec-tutor .coach .face img{width:100%!important;height:100%!important;object-fit:cover;object-position:50% 12%;transform:scale(1.9) translateY(8%);transform-origin:50% 22%}'
+'.mascot-widget.pq-poses{width:112px}.mascot-widget.pq-poses .layer>img:not(#mascot-pose),.mascot-widget.pq-poses .eye,.mascot-widget.pq-poses .mouth{display:none!important}#mascot-pose{width:100%;height:auto;display:block;filter:drop-shadow(0 6px 12px rgba(0,0,0,.45));pointer-events:none}@media (max-width:899px){.mascot-widget.pq-poses{width:86px!important}}'
+'.mascot-widget[data-fx]::after{content:attr(data-fx);position:absolute;top:-16px;right:-2px;font-size:26px;animation:pqfx .5s ease-out;pointer-events:none}'
+'@keyframes pqfx{from{transform:scale(.2) translateY(10px);opacity:0}to{transform:scale(1) translateY(0);opacity:1}}'
+'@keyframes pqjump{0%,100%{transform:translateY(0)}30%{transform:translateY(-22px) rotate(-6deg)}60%{transform:translateY(-8px) rotate(5deg)}}'
+'@keyframes pqpop{0%{transform:scale(1)}30%{transform:scale(1.18) rotate(-4deg)}60%{transform:scale(.96) rotate(3deg)}100%{transform:scale(1)}}'
+'@keyframes pqtilt{0%,100%{transform:rotate(0)}30%{transform:rotate(-9deg)}70%{transform:rotate(9deg)}}'
+'@keyframes pqpump{0%,100%{transform:translateY(0) scale(1)}40%{transform:translateY(-10px) scale(1.06)}}'
+'@keyframes pqsway{0%,100%{transform:rotate(-3deg)}50%{transform:rotate(3deg)}}'
+'#sec-tutor .coach .face{position:relative}#sec-tutor .coach .face[data-fx]::after{content:attr(data-fx);position:absolute;top:-10px;right:-10px;font-size:24px;animation:pqfx .5s ease-out}'
+'.face.pq-celebrando{animation:pqjump .8s ease-in-out 3}.face.pq-sorprendida{animation:pqpop .7s ease-out 2}.face.pq-confundida{animation:pqtilt 1.2s ease-in-out 2}.face.pq-motivando{animation:pqpump .7s ease-in-out 3}.face.pq-ensenando{animation:pqsway 1.6s ease-in-out infinite}'
+'.mascot-widget.state-celebrando .layer{animation:pqjump .8s ease-in-out 3}'
+'.mascot-widget.state-sorprendida .layer{animation:pqpop .7s ease-out 2}'
+'.mascot-widget.state-confundida .layer{animation:pqtilt 1.2s ease-in-out 2}'
+'.mascot-widget.state-motivando .layer{animation:pqpump .7s ease-in-out 3}'
+'.mascot-widget.state-ensenando .layer{animation:pqsway 1.6s ease-in-out infinite}';
document.head.appendChild(css);
const c2=document.createElement('style');
c2.textContent='.pq-moment{position:fixed;left:50%;bottom:calc(84px + env(safe-area-inset-bottom));z-index:60;display:flex;align-items:flex-end;gap:4px;max-width:min(92vw,400px);padding:0 16px 0 4px;border:1px solid var(--line-strong);border-radius:6px;background:rgba(10,14,26,.94);box-shadow:0 12px 32px rgba(0,0,0,.5);transform:translate(-50%,24px);opacity:0;pointer-events:none;transition:transform .35s cubic-bezier(.2,.9,.3,1.2),opacity .25s;cursor:pointer}'
+'.pq-moment.on{transform:translate(-50%,0);opacity:1;pointer-events:auto}.pq-moment img{width:104px;height:auto;margin:-26px 0 -2px;flex:none;filter:drop-shadow(0 6px 10px rgba(0,0,0,.5))}.pq-moment p{margin:0;padding:14px 0;font-size:14px;font-weight:600;line-height:1.35}'
+'@media(min-width:900px){.pq-moment{left:auto;right:28px;bottom:28px;transform:translateY(24px)}.pq-moment.on{transform:none}}@media(prefers-reduced-motion:reduce){.pq-moment{transition:opacity .2s}}';
document.head.appendChild(c2);
})();
