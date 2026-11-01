/* Talvo · Palanqueta con más expresiones (celebrando, sorprendida, confundida, motivando, enseñando).
   Se dibujan con animaciones y un globo de emoji sobre la mascota actual: sin imágenes nuevas. */
(function(){
'use strict';
const FX={celebrando:'',sorprendida:'',confundida:'',motivando:'',ensenando:'',feliz:'',triste:''};
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
/* reacciones automáticas en momentos clave */
const MAP={leccion_fin:'celebrando',unidad_fin:'celebrando',pronunciacion:null};
const orig=window.track;
if(typeof orig==='function'){
  window.track=function(n){try{const k=MAP[n];if(k)react(k)}catch(e){}return orig.apply(this,arguments)};
}
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
})();
