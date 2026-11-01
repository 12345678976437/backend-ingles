/* Talvo · Palanqueta con más expresiones (celebrando, sorprendida, confundida, motivando, enseñando).
   Se dibujan con animaciones y un globo de emoji sobre la mascota actual: sin imágenes nuevas. */
(function(){
'use strict';
const FX={celebrando:'🎉',sorprendida:'❗',confundida:'❓',motivando:'💪',ensenando:'📚',feliz:'✨',triste:'💧'};
let t=null;
function react(kind,ms){
  if(!FX[kind])return;
  const face=document.querySelector('#sec-tutor.active .coach .face');
  if(face){face.className='face pq-'+kind;face.dataset.fx=FX[kind];setTimeout(()=>{face.className='face';delete face.dataset.fx},ms||2800)}
  const m=document.getElementById('mascot');if(!m)return;
  const C=window.TalvoCore;
  if(C&&C.setMascotState)C.setMascotState(kind,ms||2800);else m.className='mascot-widget state-'+kind;
  m.dataset.fx=FX[kind];clearTimeout(t);t=setTimeout(()=>{delete m.dataset.fx},ms||2800);
}
window.PQ={react};
/* reacciones automáticas en momentos clave */
const MAP={leccion_fin:'celebrando',unidad_fin:'celebrando',pronunciacion:null};
const orig=window.track;
if(typeof orig==='function'){
  window.track=function(n){try{const k=MAP[n];if(k)react(k)}catch(e){}return orig.apply(this,arguments)};
}
const css=document.createElement('style');
css.textContent='.mascot-widget[data-fx]::after{content:attr(data-fx);position:absolute;top:-16px;right:-2px;font-size:26px;animation:pqfx .5s ease-out;pointer-events:none}'
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
