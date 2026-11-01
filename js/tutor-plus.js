/* Talvo · Tutor IA: corrección integrada y traducción bajo demanda en cada mensaje. */
(function(){
'use strict';
const C=()=>window.TalvoCore||{};
const lang=()=>{try{return window.TalvoI18n?TalvoI18n.get():'en'}catch(e){return 'en'}};
const T=(en,es)=>lang()==='es'?es:en;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cat=()=>{const b=document.querySelector('#tutor-category-bar .mode.active');return b?b.dataset.cat:'conversation'};
const own=div=>{const n=div.firstChild;return n&&n.nodeType===3?n.textContent:div.textContent};
function post(path,body){return C().jsonFetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
function decorate(div){
  if(div.dataset.tp||!div.classList.contains('msg'))return;div.dataset.tp='1';
  if(cat()==='maestro')return;
  const user=div.classList.contains('user');
  const bar=document.createElement('div');bar.className='tp-bar';bar.setAttribute('data-i18n-skip','1');
  bar.innerHTML=user?'<button type="button" data-tp="chk">✏️ '+T('Check my English','Revisar mi inglés')+'</button>':'<button type="button" data-tp="tr">🌐 '+T('Translate','Traducir')+'</button>';
  div.appendChild(bar);
}
async function check(div,btn){
  const text=own(div).trim();if(text.split(/\s+/).length<2){C().toast&&C().toast(T('Write a longer sentence to check it.','Escribe una frase más larga para revisarla.'));return}
  btn.disabled=true;btn.textContent=T('Checking…','Revisando…');
  try{
    const d=await post('/api/tutor/correccion',{texto:text});
    const card=document.createElement('div');card.className='tp-card '+(d.correcta?'ok':'fix');card.setAttribute('data-i18n-skip','1');
    card.innerHTML=d.correcta
      ?'<b>✅ '+T('Looks great!','¡Se ve muy bien!')+'</b>'+(d.mejor?'<div class="tp-l">'+T('Another way to say it','Otra forma de decirlo')+'</div><div class="tp-g">'+esc(d.mejor)+'</div>':'')
      :'<b>✏️ '+T('Tutor correction','Corrección del tutor')+'</b><div class="tp-l">'+T('Your sentence','Tu frase')+'</div><div class="tp-b">'+esc(text)+'</div><div class="tp-l">'+T('Correct form','Forma correcta')+'</div><div class="tp-g">'+esc(d.corregida)+'</div>'+(d.explicacion?'<p>'+esc(d.explicacion)+'</p>':'')+'<button type="button" class="tp-say" data-say="'+esc(d.corregida)+'">🔊 '+T('Listen','Escuchar')+'</button>';
    div.parentNode.insertBefore(card,div.nextSibling);btn.parentNode.remove();
    const w=document.getElementById('tutor-messages');if(w)w.scrollTop=w.scrollHeight;
  }catch(e){btn.disabled=false;btn.textContent='✏️ '+T('Check my English','Revisar mi inglés');C().toast&&C().toast(e.message)}
}
async function translate(div,btn){
  btn.disabled=true;btn.textContent='…';
  try{
    const d=await post('/api/traducir',{texto:own(div).trim(),de:'en'});
    const t=document.createElement('div');t.className='tp-tr';t.setAttribute('data-i18n-skip','1');t.textContent=d.translation;
    btn.parentNode.replaceWith(t);
  }catch(e){btn.disabled=false;btn.textContent='🌐 '+T('Translate','Traducir');C().toast&&C().toast(e.message)}
}
function init(){
  const w=document.getElementById('tutor-messages');if(!w)return;
  w.querySelectorAll('.msg').forEach(decorate);
  new MutationObserver(m=>{m.forEach(r=>r.addedNodes.forEach(n=>{if(n.nodeType===1&&n.classList.contains('msg'))decorate(n)}))}).observe(w,{childList:true});
  w.addEventListener('click',e=>{
    const b=e.target.closest('[data-tp]'),say=e.target.closest('[data-say]');
    if(say){C().speak&&C().speak(say.dataset.say);return}
    if(!b)return;const div=b.closest('.msg');
    if(b.dataset.tp==='chk')check(div,b);else translate(div,b);
  });
  /* primeros mensajes sugeridos */
  const bar=document.createElement('div');bar.className='tp-sug';bar.id='tp-sug';
  const items=[['Tell me about your day','Cuéntame sobre tu día'],['Help me order food in English','Ayúdame a pedir comida en inglés'],['Let’s practice a job interview','Practiquemos una entrevista de trabajo']];
  const render=()=>{bar.setAttribute('data-i18n-skip','1');bar.innerHTML=items.map(x=>'<button type="button">'+esc(lang()==='es'?x[1]:x[0])+'</button>').join('')};
  render();
  bar.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;const i=document.getElementById('tutor-input');if(i){i.value=items[[...bar.children].indexOf(b)][0];document.getElementById('tutor-send')&&document.getElementById('tutor-send').click();bar.remove()}});
  w.parentNode.insertBefore(bar,w.nextSibling);
  document.addEventListener('click',e=>{if(e.target.closest&&e.target.closest('.js-lang-toggle'))setTimeout(render,120)});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
