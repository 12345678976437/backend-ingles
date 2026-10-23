/* Talvo · Clips cortos y Presentaciones */
(function(){
'use strict';
const {$,jsonFetch,toast,esc}=window.TalvoCore;
const post=(p,b)=>jsonFetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});
const pq=(s)=>window.pqLoader?window.pqLoader(s):'<div class="empty">…</div>';
const fe=e=>esc(e&&e.message||'Something went wrong.');
const lsGet=(k,d)=>{try{const v=localStorage.getItem(k);return v==null?d:v}catch(e){return d}};
const lsSet=(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}};
const C={list:[],i:0,info:{},es:lsGet('talvo_clip_es','1')==='1',run:0,sess:0,done:0};
/* ---------- voz con subtítulos palabra a palabra ---------- */
function voices(){try{return speechSynthesis.getVoices().filter(v=>/^en/i.test(v.lang))}catch(e){return []}}
function sayLine(text,o,onWord,onEnd){
  let fin=false;const end=()=>{if(fin)return;fin=true;clearTimeout(t);onEnd&&onEnd()};
  const words=text.split(/\s+/).length;const t=setTimeout(end,Math.max(1800,words*520/(o.rate||1))+900);
  if(!('speechSynthesis' in window)){return}
  try{speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang='en-US';u.rate=o.rate||1;u.pitch=o.pitch||1;
    const vs=voices();if(vs.length)u.voice=vs[(o.voice||0)%vs.length];
    let n=0;u.onboundary=e=>{if(e.name&&e.name!=='word')return;const upto=text.slice(0,e.charIndex).split(/\s+/).filter(Boolean).length;onWord&&onWord(upto);n++};
    u.onend=end;u.onerror=end;speechSynthesis.speak(u)}catch(e){end()}
}
function stopSay(){C.run++;C.sess++;try{speechSynthesis.cancel()}catch(e){}}
/* ---------- CLIPS ---------- */
async function clipsHome(){
  const root=$('cl-root');if(!root)return;stopSay();root.innerHTML='<div class="empty">'+pq()+'</div>';
  try{const d=await jsonFetch('/api/clips');C.list=d.clips||[];C.i=0;C.info=d;C.done=0;clipShow()}
  catch(e){root.innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>'}
}
function clipShow(){
  const root=$('cl-root'),c=C.list[C.i];stopSay();
  if(!c){root.innerHTML='<div class="card" style="text-align:center"><div style="font-size:46px">🎬</div><b class="st-h">That\'s all for now</b><p class="st-note">Come back for more clips, or make one about your own topic.</p><div class="st-row" style="justify-content:center"><button type="button" class="btn primary" id="cl-more">More clips</button></div></div>'+topicBox();$('cl-more').onclick=clipsHome;bindTopic();return}
  root.innerHTML='<div class="cl-stage cl-lv'+(c.nivel||0)+'"><div class="cl-top"><b data-i18n-skip>'+esc(c.titulo)+'</b><small>'+(C.i+1)+' / '+C.list.length+'</small></div><div class="cl-emoji" data-i18n-skip>'+esc(c.emoji)+'</div>'
   +'<div class="cl-lines" id="cl-lines">'+c.escena.map((l,k)=>'<button type="button" class="cl-line '+(l.quien==='B'?'b':'a')+'" data-k="'+k+'"><span class="cl-who">'+(l.quien==='B'?'B':'A')+'</span><span class="cl-en" data-i18n-skip>'+l.en.split(/\s+/).map((w,j)=>'<i data-j="'+j+'">'+esc(w)+'</i>').join(' ')+'</span><small class="cl-es" data-i18n-skip>'+esc(l.es)+'</small></button>').join('')+'</div>'
   +'<div class="st-row cl-ctl"><button type="button" class="btn primary" id="cl-play">▶ Play</button><button type="button" class="btn" id="cl-slow">🐢 Slow</button><button type="button" class="btn lp-fastbtn" id="cl-fast">⚡ Native speed</button><label class="cl-tog"><input type="checkbox" id="cl-es" '+(C.es?'checked':'')+'> <span>Spanish subtitles</span></label></div></div>'
   +'<div id="cl-quiz"></div>'+topicBox();
  const lines=root.querySelector('#cl-lines');lines.classList.toggle('noes',!C.es);
  $('cl-es').onchange=e=>{C.es=e.target.checked;lsSet('talvo_clip_es',C.es?'1':'0');lines.classList.toggle('noes',!C.es)};
  $('cl-play').onclick=()=>playAll(c,1);$('cl-slow').onclick=()=>playAll(c,.65);$('cl-fast').onclick=()=>playAll(c,1.15);
  lines.querySelectorAll('[data-k]').forEach(b=>b.onclick=()=>{stopSay();playOne(c,+b.dataset.k,1)});
  bindTopic();
}
function mark(k,upto){const L=document.querySelectorAll('#cl-lines .cl-line');L.forEach((el,j)=>{el.classList.toggle('on',j===k);if(j===k)el.querySelectorAll('i').forEach((w,n)=>w.classList.toggle('hit',n<upto))});const a=L[k];if(a)try{a.scrollIntoView({block:'nearest',behavior:'smooth'})}catch(e){}}
function playOne(c,k,rate,next){const l=c.escena[k],id=++C.run,n=l.en.split(/\s+/).length;mark(k,0);
  sayLine(l.en,{rate,pitch:l.quien==='B'?.85:1.12,voice:l.quien==='B'?1:0},w=>{if(id===C.run)mark(k,w)},()=>{if(id!==C.run)return;mark(k,n);next&&next()})}
function playAll(c,rate){stopSay();const sid=C.sess;const go=k=>{if(C.sess!==sid)return;if(k>=c.escena.length){clipQuiz(c);return}playOne(c,k,rate,()=>setTimeout(()=>go(k+1),350))};go(0)}
function clipQuiz(c){
  const q=c.quiz,box=$('cl-quiz');if(!box||box.dataset.c===c.id)return;box.dataset.c=c.id;
  box.innerHTML='<div class="card"><b class="st-h">Quick check</b><p data-i18n-skip>'+esc(q.q)+'</p><div class="ob-options">'+q.opciones.map((o,i)=>'<button type="button" class="ob-option" data-o="'+i+'" data-i18n-skip>'+esc(o)+'</button>').join('')+'</div><div id="cl-res"></div></div>';
  box.querySelectorAll('[data-o]').forEach(b=>b.onclick=async()=>{const ok=+b.dataset.o===q.correcta;box.querySelectorAll('[data-o]').forEach(x=>{x.disabled=true;if(+x.dataset.o===q.correcta)x.style.borderColor='var(--success)'});if(!ok)b.style.borderColor='var(--danger)';
    let xp=0,lim=false;try{const r=await post('/api/clips/completar',{id:c.id,acierto:ok});xp=r.xp;lim=r.limite_alcanzado}catch(e){}
    $('cl-res').innerHTML='<p class="st-note">'+(ok?'Correct! 🎉':'Not quite, listen again.')+(xp?' <b>+'+xp+' XP</b>':'')+(lim?' <span data-i18n-skip>'+esc('Daily XP limit for clips reached.')+'</span>':'')+'</p><div class="st-row"><button type="button" class="btn" id="cl-re">Replay</button><button type="button" class="btn primary" id="cl-nx">Next clip →</button></div>';
    $('cl-re').onclick=()=>{box.dataset.c='';box.innerHTML='';playAll(c,1)};$('cl-nx').onclick=()=>{C.i++;clipShow()}})
}
function topicBox(){return '<div class="card"><b class="st-h">Make a clip about your topic</b><p class="st-note">'+(C.info.tema_ok?'Describe a situation and I will write a new clip. Uses 1 credit.':'Custom clips are available from the Basic plan.')+'</p><div class="st-row"><input id="cl-t" class="vz-in" maxlength="120" placeholder="Asking for help at the gym…"><button type="button" class="btn" id="cl-tb">✨ Create</button></div></div>'}
function bindTopic(){const b=$('cl-tb');if(!b)return;b.onclick=async()=>{const t=$('cl-t').value.trim();if(t.length<3)return toast('Write a topic first.');b.disabled=true;b.textContent='…';
  try{const d=await post('/api/clips/tema',{tema:t});C.list.splice(C.i,0,d.clip);clipShow()}catch(e){toast(e.message);b.disabled=false;b.textContent='✨ Create'}}}
/* ---------- PRESENTACIONES ---------- */
const P={slides:[],i:0,scores:[],title:'',hide:false,rec:null,stream:null,chunks:[],t0:0,tick:null};
function presHome(){
  const root=$('pr-root');if(!root)return;P.slides=[];stopSay();
  root.innerHTML='<div class="card"><b class="st-h">Rehearse your presentation</b><p class="st-note">Paste the text of your slides (one slide per paragraph, in Spanish or English) or upload a .pptx. I will write what to say in English and you practice each slide out loud. Uses 2 credits · Basic plan and up.</p>'
   +'<textarea id="pr-in" class="vz-in" rows="8" maxlength="3500" style="width:100%" placeholder="Slide 1: Sales results Q3&#10;Sales grew 12%…&#10;&#10;Slide 2: Next steps…"></textarea>'
   +'<div class="st-row" style="margin-top:10px"><button type="button" class="btn primary" id="pr-go">✨ Create my presentation</button><label class="btn" for="pr-up">📁 Upload .pptx</label><input type="file" id="pr-up" accept=".pptx" hidden></div><div id="pr-out"></div></div>';
  $('pr-go').onclick=presCreate;$('pr-up').onchange=presUpload;
}
function loadJSZip(){return new Promise((res,rej)=>{if(window.JSZip)return res(window.JSZip);const s=document.createElement('script');s.src='https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js';s.onload=()=>res(window.JSZip);s.onerror=()=>rej(new Error('Could not load the .pptx reader. Paste the text instead.'));document.head.appendChild(s)})}
async function pptxText(file){
  const Z=await loadJSZip();const zip=await Z.loadAsync(file);
  const names=Object.keys(zip.files).filter(n=>/^ppt\/slides\/slide\d+\.xml$/.test(n)).sort((a,b)=>parseInt(a.match(/(\d+)\.xml/)[1])-parseInt(b.match(/(\d+)\.xml/)[1]));
  const out=[];for(const n of names){const xml=await zip.files[n].async('string');const doc=new DOMParser().parseFromString(xml,'application/xml');const t=[...doc.getElementsByTagName('a:t')].map(x=>x.textContent.trim()).filter(Boolean);if(t.length)out.push(t.join('\n'))}
  return out.join('\n\n');
}
async function presUpload(e){const f=e.target.files[0];if(!f)return;if(f.size>10*1024*1024)return toast('File too large (10 MB max).');
  $('pr-out').innerHTML='<div class="empty">'+pq('sm')+'</div>';
  try{const t=await pptxText(f);if(!t)throw new Error('I could not find text in that file.');$('pr-in').value=t.slice(0,3500);$('pr-out').innerHTML='<p class="st-note">Slides loaded. Review the text and tap Create.</p>'}catch(er){$('pr-out').innerHTML='<p class="st-note" data-i18n-skip>'+fe(er)+'</p>'}}
async function presCreate(){
  const t=$('pr-in').value.trim();if(t.length<20)return toast('Paste the text of your slides first.');
  const b=$('pr-go');b.disabled=true;$('pr-out').innerHTML='<div class="empty">'+pq()+'</div>';
  try{const d=await post('/api/presentacion/guion',{texto:t});P.slides=d.slides;P.title=d.titulo;P.i=0;P.scores=[];presSlide()}
  catch(e){$('pr-out').innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>';b.disabled=false}
}
function recKill(){clearInterval(P.tick);try{if(P.rec&&P.rec.state!=='inactive')P.rec.stop();if(P.stream)P.stream.getTracks().forEach(t=>t.stop())}catch(e){}P.rec=null}
function presSlide(){
  const root=$('pr-root');recKill();stopSay();
  if(P.i>=P.slides.length){const sc=P.scores.filter(x=>x!=null),avg=sc.length?Math.round(sc.reduce((a,c)=>a+c,0)/sc.length):0;
    root.innerHTML='<div class="card" style="text-align:center"><div style="font-size:46px">🎤</div><b class="st-h" data-i18n-skip>'+esc(P.title)+'</b><div class="vz-scores" style="justify-content:center"><div class="vz-sc"><strong>'+avg+'</strong><small>Average</small></div><div class="vz-sc"><strong>'+sc.length+'/'+P.slides.length+'</strong><small>Slides practiced</small></div></div><div class="st-row" style="justify-content:center"><button type="button" class="btn" id="pr-again">Practice again</button><button type="button" class="btn primary" id="pr-new">New presentation</button></div></div>';
    $('pr-again').onclick=()=>{P.i=0;P.scores=[];presSlide()};$('pr-new').onclick=presHome;return}
  const s=P.slides[P.i];
  root.innerHTML='<div class="card"><div class="st-row" style="justify-content:space-between"><b class="st-h">Slide '+(P.i+1)+' / '+P.slides.length+'</b><label class="cl-tog"><input type="checkbox" id="pr-hide" '+(P.hide?'checked':'')+'> <span>Hide the script</span></label></div>'
   +'<p class="vz-phrase" data-i18n-skip>'+esc(s.titulo)+'</p><p class="st-note" data-i18n-skip>'+esc(s.es)+'</p>'
   +'<div class="pr-script" id="pr-script" data-i18n-skip>'+esc(s.guion)+'</div><div class="vz-words" data-i18n-skip>'+s.frases_clave.map(x=>'<span class="chip">'+esc(x)+'</span>').join('')+'</div>'
   +'<div class="st-row"><button type="button" class="btn" id="pr-l">🔊 Listen</button><button type="button" class="btn lp-fastbtn" id="pr-f">⚡ Native speed</button><button type="button" class="btn primary" id="pr-r">🎙️ Rehearse</button><button type="button" class="btn" id="pr-n">Skip →</button><span id="pr-t" class="st-note" style="margin:0"></span></div><div id="pr-sc"></div></div>';
  const sh=()=>$('pr-script').style.display=P.hide?'none':'block';sh();
  $('pr-hide').onchange=e=>{P.hide=e.target.checked;sh()};
  $('pr-l').onclick=()=>window.TalvoCore.speak(s.guion,.95);const pf=$('pr-f');if(pf)pf.onclick=()=>window.TalvoNative.say(s.guion);$('pr-n').onclick=()=>{P.scores[P.i]=null;P.i++;presSlide()};
  let on=false;const r=$('pr-r');
  const stop=async()=>{if(!on)return;on=false;clearInterval(P.tick);r.disabled=true;r.textContent='Scoring…';
    const x=await new Promise(res=>{const rc=P.rec;if(!rc)return res(null);rc.onstop=()=>{const type=(P.chunks[0]&&P.chunks[0].type)||'audio/webm';if(P.stream)P.stream.getTracks().forEach(t=>t.stop());res({blob:new Blob(P.chunks,{type}),secs:(Date.now()-P.t0)/1000})};try{rc.stop()}catch(e){res(null)}});
    $('pr-t').textContent='';
    try{if(!x||x.secs<2)throw new Error('I did not hear enough. Try again.');const fd=new FormData();fd.append('audio',x.blob,'recording.webm');fd.append('frase_esperada',s.guion);fd.append('fast','1');fd.append('shadow','1');
      const d=await jsonFetch('/analizar-audio-real',{method:'POST',body:fd});const sc=Math.round(d.puntuacion_global||0);P.scores[P.i]=sc;
      const chips=(d.palabras||[]).map(w=>{const a=w.precision||0;return '<span class="lp-w '+(a>=80?'g':a>=60?'m':'b')+'" data-i18n-skip>'+esc(w.palabra)+'<i>'+Math.round(a)+'</i></span>'}).join('');
      $('pr-sc').innerHTML='<div class="vz-scores"><div class="vz-sc"><strong>'+sc+'</strong><small>Score</small></div><div class="vz-sc"><strong>'+Math.round(d.completitud||0)+'</strong><small>Completeness</small></div></div><div class="vz-words">'+chips+'</div><div class="st-row"><button type="button" class="btn" id="pr-a">Try again</button><button type="button" class="btn primary" id="pr-x">'+(P.i>=P.slides.length-1?'Finish':'Next slide →')+'</button></div>';
      $('pr-a').onclick=()=>{$('pr-sc').innerHTML=''};$('pr-x').onclick=()=>{P.i++;presSlide()}}
    catch(e){$('pr-sc').innerHTML='<p class="st-note" data-i18n-skip>'+fe(e)+'</p>'}
    r.disabled=false;r.textContent='🎙️ Rehearse'};
  r.onclick=async()=>{if(on)return stop();
    try{if(!navigator.mediaDevices||!window.MediaRecorder)throw new Error('Your browser does not support microphone recording.');
      const st=await navigator.mediaDevices.getUserMedia({audio:true});let m='';for(const k of ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/mp4']){if(MediaRecorder.isTypeSupported(k)){m=k;break}}
      P.stream=st;P.chunks=[];P.rec=new MediaRecorder(st,m?{mimeType:m}:undefined);P.rec.ondataavailable=e=>{if(e.data.size)P.chunks.push(e.data)};P.rec.start();P.t0=Date.now();on=true;r.textContent='⏹ Stop';
      P.tick=setInterval(()=>{const t=(Date.now()-P.t0)/1000;$('pr-t').textContent=Math.floor(t)+'s / 45s';if(t>=45)stop()},300)}
    catch(e){$('pr-sc').innerHTML='<p class="st-note" data-i18n-skip>'+(e&&e.name==='NotAllowedError'?'Microphone blocked. Allow it in your browser settings.':fe(e))+'</p>'}};
}
window.TalvoClips={onSection(n){if(n==='clips')clipsHome();else if(n==='presentacion')presHome();else{stopSay();recKill()}},_pptx:pptxText};
})();
