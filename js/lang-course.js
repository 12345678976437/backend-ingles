/* Talvo · Reproductor genérico para cursos de idiomas (español, chino): lecciones, escuchar, quiz, hablar con nota y tutor IA. */
(function(){
'use strict';
const C=window.TalvoCore||{};
const esc=C.esc||(s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])));
const lang=()=>{try{return window.TalvoI18n?TalvoI18n.get():'en'}catch(e){return 'en'}};
const T=(en,es)=>lang()==='es'?es:en;
const L2=a=>lang()==='es'?a[1]:a[0];
const lsGet=(k,d)=>{try{const v=localStorage.getItem(k);return v==null?d:JSON.parse(v)}catch(e){return d}};
const lsSet=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}};
const shuffle=a=>{a=a.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a};
const TONE_C=['','#ff6b6b','#ffb347','#5ee6a8','#6ab7ff'];
const TONES={ā:1,ē:1,ī:1,ō:1,ū:1,ǖ:1,á:2,é:2,í:2,ó:2,ú:2,ǘ:2,ǎ:3,ě:3,ǐ:3,ǒ:3,ǔ:3,ǚ:3,à:4,è:4,ì:4,ò:4,ù:4,ǜ:4};
function pyHtml(p){return Array.from(p).map(ch=>TONES[ch]?'<span style="color:'+TONE_C[TONES[ch]]+';font-weight:700">'+ch+'</span>':esc(ch)).join('')}

function make(cfg){
  const root=()=>document.getElementById(cfg.root);
  const key='talvo_lc_'+cfg.id;
  const prog=()=>lsGet(key,{});
  const meaning=it=>cfg.pinyin?(lang()==='es'?it[3]:it[2]):it[1];
  const py=it=>cfg.pinyin?it[1]:'';
  let tab='learn',unit=null,quiz=null,chat=[],audioCache=new Map(),cur=null;

  async function fetchAudio(text,ritmo,voz){
    const k=text+'|'+(ritmo||0)+'|'+(voz||'');
    if(audioCache.has(k))return audioCache.get(k);
    const r=await C.authFetch('/api/idioma/voz',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({curso:cfg.id,texto:text,ritmo:ritmo||0,voz:voz||cfg.voices[0]})});
    if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.error||'Audio error')}
    const url=URL.createObjectURL(await r.blob());audioCache.set(k,url);return url;
  }
  async function say(text,ritmo,voz){
    try{if(cur){cur.pause()}const a=new Audio(await fetchAudio(text,ritmo,voz));cur=a;await a.play()}
    catch(e){C.toast&&C.toast(e.message||T('Could not play audio.','No se pudo reproducir el audio.'))}
  }
  const track=(n,m)=>{try{window.track&&window.track(n,'curso_'+cfg.id,m)}catch(e){}};

  /* ---------- pantalla principal ---------- */
  function home(){
    const p=prog(),done=cfg.units.filter(u=>p[u.id]).length;
    let h='<p class="lc-intro">'+esc(L2(cfg.intro))+'</p>'
      +'<div class="lc-tabs"><button type="button" class="'+(tab==='learn'?'on':'')+'" data-lc-tab="learn">'+T('Lessons','Lecciones')+'</button><button type="button" class="'+(tab==='tutor'?'on':'')+'" data-lc-tab="tutor">'+T('Talk to the tutor','Habla con el tutor')+'</button></div>';
    if(tab==='tutor')return h+tutorHtml();
    h+='<div class="lc-prog"><i style="width:'+Math.round(done/cfg.units.length*100)+'%"></i></div><small class="lc-muted">'+done+'/'+cfg.units.length+' '+T('units completed','unidades completadas')+'</small><div class="lc-units">';
    cfg.units.forEach(u=>{const s=p[u.id]||0;h+='<button type="button" class="lc-unit'+(s?' done':'')+'" data-lc-unit="'+u.id+'"><span class="lc-ic">'+u.icon+'</span><span class="lc-ut"><b>'+esc(L2(u.name))+'</b><small>'+u.items.length+' '+T('phrases','frases')+'</small></span><span class="lc-st">'+(s?'★'.repeat(s)+'☆'.repeat(3-s):'')+'</span></button>'});
    return h+'</div>';
  }
  function render(){const r=root();if(!r)return;
    r.innerHTML=unit?unitHtml():(quiz?'':home());
    if(quiz)r.innerHTML=quizHtml();
    r.dataset.i18nSkip='1';
  }

  /* ---------- unidad: aprender ---------- */
  function itemHtml(it,i){
    return '<div class="lc-item"><button type="button" class="lc-play" data-lc-say="'+i+'" aria-label="'+T('Listen','Escuchar')+'">🔊</button>'
      +'<div class="lc-tx"><div class="lc-t'+(cfg.pinyin?' zh':'')+'">'+esc(it[0])+'</div>'+(cfg.pinyin?'<div class="lc-py">'+pyHtml(it[1])+'</div>':'')+'<div class="lc-m">'+esc(meaning(it))+'</div></div>'
      +'<button type="button" class="lc-slow" data-lc-slow="'+i+'" aria-label="'+T('Slower','Más lento')+'">🐢</button>'
      +'<button type="button" class="lc-mic" data-lc-speak="'+i+'" aria-label="'+T('Say it','Dilo tú')+'">🎤</button><div class="lc-fb" id="lc-fb-'+i+'"></div></div>';
  }
  function unitHtml(){
    const u=unit;
    return '<button type="button" class="btn" data-lc-back>← '+T('All units','Todas las unidades')+'</button><h2 class="lc-h">'+u.icon+' '+esc(L2(u.name))+'</h2>'
      +'<div class="lc-tip">💡 '+esc(L2(u.tip))+'</div><div class="lc-list">'+u.items.map(itemHtml).join('')+'</div>'
      +'<button type="button" class="btn primary" data-lc-quiz style="width:100%;margin-top:14px">'+T('Practice this unit','Practicar esta unidad')+'</button>';
  }

  /* ---------- quiz ---------- */
  function buildQuiz(u){
    const items=u.items,qs=[];
    const types=['listen','mean','rev'];
    shuffle(items).slice(0,8).forEach((it,i)=>{
      const type=types[i%3];
      let pool=shuffle(cfg.units.flatMap(x=>x.items).filter(o=>o!==it&&(type==='mean'?meaning(o)!==meaning(it):o[0]!==it[0])));
      const opts=shuffle([it].concat(pool.slice(0,3)));
      qs.push({type,it,opts});
    });
    return {u,qs,i:0,ok:0,answered:false};
  }
  function quizHtml(){
    const q=quiz.qs[quiz.i];
    if(!q){const stars=quiz.ok>=quiz.qs.length-0?3:quiz.ok>=Math.ceil(quiz.qs.length*.7)?2:quiz.ok>=Math.ceil(quiz.qs.length*.4)?1:0;
      const p=prog();p[quiz.u.id]=Math.max(p[quiz.u.id]||0,Math.max(stars,1));lsSet(key,p);track('unidad_fin',quiz.u.id);
      return '<div class="lc-end"><div class="lc-big">'+'★'.repeat(Math.max(stars,1))+'☆'.repeat(3-Math.max(stars,1))+'</div><h2>'+quiz.ok+'/'+quiz.qs.length+'</h2><p>'+(stars>=2?T('Great work! Now say the phrases out loud with 🎤.','¡Buen trabajo! Ahora di las frases en voz alta con 🎤.'):T('Good start. Review the unit and try again.','Buen comienzo. Repasa la unidad e inténtalo otra vez.'))+'</p>'
        +'<button type="button" class="btn primary" data-lc-unit="'+quiz.u.id+'" style="width:100%">'+T('Back to the unit','Volver a la unidad')+'</button></div>'}
    let h='<div class="lc-prog"><i style="width:'+Math.round(quiz.i/quiz.qs.length*100)+'%"></i></div>';
    if(q.type==='listen')h+='<p class="lc-q">'+T('What do you hear?','¿Qué escuchas?')+'</p><div style="text-align:center"><button type="button" class="lc-play big" data-lc-qsay>🔊</button><button type="button" class="lc-slow" data-lc-qslow>🐢</button></div>';
    else if(q.type==='mean')h+='<p class="lc-q">'+T('What does this mean?','¿Qué significa?')+'</p><div class="lc-prompt"><button type="button" class="lc-play" data-lc-qsay>🔊</button><span class="lc-t'+(cfg.pinyin?' zh':'')+'">'+esc(q.it[0])+'</span></div>'+(cfg.pinyin?'<div class="lc-py" style="text-align:center">'+pyHtml(q.it[1])+'</div>':'');
    else h+='<p class="lc-q">'+T('How do you say it?','¿Cómo se dice?')+'</p><div class="lc-prompt"><span class="lc-m big">'+esc(meaning(q.it))+'</span></div>';
    h+='<div class="lc-opts">'+q.opts.map((o,i)=>'<button type="button" class="lc-opt" data-lc-opt="'+i+'">'+(q.type==='mean'?esc(meaning(o)):'<span class="'+(cfg.pinyin?'zh':'')+'">'+esc(o[0])+'</span>'+(cfg.pinyin&&q.type!=='listen'?'<small>'+pyHtml(o[1])+'</small>':''))+'</button>').join('')+'</div><div id="lc-qfb"></div>';
    return h;
  }
  function answer(i,btn){
    const q=quiz.qs[quiz.i];if(quiz.answered)return;quiz.answered=true;
    const right=q.opts[i]===q.it;if(right)quiz.ok++;
    root().querySelectorAll('.lc-opt').forEach((b,k)=>{b.disabled=true;if(q.opts[k]===q.it)b.classList.add('right')});
    if(!right)btn.classList.add('wrong');
    const fb=root().querySelector('#lc-qfb');
    fb.innerHTML='<div class="lc-qf '+(right?'ok':'no')+'">'+(right?T('Correct!','¡Correcto!'):T('Not quite: ','Casi: ')+'<b>'+esc(q.it[0])+'</b>'+(cfg.pinyin?' · '+pyHtml(q.it[1]):'')+' = '+esc(meaning(q.it)))+'</div><button type="button" class="btn primary" data-lc-next style="width:100%;margin-top:10px">'+T('Continue','Continuar')+'</button>';
    if(q.type!=='listen')say(q.it[0]);
  }

  /* ---------- hablar con nota ---------- */
  let rec=null;
  async function speak(i){
    const it=unit.items[i],fb=root().querySelector('#lc-fb-'+i);
    if(rec){rec.stop();return}
    if(!navigator.mediaDevices||!window.MediaRecorder){C.toast&&C.toast(T('Your browser cannot record audio.','Tu navegador no puede grabar audio.'));return}
    let stream;try{stream=await navigator.mediaDevices.getUserMedia({audio:true})}catch(e){C.toast&&C.toast(T('Allow the microphone to practice speaking.','Permite el micrófono para practicar.'));return}
    const chunks=[],mr=new MediaRecorder(stream);rec=mr;
    const btn=root().querySelector('[data-lc-speak="'+i+'"]');btn.classList.add('rec');fb.textContent=T('Listening… tap 🎤 to stop','Escuchando… toca 🎤 para parar');
    mr.ondataavailable=e=>chunks.push(e.data);
    const timer=setTimeout(()=>{if(rec===mr)mr.stop()},7000);
    mr.onstop=async()=>{clearTimeout(timer);rec=null;stream.getTracks().forEach(t=>t.stop());btn.classList.remove('rec');
      fb.textContent=T('Scoring…','Evaluando…');
      try{const fd=new FormData();fd.append('audio',new Blob(chunks,{type:mr.mimeType||'audio/webm'}),'a.webm');fd.append('curso',cfg.id);fd.append('frase',it[0]);
        const r=await C.authFetch('/api/idioma/pronunciacion',{method:'POST',body:fd});const d=await r.json().catch(()=>({}));
        if(!r.ok)throw new Error(d.error||'Error');
        if(!d.heard){fb.innerHTML='<span class="lc-bad">'+T('I could not hear you. Try again closer to the mic.','No te oí. Inténtalo más cerca del micrófono.')+'</span>';return}
        const cls=d.score>=80?'good':d.score>=60?'mid':'bad';
        fb.innerHTML='<span class="lc-score '+cls+'">'+d.score+'</span> '+(d.words||[]).map(w=>'<span class="lc-w '+(w.accuracy>=80?'good':w.accuracy>=60?'mid':'bad')+'">'+esc(w.word)+'</span>').join(' ')
          +'<div class="lc-muted">'+(d.score>=80?T('Excellent!','¡Excelente!'):d.score>=60?T('Good. Listen again and repeat.','Bien. Escucha otra vez y repite.'):T('Listen with 🐢 and try again.','Escucha con 🐢 e inténtalo otra vez.'))+'</div>';
        track('pronunciacion',String(d.score));
      }catch(e){fb.textContent=e.message||T('Could not score now.','No se pudo evaluar ahora.')}};
    mr.start();
  }

  /* ---------- tutor ---------- */
  function tutorHtml(){
    return '<div class="lc-chat" id="lc-chat">'+(chat.length?chat.map(m=>m.rol==='yo'?'<div class="lc-b me">'+esc(m.texto)+'</div>':'<div class="lc-b tu"><div class="'+(cfg.pinyin?'zh ':'')+'lc-t">'+esc(m.texto)+'</div>'+(m.pinyin?'<div class="lc-py">'+pyHtml(m.pinyin)+'</div>':'')+(m.sig?'<div class="lc-m">'+esc(m.sig)+'</div>':'')
      +(m.corr?'<div class="lc-corr">✏️ '+esc(m.corr)+(m.exp?' — '+esc(m.exp):'')+'</div>':'')+'<button type="button" class="lc-play" data-lc-tsay="'+esc(m.texto)+'">🔊</button></div>').join(''):'<div class="lc-muted" style="padding:14px 0">'+T('Say hello to your tutor in '+(cfg.id==='es'?'Spanish':'Chinese')+' — or in English, they will help you.','Saluda a tu tutor en '+(cfg.id==='es'?'español':'chino')+' o en tu idioma; te ayudará.')+'</div>')
      +'</div><form class="lc-form" id="lc-form"><input id="lc-in" autocomplete="off" maxlength="300" placeholder="'+T('Type your message…','Escribe tu mensaje…')+'"><button class="btn primary" type="submit">'+T('Send','Enviar')+'</button></form>';
  }
  async function send(text){
    chat.push({rol:'yo',texto:text});render();scrollChat();
    try{const d=await C.jsonFetch('/api/idioma/tutor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({curso:cfg.id,mensaje:text,ui:lang(),historial:chat.slice(-7,-1)})});
      chat.push({rol:'tutor',texto:d.respuesta,pinyin:d.pinyin,sig:d.significado,corr:d.correccion,exp:d.explicacion});track('tutor');
    }catch(e){chat.push({rol:'tutor',texto:'…',sig:e.message||T('The tutor is busy. Try again.','El tutor está ocupado. Inténtalo otra vez.')})}
    render();scrollChat();
    const last=chat[chat.length-1];if(last&&last.texto&&last.texto!=='…')say(last.texto);
  }
  const scrollChat=()=>{const c=root().querySelector('#lc-chat');if(c)c.scrollTop=c.scrollHeight;const f=root().querySelector('#lc-in');if(f)f.focus()};

  /* ---------- eventos ---------- */
  function bind(){
    const r=root();if(!r||r.dataset.bound)return;r.dataset.bound='1';
    r.addEventListener('click',e=>{
      const g=s=>e.target.closest(s);let x;
      if(x=g('[data-lc-tab]')){tab=x.dataset.lcTab;render();return}
      if(x=g('[data-lc-unit]')){unit=cfg.units.find(u=>u.id===x.dataset.lcUnit);quiz=null;render();return}
      if(g('[data-lc-back]')){unit=null;quiz=null;render();return}
      if(x=g('[data-lc-say]')){say(unit.items[+x.dataset.lcSay][0]);return}
      if(x=g('[data-lc-slow]')){say(unit.items[+x.dataset.lcSlow][0],-35);return}
      if(x=g('[data-lc-speak]')){speak(+x.dataset.lcSpeak);return}
      if(g('[data-lc-quiz]')){quiz=buildQuiz(unit);render();const q=quiz.qs[0];if(q.type==='listen')say(q.it[0]);return}
      if(g('[data-lc-qsay]')){say(quiz.qs[quiz.i].it[0]);return}
      if(g('[data-lc-qslow]')){say(quiz.qs[quiz.i].it[0],-35);return}
      if(x=g('[data-lc-opt]')){answer(+x.dataset.lcOpt,x);return}
      if(g('[data-lc-next]')){quiz.i++;quiz.answered=false;if(quiz.i>=quiz.qs.length){unit=quiz.u}render();const q=quiz.qs[quiz.i];if(q&&q.type==='listen')say(q.it[0]);return}
      if(x=g('[data-lc-tsay]')){say(x.dataset.lcTsay);return}
    });
    r.addEventListener('submit',e=>{if(e.target.id!=='lc-form')return;e.preventDefault();const i=root().querySelector('#lc-in'),v=i.value.trim();if(v){i.value='';send(v)}});
  }
  return {open(){bind();unit=null;quiz=null;render()}};
}

const css=document.createElement('style');
css.textContent='.lc-intro{color:var(--muted,#9aa3b2);margin:0 0 12px}.lc-tabs{display:flex;gap:8px;margin-bottom:14px}.lc-tabs button{flex:1;min-height:42px;border:1px solid var(--line-strong,#2b3550);background:transparent;color:inherit;border-radius:4px;font-weight:600}.lc-tabs button.on{border-color:var(--cyan,#38e1ff);background:rgba(56,225,255,.1)}'
+'.lc-prog{height:6px;border-radius:3px;background:rgba(255,255,255,.1);overflow:hidden;margin:6px 0}.lc-prog i{display:block;height:100%;background:var(--signal,#38e1ff);transition:width .3s}.lc-muted{color:var(--muted,#9aa3b2);font-size:12px}'
+'.lc-units{display:grid;gap:10px;margin-top:12px}.lc-unit{display:flex;align-items:center;gap:12px;width:100%;padding:12px 14px;border:1px solid var(--line-strong,#2b3550);border-radius:6px;background:rgba(18,26,48,.6);color:inherit;text-align:left}.lc-unit.done{border-color:rgba(94,230,168,.5)}.lc-ic{font-size:26px}.lc-ut{flex:1;display:flex;flex-direction:column}.lc-ut small{color:var(--muted,#9aa3b2)}.lc-st{color:#ffd166;letter-spacing:2px}'
+'.lc-h{margin:14px 0 8px}.lc-tip{padding:10px 12px;border-radius:6px;background:rgba(255,209,102,.1);border:1px solid rgba(255,209,102,.3);font-size:13px;margin-bottom:12px}'
+'.lc-item{display:grid;grid-template-columns:44px 1fr 40px 44px;gap:8px;align-items:center;padding:10px;border:1px solid rgba(255,255,255,.1);border-radius:6px;margin-bottom:8px}.lc-fb{grid-column:1/-1;font-size:13px;min-height:0}.lc-fb:empty{display:none}'
+'.lc-play,.lc-slow,.lc-mic{min-width:40px;min-height:40px;border-radius:50%;border:1px solid var(--line-strong,#2b3550);background:rgba(255,255,255,.05);color:inherit;font-size:18px}.lc-play.big{width:84px;height:84px;font-size:34px}.lc-mic.rec{background:#ff5c5c;animation:lcp 1s infinite}@keyframes lcp{50%{opacity:.5}}'
+'.lc-t{font-size:18px;font-weight:600}.lc-t.zh,.zh{font-size:26px;font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif}.lc-py{font-size:15px}.lc-m{color:var(--muted,#9aa3b2);font-size:14px}.lc-m.big{font-size:22px;color:inherit}'
+'.lc-score{display:inline-block;min-width:44px;text-align:center;padding:2px 8px;border-radius:12px;font-weight:700}.lc-score.good,.lc-w.good{background:rgba(94,230,168,.2);color:#5ee6a8}.lc-score.mid,.lc-w.mid{background:rgba(255,209,102,.2);color:#ffd166}.lc-score.bad,.lc-w.bad,.lc-bad{background:rgba(255,92,92,.18);color:#ff8080}.lc-w{padding:1px 6px;border-radius:4px}'
+'.lc-q{font-weight:600;margin:10px 0}.lc-prompt{display:flex;align-items:center;gap:10px;justify-content:center;margin:10px 0}.lc-opts{display:grid;gap:8px;margin-top:14px}.lc-opt{min-height:50px;padding:8px 12px;border:1px solid var(--line-strong,#2b3550);border-radius:6px;background:rgba(18,26,48,.6);color:inherit;display:flex;flex-direction:column;align-items:center;justify-content:center}.lc-opt.right{border-color:#5ee6a8;background:rgba(94,230,168,.15)}.lc-opt.wrong{border-color:#ff5c5c;background:rgba(255,92,92,.15)}'
+'.lc-qf{margin-top:12px;padding:10px;border-radius:6px}.lc-qf.ok{background:rgba(94,230,168,.12)}.lc-qf.no{background:rgba(255,92,92,.12)}.lc-end{text-align:center;padding:20px 0}.lc-big{font-size:40px;color:#ffd166;letter-spacing:6px}'
+'.lc-chat{max-height:52vh;overflow:auto;display:flex;flex-direction:column;gap:10px;padding:6px 0}.lc-b{max-width:88%;padding:10px 12px;border-radius:10px}.lc-b.me{align-self:flex-end;background:rgba(56,225,255,.15)}.lc-b.tu{align-self:flex-start;background:rgba(255,255,255,.07)}.lc-corr{margin-top:6px;font-size:13px;color:#ffd166}.lc-form{display:flex;gap:8px;margin-top:10px}.lc-form input{flex:1;min-height:44px;padding:0 12px;border-radius:6px;border:1px solid var(--line-strong,#2b3550);background:rgba(18,26,48,.7);color:inherit;font-size:16px}';
document.head.appendChild(css);

const courses={};
function init(){
  [['TALVO_COURSE_ES','es'],['TALVO_COURSE_ZH','zh']].forEach(([g,id])=>{if(window[g])courses[id]=make(window[g])});
}
init();
window.TalvoLang={onSection(name){
  if(name==='espanol'&&courses.es)courses.es.open();
  if(name==='chino'&&courses.zh)courses.zh.open();
}};
})();
