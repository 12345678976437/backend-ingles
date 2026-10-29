/* Talvo · Studio: Traductor en vivo, Escenarios de rol y Rutas por tema */
(function(){
'use strict';
const {$,jsonFetch,toast,section,esc}=window.TalvoCore;
const post=(p,b)=>jsonFetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
const lsGet=(k,d)=>{try{const v=localStorage.getItem(k);return v==null?d:v}catch(e){return d}};
const lsSet=(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}};
const pq=(s)=>window.pqLoader?window.pqLoader(s):'<div class="empty">…</div>';
function say(text,lang){
  if(lang!=='es'&&window.TalvoCore.speak)return window.TalvoCore.speak(text,1);
  try{speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(String(text||''));u.lang='es-MX';speechSynthesis.speak(u)}catch(e){}
}
function sayLang(text,lang){lang==='es'?say(text,'es'):window.TalvoCore.speak(text,1)}
function micErr(e){return e==='not-allowed'||e==='service-not-allowed'?'Microphone blocked. Allow it in your browser settings.':(e==='no-speech'?'I did not hear anything. Try again.':'Could not use the microphone.')}
/* Reconocimiento de voz del navegador (gratis). onInterim(texto) mientras hablas, onFinal(texto) al terminar. */
function listen(lang,onInterim,onFinal,onEnd){
  const r=new SR();r.lang=lang;r.interimResults=true;r.continuous=false;r.maxAlternatives=1;let fin='';
  r.onresult=ev=>{let t='';for(let i=0;i<ev.results.length;i++){t+=ev.results[i][0].transcript;if(ev.results[i].isFinal)fin=t}onInterim&&onInterim(t)};
  r.onerror=ev=>{toast(micErr(ev.error))};
  r.onend=()=>{onEnd&&onEnd();if(fin&&onFinal)onFinal(fin.trim())};
  try{r.start()}catch(e){toast(micErr('x'));onEnd&&onEnd()}
  return r;
}
const fmtErr=e=>esc(e&&e.message||'Something went wrong.');

/* ===================== TRADUCTOR ===================== */
const T={dir:lsGet('tr_dir','auto'),tone:'neutral',mode:'text',live:lsGet('tr_live','1')==='1',auto:lsGet('tr_auto','1')==='1',side:'es',last:'',tok:0,timer:null,rec:null,res:null,log:[]};
const recLang=d=>d==='en'?'en-US':'es-MX';
function trRender(){
  const root=$('tr-root');if(!root||root.dataset.ready)return;root.dataset.ready='1';
  root.innerHTML=`<div class="card"><div class="modebar"><button type="button" class="mode active" data-trm="text">Text</button><button type="button" class="mode" data-trm="chat">Conversation</button></div>
  <div id="tr-text" class="tr-box" style="margin-top:14px">
   <div class="st-row"><select id="tr-dir" class="st-sel" aria-label="Direction"><option value="auto">Auto-detect</option><option value="es">Spanish → English</option><option value="en">English → Spanish</option></select>
    <select id="tr-tone" class="st-sel" aria-label="Tone"><option value="neutral">Neutral</option><option value="formal">Formal</option><option value="casual">Casual</option></select></div>
   <textarea id="tr-in" class="tr-in" maxlength="1500" placeholder="Type or tap the mic and speak…" aria-label="Text to translate"></textarea>
   <div class="st-row"><button type="button" class="st-ic" id="tr-mic" aria-label="Speak">🎤</button><button type="button" class="btn primary" id="tr-go">Translate</button><button type="button" class="btn" id="tr-clear">Clear</button>
    <label class="tr-live"><input type="checkbox" id="tr-live"> Translate as I type</label></div>
   <div id="tr-out"></div>
   <p class="st-note">Each translation uses 0.3 credits from your plan. Voice uses your browser, so it is free.</p></div>
  <div id="tr-chat" class="tr-box" style="margin-top:14px;display:none">
   <div class="st-row"><button type="button" class="st-chip on" data-side="es">🇲🇽 I speak Spanish</button><button type="button" class="st-chip" data-side="en">🇺🇸 They speak English</button>
    <label class="tr-live"><input type="checkbox" id="tr-auto"> Read translations aloud</label></div>
   <div class="tr-log" id="tr-log"><div class="empty">Pick who is talking, tap the mic and start. Each phrase is translated for the other person.</div></div>
   <div class="sc-bar"><button type="button" class="st-ic" id="tc-mic" aria-label="Speak">🎤</button><input id="tc-in" class="input" placeholder="Or type here…" aria-label="Message"><button type="button" class="btn primary" id="tc-send">Send</button></div></div></div>`;
  $('tr-dir').value=T.dir;$('tr-live').checked=T.live;$('tr-auto').checked=T.auto;
  if(!SR){$('tr-mic').style.display='none';$('tc-mic').style.display='none'}
  root.querySelectorAll('[data-trm]').forEach(b=>b.addEventListener('click',()=>{
    root.querySelectorAll('[data-trm]').forEach(x=>x.classList.toggle('active',x===b));T.mode=b.dataset.trm;
    $('tr-text').style.display=T.mode==='text'?'':'none';$('tr-chat').style.display=T.mode==='chat'?'':'none'}));
  $('tr-dir').addEventListener('change',e=>{T.dir=e.target.value;lsSet('tr_dir',T.dir);T.last='';trGo(true)});
  $('tr-tone').addEventListener('change',e=>{T.tone=e.target.value;T.last='';trGo(true)});
  $('tr-live').addEventListener('change',e=>{T.live=e.target.checked;lsSet('tr_live',T.live?'1':'0')});
  $('tr-auto').addEventListener('change',e=>{T.auto=e.target.checked;lsSet('tr_auto',T.auto?'1':'0')});
  $('tr-in').addEventListener('input',()=>{clearTimeout(T.timer);if(T.live&&$('tr-in').value.trim().length>=3)T.timer=setTimeout(()=>trGo(false),1100)});
  $('tr-in').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();trGo(true)}});
  $('tr-go').addEventListener('click',()=>trGo(true));
  $('tr-clear').addEventListener('click',()=>{$('tr-in').value='';$('tr-out').innerHTML='';T.last='';T.res=null});
  $('tr-mic').addEventListener('click',()=>trMic($('tr-mic'),recLang(T.dir==='en'?'en':'es'),t=>{$('tr-in').value=t},()=>{},t=>{$('tr-in').value=t;trGo(true)}));
  root.querySelectorAll('[data-side]').forEach(b=>b.addEventListener('click',()=>{T.side=b.dataset.side;root.querySelectorAll('[data-side]').forEach(x=>x.classList.toggle('on',x===b))}));
  $('tc-mic').addEventListener('click',()=>trMic($('tc-mic'),recLang(T.side),t=>{$('tc-in').value=t},()=>{},t=>{$('tc-in').value='';chatSend(t)}));
  $('tc-send').addEventListener('click',()=>{const v=$('tc-in').value.trim();if(v){$('tc-in').value='';chatSend(v)}});
  $('tc-in').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('tc-send').click()}});
}
function trMic(btn,lang,onI,_x,onF){
  if(!SR)return toast('Voice input is not available in this browser.');
  if(T.rec){try{T.rec.stop()}catch(e){}return}
  btn.classList.add('rec');T.rec=listen(lang,onI,onF,()=>{btn.classList.remove('rec');T.rec=null});
}
async function trCall(text,de){return post('/api/traducir',{texto:text,de:de||'auto',tono:T.tone})}
async function trGo(force){
  const text=$('tr-in').value.trim();if(!text){$('tr-out').innerHTML='';return}
  if(!force&&text===T.last+'')return;
  clearTimeout(T.timer);T.last=text;const tok=++T.tok;
  $('tr-out').innerHTML='<div class="tr-out"><div data-pq-wrap>'+pq('sm')+'</div></div>';
  try{
    const d=await trCall(text,T.dir);if(tok!==T.tok)return;T.res=d;trShow(d,text)
  }catch(e){if(tok!==T.tok)return;$('tr-out').innerHTML='<div class="tr-out"><span data-i18n-skip>'+fmtErr(e)+'</span></div>'}
}
function trShow(d,src){
  const tgt=d.target;
  let h='<div class="tr-out"><span class="tag">'+(tgt==='en'?'English':'Español')+'</span><p class="big" data-i18n-skip>'+esc(d.translation)+(d.ipa?'<span class="ipa">/'+esc(d.ipa.replace(/^\/|\/$/g,''))+'/</span>':'')+'</p>'
   +'<div class="tr-acts"><button type="button" class="st-ic" data-a="say" aria-label="Listen">🔊</button><button type="button" class="st-ic" data-a="copy" aria-label="Copy">📋</button>'
   +(tgt==='en'||d.detected==='en'?'<button type="button" class="btn" data-a="save">⭐ Save to vocabulary</button>':'')+'</div>';
  if(d.alternatives&&d.alternatives.length)h+='<div class="tr-alt"><small>Other ways to say it</small>'+d.alternatives.map((a,i)=>'<button type="button" class="st-chip" data-alt="'+i+'" data-i18n-skip>'+esc(a)+'</button>').join('')+'</div>';
  if(d.literal)h+='<div class="tr-tip"><b>Literal:</b> <span data-i18n-skip>'+esc(d.literal)+'</span></div>';
  if(d.note)h+='<div class="tr-tip" data-i18n-skip>💡 '+esc(d.note)+'</div>';
  if(d.examples&&d.examples.length)h+=d.examples.map(x=>'<div class="tr-ex" data-i18n-skip>'+esc(x.en)+'<em>'+esc(x.es)+'</em></div>').join('');
  h+='</div>';$('tr-out').innerHTML=h;
  $('tr-out').querySelector('[data-a=say]').onclick=()=>sayLang(d.translation,tgt);
  $('tr-out').querySelector('[data-a=copy]').onclick=()=>{try{navigator.clipboard.writeText(d.translation);toast('Copied')}catch(e){}};
  const sv=$('tr-out').querySelector('[data-a=save]');
  if(sv)sv.onclick=async()=>{const en=tgt==='en'?d.translation:src,es=tgt==='en'?src:d.translation;
    try{await post('/api/vocabulario/guardar',{palabra:en.slice(0,120),significado:es.slice(0,200),ejemplo:'',origen:'traductor'});toast('Saved to your vocabulary')}catch(e){toast(e.message)}};
  $('tr-out').querySelectorAll('[data-alt]').forEach(b=>b.onclick=()=>sayLang(d.alternatives[+b.dataset.alt],tgt));
}
async function chatSend(text){
  const log=$('tr-log');if(log.querySelector('.empty'))log.innerHTML='';
  const side=T.side,id='tp'+Date.now();
  log.insertAdjacentHTML('beforeend','<div class="tr-pair'+(side==='es'?' me':'')+'" id="'+id+'"><small>'+(side==='es'?'Español':'English')+'</small><b data-i18n-skip>'+esc(text)+'</b><div data-pq-wrap>'+pq('sm')+'</div></div>');
  log.scrollTop=log.scrollHeight;
  const el=$(id);
  try{
    const d=await trCall(text,side);
    el.querySelector('[data-pq-wrap]').outerHTML='<small style="margin-top:8px">'+(d.target==='en'?'English':'Español')+'</small><b data-i18n-skip style="color:var(--cyan)">'+esc(d.translation)+'</b><button type="button" class="st-ic sm" aria-label="Listen">🔊</button>';
    el.querySelector('.st-ic').onclick=()=>sayLang(d.translation,d.target);
    if(T.auto)sayLang(d.translation,d.target);
  }catch(e){el.querySelector('[data-pq-wrap]').outerHTML='<small data-i18n-skip>'+fmtErr(e)+'</small>'}
  log.scrollTop=log.scrollHeight;
}

/* ===================== ESCENARIOS ===================== */
const S={mood:'calm',list:null,libre:false,cat:'all',sc:null,hist:[],turns:0,busy:false,rec:null,hint:null,ruta:null,done:false};
const MAXT=10;
const CATS=[['all','All'],['work','Work'],['travel','Travel'],['life','Daily life']];
async function scHome(){
  const root=$('sc-root');if(!root)return;
  if(S.sc&&!S.done)return;      // conversación en curso: no la pierdas al cambiar de pestaña
  if(!S.list)root.innerHTML='<div class="empty">'+pq()+'</div>';
  try{
    if(!S.list){const d=await jsonFetch('/api/escenarios');S.list=d.escenarios;S.libre=d.libre}
    scList();
  }catch(e){root.innerHTML='<div class="empty" data-i18n-skip>'+fmtErr(e)+'</div>'}
}
function scList(){
  S.sc=null;S.done=false;const root=$('sc-root');
  const items=S.list.filter(s=>S.cat==='all'||s.cat===S.cat);
  root.innerHTML='<div class="modebar" id="sc-cats">'+CATS.map(c=>'<button type="button" class="mode'+(S.cat===c[0]?' active':'')+'" data-cat="'+c[0]+'">'+c[1]+'</button>').join('')+'</div>'
   +'<div class="sc-grid">'
   +'<button type="button" class="sc-card custom" id="sc-custom"><span class="ic">✨</span><b>Create your own</b><span class="d">Describe any situation and the coach will play the other person.</span>'+(S.libre?'':'<span class="sc-lock">🔒 Pro</span>')+'</button>'
   +items.map(s=>'<button type="button" class="sc-card'+(s.bloqueado?' lock':'')+'" data-id="'+s.id+'"><span class="ic">'+s.icon+'</span><b data-i18n-skip>'+esc(s.es)+'</b><span class="d" data-i18n-skip>'+esc(s.desc)+'</span>'+(s.bloqueado?'<span class="sc-lock">🔒 Basic</span>':'')+'</button>').join('')+'</div>'
   +'<p class="st-note">Each message you send uses 1 credit and the final report uses 3. Voice uses your browser, so it is free.</p>';
  root.querySelectorAll('[data-cat]').forEach(b=>b.addEventListener('click',()=>{S.cat=b.dataset.cat;scList()}));
  root.querySelectorAll('[data-id]').forEach(b=>b.addEventListener('click',()=>{
    const s=S.list.find(x=>x.id===b.dataset.id);
    if(s.bloqueado){toast('This scenario is available from the Basic plan.');section('cuenta');return}
    scStart({id:s.id,icon:s.icon,es:s.es,goal:s.goal,opening:s.opening,user_role:s.user_role})}));
  $('sc-custom').addEventListener('click',scCustomForm);
}
function scCustomForm(){
  if(!S.libre){toast('Creating your own situations is a Pro feature.');section('cuenta');return}
  $('sc-root').innerHTML='<div class="card rt-create"><button type="button" class="rt-back" id="sc-b">← Back</button><b class="st-h" style="display:block;margin-top:0">What do you want to practice?</b>'
   +'<textarea id="sc-desc" maxlength="300" placeholder="E.g. I want to ask my boss for a raise · I need to return a broken laptop at a store"></textarea><div class="st-row" style="margin-top:12px"><button type="button" class="btn primary" id="sc-mk">Create situation</button></div><div id="sc-mkout"></div></div>';
  $('sc-b').onclick=scList;
  $('sc-mk').onclick=async()=>{
    const v=$('sc-desc').value.trim();$('sc-mk').disabled=true;$('sc-mkout').innerHTML=pq('sm');
    try{const d=await post('/api/escenario/nuevo',{descripcion:v});const s=d.escenario;scStart({custom:{setup:s.setup,ai_role:s.ai_role,user_role:s.user_role,goal:s.goal,opening:s.opening},icon:s.icon,es:s.es,goal:s.goal,opening:s.opening,user_role:s.user_role})}
    catch(e){$('sc-mkout').innerHTML='<p class="st-note" data-i18n-skip>'+fmtErr(e)+'</p>';$('sc-mk').disabled=false}};
}
function scStart(sc){
  S.sc=sc;S.hist=[{role:'assistant',content:sc.opening}];S.turns=0;S.busy=false;S.hint=null;S.done=false;
  $('sc-root').innerHTML='<div class="card"><div class="sc-top"><button type="button" class="rt-back" id="sc-exit">←</button><span class="ic">'+esc(sc.icon||'🎭')+'</span><div><b data-i18n-skip>'+esc(sc.es||'Role-play')+'</b><small style="color:var(--muted)" data-i18n-skip>You: '+esc(sc.user_role||'')+'</small></div></div>'
   +'<p class="sc-goal" data-i18n-skip>🎯 '+esc(sc.goal||'')+'</p><div class="sc-mood" id="sc-mood">'+[['calm','😊 Friendly'],['rushed','⏱️ In a hurry'],['upset','😠 Upset']].map(m=>'<button type="button" class="mode'+(S.mood===m[0]?' active':'')+'" data-mood="'+m[0]+'">'+m[1]+'</button>').join('')+'</div><div class="sc-chat" id="sc-chat"></div><div id="sc-hint"></div>'
   +'<div class="sc-bar"><button type="button" class="st-ic" id="sc-mic" aria-label="Speak">🎤</button><input id="sc-in" class="input" placeholder="Reply in English…" aria-label="Your reply" autocomplete="off"><button type="button" class="btn primary" id="sc-send">Send</button></div>'
   +'<div class="sc-meta"><span id="sc-count"></span><span class="st-row"><button type="button" class="btn" id="sc-hintb">💡 Hint</button><button type="button" class="btn" id="sc-end" disabled>Finish & get feedback</button></span></div></div>';
  if(!SR)$('sc-mic').style.display='none';
  document.querySelectorAll('#sc-mood [data-mood]').forEach(b=>b.onclick=()=>{S.mood=b.dataset.mood;document.querySelectorAll('#sc-mood [data-mood]').forEach(x=>x.classList.toggle('active',x===b))});
  addAi(sc.opening,true);scCount();
  $('sc-exit').onclick=()=>{if(S.turns>0&&!confirm(window.TalvoI18n?TalvoI18n.tr('Leave this conversation? You will lose it.'):'Leave this conversation? You will lose it.'))return;try{speechSynthesis.cancel()}catch(e){}scList()};
  $('sc-send').onclick=()=>{const v=$('sc-in').value.trim();if(v){$('sc-in').value='';scSend(v)}};
  $('sc-in').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('sc-send').click()}});
  $('sc-mic').onclick=()=>{if(S.rec){try{S.rec.stop()}catch(e){}return}$('sc-mic').classList.add('rec');S.rec=listen('en-US',t=>{$('sc-in').value=t},t=>{$('sc-in').value='';scSend(t)},()=>{$('sc-mic').classList.remove('rec');S.rec=null})};
  $('sc-hintb').onclick=()=>{if(!S.hint)return toast('Send a message first to get a hint.');scHint()};
  $('sc-end').onclick=scFinish;
}
function scBody(){const o={history:S.hist};if(S.sc.id&&S.sc.id!=='custom'&&!S.ruta)o.escenario_id=S.sc.id;if(S.ruta)o.ruta_id=S.ruta;if(S.mood&&S.mood!=='calm')o.mood=S.mood;if(S.sc.custom)o.custom=S.sc.custom;return o}
function chatEl(){return $('sc-chat')}
function addAi(text,speakIt){
  const c=chatEl();c.insertAdjacentHTML('beforeend','<div class="sc-m ai"><span data-i18n-skip>'+esc(text)+'</span><button type="button" class="st-ic sm" aria-label="Listen">🔊</button><button type="button" class="st-ic sm" aria-label="Native speed" title="Native speed">⚡</button></div>');
  const bs=c.lastElementChild.querySelectorAll('button'),b=bs[0];b.onclick=()=>window.TalvoCore.speak(text,.95);bs[1].onclick=()=>window.TalvoNative.say(text);
  c.scrollTop=c.scrollHeight;if(speakIt)setTimeout(()=>window.TalvoCore.speak(text,.95),250);
}
function scCount(){$('sc-count').textContent='Turn '+Math.min(S.turns+1,MAXT)+' of '+MAXT;$('sc-end').disabled=S.turns<2}
async function scSend(text){
  if(S.busy)return;S.busy=true;try{speechSynthesis.cancel()}catch(e){}
  const c=chatEl();c.insertAdjacentHTML('beforeend','<div class="sc-m me" data-i18n-skip>'+esc(text)+'</div>');
  const me=c.lastElementChild;c.insertAdjacentHTML('beforeend','<div class="sc-think" id="sc-think">'+pq('sm')+'</div>');c.scrollTop=c.scrollHeight;
  $('sc-send').disabled=true;
  try{
    const d=await post('/api/escenario/turno',Object.assign(scBody(),{mensaje:text}));
    S.hist.push({role:'user',content:text},{role:'assistant',content:d.reply});S.turns++;
    const th=$('sc-think');if(th)th.remove();
    if(d.correction)me.insertAdjacentHTML('afterend','<div class="sc-fix" data-i18n-skip>✏️ <s>'+esc(d.correction.said)+'</s> → <b>'+esc(d.correction.better)+'</b><small>'+esc(d.correction.why_es)+'</small></div>');
    addAi(d.reply,true);S.hint={tip:d.tip_es,sug:d.suggestion_en};$('sc-hint').innerHTML='';
    scCount();
    if(d.goal_reached||S.turns>=MAXT){toast(d.goal_reached?'Goal reached! Tap Finish to see your feedback.':'Great practice! Tap Finish to see your feedback.');$('sc-end').classList.add('primary');$('sc-end').disabled=false}
  }catch(e){const th=$('sc-think');if(th)th.remove();me.remove();$('sc-in').value=text;toast(e.message)}
  S.busy=false;$('sc-send').disabled=false;
}
function scHint(){
  const h=S.hint;if(!h)return;
  $('sc-hint').innerHTML='<div class="sc-hint" data-i18n-skip>'+(h.tip?'💡 '+esc(h.tip)+'<br>':'')+(h.sug?'<b>Try:</b> “'+esc(h.sug)+'” <button type="button" class="st-ic sm" id="sc-hs" aria-label="Listen">🔊</button> <button type="button" class="btn" id="sc-hu" style="min-height:30px;font-size:11.5px">Use it</button>':'')+'</div>';
  const s=$('sc-hs');if(s)s.onclick=()=>window.TalvoCore.speak(h.sug,.95);const u=$('sc-hu');if(u)u.onclick=()=>{$('sc-in').value=h.sug;$('sc-in').focus()};
}
async function scFinish(){
  if(S.busy)return;S.busy=true;$('sc-root').innerHTML='<div class="card"><div class="rt-wait">'+pq()+'<p>Palanqueta is reviewing your conversation…</p></div></div>';
  try{const d=await post('/api/escenario/feedback',scBody());S.busy=false;S.done=true;scReport(d)}
  catch(e){S.busy=false;S.done=false;toast(e.message);scStart(S.sc)}
}
function scReport(d){
  const sc=S.sc;
  $('sc-root').innerHTML='<div class="card" style="text-align:center"><div class="eyebrow">'+(d.objetivo_logrado?'Goal achieved 🎉':'Keep practicing 💪')+'</div><div class="sc-res-ring" style="--p:'+d.puntuacion+'"><b>'+d.puntuacion+'</b></div>'
   +'<p style="color:var(--muted);margin:0 0 6px">+'+d.xp+' XP</p><div class="sc-subs"><div><b>'+d.fluidez+'</b><small>Fluency</small></div><div><b>'+d.gramatica+'</b><small>Grammar</small></div><div><b>'+d.vocabulario+'</b><small>Vocabulary</small></div></div>'
   +'<p data-i18n-skip style="text-align:left;line-height:1.55">'+esc(d.resumen)+'</p>'
   +(d.fortalezas.length?'<div style="text-align:left"><b class="st-h" style="display:block">Strengths</b>'+d.fortalezas.map(f=>'<div class="sc-li" data-i18n-skip>✅ <div>'+esc(f)+'</div></div>').join('')+'</div>':'')
   +(d.mejoras.length?'<div style="text-align:left"><b class="st-h" style="display:block">Say it better</b>'+d.mejoras.map(m=>'<div class="sc-li" data-i18n-skip><div><s style="color:#ff9aa8">'+esc(m.dijiste)+'</s><br><b style="color:#9ff5d3">'+esc(m.mejor)+'</b><small>'+esc(m.por_que)+'</small></div></div>').join('')+'</div>':'')
   +(d.frases_utiles.length?'<div style="text-align:left"><b class="st-h" style="display:block">Useful phrases</b>'+d.frases_utiles.map((f,i)=>'<div class="sc-li"><button type="button" class="st-ic sm" data-say="'+i+'" aria-label="Listen">🔊</button><div data-i18n-skip><b>'+esc(f.en)+'</b><small>'+esc(f.es)+'</small></div><button type="button" class="st-ic sm" data-save="'+i+'" aria-label="Save">⭐</button></div>').join('')+'</div>':'')
   +(d.siguiente_paso?'<p class="sc-goal" style="text-align:left" data-i18n-skip>➡️ '+esc(d.siguiente_paso)+'</p>':'')
   +'<div class="st-row" style="justify-content:center;margin-top:16px"><button type="button" class="btn primary" id="sc-again">Try again</button><button type="button" class="btn" id="sc-more">More scenarios</button></div></div>';
  document.querySelectorAll('#sc-root [data-say]').forEach(b=>b.onclick=()=>window.TalvoCore.speak(d.frases_utiles[+b.dataset.say].en,.9));
  document.querySelectorAll('#sc-root [data-save]').forEach(b=>b.onclick=async()=>{const f=d.frases_utiles[+b.dataset.save];try{await post('/api/vocabulario/guardar',{palabra:f.en,significado:f.es,ejemplo:'',origen:'escenario'});b.textContent='✓';toast('Saved to your vocabulary')}catch(e){toast(e.message)}});
  $('sc-again').onclick=()=>scStart(sc);
  $('sc-more').onclick=()=>{if(S.ruta){const r=S.ruta;S.ruta=null;S.done=false;S.sc=null;section('rutas');rtOpen(r)}else{S.done=false;scList()}};
}
window.TalvoScenarioFromRoute=(rid,rp,meta)=>{S.ruta=rid;section('escenarios');S.sc=null;S.done=false;scStart({id:'route',icon:meta.emoji||'🎭',es:meta.titulo,goal:rp.goal,opening:rp.opening,user_role:rp.user_role})};

/* ===================== RUTAS ===================== */
const R={list:null,cur:null,busy:false};
R.tab='rutas';
async function rtHome(){
  const root=$('rt-root');if(!root)return;
  window.ltRender&&ltRender(R.tab);
  if(R.cur){return rtOpen(R.cur)}
  root.innerHTML='<div class="empty">'+pq()+'</div>';
  try{R.list=await jsonFetch('/api/rutas');if(R.tab==='reto'&&R.list.reto)return rtOpen(R.list.reto.id);rtList()}catch(e){root.innerHTML='<div class="empty" data-i18n-skip>'+fmtErr(e)+'</div>'}
}
const WAIT=['Palanqueta is gathering the right words for you…','Writing lessons about your situation…','Preparing dialogs and practice phrases…','Almost ready — polishing your route…'];
async function rtCreate(){
  if(R.busy)return;const v=$('rt-in').value.trim();
  if(v.length<12)return toast('Tell me a bit more: what do you want to achieve, and where?');
  if(!R.list.puede_crear){toast('You reached your route limit. Delete one or upgrade your plan.');return}
  R.busy=true;$('rt-mk').disabled=true;let i=0;
  const out=$('rt-mkout');out.innerHTML='<div class="rt-wait">'+pq()+'<p id="rt-wp" data-i18n-skip>'+WAIT[0]+'</p></div>';
  const iv=setInterval(()=>{i=Math.min(i+1,WAIT.length-1);const p=$('rt-wp');if(p)p.textContent=WAIT[i]},5000);
  try{const d=await post('/api/rutas/crear',{pedido:v});clearInterval(iv);R.busy=false;toast('Your route is ready! 🎉');rtOpen(d.ruta.id)}
  catch(e){clearInterval(iv);R.busy=false;$('rt-mk').disabled=false;out.innerHTML='<p class="st-note" data-i18n-skip>'+fmtErr(e)+'</p>'}
}
const PQI='<img src="palanqueta-asoma.webp" alt="" draggable="false">';
const PQA='<img src="palanqueta-a.webp" alt="" draggable="false">';
function rtRing(pc,label,sz){const r=26,c=2*Math.PI*r;return '<div class="rt-ring" style="--sz:'+(sz||84)+'px"><svg viewBox="0 0 64 64"><circle class="bg" cx="32" cy="32" r="'+r+'"/><circle class="fg" cx="32" cy="32" r="'+r+'" stroke-dasharray="'+c.toFixed(1)+'" stroke-dashoffset="'+(c*(1-pc/100)).toFixed(1)+'"/></svg><b>'+pc+'%</b>'+(label?'<small>'+label+'</small>':'')+'</div>'}
function rtList(){
  R.cur=null;R.det=null;const d=R.list,root=$('rt-root'),reto=d.reto;
  window.ltRender&&ltRender(R.tab);
  let main='';
  if(R.tab==='reto'){
    main+='<div class="rt-reto"><div class="rt-reto-t"><span class="rt-tag">🔥 New · 21-day challenge</span><b>Speak real English in 3 weeks.</b>'
      +'<small>A fixed plan of 21 short days built around your goal. It adapts to your level, your mistakes and your pace.</small>'
      +'<div class="rt-pills"><span>📅 One day at a time</span><span>🎯 Built for your goal</span><span>🧠 Adapts to you</span></div>'
      +'<button type="button" class="btn primary" id="rt-r21">Start my 21 days</button></div><div class="rt-pq">'+PQI+'</div></div>';
  }
  if(R.tab==='reto'){}
  else if(d.rutas.length)main+='<div class="rt-h"><b>Your routes</b><small>'+d.rutas.length+'/'+d.maximo+'</small></div><div class="rt-list">'+d.rutas.map(r=>{const pc=r.lecciones?Math.round(r.completadas/r.lecciones*100):0;
    return '<button type="button" class="rt-card" data-r="'+r.id+'"><div class="h"><span class="e">'+esc(r.emoji)+'</span><div><b data-i18n-skip>'+esc(r.titulo)+'</b><small>'+esc(r.nivel)+' · '+r.completadas+'/'+r.lecciones+' lessons</small></div>'+rtRing(pc,'',46)+'</div><p data-i18n-skip>'+esc(r.resumen||r.pedido)+'</p></button>'}).join('')+'</div>';
  else if(R.tab!=='reto')main+='<div class="rt-empty"><div class="rt-pq sm">'+PQA+'</div><div><b>No routes yet</b><small>Describe your goal on the right and Palanqueta will build your first course.</small></div></div>';
  const HOW='<aside class="rt-side"><div class="rt-how"><b>How it works</b><ol><li><b>3 weeks, 21 days.</b> Survive → Interact → Perform.</li><li><b>One day at a time.</b> A new day opens every morning, so you build the habit.</li><li><b>It adapts.</b> Level, difficulty and review words change with your results.</li><li><b>Days 7, 14 and 21</b> are milestones with real-life practice.</li></ol></div></aside>';
  const side0='<aside class="rt-side"><div class="rt-create"><div class="rt-create-h"><span class="rt-pq xs">'+PQA+'</span><div><b>Build a custom route</b><small>Lessons made for your real situation</small></div></div>'
   +'<textarea id="rt-in" maxlength="400" placeholder="E.g. I sell artisan cheese and I want to hold a sales conversation in English"></textarea>'
   +'<div class="rt-ex">'+(d.ejemplos||[]).slice(0,4).map((e,i)=>'<button type="button" class="st-chip" data-ex="'+i+'" data-i18n-skip>'+esc(e)+'</button>').join('')+'</div>'
   +'<button type="button" class="btn primary rt-mkb" id="rt-mk">✨ Create my route</button><span class="st-note" style="margin:8px 0 0;display:block">Your plan: '+esc(d.plan_nombre)+' · '+d.rutas.length+'/'+d.maximo+' routes · up to '+d.max_lecciones+' lessons · 4 credits</span><div id="rt-mkout"></div></div></aside>';
  const side=R.tab==='reto'?HOW:side0;
  root.innerHTML='<div class="rt-wrap"><div class="rt-main">'+main+'</div>'+side+'</div>';
  root.querySelectorAll('[data-ex]').forEach(b=>b.onclick=()=>{$('rt-in').value=d.ejemplos[+b.dataset.ex];$('rt-in').focus()});
  root.querySelectorAll('[data-r]').forEach(b=>b.onclick=()=>rtOpen(b.dataset.r));
  const rb=root.querySelector('[data-reto]');if(rb)rb.onclick=()=>rtOpen(rb.dataset.reto);
  const r21=$('rt-r21');if(r21)r21.onclick=retoForm;
  if($('rt-mk'))$('rt-mk').onclick=rtCreate;
}
function retoForm(){
  const root=$('rt-root'),d=R.list;R.f={min:10,lvl:''};
  root.innerHTML='<div class="rt-wrap"><div class="rt-main"><button type="button" class="rt-back" id="rt-b">← Back</button><div class="rt-reto form"><div class="rt-reto-t"><span class="rt-tag">🔥 21-day challenge</span><b>Tell Palanqueta your goal.</b><small>The more specific, the better your 21 days will fit you.</small>'
   +'<textarea id="r21-in" maxlength="400" placeholder="E.g. I work in customer service and I need to talk with English-speaking clients"></textarea>'
   +'<div class="rt-ex">'+(d.ejemplos||[]).slice(0,3).map((e,i)=>'<button type="button" class="st-chip" data-ex="'+i+'" data-i18n-skip>'+esc(e)+'</button>').join('')+'</div>'
   +'<b class="rt-lbl">Time per day</b><div class="rt-opts" id="r21-min">'+[5,10,15,20].map(m=>'<button type="button" data-v="'+m+'" class="'+(m===10?'on':'')+'">'+m+' min</button>').join('')+'</div>'
   +'<b class="rt-lbl">Your level</b><div class="rt-opts" id="r21-lvl">'+[['','Auto'],['A1','A1'],['A2','A2'],['B1','B1'],['B2','B2']].map(x=>'<button type="button" data-v="'+x[0]+'" class="'+(x[0]===''?'on':'')+'">'+x[1]+'</button>').join('')+'</div>'
   +'<button type="button" class="btn primary rt-mkb" id="r21-go">🔥 Create my challenge</button><div id="r21-out"></div></div><div class="rt-pq">'+PQI+'</div></div></div>'
   +'<aside class="rt-side"><div class="rt-how"><b>How it works</b><ol><li><b>3 weeks, 21 days.</b> Survive → Interact → Perform.</li><li><b>One day at a time.</b> A new day opens every morning, so you build the habit.</li><li><b>It adapts.</b> Level, difficulty and review words change with your results.</li><li><b>Days 7, 14 and 21</b> are milestones with real-life practice.</li></ol></div></aside></div>';
  $('rt-b').onclick=rtHome;
  root.querySelectorAll('[data-ex]').forEach(b=>b.onclick=()=>{$('r21-in').value=d.ejemplos[+b.dataset.ex];$('r21-in').focus()});
  [['r21-min','min'],['r21-lvl','lvl']].forEach(([id,k])=>$(id).querySelectorAll('button').forEach(b=>b.onclick=()=>{$(id).querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');R.f[k]=k==='min'?+b.dataset.v:b.dataset.v}));
  $('r21-go').onclick=retoCreate;
}
async function retoCreate(){
  if(R.busy)return;const v=$('r21-in').value.trim();
  if(v.length<12)return toast('Tell me a bit more: what do you want to achieve, and where?');
  R.busy=true;$('r21-go').disabled=true;const out=$('r21-out');out.innerHTML='<div class="rt-wait">'+pq()+'<p>Palanqueta is designing your 21 days…</p></div>';
  let tz='';try{tz=Intl.DateTimeFormat().resolvedOptions().timeZone||''}catch(e){}
  try{const d=await post('/api/reto21/crear',{pedido:v,minutos:R.f.min,nivel:R.f.lvl,tz});R.busy=false;toast('Your challenge is ready! 🔥');rtOpen(d.ruta.id)}
  catch(e){R.busy=false;$('r21-go').disabled=false;out.innerHTML='<p class="st-note" data-i18n-skip>'+fmtErr(e)+'</p>'}
}
function rtLessonRow(l,i,last){
  const ic=l.state==='locked'?(l.wait?'⏳':'🔒'):(l.challenge?'🏆':(l.state==='done'?'✓':l.n));
  const sub=l.state==='done'?'Best '+Math.round(l.score||0)+'%':(l.wait?'Opens tomorrow':(l.state==='locked'?'Finish the previous lesson':'Ready'));
  return '<button type="button" class="rt-step '+l.state+(l.challenge?' boss':'')+'" data-l="'+l.id+'"><span class="rt-node">'+ic+'</span><span class="rt-st-t"><b data-i18n-skip>'+esc(l.title)+'</b><small>'+sub+(l.state==='done'&&l.stars?' · '+'★'.repeat(l.stars):'')+'</small></span>'+(l.state==='available'?'<span class="rt-pill">Start</span>':'')+'</button>';
}
function rtWords(d){
  return '<div class="rt-card2"><div class="rt-c2h"><b>📖 Key words</b><small>'+d.palabras.length+'</small></div><div class="rt-words">'+d.palabras.slice(0,12).map((w,i)=>'<button type="button" class="rt-w" data-w="'+i+'" data-i18n-skip><span>🔊</span><span><b>'+esc(w.en)+'</b><small>'+esc(w.es)+'</small></span></button>').join('')+'</div></div>';
}
async function rtOpen(id){
  R.cur=id;const root=$('rt-root');root.innerHTML='<div class="empty">'+pq()+'</div>';
  try{
    const d=await jsonFetch('/api/rutas/'+encodeURIComponent(id));R.det=d;const r=d.ruta;R.tab=r.tipo==='reto21'?'reto':'rutas';window.ltRender&&ltRender(R.tab);
    if(r.tipo==='reto21')return retoView(d);
    const pc=r.lecciones?Math.round(r.completadas/r.lecciones*100):0;
    const nxt=d.lecciones.find(l=>l.state==='available');
    root.innerHTML='<div class="rt-wrap one"><div class="rt-main"><button type="button" class="rt-back" id="rt-b">← My routes</button>'
     +'<div class="rt-hero"><span class="rt-hico">'+esc(r.emoji)+'</span><div class="rt-hmain"><span class="rt-tag">'+esc(r.nivel)+' · custom route</span><h2 data-i18n-skip>'+esc(r.titulo)+'</h2><p data-i18n-skip>'+esc(r.resumen)+'</p>'
     +'<div class="rt-chips"><span>'+r.completadas+'/'+r.lecciones+' lessons</span><span>★ '+r.estrellas+'</span><span>'+d.palabras.length+' words</span></div></div>'+rtRing(pc,'done',96)+'<div class="rt-pq">'+PQI+'</div></div></div></div>'
     +'<div class="rt-wrap"><div class="rt-main"><div class="rt-h"><b>Your path</b><small>'+d.lecciones.length+' steps</small></div><div class="rt-path">'+d.lecciones.map((l,i)=>rtLessonRow(l,i)).join('')+'</div></div>'
     +'<aside class="rt-side">'+(nxt?'<div class="rt-next"><small>Up next</small><b data-i18n-skip>'+esc(nxt.title)+'</b><button type="button" class="btn primary" id="rt-nx">▶ Continue</button></div>':'<div class="rt-next done"><small>Route complete</small><b>Great job! 🎉</b></div>')
     +(r.roleplay?'<div class="rt-card2"><div class="rt-c2h"><b>🎭 Real conversation</b></div><p class="rt-cp">Practice the real situation out loud with an AI partner.</p><button type="button" class="btn" id="rt-rp">Start the role-play</button></div>':'')
     +rtWords(d)+'<button type="button" class="rt-del" id="rt-del">🗑 Delete route</button></aside></div>';
    rtBind(id,d);
  }catch(e){R.cur=null;root.innerHTML='<div class="empty" data-i18n-skip>'+fmtErr(e)+'<br><button type="button" class="btn" style="margin-top:10px" id="rt-r">Back</button></div>';$('rt-r').onclick=rtHome}
}
function rtBind(id,d){
  const root=$('rt-root'),r=d.ruta;
  $('rt-b').onclick=()=>{R.cur=null;rtHome()};
  root.querySelectorAll('.rt-step[data-l]').forEach(b=>b.onclick=()=>{if(b.classList.contains('locked'))return toast(b.querySelector('.rt-node').textContent==='⏳'?'This day opens tomorrow. One day at a time!':'Complete the previous lesson first.');rtStart(id,b.dataset.l)});
  const nx=$('rt-nx');if(nx)nx.onclick=()=>{const l=d.lecciones.find(x=>x.state==='available');if(l)rtStart(id,l.id)};
  const rp=$('rt-rp');if(rp)rp.onclick=()=>window.TalvoScenarioFromRoute(id,d.roleplay,r);
  root.querySelectorAll('[data-w]').forEach(b=>b.onclick=()=>window.TalvoCore.speak(d.palabras[+b.dataset.w].en,.9));
  $('rt-del').onclick=async()=>{if(!confirm(window.TalvoI18n?TalvoI18n.tr('Delete this route and its progress?'):'Delete this route and its progress?'))return;try{await post('/api/rutas/'+id+'/eliminar');R.cur=null;toast('Route deleted');rtHome()}catch(e){toast(e.message)}};
}
const R21W=[['Week 1','Survive'],['Week 2','Interact'],['Week 3','Perform']];
function retoView(d){
  const root=$('rt-root'),r=d.ruta,x=d.reto||{},pc=Math.round(r.completadas/21*100);
  const today=Math.min(21,r.dia_hoy||1);
  const sel=R.sel&&R.sel.id===r.id?R.sel.n:((d.lecciones.find(l=>l.state==='available')||d.lecciones.find(l=>l.state!=='done')||d.lecciones[20]).n);
  let cal='';
  for(let w=0;w<3;w++){
    cal+='<div class="r21-w"><div class="r21-wh"><b>'+R21W[w][0]+'</b><span>'+R21W[w][1]+'</span></div><div class="r21-row">'
      +d.lecciones.slice(w*7,w*7+7).map(l=>'<button type="button" class="r21-d '+l.state+(l.wait?' wait':'')+(l.challenge?' boss':'')+(l.n===today?' today':'')+(l.n===sel?' sel':'')+'" data-n="'+l.n+'"><small>Day</small><b>'+(l.state==='done'?'✓':l.n)+'</b><i>'+(l.challenge?'🏆':(l.wait?'⏳':(l.state==='locked'?'🔒':'')))+'</i></button>').join('')+'</div></div>';
  }
  const esc_=(x.escucha||[]).length?'<div class="rt-card2"><div class="rt-c2h"><b>🎧 Listening check</b></div><p class="rt-cp">How well you catch native-speed English (days 1, 7, 14, 21).</p><div class="r21-lc">'+[1,7,14,21].map(k=>{const e=x.escucha.find(z=>z.day===k);return '<div><i style="height:'+(e?Math.max(6,e.pct):4)+'%"></i><b>'+(e?e.pct+'%':'—')+'</b><small>Day '+k+'</small></div>'}).join('')+'</div></div>':'';
  const adj=(x.ajustes||[]).length?'<div class="rt-card2 adapt"><div class="rt-c2h"><b>🧠 Adapted for you</b></div>'+x.ajustes.slice().reverse().map(a=>'<p class="rt-cp" data-i18n-skip><em>Day '+a.day+'</em> · '+esc(a.note)+'</p>').join('')+'</div>':'';
  root.innerHTML='<div class="rt-wrap one"><div class="rt-main">'
   +'<div class="rt-hero r21"><span class="rt-hico">'+esc(r.emoji)+'</span><div class="rt-hmain"><span class="rt-tag">🔥 21-day challenge</span><h2 data-i18n-skip>'+esc(r.titulo)+'</h2><p data-i18n-skip>'+esc(r.resumen)+'</p>'
   +'<div class="rt-chips"><span>Day '+today+' of 21</span><span>🔥 '+(x.racha||0)+' in a row</span><span>Level '+esc(x.nivel||r.nivel)+'</span><span>'+(x.minutos||10)+' min/day</span></div></div>'+rtRing(pc,'done',96)+'<div class="rt-pq">'+PQI+'</div></div></div></div>'
   +'<div class="rt-wrap"><div class="rt-main"><div class="r21-cal">'+cal+'</div></div><aside class="rt-side" id="r21-side"></aside></div>';
  const side=()=>{
    const n=R.sel&&R.sel.id===r.id?R.sel.n:sel,l=d.lecciones[n-1];if(!l)return;
    const can=l.state==='available',done=l.state==='done';
    $('r21-side').innerHTML='<div class="rt-next '+(done?'done':'')+'"><small>Day '+l.n+(l.challenge?' · milestone 🏆':'')+'</small><b data-i18n-skip>'+esc(l.title)+'</b><p class="rt-cp" data-i18n-skip>'+esc(l.focus)+'</p>'
      +(can?'<button type="button" class="btn primary" id="r21-start">▶ '+(l.n===today?'Start today':'Start day '+l.n)+'</button>':(done?'<button type="button" class="btn" id="r21-start">↻ Practice again · Best '+Math.round(l.score||0)+'%</button>':'<p class="rt-lockmsg">'+(l.wait?'⏳ Opens tomorrow. One day at a time builds the habit.':'🔒 Finish the previous day first.')+'</p>'))+'</div>'
      +esc_+adj+(r.roleplay?'<div class="rt-card2"><div class="rt-c2h"><b>🎭 Real conversation</b></div><p class="rt-cp">Practice your real situation out loud.</p><button type="button" class="btn" id="rt-rp">Start the role-play</button></div>':'')
      +'<button type="button" class="rt-del" id="rt-del">🗑 Delete challenge</button>';
    const st=$('r21-start');if(st)st.onclick=()=>retoStart(r.id,l,st);
    const rp=$('rt-rp');if(rp)rp.onclick=()=>window.TalvoScenarioFromRoute(r.id,d.roleplay,r);
    $('rt-del').onclick=async()=>{if(!confirm(window.TalvoI18n?TalvoI18n.tr('Delete this route and its progress?'):'Delete this route and its progress?'))return;try{await post('/api/rutas/'+r.id+'/eliminar');R.cur=null;R.sel=null;toast('Route deleted');rtHome()}catch(e){toast(e.message)}};
  };
  side();
  root.querySelectorAll('.r21-d').forEach(b=>b.onclick=()=>{R.sel={id:r.id,n:+b.dataset.n};root.querySelectorAll('.r21-d').forEach(z=>z.classList.remove('sel'));b.classList.add('sel');side()});
}
async function retoStart(rid,l,btn){
  if(R.busy)return;R.busy=true;const t=btn.innerHTML;btn.disabled=true;btn.textContent='…';
  try{
    if(!l.ready){const w=$('r21-side').querySelector('.rt-next');w.insertAdjacentHTML('beforeend','<div class="rt-wait" id="r21-w">'+pq()+'<p>Palanqueta is preparing your day…</p></div>');
      await post('/api/reto21/dia',{route_id:rid,lesson_id:l.id})}
    R.busy=false;await rtStart(rid,l.id,true);
  }catch(e){R.busy=false;btn.disabled=false;btn.innerHTML=t;const w=$('r21-w');if(w)w.remove();toast(e.message)}
}
async function rtStart(id,lid){
  try{const d=await jsonFetch('/api/rutas/'+encodeURIComponent(id)+'/leccion/'+encodeURIComponent(lid));window.lpOpenRoute(d,'rutas')}
  catch(e){toast(e.message)}
}
window.TalvoStudio={goTab(tab){R.tab=tab==='reto'?'reto':'rutas';R.cur=null;R.sel=null;const sec=document.getElementById('sec-rutas');if(sec&&sec.classList.contains('active'))rtHome();else section('rutas')},onSection(name){if(name==='traductor')trRender();if(name==='escenarios')scHome();if(name==='rutas')rtHome()},startRouteLesson:rtStart};
})();
