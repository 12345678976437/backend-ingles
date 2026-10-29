/* Talvo · Ruta de aprendizaje v2
   Mapa de la ruta, reproductor de lecciones (estilo Duolingo), práctica de pronunciación
   con retroalimentación por sonido (estilo ELSA) y Sound Lab. */
(function(){
'use strict';
const {$,jsonFetch,state,toast,section,speak,esc,setMascotState,reactToScore,loadDashboard}=window.TalvoCore;
const ready=f=>document.readyState==='loading'?document.addEventListener('DOMContentLoaded',f):f();
const LP={data:null,sounds:null,openPlaced:{}};
window.lpTogglePlaced=function(c){LP.openPlaced[c]=!LP.openPlaced[c];if(LP.data)renderHome(LP.data,LP.plan)};
window.LP=LP;
const nrm=s=>String(s||'').toLowerCase().replace(/[’]/g,"'").replace(/[^a-z0-9' ]+/g,' ').replace(/\s+/g,' ').trim();
function lev(a,b){const m=a.length,n=b.length;if(!m)return n;if(!n)return m;let p=Array.from({length:n+1},(_,i)=>i);for(let i=1;i<=m;i++){const c=[i];for(let j=1;j<=n;j++)c[j]=Math.min(p[j]+1,c[j-1]+1,p[j-1]+(a[i-1]===b[j-1]?0:1));p=c}return p[n]}
const shuffle=a=>{a=a.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a};
const starStr=n=>'★'.repeat(n)+'☆'.repeat(3-n);

/* ---------- sonidos (sin archivos, WebAudio) ---------- */
let actx=null;
function beep(ok){try{actx=actx||new (window.AudioContext||window.webkitAudioContext)();const o=actx.createOscillator(),g=actx.createGain();o.connect(g);g.connect(actx.destination);const t=actx.currentTime;o.type='sine';o.frequency.setValueAtTime(ok?660:220,t);if(ok)o.frequency.setValueAtTime(880,t+.09);g.gain.setValueAtTime(.08,t);g.gain.exponentialRampToValueAtTime(.0001,t+.28);o.start(t);o.stop(t+.3)}catch(e){}}
function buzz(ms){try{navigator.vibrate&&navigator.vibrate(ms)}catch(e){}}

/* =====================  MAPA DE LA RUTA  ===================== */
window.loadLearningPath=async function(){
  const root=$('lp-home');if(!root)return;
  root.innerHTML='<div class="empty">'+window.pqLoader()+'</div>';
  try{const [d,plan]=await Promise.all([jsonFetch('/api/learning-path'),jsonFetch('/api/learning-path/daily-plan').catch(()=>null)]);LP.data=d;LP.plan=plan;renderHome(d,plan);if(window.TalvoOffline&&!d.__offline)setTimeout(()=>window.TalvoOffline.prefetch(d),2500)}
  catch(e){root.innerHTML='<div class="empty">'+esc(e.message)+'<br><button type="button" class="btn" style="margin-top:10px" onclick="loadLearningPath()">Retry</button></div>'}
};
function ring(pct){const r=22,c=2*Math.PI*r;return '<svg viewBox="0 0 54 54" class="lp2-ring"><circle cx="27" cy="27" r="'+r+'" class="bg"/><circle cx="27" cy="27" r="'+r+'" class="fg" style="stroke-dasharray:'+c+';stroke-dashoffset:'+(c*(1-Math.min(1,pct)))+'"/></svg>'}
function planHTML(p){
  if(!p||!p.steps||!p.steps.length)return '';
  let h='<div class="lp2-plan"><div class="lp2-plan-h"><b>🎯 Today\'s plan</b><span>'+p.done+'/'+p.total+'</span></div><div class="bar" style="height:6px;margin:8px 0 10px"><div class="fill" style="width:'+Math.round(p.done/p.total*100)+'%"></div></div>';
  p.steps.forEach(st=>{
    h+='<button type="button" class="lp2-step'+(st.done?' done':'')+'" onclick="lpRunStep(\''+st.id+'\')"><span class="ico">'+(st.done?'✓':st.icon)+'</span><span class="tx"><b data-i18n-skip>'+esc(st.title)+'</b><small>'+esc(st.desc)+'</small></span><span class="go">'+(st.done?'':'›')+'</span></button>';
  });
  h+='<p class="lp2-plan-note">'+(p.bonus.claimed?'🎉 Plan complete — bonus earned today.':(p.complete?'Plan complete!':'Finish all steps to earn +'+p.bonus.xp+' bonus XP.'))+'</p></div>';
  return h;
}
function renderHome(d,plan){
  const t=d.today||{lessons:0,target:2},tot=d.totals||{};
  const pct=t.target?t.lessons/t.target:0;
  let h='<div class="lp3-side"><div class="lp2-stats">'
   +'<div class="lp2-stat"><b>⭐ '+d.xp+'</b><small>XP</small></div>'
   +'<div class="lp2-stat"><b>🏆 '+(tot.stars||0)+'<em>/'+(tot.max_stars||0)+'</em></b><small>Stars</small></div>'
   +'<div class="lp2-stat goal">'+ring(pct)+'<span><b>'+t.lessons+'/'+t.target+'</b><small>Today</small></span></div></div>';
  if(d.profile&&d.profile.goal_label)h+='<p class="lp2-goal">🎯 '+esc(d.profile.goal_label)+' · '+esc(String(d.profile.level))+' · '+esc(String(d.profile.daily_minutes))+' min/day</p>';
  const planH=planHTML(plan);
  if(planH)h+=planH;
  else if(d.next){const n=d.next;
    h+='<div class="lp2-hero lp3-next"><span class="lp3-pq"><img src="palanqueta-asoma.webp" alt="" draggable="false"></span><div class="lp2-hero-ico">'+(n.challenge?'🏆':esc(n.icon))+'</div><div class="lp2-hero-txt"><small>Up next · '+esc(n.reason)+'</small><b data-i18n-skip>'+esc(n.unit_title)+' — '+esc(n.lesson_title)+'</b></div><button type="button" class="btn primary" onclick="lpStart(\''+n.unit_code+'\',\''+n.lesson_id+'\')">▶ Start</button></div>';
  }
  h+='<div class="lp2-quick">'
   +'<button type="button" class="lp2-q" onclick="lpReview()"'+(d.review&&d.review.available?'':' disabled')+'><span>🔁</span><b>Review</b><small>'+(d.review&&d.review.mistakes?d.review.mistakes+' tricky items':'Refresh what you learned')+'</small></button>'
   +'<button type="button" class="lp2-q" onclick="lpOpenSounds()"><span>🎙️</span><b>Sound Lab</b><small data-i18n-skip>'+((d.sounds&&d.sounds.focus)||[]).map(s=>esc(s.ipa)).join(' · ')+'</small></button></div>';
  if(d.profile&&d.profile.level_label)h+='<div class="lp2-start">🧭 Your path starts at <b data-i18n-skip>'+esc(d.profile.level_label)+'</b>. Earlier sections are marked as already known, and your level moves up or down automatically as you practice.<div class="lp3-lv"><small>Not your level? Change it:</small>'+[['beginner','A1'],['elementary','A2'],['intermediate','B1'],['advanced','B2']].map(x=>'<button type="button" class="'+(d.profile.level===x[0]?'on':'')+'" onclick="lpSetLevel(\''+x[0]+'\')">'+x[1]+'</button>').join('')+'</div></div>';
  h+='</div><div class="lp3-main">';
  (d.sections||[]).forEach((s,si)=>{
    const pc=s.total?Math.round(s.done/s.total*100):0;
    if(s.placed&&!LP.openPlaced[s.code]){h+='<div class="lp2-placed"><div><small>Section '+(si+1)+' · '+esc(s.level)+'</small><b>'+esc(s.title)+'</b><small>You tested above this level</small></div><span><span class="tag">✓ Already known</span> <button type="button" class="btn" onclick="lpTogglePlaced(\''+s.code+'\')">Review anyway</button></span></div>';return}
    h+='<div class="lp2-sec'+(s.open?'':' closed')+'"><div class="lp2-sec-h"><div><small>Section '+(si+1)+' · '+esc(s.level)+'</small><b>'+esc(s.title)+'</b></div><span class="lp2-pct">'+pc+'%</span></div><div class="bar lp3-bar"><div class="fill" style="width:'+pc+'%"></div></div>';
    if(!s.open)h+='<p class="lp2-lock-note">🔒 Unlocks when you finish 60% of the previous section.</p>';
    h+='<div class="lp3-units">';s.units.forEach(u=>{h+=unitHTML(u)});h+='</div>';
    h+='</div>';
  });
  $('lp-home').innerHTML='<div class="lp3">'+h+'</div></div>';
  ltRender('path');
}
window.lpSetLevel=async function(l){
  try{await jsonFetch('/api/learning-path/level',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({level:l})});toast('Level updated');window.loadLearningPath()}catch(e){toast(e.message)}
};
function unitHTML(u){
  const pc=u.total_topics?Math.round(u.completed_topics/u.total_topics*100):0;
  let h='<div class="lp2-unit'+(u.unlocked?'':' locked')+(u.recommended?' rec':'')+'"><div class="lp2-unit-h"><span class="lp2-unit-ico">'+(u.unlocked?esc(u.icon):'🔒')+'</span><div class="lp2-unit-t"><b data-i18n-skip>'+esc(u.title)+'</b><small data-i18n-skip>'+esc(u.description)+'</small></div>'+(u.recommended?'<span class="lp2-rec">For your goal</span>':'')+'</div>'
   +'<div class="bar" style="height:6px;margin:8px 0 4px"><div class="fill" style="width:'+pc+'%"></div></div>';
  if(!u.unlocked){h+='<p class="lp2-lock-note">Finish the previous section or unlock it with gems in the Shop.</p></div>';return h}
  h+='<div class="lp2-nodes">';
  const offs=[0,38,64,38,0,-38,-64,-38];
  u.lessons.forEach((l,i)=>{
    const off=offs[i%offs.length];
    const ico=l.state==='locked'?'🔒':(l.challenge?'🏆':(l.state==='done'?'✓':(i+1)));
    h+='<button type="button" class="lp2-node '+l.state+(l.challenge?' boss':'')+'" style="--off:'+off+'px" onclick="lpStart(\''+u.code+'\',\''+l.id+'\',null,\''+l.state+'\')"><span class="lp2-hex">'+ico+'</span><span class="lp2-nl"><b data-i18n-skip>'+esc(l.title)+'</b>'+(l.state==='done'?'<i class="st s'+l.stars+'">'+starStr(l.stars)+'</i>':'')+'</span></button>';
  });
  return h+'</div></div>';
}
window.backToLPUnits=window.loadLearningPath;

/* =====================  REPRODUCTOR  ===================== */
const P={d:null,kind:'lesson',queue:[],i:0,total:0,correct:0,cleared:0,mistakes:[],t0:0,cur:null,answered:false,ready:false,evalFn:null,speakScores:[],sound:null,data:null};
const show=(id,on)=>{const e=$(id);if(e)e.hidden=!on};
function body(h){$('lp-pbody').innerHTML=h;$('lp-pbody').scrollTop=0}
function setMain(label,cls,enabled){const b=$('lp-pmain');b.textContent=label;b.className='btn primary'+(cls?' '+cls:'');b.disabled=!enabled;b.style.display=''}
function hideMain(){$('lp-pmain').style.display='none'}
function feedback(ok,msg,sub,ans){const f=$('lp-fb');f.className='lp-fb show '+(ok?'good':'bad');f.innerHTML='<b>'+esc(msg)+'</b>'+(sub||ans?'<span>'+esc(sub||'')+(ans?' <em data-i18n-skip>'+esc(ans)+'</em>':'')+'</span>':'')}
function clearFb(){const f=$('lp-fb');f.className='lp-fb';f.innerHTML=''}
const REAL_TIPS=["Real English: people say “gonna”, “wanna” and “gotta” all the time. “I'm gonna go” = “I am going to go”.","Real English: natives blend words. “What do you want?” often sounds like “Whaddya want?”. Listen to the rhythm, not word by word.","Real English: “I don't know” usually sounds like “I dunno”. You'll hear it everywhere.","Real English: if you don't catch something, say “Sorry, could you say that again?” or “Come again?”. Nobody minds.","Real English: “How's it going?” and “What's up?” are greetings, not real questions. A quick “Good, you?” is enough.","Real English: in the US a T between vowels sounds almost like a D. “Water” ≈ “wader”, “better” ≈ “bedder”.","Real English: at a restaurant people say “Can I get a…?” more than “I would like…”.","Real English: “Yeah, no worries” and “No problem” are the everyday answers to “thank you”.","Real English: “Let me know” and “Sounds good” are the glue of daily conversation. Use them.","Real English: native speakers talk fast because they link sounds: “check it out” ≈ “che-ki-dout”. Slow audio helps; then try normal speed.","Real English: “Kind of” and “sort of” (“kinda”, “sorta”) soften almost everything: “It's kinda expensive”."];
const COACH_OK=["Nice! That's exactly how people say it.","You got it. Keep that rhythm!","Clean. That one's yours now.","Perfect — that's real, everyday English.","Yes! Your ear is getting sharper."];
const COACH_NO=["No worries — mistakes are how it sticks. I'll bring it back.","Close! Read the correct one below and say it out loud once.","That one trips everyone. It will come back in a moment.","Good try. Listen again, then keep going."];
const KIND_LABEL={pick_meaning:'Meaning',pick_word:'Vocabulary',listen_pick:'Listening',dialog:'Conversation',fill:'Grammar in context',build:'Build the sentence',type_listen:'Dictation',type_translate:'Writing',match:'Match',speak:'Speaking'};
let tipI=0;document.addEventListener('click',e=>{if(e.target&&e.target.id==='lp-explain')explainNow()});
function coach(msg,mood){
  const b=$('lp-cbub'),pq=$('lp-cpq');if(!b)return;
  b.innerHTML='<span>'+msg+'</span>';b.className='lp-cbub '+(mood||'');
  pq.className='lp-coach-pq '+(mood||'');void pq.offsetWidth;
}
let explainBusy=false;
async function explainNow(){
  const ex=P.cur;if(!ex||explainBusy)return;explainBusy=true;const btn=$('lp-explain');if(btn)btn.disabled=true;
  coach('🎓 Un momento, te lo explico…','idle');
  try{
    const info=[ex.q,ex.text,ex.say,ex.answer,ex.es].filter(Boolean).join(' | ').slice(0,400);
    const d=await TalvoCore.jsonFetch('/api/tutor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({modo:'maestro',mensaje:'Estoy en una lección y no entiendo este ejercicio ('+ex.type+'): '+info+'. Explícamelo en español, muy corto y fácil, y dime cómo se dice de forma natural.'})});
    const t=d.respuesta||'';coach(TalvoCore.esc(t),'idle');TalvoCore.teacherSpeak(t)
  }catch(e){coach(TalvoCore.esc(e.message),'idle')}
  finally{explainBusy=false;if(btn)btn.disabled=false}
}
function realTip(){return REAL_TIPS[(tipI++)%REAL_TIPS.length]}
function coachStats(){
  const done=P.answeredN||0;$('lp-cacc').textContent=done?Math.round(P.okN/done*100)+'%':'—';
  $('lp-cstreak').textContent=P.streak||0;
  const c=$('lp-combo');if(c){c.hidden=!(P.streak>=2);c.querySelector('b').textContent=P.streak||0;c.classList.remove('bump');void c.offsetWidth;c.classList.add('bump')}
}
function progress(){const n=Math.max(1,P.total);
  const t=$('lp-ptitle');if(t&&P.d)t.textContent=P.d.title||P.d.unit_title||'';
  const k=$('lp-pkind');if(k&&P.d)k.textContent=(P.kind==='review'?'Review':P.kind==='sound'?'Sound practice':P.kind==='route'?(P.d.unit_title||'Route'):(P.d.unit_title||'Lesson'));
$('lp-pfill').style.width=Math.min(100,Math.round(P.cleared/n*100))+'%';$('lp-pcount').textContent=Math.min(P.cleared,P.total)+'/'+P.total}

window.lpStart=async function(unit,lesson,mode,state){
  if(state==='locked')return toast('Complete the previous lesson first.');
  try{
    const d=await jsonFetch('/api/learning-path/lesson/'+encodeURIComponent(unit)+'/'+encodeURIComponent(lesson)+(mode?'?mode='+mode:''));
    openPlayer(d,mode==='review'?'review':'lesson');
  }catch(e){toast(e.message)}
};
window.lpReview=function(){
  const d=LP.data;if(!d)return;
  const units=(d.units||[]).filter(u=>u.completed_topics>0).sort((a,b)=>b.completed_topics-a.completed_topics);
  const u=units[0]||(d.units||[])[0];if(!u)return;
  lpStart(u.code,'review','review');
};
function openPlayer(d,kind,origin){
  Object.assign(P,{d,kind,queue:d.exercises.map(e=>Object.assign({},e)),i:0,total:d.exercises.length,correct:0,cleared:0,mistakes:[],t0:Date.now(),cur:null,answered:false,ready:false,speakScores:[],sound:d.sound||null,origin:origin||null,finished:false,resultAction:null});
  P.streak=0;P.okN=0;P.answeredN=0;P.lcN=0;P.lcOk=0;tipI=Math.floor(Math.random()*REAL_TIPS.length);
  document.body.classList.add('lp-open');show('lp-player',true);clearFb();progress();coachStats();
  const cw=$('lp-cwords');if(cw){const ws=(d.teach||[]).slice(0,10);cw.parentNode.style.display=ws.length?'':'none';cw.innerHTML=ws.map((w,i)=>'<button type="button" data-i="'+i+'" data-i18n-skip>'+esc(w.en)+'</button>').join('');cw.querySelectorAll('button').forEach(b=>b.onclick=()=>speak(ws[+b.dataset.i].en,.9))}
  coach(d.note?('💡 '+esc(d.note)):realTip(),'idle');
  if(d.teach&&d.teach.length||d.sound||d.note)renderTeach();else nextEx();
}
function closePlayer(){stopRec();try{speechSynthesis.cancel()}catch(e){}show('lp-player',false);document.body.classList.remove('lp-open');setMascotState&&setMascotState('idle')}
window.lpClosePlayer=closePlayer;
window.lpOpenRoute=function(d,origin){openPlayer(d,'route',origin||'rutas')};
function renderTeach(){
  const d=P.d;clearFb();
  const hasWords=P.sound||(d.teach&&d.teach.length);
  let h='<div class="lp-card"><div class="lp-kicker">'+(P.sound?'New sound':(hasWords?'New words':'Personalized for you'))+'</div><h2 data-i18n-skip>'+esc(d.title)+'</h2>';
  if(P.sound)h+='<div class="lp-ipa" data-i18n-skip>/'+esc(P.sound.ipa)+'/</div><p class="lp-tip" data-i18n-skip>'+esc(P.sound.tip)+'</p>'+(window.mouthDiagram?window.mouthDiagram(P.sound.id):'');
  if(d.note&&!P.sound)h+='<p class="lp-tip" '+(d.mode==='exercises'?'':'data-i18n-skip')+'>💡 '+esc(d.note)+'</p>';
  const words=P.sound?P.sound.words.map(w=>({en:w,es:'',emoji:''})):d.teach;
  h+='<div class="lp-teach">'+words.map((w,i)=>'<button type="button" class="lp-word" data-w="'+i+'"><span class="e">'+(w.emoji||'🔊')+'</span><b data-i18n-skip>'+esc(w.en)+'</b><small data-i18n-skip>'+esc(w.es)+'</small></button>').join('')+'</div></div>';
  body(h);
  $('lp-pbody').querySelectorAll('.lp-word').forEach(b=>b.addEventListener('click',()=>speak(words[+b.dataset.w].en,.9)));
  setMain('Start','',true);P.evalFn=null;P.answered=true;P.teach=true;
}
function nextEx(){
  clearFb();P.teach=false;
  if(P.i>=P.queue.length)return finish();
  const ex=P.queue[P.i];P.cur=ex;P.answered=false;P.ready=false;P.evalFn=null;progress();
  const r=R[ex.type];if(!r){P.i++;return nextEx()}
  if(ex.type==='speak'&&window.TalvoOffline&&window.TalvoOffline.isOff()){if(P.kind!=='sound')P.total=Math.max(1,P.total-1);P.queue.splice(P.i,1);P.cur=null;progress();return nextEx()}
  if(ex.check)coach('🎧 Listening check: native speed, like real life. Don\'t translate word by word — catch the meaning.','idle');
  if(P.streak<2||Math.random()<.35)coach(realTip(),'idle');
  r(ex);
}
function resolve(ok,correctText,opts){
  opts=opts||{};P.answered=true;const ex=P.cur;const first=!ex._retry;
  if(ok){if(first)P.correct++;P.cleared++;}
  else if(first){if(ex.ref&&ex.ref.en)P.mistakes.push(ex.ref);}
  if(!ok&&!opts.noRequeue)P.queue.push(Object.assign({},ex,{_retry:true}));
  if(!ok&&opts.noRequeue)P.cleared++;
  beep(ok);if(!ok)buzz(60);
  if(first&&ex.check){P.lcN=(P.lcN||0)+1;if(ok)P.lcOk=(P.lcOk||0)+1}
  if(first){P.answeredN++;if(ok){P.okN++;P.streak++}else P.streak=0}
  coachStats();coach(ok?COACH_OK[Math.floor(Math.random()*COACH_OK.length)]:COACH_NO[Math.floor(Math.random()*COACH_NO.length)],ok?'good':'bad');
  progress();
  const praise=['Great!','Nice!','Perfect!','Well done!','Exactly!'];
  feedback(ok,ok?(opts.msg||praise[Math.floor(Math.random()*praise.length)]):(opts.msg||'Not quite'),ok?(opts.sub||''):(correctText?'Correct:':(opts.sub||'')),ok?opts.ans:correctText);
  setMain('Continue',ok?'good':'bad',true);
}
function mainClick(){
  const b=$('lp-pmain');if(b.disabled)return;
  if(P.teach){nextEx();return}
  if(!P.answered){if(P.evalFn)P.evalFn();return}
  P.i++;nextEx();
}

/* ----- renderizadores ----- */
function optionsUI(ex,promptHTML,autoSay){
  body('<div class="lp-card">'+promptHTML+'<div class="lp-opts">'+ex.options.map((o,i)=>'<button type="button" class="lp-opt" data-i="'+i+'"><span class="k">'+(i+1)+'</span><span data-i18n-skip>'+esc(o)+'</span></button>').join('')+'</div></div>');
  let sel=null;const btns=[...$('lp-pbody').querySelectorAll('.lp-opt')];
  const pick=i=>{if(P.answered)return;sel=i;btns.forEach((b,j)=>b.classList.toggle('sel',j===i));setMain('Check','',true);P.ready=true};
  btns.forEach((b,i)=>b.addEventListener('click',()=>pick(i)));
  const sayEx=r=>ex.check?speak(nativeForm(ex.say),r<.9?.8:1.08):speak(ex.say,r);
  const sp=$('lp-pbody').querySelector('.lp-say');if(sp)sp.addEventListener('click',()=>sayEx(.9));
  const slow=$('lp-pbody').querySelector('.lp-slow');if(slow)slow.addEventListener('click',()=>sayEx(.55));
  P.evalFn=()=>{if(sel==null)return;const ok=ex.options[sel]===ex.answer;btns.forEach((b,j)=>{if(ex.options[j]===ex.answer)b.classList.add('right');else if(j===sel)b.classList.add('wrong');b.disabled=true});if(ok&&ex.say&&!ex.check)speak(ex.say,.9);resolve(ok,ex.answer)};
  setMain('Check','',false);
  if(autoSay&&ex.say)setTimeout(()=>sayEx(.9),250);
}
const speakBtns='<div class="lp-say-row"><button type="button" class="lp-say" aria-label="Listen">🔊</button><button type="button" class="lp-slow" aria-label="Listen slowly">🐢</button><button type="button" class="lp-fast" aria-label="Native speed" title="Native speed">⚡<small>Native speed</small></button></div>';
const REDUCE=[[/\bI don't know\b/gi,'I dunno'],[/\bwhat do you\b/gi,'whaddya'],[/\bwhat are you\b/gi,'whatcha'],[/\bgoing to\b/gi,'gonna'],[/\bwant to\b/gi,'wanna'],[/\bgot to\b/gi,'gotta'],[/\bhave to\b/gi,'hafta'],[/\blet me\b/gi,'lemme'],[/\bgive me\b/gi,'gimme'],[/\bkind of\b/gi,'kinda'],[/\bsort of\b/gi,'sorta'],[/\bout of\b/gi,'outta'],[/\ba lot of\b/gi,'a lotta'],[/\bdid you\b/gi,'didja'],[/\bdo you\b/gi,'d\'ya'],[/\bcould you\b/gi,'couldja'],[/\bwould you\b/gi,'wouldja'],[/\bcan't you\b/gi,'can\'tcha'],[/\bthank you\b/gi,'thank ya'],[/\byou know\b/gi,'y\'know']];
function nativeForm(t){let r=String(t||'');REDUCE.forEach(([a,b])=>{r=r.replace(a,b)});return r}
function playFast(){
  const ex=P.cur;if(!ex)return;const t=ex.say||ex.answer||ex.q;if(!t)return;
  const f=nativeForm(t);speak(f,1.12);
  if(f.toLowerCase()!==String(t).toLowerCase()){coach('⚡ At native speed it sounds like: <b>“'+esc(f)+'”</b>. Words melt together — that is normal.','idle')}
  else coach('⚡ This one has no big reductions — just speed and rhythm. Try repeating it at the same pace.','idle');
}
const R={
  pick_meaning(ex){optionsUI(ex,'<div class="lp-kicker">What does it mean?</div><div class="lp-big" data-i18n-skip>'+(ex.emoji?'<span class="e">'+ex.emoji+'</span> ':'')+esc(ex.q)+'</div>'+speakBtns,true)},
  pick_word(ex){optionsUI(ex,'<div class="lp-kicker">Choose the English word</div><div class="lp-big" data-i18n-skip>'+(ex.emoji?'<span class="e">'+ex.emoji+'</span> ':'')+esc(ex.q)+'</div>',false)},
  listen_pick(ex){optionsUI(ex,'<div class="lp-kicker">Tap what you hear</div>'+speakBtns,true)},
  dialog(ex){optionsUI(ex,'<div class="lp-kicker">Choose the best reply</div><div class="lp-bubble" data-i18n-skip>'+esc(ex.q)+'</div>'+speakBtns,true)},
  fill(ex){
    const s=esc(ex.sentence).replace('____','<span class="lp-blank">____</span>');
    optionsUI(ex,'<div class="lp-kicker">Complete the sentence</div><div class="lp-big" data-i18n-skip>'+s+'</div><div class="lp-hint" data-i18n-skip>'+esc(ex.es)+'</div>'+speakBtns,false);
  },
  build(ex){
    body('<div class="lp-card"><div class="lp-kicker">Translate this sentence</div><div class="lp-big" data-i18n-skip>'+esc(ex.q)+'</div><div class="lp-answer" id="lp-ans"></div><div class="lp-bank" id="lp-bank"></div></div>');
    const placed=[];const bank=ex.bank.map((t,i)=>({t,i,used:false}));
    const draw=()=>{
      $('lp-ans').innerHTML=placed.map((p,k)=>'<button type="button" class="lp-chip in" data-k="'+k+'" data-i18n-skip>'+esc(bank[p].t)+'</button>').join('');
      $('lp-bank').innerHTML=bank.map((b,i)=>'<button type="button" class="lp-chip'+(b.used?' used':'')+'" data-i="'+i+'" data-i18n-skip>'+esc(b.t)+'</button>').join('');
      $('lp-ans').querySelectorAll('.lp-chip').forEach(c=>c.addEventListener('click',()=>{if(P.answered)return;const k=+c.dataset.k;bank[placed[k]].used=false;placed.splice(k,1);draw()}));
      $('lp-bank').querySelectorAll('.lp-chip').forEach(c=>c.addEventListener('click',()=>{if(P.answered)return;const i=+c.dataset.i;if(bank[i].used)return;bank[i].used=true;placed.push(i);draw();speak(bank[i].t,1)}));
      P.ready=placed.length>0;setMain('Check','',P.ready);
    };
    draw();
    P.evalFn=()=>{const got=nrm(placed.map(i=>bank[i].t).join(' '));const ok=got===nrm(ex.answer);$('lp-ans').classList.add(ok?'ok':'no');speak(ex.say||ex.answer,.9);resolve(ok,ex.answer)};
  },
  type_listen(ex){
    body('<div class="lp-card"><div class="lp-kicker">Type what you hear</div>'+speakBtns+'<textarea id="lp-type" rows="2" placeholder="Type in English..." autocomplete="off" autocapitalize="off" spellcheck="false"></textarea><div class="lp-hint" data-i18n-skip>'+esc(ex.es||'')+'</div></div>');
    typeLogic(ex,ex.answer);setTimeout(()=>speak(ex.say,.85),250);
    $('lp-pbody').querySelector('.lp-say').addEventListener('click',()=>speak(ex.say,.9));
    $('lp-pbody').querySelector('.lp-slow').addEventListener('click',()=>speak(ex.say,.55));
  },
  type_translate(ex){
    body('<div class="lp-card"><div class="lp-kicker">Write it in English</div><div class="lp-big" data-i18n-skip>'+esc(ex.q)+'</div><textarea id="lp-type" rows="2" placeholder="Type in English..." autocomplete="off" autocapitalize="off" spellcheck="false"></textarea></div>');
    typeLogic(ex,ex.answer);
  },
  match(ex){
    const L=shuffle(ex.pairs.map(p=>p.en)),Rr=shuffle(ex.pairs.map(p=>p.es));
    body('<div class="lp-card"><div class="lp-kicker">Match the pairs</div><div class="lp-match"><div id="lp-ml">'+L.map(t=>'<button type="button" class="lp-m" data-s="l" data-t="'+esc(t)+'" data-i18n-skip>'+esc(t)+'</button>').join('')+'</div><div id="lp-mr">'+Rr.map(t=>'<button type="button" class="lp-m" data-s="r" data-t="'+esc(t)+'" data-i18n-skip>'+esc(t)+'</button>').join('')+'</div></div></div>');
    let a=null,errors=0,done=0;const map=Object.fromEntries(ex.pairs.map(p=>[p.en,p.es]));
    $('lp-pbody').querySelectorAll('.lp-m').forEach(b=>b.addEventListener('click',()=>{
      if(b.classList.contains('done'))return;
      if(b.dataset.s==='l')speak(b.dataset.t,1);
      if(!a||a.dataset.s===b.dataset.s){if(a)a.classList.remove('sel');a=b;b.classList.add('sel');return}
      const l=a.dataset.s==='l'?a:b,r=a.dataset.s==='l'?b:a;
      if(map[l.dataset.t]===r.dataset.t){l.classList.remove('sel');r.classList.remove('sel');l.classList.add('done');r.classList.add('done');beep(true);done++;a=null;
        if(done===ex.pairs.length){ex.ref=ex.pairs[0]?{en:ex.pairs[0].en,es:ex.pairs[0].es}:null;resolve(errors<=1,'',{noRequeue:true,sub:errors?'Just '+errors+' slip'+(errors>1?'s':''):'No mistakes',msg:errors<=1?'Matched!':'Matched, with some slips'});if(errors>1){P.mistakes.push(...ex.pairs.slice(0,2))}}}
      else{errors++;beep(false);buzz(40);a.classList.add('wrong');b.classList.add('wrong');const x=a,y=b;a=null;setTimeout(()=>{x.classList.remove('wrong','sel');y.classList.remove('wrong','sel')},450)}
    }));
    hideMain();
  },
  speak(ex){renderSpeak(ex)}
};
document.addEventListener('click',e=>{if(e.target.closest('.lp-fast')&&document.body.classList.contains('lp-open'))playFast()});
window.TalvoNative={form:nativeForm,say(text){const t=String(text||'').trim();if(!t)return;const f=nativeForm(t);speak(f,1.12);if(f.toLowerCase()!==t.toLowerCase())toast('⚡ '+f)}};
function typeLogic(ex,answer){
  const ta=$('lp-type');const upd=()=>{P.ready=ta.value.trim().length>0;setMain('Check','',P.ready)};
  ta.addEventListener('input',upd);ta.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();mainClick()}});
  setMain('Check','',false);setTimeout(()=>{try{ta.focus({preventScroll:true})}catch(e){}},300);
  P.evalFn=()=>{const g=nrm(ta.value),a=nrm(answer);const d=lev(g,a);const ok=g===a||d<=1;ta.disabled=true;ta.classList.add(ok?'ok':'no');speak(answer,.9);
    resolve(ok,answer,ok&&g!==a?{sub:'Tiny typo · correct:',ans:answer}:{})};
}

/* ----- grabación y pronunciación ----- */
const REC={rec:null,chunks:[],stream:null,timer:null};
function stopRec(){try{clearTimeout(REC.timer);if(REC.rec&&REC.rec.state!=='inactive')REC.rec.stop();if(REC.stream)REC.stream.getTracks().forEach(t=>t.stop())}catch(e){}REC.rec=null}
function recStart(){
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia||!window.MediaRecorder)return Promise.reject(new Error('Your browser does not support microphone recording.'));
  return navigator.mediaDevices.getUserMedia({audio:true}).then(stream=>{
    let mime='';for(const m of ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/mp4']){if(MediaRecorder.isTypeSupported(m)){mime=m;break}}
    REC.stream=stream;REC.chunks=[];REC.rec=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);
    REC.rec.ondataavailable=e=>{if(e.data.size)REC.chunks.push(e.data)};REC.rec.start();
    REC.timer=setTimeout(()=>{const b=$('lp-rec');if(b&&b.dataset.on==='1')b.click()},14000);
  });
}
function recStop(){return new Promise(res=>{const r=REC.rec;if(!r)return res(null);r.onstop=()=>{const type=(REC.chunks[0]&&REC.chunks[0].type)||'audio/webm';if(REC.stream)REC.stream.getTracks().forEach(t=>t.stop());res(new Blob(REC.chunks,{type}))};try{r.stop()}catch(e){res(null)}clearTimeout(REC.timer)})}
async function assess(blob,text){
  const fd=new FormData();fd.append('audio',blob,'recording.webm');fd.append('frase_esperada',text);fd.append('fast','1');
  return jsonFetch('/analizar-audio-real',{method:'POST',body:fd});
}
function wordChips(d){
  return (d.palabras||[]).map(w=>{const a=w.precision||0;const c=a>=80?'g':a>=60?'m':'b';return '<span class="lp-w '+c+'" data-i18n-skip>'+esc(w.palabra)+'<i>'+Math.round(a)+'</i></span>'}).join('');
}
function renderSpeak(ex){
  const isSound=P.kind==='sound';let tries=0,best=null;
  body('<div class="lp-card"><div class="lp-kicker">'+(isSound?'Say the word':'Say it out loud')+'</div><div class="lp-big" data-i18n-skip>'+esc(ex.text)+'</div><div class="lp-hint" data-i18n-skip>'+esc(ex.es||'')+'</div>'+speakBtns+'<div class="lp-mic"><button type="button" id="lp-rec" class="lp-recbtn" data-on="0" aria-label="Record">🎤</button><small id="lp-recmsg">Tap the mic and speak</small></div><div id="lp-sres"></div></div>');
  $('lp-pbody').querySelector('.lp-say').addEventListener('click',()=>speak(ex.text,.9));
  $('lp-pbody').querySelector('.lp-slow').addEventListener('click',()=>speak(ex.text,.55));
  const rb=$('lp-rec'),msg=$('lp-recmsg');
  hideMain();
  const skip=document.createElement('button');skip.type='button';skip.className='lp-skip';skip.textContent="I can't speak now";
  $('lp-pbody').firstChild.appendChild(skip);
  skip.addEventListener('click',()=>{stopRec();if(!isSound)P.total=Math.max(1,P.total-1);P.queue.splice(P.i,1);P.cur=null;progress();nextEx()});
  rb.addEventListener('click',async()=>{
    if(rb.dataset.on==='0'){
      try{await recStart()}catch(e){msg.textContent=(e&&e.name==='NotAllowedError')?'Microphone blocked. Allow it in your browser, or skip.':(e.message||'Could not use the microphone.');return}
      rb.dataset.on='1';rb.classList.add('on');rb.textContent='■';msg.textContent='Listening... tap to stop';
    }else{
      rb.dataset.on='2';rb.classList.remove('on');rb.disabled=true;rb.textContent='…';msg.textContent='Analyzing your pronunciation...';
      const blob=await recStop();
      try{
        if(!blob||blob.size<800)throw new Error('I could not hear you. Try again, a little closer to the mic.');
        const d=await assess(blob,ex.text);tries++;
        const sc=Math.round(d.puntuacion_global||0);if(best==null||sc>best)best=sc;
        showSpeakResult(ex,d,sc,tries,best,isSound);
      }catch(e){rb.disabled=false;rb.dataset.on='0';rb.textContent='🎤';msg.textContent=e.message||'Something went wrong. Try again.'}
    }
  });
}
function showSpeakResult(ex,d,sc,tries,best,isSound){
  const pass=sc>=60;const cls=sc>=80?'g':sc>=60?'m':'b';
  let tips='';(d.weak_sounds||[]).forEach(s=>{tips+='<div class="lp-soundtip" data-i18n-skip><b>/'+esc(s.ipa)+'/ '+esc(s.name)+'</b> · '+esc(s.tip)+(window.mouthDiagram?window.mouthDiagram(s.id):'')+'</div>'});
  $('lp-sres').innerHTML='<div class="lp-score '+cls+'"><b>'+sc+'</b><small>'+(sc>=80?'Excellent':sc>=60?'Good — keep it up':'Keep trying')+'</small></div><div class="lp-words">'+wordChips(d)+'</div>'+tips;
  $('lp-recmsg').textContent='';const rb=$('lp-rec');
  rb.disabled=false;rb.dataset.on='0';rb.textContent='🎤';
  const done=()=>{
    P.speakScores.push(best);
    if(isSound){P.answered=true;P.cleared++;progress();setMain('Continue',pass?'good':'',true);feedback(pass,pass?'Nice sound!':'Keep practicing this one',pass?'':'You can retry or continue');}
    else{resolve(pass,'',{noRequeue:true,msg:pass?'Great speaking!':'Needs more practice',sub:pass?'':'We saved this phrase for review.'})}
  };
  if(pass||tries>=3){done()}
  else{P.answered=false;P.evalFn=done;setMain('Continue anyway','',true);$('lp-recmsg').textContent='Try again — listen first, then record.'}
  if(pass){try{reactToScore(sc)}catch(e){}}
}

/* =====================  RESULTADOS  ===================== */
async function finish(){
  const secs=Math.round((Date.now()-P.t0)/1000);
  body('<div class="lp-card center"><div class="lp-big">Saving your progress...</div></div>');hideMain();clearFb();
  const sound=P.kind==='sound';
  const payload={kind:P.kind==='review'?'review':(P.kind==='focus'?'focus':(sound?'sound':'lesson')),unit_code:P.d.unit_code,lesson_id:P.d.lesson_id,correct:P.correct,total:P.total,seconds:secs,mistakes:P.mistakes.filter(m=>m&&m.en).slice(0,12)};
  if(sound){payload.sound_id=P.sound.id;payload.score=P.speakScores.length?P.speakScores.reduce((a,b)=>a+b,0)/P.speakScores.length:0;payload.seconds=Math.max(secs,15)}
  let r=null;
  try{
    if(P.kind==='route'){r=await jsonFetch('/api/rutas/'+encodeURIComponent(P.d.route_id)+'/completar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lesson_id:P.d.lesson_id,correct:P.correct,total:P.total,seconds:secs,mistakes:payload.mistakes,listen:P.lcN?{ok:P.lcOk||0,n:P.lcN}:undefined})})}
    else r=await jsonFetch('/api/learning-path/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})}
  catch(e){
    body('<div class="lp-card center"><div class="lp-big">Could not save</div><p class="lp-tip">'+esc(e.message)+'</p></div>');
    setMain('Try again','',true);P.teach=false;P.answered=false;P.evalFn=()=>finish();return;
  }
  renderResults(r,sound?Math.round(payload.score):Math.round(P.total?P.correct/P.total*100:0),secs);
}
function renderResults(r,pct,secs){
  const stars=r.stars||0;
  let h='<div class="lp-card center lp-res"><div class="lp-kicker">'+(P.kind==='review'?'Review complete':P.kind==='focus'?'Personalized practice':P.kind==='sound'?'Sound practice':(P.d.challenge?'Challenge':'Lesson')+' complete')+'</div>';
  h+='<div class="lp-stars">'+[1,2,3].map(i=>'<span class="'+(i<=stars?'on':'')+'" style="animation-delay:'+(i*.18)+'s">★</span>').join('')+'</div>';
  h+='<h2>'+(r.passed?(pct>=100?'Flawless!':(stars===3?'Excellent!':'Well done!')):'Almost there')+'</h2>';
  h+='<div class="lp-resgrid"><div><b>'+pct+'%</b><small>Accuracy</small></div><div><b>+'+r.xp+'</b><small>XP</small></div><div><b>'+Math.floor(secs/60)+':'+String(secs%60).padStart(2,'0')+'</b><small>Time</small></div></div>';
  if(r.level_change){const up=r.level_change.direction==='up';h+='<div class="lp-banner lvl">'+(up?'🚀 You moved up to ':'🔄 We adjusted your path to ')+'<b data-i18n-skip>'+esc(r.level_change.label)+'</b>'+(up?' — your results were consistently excellent!':' so lessons feel right for you. You can climb back up anytime.')+'</div>'}
  if(r.plan_bonus)h+='<div class="lp-banner">🎯 Daily plan complete! +'+r.plan_bonus+' bonus XP</div>';
  if(r.unit_completed)h+=(P.kind==='route'?'<div class="lp-banner">🏆 Route completed! +'+r.unit_bonus+' bonus XP</div>':'<div class="lp-banner">🏆 Unit completed! +'+r.unit_bonus+' bonus XP</div>');
  if(!r.passed)h+='<p class="lp-tip">You need at least 60% to pass. You can retry as many times as you want — no hearts, no penalty.</p>';
  else if(r.offline)h+='<p class="lp-tip">Saved on this device. It will sync and count for XP when you are back online.</p>';
  else if(r.xp===0)h+='<p class="lp-tip">Progress saved. Spend a little more time per lesson to earn XP.</p>';
  const ms=P.mistakes.filter((m,i,a)=>m&&m.en&&a.findIndex(x=>x.en===m.en)===i).slice(0,6);
  if(ms.length)h+='<div class="lp-mist"><div class="lp-kicker">Worth a second look'+(P.kind==='sound'?'':' · saved to your vocabulary')+'</div>'+ms.map(m=>'<div class="lp-mrow" data-i18n-skip><button type="button" class="lp-mplay" data-t="'+esc(m.en)+'">🔊</button><b>'+esc(m.en)+'</b><small>'+esc(m.es||'')+'</small></div>').join('')+'</div>';
  h+='</div>';
  body(h);
  $('lp-pbody').querySelectorAll('.lp-mplay').forEach(b=>b.addEventListener('click',()=>speak(b.dataset.t,.9)));
  P.after=r;P.teach=false;P.answered=true;P.evalFn=null;
  const b=$('lp-pmain');b.style.display='';b.disabled=false;
  const nxt=r.next;
  if(P.kind==='route'){const nr=r.next_route;
    if(r.passed&&nr){b.textContent='Next: '+nr.lesson_title;b.className='btn primary good';P.resultAction=()=>{closePlayer();window.TalvoStudio.startRouteLesson(nr.route_id,nr.lesson_id)}}
    else if(!r.passed){b.textContent='Try again';b.className='btn primary';P.resultAction=()=>{closePlayer();window.TalvoStudio.startRouteLesson(P.d.route_id,P.d.lesson_id)}}
    else{b.textContent='Back to my route';b.className='btn primary';P.resultAction=()=>{closePlayer();section('rutas')}}}
  else if(r.passed&&nxt&&P.kind==='lesson'){b.textContent='Next: '+nxt.lesson_title;b.className='btn primary good';P.resultAction=()=>{closePlayer();lpStart(nxt.unit_code,nxt.lesson_id)}}
  else if(!r.passed&&P.kind==='lesson'){b.textContent='Try again';b.className='btn primary';P.resultAction=()=>{closePlayer();lpStart(P.d.unit_code,P.d.lesson_id)}}
  else if(P.origin){b.textContent='Back';b.className='btn primary';P.resultAction=()=>{const o=P.origin;closePlayer();section(o);try{loadDashboard()}catch(e){}}}
  else{b.textContent='Back to path';b.className='btn primary';P.resultAction=()=>{closePlayer();loadLearningPath()}}
  P.finished=true;try{window.track&&window.track('leccion_fin','learning-path',{tipo:P.kind||'',ok:!!r.passed})}catch(e){}
  $('lp-fb').className='lp-fb show '+(r.passed?'good':'bad');$('lp-fb').innerHTML='<button type="button" class="lp-linkbtn" id="lp-back">'+(P.kind==='route'?'Back to my route':'Back to path')+'</button>';
  $('lp-back').addEventListener('click',()=>{closePlayer();if(P.origin){section(P.origin)}else loadLearningPath();try{loadDashboard()}catch(e){}});
  try{setMascotState(r.passed?'feliz':'triste',4000)}catch(e){}
}

/* ----- eventos del reproductor ----- */
ready(()=>{
  const m=$('lp-pmain');if(!m)return;
  m.addEventListener('click',()=>{if(P.finished&&P.resultAction){const f=P.resultAction;P.finished=false;P.resultAction=null;f();return}mainClick()});
  $('lp-pclose').addEventListener('click',()=>{if(P.finished){closePlayer();loadLearningPath();return}if(confirm(window.TalvoI18n?TalvoI18n.tr('Quit this lesson? Your progress in it will be lost.'):'Quit this lesson? Your progress in it will be lost.'))closePlayer()});
  document.addEventListener('keydown',e=>{if(!$('lp-player')||$('lp-player').hidden)return;
    if(e.key==='Enter'&&document.activeElement&&document.activeElement.tagName!=='TEXTAREA'&&document.activeElement.tagName!=='BUTTON'){mainClick()}
    if(/^[1-4]$/.test(e.key)&&P.cur&&!P.answered){const b=$('lp-pbody').querySelectorAll('.lp-opt')[+e.key-1];if(b)b.click()}});
});

/* =====================  SOUND LAB  ===================== */
window.lpOpenSounds=async function(){
  const sh=$('lp-sheet');sh.hidden=false;document.body.classList.add('lp-open');
  $('lp-sheet-body').innerHTML='<div class="empty">'+window.pqLoader()+'</div>';
  try{
    const d=await jsonFetch('/api/learning-path/sounds');LP.sounds=d.sounds;
    let h='<p class="lp-tip">'+(d.personalized?'Sorted by your weakest sounds, based on your real speaking history.':'Start with the sounds that are hardest for Spanish speakers. As you practice speaking, this list adapts to you.')+'</p><div class="lp-sounds">';
    d.sounds.forEach(s=>{
      const chip=s.status==='weak'?'<span class="lp-chipst weak">Needs work · '+Math.round(s.avg)+'</span>':(s.status==='ok'?'<span class="lp-chipst ok">Good · '+Math.round(s.avg)+'</span>':'<span class="lp-chipst">New</span>');
      h+='<button type="button" class="lp-srow" onclick="lpSound(\''+s.id+'\')"><span class="ipa" data-i18n-skip>'+esc(s.ipa)+'</span><span class="nm"><b data-i18n-skip>'+esc(s.name)+'</b><small data-i18n-skip>'+esc(s.words.slice(0,3).join(' · '))+'</small></span>'+chip+(s.best!=null?'<i class="lp-best">'+Math.round(s.best)+'%</i>':'')+'</button>';
    });
    $('lp-sheet-body').innerHTML=h+'</div>';
  }catch(e){$('lp-sheet-body').innerHTML='<div class="empty">'+esc(e.message)+'</div>'}
};
window.lpCloseSounds=function(){$('lp-sheet').hidden=true;if($('lp-player').hidden)document.body.classList.remove('lp-open');loadLearningPath()};
window.lpSound=function(id){
  const s=(LP.sounds||[]).find(x=>x.id===id);if(!s)return;
  $('lp-sheet').hidden=true;startSoundDrill(s);
};
function startSoundDrill(s,origin){
  const ex=s.words.map(w=>({type:'speak',text:w,es:'',ref:{en:w,es:''}}));
  ex.push({type:'speak',text:s.phrase,es:'',ref:{en:s.phrase,es:''}});
  openPlayer({title:s.name,exercises:ex,teach:[],sound:{id:s.id,ipa:s.ipa,tip:s.tip,words:s.words},unit_code:'sound_lab',lesson_id:s.id},'sound',origin);
}
window.lpFocus=async function(skill,origin){
  try{
    toast('Preparing your practice...');
    const d=await jsonFetch('/api/learning-path/focus?skill='+encodeURIComponent(skill));
    if(d.mode==='sound'){startSoundDrill(d.sound,origin);return}
    d.unit_code='focus';d.lesson_id=skill;
    openPlayer(d,'focus',origin);
  }catch(e){toast(e.message)}
};
window.lpFocusFromTool=function(tool,label){
  let skill={pronunciation:'speaking',writing:'writing',reading:'reading',dictado:'listening'}[tool]||'speaking';
  if(/vocab/i.test(label||''))skill='vocabulary';else if(/grammar/i.test(label||''))skill='writing';
  const active=document.querySelector('.section.active');
  lpFocus(skill,active?active.id.replace('sec-',''):null);
};
window.lpRunStep=function(id){
  const p=LP.plan;if(!p)return;const st=p.steps.find(x=>x.id===id);if(!st)return;
  if(st.kind==='review')lpReview();else if(st.kind==='focus')lpFocus(st.skill,null);else lpStart(st.unit_code,st.lesson_id);
};

/* =====================  PRÓXIMO PASO EN INICIO  ===================== */
window.loadNextStep=async function(){
  const t=$('home-next-title'),l=$('home-next-label');if(!t||!l)return;
  try{
    const plan=await jsonFetch('/api/learning-path/daily-plan');LP.plan=plan;
    const st=plan.steps.find(x=>!x.done);
    if(!st){l.textContent='Today\'s plan complete';t.textContent='🎉 Keep going with your path';state.next={step:null};return}
    state.next={step:st.id};
    l.textContent='Today\'s plan · '+plan.done+'/'+plan.total;
    t.textContent=(st.icon+' '+st.title).trim();
  }catch(e){state.next=null;l.textContent='Next step';t.textContent='Start with a free practice'}
};
window.continueLearning=function(){
  if(!state.next){section('pronunciacion');return}
  section('learning-path');
  const n=state.next;setTimeout(()=>{if(n.step)lpRunStep(n.step)},150);
};
ready(()=>{const b=$('home-next');if(b)b.addEventListener('click',()=>window.continueLearning())});
})();

/* ---- Pestañas de aprendizaje: Camino · Reto de 21 días · Mis rutas ---- */
window.ltRender=function(active){
  const T_=[['path','🗺️ Course path'],['reto','🔥 21-day challenge'],['rutas','🧭 My routes']];
  document.querySelectorAll('[data-lt]').forEach(el=>{el.innerHTML=T_.map(t=>'<button type="button" class="lt-tab'+(t[0]===active?' on':'')+'" data-ltab="'+t[0]+'">'+t[1]+'</button>').join('')});
};
document.addEventListener('click',e=>{
  const b=e.target.closest&&e.target.closest('[data-ltab]');if(!b)return;
  const t=b.dataset.ltab;
  if(t==='path'){window.TalvoCore.section('learning-path')}
  else if(window.TalvoStudio&&window.TalvoStudio.goTab){window.TalvoStudio.goTab(t)}
});
