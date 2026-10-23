/* Talvo · Taller de Voz: Analizador, Shadowing, Diccionario, Reunión */
(function(){
'use strict';
const {$,jsonFetch,toast,esc}=window.TalvoCore;
const post=(p,b)=>jsonFetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});
const pq=(s)=>window.pqLoader?window.pqLoader(s):'<div class="empty">…</div>';
const fe=e=>esc(e&&e.message||'Something went wrong.');
const V={tab:'analyzer',rec:null,stream:null,chunks:[],timer:null,t0:0,tick:null,sh:{list:[],i:0,scores:[],info:null,busy:false},dict:null};
const TABS=[['analyzer','🎙️ Analyzer'],['shadowing','🔁 Shadowing'],['dictionary','📖 Dictionary'],['meeting','🗣️ Meeting']];
function chips(ws){return (ws||[]).map(w=>{const a=w.precision||0;const c=a>=80?'g':a>=60?'m':'b';return '<span class="lp-w '+c+'" data-i18n-skip>'+esc(w.palabra)+'<i>'+Math.round(a)+'</i></span>'}).join('')}
function mime(){for(const m of ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/mp4']){if(window.MediaRecorder&&MediaRecorder.isTypeSupported(m))return m}return ''}
async function recBegin(maxS,onTick,onAuto){
  if(!navigator.mediaDevices||!window.MediaRecorder)throw new Error('Your browser does not support microphone recording.');
  const s=await navigator.mediaDevices.getUserMedia({audio:true});const m=mime();
  V.stream=s;V.chunks=[];V.rec=new MediaRecorder(s,m?{mimeType:m}:undefined);
  V.rec.ondataavailable=e=>{if(e.data.size)V.chunks.push(e.data)};V.rec.start();V.t0=Date.now();
  V.tick=setInterval(()=>{const t=(Date.now()-V.t0)/1000;onTick&&onTick(t);if(t>=maxS){onAuto&&onAuto()}},250);
}
function recEnd(){return new Promise(res=>{clearInterval(V.tick);const r=V.rec;if(!r)return res(null);r.onstop=()=>{const type=(V.chunks[0]&&V.chunks[0].type)||'audio/webm';if(V.stream)V.stream.getTracks().forEach(t=>t.stop());V.rec=null;res({blob:new Blob(V.chunks,{type}),secs:(Date.now()-V.t0)/1000})};try{r.stop()}catch(e){res(null)}})}
function recAbort(){clearInterval(V.tick);try{if(V.rec&&V.rec.state!=='inactive')V.rec.stop();if(V.stream)V.stream.getTracks().forEach(t=>t.stop())}catch(e){}V.rec=null}
const fmt=t=>Math.floor(t/60)+':'+String(Math.floor(t%60)).padStart(2,'0');
function micErr(e){return e&&e.name==='NotAllowedError'?'Microphone blocked. Allow it in your browser settings.':fe(e)}

function render(){
  recAbort();const root=$('vz-root');if(!root)return;
  root.innerHTML='<div class="vz-tabs" role="tablist">'+TABS.map(t=>'<button type="button" role="tab" class="vz-tab'+(V.tab===t[0]?' on':'')+'" data-t="'+t[0]+'">'+t[1]+'</button>').join('')+'</div><div id="vz-body"></div>';
  root.querySelectorAll('[data-t]').forEach(b=>b.onclick=()=>{V.tab=b.dataset.t;render()});
  ({analyzer:vzAnalyzer,shadowing:vzShadow,dictionary:vzDict,meeting:vzMeeting})[V.tab]();
}
/* ---------- Analizador ---------- */
function vzAnalyzer(){
  const b=$('vz-body');
  b.innerHTML='<div class="card"><b class="st-h">Free-speech analyzer</b><p class="st-note">Talk about anything for up to 60 seconds. You get pronunciation, speed, filler words and weak words. Uses 2 credits.</p><div class="st-row"><input id="an-topic" class="vz-in" maxlength="120" placeholder="Topic (optional): my last holiday…"><button type="button" class="btn primary" id="an-rec">🎙️ Start</button><span id="an-t" class="st-note" style="margin:0"></span></div><div id="an-out"></div></div>';
  let on=false;const btn=$('an-rec');
  const stop=async()=>{if(!on)return;on=false;btn.disabled=true;btn.textContent='Analyzing…';const r=await recEnd();$('an-t').textContent='';
    if(!r||r.secs<3){btn.disabled=false;btn.textContent='🎙️ Start';return toast('Speak for at least 3 seconds.')}
    $('an-out').innerHTML='<div class="empty">'+pq()+'</div>';
    try{const fd=new FormData();fd.append('audio',r.blob,'recording.webm');fd.append('modo','habla_libre');fd.append('topic',$('an-topic').value.trim());
      const d=await jsonFetch('/analizar-audio-real',{method:'POST',body:fd});showAn(d,r.secs)}
    catch(e){$('an-out').innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>'}
    btn.disabled=false;btn.textContent='🎙️ Start'};
  btn.onclick=async()=>{if(on)return stop();
    try{await recBegin(60,t=>{$('an-t').textContent=fmt(t)+' / 1:00'},stop);on=true;btn.textContent='⏹ Stop';$('an-out').innerHTML=''}catch(e){$('an-out').innerHTML='<p class="st-note" data-i18n-skip>'+micErr(e)+'</p>'}};
}
function words(t){return (t||'').toLowerCase().match(/[a-z']+/g)||[]}
function showAn(d,secs){
  const ws=words(d.transcript),uniq=new Set(ws).size,variety=ws.length?Math.round(uniq/ws.length*100):0;
  const FILL=['um','uh','like','basically','actually','literally','you know'];const txt=' '+ws.join(' ')+' ';
  const fill=FILL.map(f=>[f,(txt.split(' '+f+' ').length-1)]).filter(x=>x[1]>0);
  const weak=(d.palabras||[]).filter(w=>(w.precision||0)<70).slice(0,8);
  const sc=(l,v)=>'<div class="vz-sc"><strong>'+Math.round(v||0)+'</strong><small>'+l+'</small></div>';
  const co=d.coach||{};
  $('an-out').innerHTML='<div class="vz-scores">'+sc('Overall',d.puntuacion_global)+sc('Accuracy',d.precision)+sc('Fluency',d.fluidez)+sc('Words/min',d.velocidad_wpm)+sc('Variety %',variety)+(d.gramatica!=null?sc('Grammar',d.gramatica):'')+'</div>'
   +'<p class="st-note" data-i18n-skip>“'+esc(d.transcript||'')+'”</p>'
   +'<div class="vz-words">'+chips(d.palabras)+'</div>'
   +(fill.length?'<p class="st-note"><b>Filler words:</b> <span data-i18n-skip>'+fill.map(f=>esc(f[0])+' ×'+f[1]).join(' · ')+'</span></p>':'<p class="st-note">No filler words detected. Nice!</p>')
   +(weak.length?'<p class="st-note"><b>Practice these:</b> <span data-i18n-skip>'+weak.map(w=>esc(w.palabra)).join(', ')+'</span></p>':'')
   +(co.comentario?'<p class="st-note" data-i18n-skip>'+esc(co.comentario)+'</p>':'')
   +((co.consejos||[]).length?'<ul class="vz-ul" data-i18n-skip>'+co.consejos.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'');
}
/* ---------- Shadowing ---------- */
async function vzShadow(){
  const b=$('vz-body');b.innerHTML='<div class="empty">'+pq()+'</div>';
  try{const d=await jsonFetch('/api/shadowing/frases');V.sh={list:d.frases||[],i:0,scores:[],info:d,busy:false};shDraw()}
  catch(e){b.innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>'}
}
function shDraw(){
  const S=V.sh,b=$('vz-body');
  if(!S.list.length){b.innerHTML='<p class="st-note">No phrases available.</p>';return}
  if(S.i>=S.list.length){const avg=S.scores.length?Math.round(S.scores.reduce((a,c)=>a+c,0)/S.scores.length):0;
    b.innerHTML='<div class="card" style="text-align:center"><div style="font-size:42px">🎉</div><b class="st-h">Session complete</b><div class="vz-scores" style="justify-content:center"><div class="vz-sc"><strong>'+avg+'</strong><small>Average</small></div></div><div class="st-row" style="justify-content:center"><button type="button" class="btn primary" id="sh-more">Another round</button></div></div>';
    $('sh-more').onclick=vzShadow;return}
  const p=S.list[S.i];
  b.innerHTML='<div class="card"><div class="st-row" style="justify-content:space-between"><b class="st-h">Shadowing '+(S.i+1)+'/'+S.list.length+'</b><small class="st-note" style="margin:0" data-i18n-skip>'+esc(p.tema||'')+'</small></div>'
   +'<p class="vz-phrase" data-i18n-skip>'+esc(p.en)+'</p><p class="st-note" data-i18n-skip>'+esc(p.es)+'</p>'
   +'<div class="st-row"><button type="button" class="btn" id="sh-l">🔊 Listen</button><button type="button" class="btn" id="sh-s">🐢 Slow</button><button type="button" class="btn lp-fastbtn" id="sh-f">⚡ Native speed</button><button type="button" class="btn primary" id="sh-r">🎙️ Repeat</button><button type="button" class="btn" id="sh-n">Skip →</button></div><div id="sh-out"></div>'
   +'<div class="st-row" style="margin-top:12px"><input id="sh-topic" class="vz-in" maxlength="120" placeholder="Phrases about… (e.g. ordering coffee)"><button type="button" class="btn" id="sh-t">✨ My topic</button></div><small class="st-note" data-i18n-skip>'+(S.info.limite_dia)+' daily attempts · custom topics '+(S.info.tema_ok?'included':'on Basic and up')+'</small></div>';
  $('sh-l').onclick=()=>window.TalvoCore.speak(p.en,1);$('sh-s').onclick=()=>window.TalvoCore.speak(p.en,.6);$('sh-f').onclick=()=>window.TalvoNative.say(p.en);
  $('sh-n').onclick=()=>{recAbort();S.i++;shDraw()};
  let on=false;const r=$('sh-r');
  const stop=async()=>{if(!on)return;on=false;r.disabled=true;r.textContent='Scoring…';const x=await recEnd();
    if(!x||x.secs<.8){r.disabled=false;r.textContent='🎙️ Repeat';return toast('I did not hear anything. Try again.')}
    try{const fd=new FormData();fd.append('audio',x.blob,'recording.webm');fd.append('frase_esperada',p.en);fd.append('fast','1');fd.append('shadow','1');
      const d=await jsonFetch('/analizar-audio-real',{method:'POST',body:fd});const sc=Math.round(d.puntuacion_global||0);
      $('sh-out').innerHTML='<div class="vz-scores"><div class="vz-sc"><strong>'+sc+'</strong><small>Score</small></div></div><div class="vz-words">'+chips(d.palabras)+'</div><div class="st-row"><button type="button" class="btn" id="sh-a">Try again</button><button type="button" class="btn primary" id="sh-x">Next →</button></div>';
      $('sh-a').onclick=()=>{$('sh-out').innerHTML=''};$('sh-x').onclick=()=>{S.scores.push(sc);S.i++;shDraw()}}
    catch(e){$('sh-out').innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>'}
    r.disabled=false;r.textContent='🎙️ Repeat'};
  r.onclick=async()=>{if(on)return stop();try{await recBegin(15,null,stop);on=true;r.textContent='⏹ Stop'}catch(e){$('sh-out').innerHTML='<p class="st-note" data-i18n-skip>'+micErr(e)+'</p>'}};
  $('sh-t').onclick=async()=>{const t=$('sh-topic').value.trim();if(t.length<3)return toast('Write a topic first.');
    $('sh-t').disabled=true;try{const d=await post('/api/shadowing/tema',{tema:t});S.list=d.frases;S.i=0;S.scores=[];shDraw()}catch(e){$('sh-out').innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>';$('sh-t').disabled=false}};
}
/* ---------- Diccionario ---------- */
function vzDict(){
  $('vz-body').innerHTML='<div class="card"><b class="st-h">Smart dictionary</b><p class="st-note">Meanings, pronunciation, examples and collocations in one place.</p><form class="st-row" id="dc-f"><input id="dc-q" class="vz-in" maxlength="60" placeholder="Type a word or phrase…" autocomplete="off"><button class="btn primary" type="submit">Look up</button></form><div id="dc-out"></div></div>';
  $('dc-f').onsubmit=async ev=>{ev.preventDefault();const q=$('dc-q').value.trim();if(!q)return;
    $('dc-out').innerHTML='<div class="empty">'+pq('sm')+'</div>';
    try{const d=await post('/api/diccionario',{q});V.dict=d;dcShow(d)}catch(e){$('dc-out').innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>'}};
}
function dcShow(d){
  const sp=t=>'<button type="button" class="vz-sp" data-say="'+esc(t)+'" aria-label="Listen">🔊</button>';
  $('dc-out').innerHTML='<div class="vz-dh"><div><b class="vz-big" data-i18n-skip>'+esc(d.word)+'</b> '+sp(d.word)+'<div class="st-note" style="margin:2px 0" data-i18n-skip>/'+esc(d.ipa)+'/ '+(d.level?'· '+esc(d.level):'')+'</div></div></div>'
   +(d.meanings||[]).map(m=>'<div class="vz-m"><b data-i18n-skip>'+esc(m.pos)+'</b> — <span data-i18n-skip>'+esc(m.es)+'</span>'+(m.examples||[]).map(x=>'<div class="vz-ex">'+sp(x.en)+' <span data-i18n-skip>'+esc(x.en)+'<small>'+esc(x.es)+'</small></span></div>').join('')+'</div>').join('')
   +((d.synonyms||[]).length?'<p class="st-note"><b>Synonyms:</b> <span data-i18n-skip>'+d.synonyms.map(esc).join(', ')+'</span></p>':'')
   +((d.collocations||[]).length?'<p class="st-note"><b>Collocations:</b> <span data-i18n-skip>'+d.collocations.map(c=>esc(c.en)+' ('+esc(c.es)+')').join(' · ')+'</span></p>':'')
   +(d.note?'<p class="st-note" data-i18n-skip>💡 '+esc(d.note)+'</p>':'')
   +'<div class="st-row"><button type="button" class="btn primary" id="dc-save">⭐ Save to my vocabulary</button><button type="button" class="btn" id="dc-say">🎙️ Practice saying it</button></div><div id="dc-pr"></div>';
  $('dc-out').querySelectorAll('[data-say]').forEach(b=>b.onclick=()=>window.TalvoCore.speak(b.dataset.say,.95));
  $('dc-save').onclick=async()=>{const m=(d.meanings||[])[0]||{};try{const r=await post('/api/vocabulario/guardar',{palabra:d.word,significado:m.es||'',ejemplo:(m.examples&&m.examples[0]&&m.examples[0].en)||'',origen:'diccionario'});toast(r.duplicada?'Already in your vocabulary.':'Saved! ⭐')}catch(e){toast(e.message)}};
  let on=false;const pb=$('dc-say');
  const stop=async()=>{if(!on)return;on=false;pb.disabled=true;const x=await recEnd();
    try{if(!x||x.secs<.5)throw new Error('I did not hear anything. Try again.');const fd=new FormData();fd.append('audio',x.blob,'recording.webm');fd.append('frase_esperada',d.word);fd.append('fast','1');
      const r=await jsonFetch('/analizar-audio-real',{method:'POST',body:fd});$('dc-pr').innerHTML='<div class="vz-scores"><div class="vz-sc"><strong>'+Math.round(r.puntuacion_global||0)+'</strong><small>Score</small></div></div><div class="vz-words">'+chips(r.palabras)+'</div>'}
    catch(e){$('dc-pr').innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>'}
    pb.disabled=false;pb.textContent='🎙️ Practice saying it'};
  pb.onclick=async()=>{if(on)return stop();try{await recBegin(8,null,stop);on=true;pb.textContent='⏹ Stop'}catch(e){$('dc-pr').innerHTML='<p class="st-note" data-i18n-skip>'+micErr(e)+'</p>'}};
}
/* ---------- Reunión ---------- */
function vzMeeting(){
  $('vz-body').innerHTML='<div class="card"><b class="st-h">Record a meeting</b><p class="st-note">Record up to 3 minutes of a real meeting or presentation, or upload an audio file. You get a transcript, filler words, better phrasing and action items. Pro and Max plans · 6 credits.</p><div class="st-row"><button type="button" class="btn primary" id="mt-rec">🎙️ Record</button><label class="btn" for="mt-up">📁 Upload audio</label><input type="file" id="mt-up" accept="audio/*" hidden><span id="mt-t" class="st-note" style="margin:0"></span></div><div id="mt-out"></div></div>';
  let on=false;const btn=$('mt-rec');
  const send=async(blob,name)=>{$('mt-out').innerHTML='<div class="empty">'+pq()+'</div>';
    try{const fd=new FormData();fd.append('audio',blob,name);const d=await jsonFetch('/api/reunion/analizar',{method:'POST',body:fd});mtShow(d)}
    catch(e){$('mt-out').innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>'}};
  const stop=async()=>{if(!on)return;on=false;btn.textContent='🎙️ Record';const r=await recEnd();$('mt-t').textContent='';if(!r||r.secs<8)return toast('Record at least 8 seconds.');send(r.blob,'meeting.webm')};
  btn.onclick=async()=>{if(on)return stop();try{await recBegin(180,t=>{$('mt-t').textContent=fmt(t)+' / 3:00'},stop);on=true;btn.textContent='⏹ Stop & analyze'}catch(e){$('mt-out').innerHTML='<p class="st-note" data-i18n-skip>'+micErr(e)+'</p>'}};
  $('mt-up').onchange=e=>{const f=e.target.files[0];if(!f)return;if(f.size>15*1024*1024)return toast('File too large (15 MB max).');send(f,f.name)};
}
function mtShow(d){
  const li=a=>'<ul class="vz-ul" data-i18n-skip>'+a.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>';
  $('mt-out').innerHTML='<div class="vz-scores"><div class="vz-sc"><strong>'+Math.round(d.puntuacion||0)+'</strong><small>Score</small></div><div class="vz-sc"><strong>'+(d.palabras||0)+'</strong><small>Words</small></div><div class="vz-sc"><strong>'+fmt(d.segundos||0)+'</strong><small>Length</small></div></div>'
   +(d.resumen?'<p class="st-note" data-i18n-skip>'+esc(d.resumen)+'</p>':'')
   +((d.fortalezas||[]).length?'<b class="st-h">Strengths</b>'+li(d.fortalezas):'')
   +((d.mejoras||[]).length?'<b class="st-h">Say it better</b>'+d.mejoras.map(m=>'<div class="vz-m" data-i18n-skip><s>'+esc(m.dijiste)+'</s><br><b>'+esc(m.mejor)+'</b><small>'+esc(m.por_que)+'</small></div>').join(''):'')
   +((d.vocabulario||[]).length?'<b class="st-h">Useful vocabulary</b>'+li(d.vocabulario.map(v=>v.en+' — '+v.es)):'')
   +((d.acciones||[]).length?'<b class="st-h">Action items</b>'+li(d.acciones):'')
   +(d.consejo?'<p class="st-note" data-i18n-skip>💡 '+esc(d.consejo)+'</p>':'')
   +'<details class="vz-det"><summary>Transcript</summary><p class="st-note" data-i18n-skip>'+esc(d.transcript||'')+'</p></details>';
}
window.TalvoVoice={onSection(n){if(n==='voz')render()}};
})();
