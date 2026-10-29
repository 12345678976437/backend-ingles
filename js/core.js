(()=>{
'use strict';
const API_URL='https://backend-ingles-e3ms.onrender.com';
const SUPABASE_URL='https://lqdgbmuodnshfgokesvd.supabase.co';
const SUPABASE_ANON_KEY='sb_publishable_ivnebDTQZ9SeyZQUHBKtmg_yRtH6mFu';
const sb=window.supabase.createClient(SUPABASE_URL,SUPABASE_ANON_KEY);
const TURNSTILE_SITE_KEY='0x4AAAAAAFUxt8RAAaEtFwuJ';
let tsId=null,tsToken='';
function tsEnsure(){if(tsId!==null)return;if(window.turnstile){tsId=turnstile.render('#turnstile-box',{sitekey:TURNSTILE_SITE_KEY,theme:'auto',callback:t=>{tsToken=t},'expired-callback':()=>{tsToken=''},'error-callback':()=>{tsToken=''}})}else{setTimeout(tsEnsure,300)}}
function tsReset(){tsToken='';if(tsId!==null&&window.turnstile){try{turnstile.reset(tsId)}catch(e){}}}
let recoveryMode=false;
sb.auth.onAuthStateChange((_event,session)=>{if(_event==='PASSWORD_RECOVERY'){recoveryMode=true;closeAuth();$('reset-modal').style.display='flex';return}if(!recoveryMode)syncUser(session?.user||null)});
const $=id=>document.getElementById(id);const $$=sel=>Array.from(document.querySelectorAll(sel));
const state={user:null,subscribed:false,authRegister:false,pron:'lectura',recording:false,recorder:null,chunks:[],timer:null,seconds:0,dictation:'',reading:null,callMessages:[],callRecorder:null,callChunks:[],callBusy:false};
function esc(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function toast(msg){const t=$('toast');t.textContent=msg;t.style.display='block';clearTimeout(toast.timer);toast.timer=setTimeout(()=>t.style.display='none',3200)}
let mascotRevertTimer=null;
let mascotBlinkTimer=null;
const MASCOT_PEEK_IMG="img/5ef4891258.webp";
const EYE_OPEN_L="img/6f23951225.webp";
const EYE_OPEN_R="img/616c0afe99.webp";
const EYE_CLOSED_L="img/9abc8766f9.webp";
const EYE_CLOSED_R="img/573023fda0.webp";
let mascotClickTimes=[];
function eyesClosed(closed){const l=$('mascot-eye-l'),r=$('mascot-eye-r');if(!l||!r)return;const li=l.querySelector('img'),ri=r.querySelector('img');li.src=closed?EYE_CLOSED_L:EYE_OPEN_L;ri.src=closed?EYE_CLOSED_R:EYE_OPEN_R}
function scheduleBlink(){clearTimeout(mascotBlinkTimer);const wait=2600+Math.random()*3200;mascotBlinkTimer=setTimeout(()=>{const el=$('mascot');if(el&&!el.className.includes('state-pensando')){eyesClosed(true);setTimeout(()=>eyesClosed(false),160)}scheduleBlink()},wait)}
function setMascotState(state,autoRevertMs){const el=$('mascot');if(!el)return;el.className='mascot-widget state-'+state;eyesClosed(state==='pensando');clearTimeout(mascotRevertTimer);if(autoRevertMs)mascotRevertTimer=setTimeout(()=>setMascotState('idle'),autoRevertMs)}
function spawnConfetti(){const colors=['#ff6b6b','#ffd166','#06d6a0','#4cc9f0','#f472b6'];const host=$('mascot');for(let i=0;i<14;i++){const c=document.createElement('div');c.className='confetti-piece';c.style.background=colors[i%colors.length];c.style.left=(38+Math.random()*24)+'%';c.style.setProperty('--dx',(Math.random()*90-45)+'px');c.style.setProperty('--dy',(-(60+Math.random()*50))+'px');c.style.animationDelay=(Math.random()*0.12)+'s';host.appendChild(c);setTimeout(()=>c.remove(),1100)}}
function spawnEggSequence(){const egg=$('mascot-egg');clearTimeout(egg._t1);clearTimeout(egg._t2);egg.textContent='🥚';egg.classList.remove('hatch');egg.classList.add('show');egg._t1=setTimeout(()=>{egg.innerHTML='<img src="palanqueta-a.webp" alt="" draggable="false">';egg.classList.add('hatch');spawnConfetti()},850);egg._t2=setTimeout(()=>{egg.classList.remove('show','hatch')},2700)}
function reactToScore(score){const n=Number(score)||0;if(n>=70){setMascotState('feliz',3200);spawnEggSequence()}else{setMascotState('triste',4500)}}
function startMascotTalking(){$('mascot-mouth').classList.add('talk')}
function stopMascotTalking(){$('mascot-mouth').classList.remove('talk')}
function showCardPeek(){const activeSection=document.querySelector('.section.active');if(!activeSection)return;const card=activeSection.querySelector('.card');if(!card)return;card.style.position=card.style.position||'relative';let peek=document.getElementById('mascot-peek');if(!peek){peek=document.createElement('img');peek.id='mascot-peek';peek.className='mascot-peek';peek.src=MASCOT_PEEK_IMG;peek.alt=''}card.appendChild(peek);requestAnimationFrame(()=>peek.classList.add('show'));clearTimeout(window._peekTimer);window._peekTimer=setTimeout(()=>peek.classList.remove('show'),3500)}
function mascotClicked(){const now=Date.now();mascotClickTimes=mascotClickTimes.filter(t=>now-t<2200);mascotClickTimes.push(now);if(mascotClickTimes.length>=5){mascotClickTimes=[];setMascotState('feliz',3200);spawnEggSequence()}}
scheduleBlink();
/* ---- Palanqueta recogiendo palabras: cargador animado ---- */
const PQ_HEN="img/d7b8a9c181.webp";
try{const st=document.createElement('style');st.id='pq-img';st.textContent='.pq-hen,.pq-mini,.pq-cheer{background-image:url("'+PQ_HEN+'")}';document.head.appendChild(st)}catch(e){}
const PQ_WORDS=['hello','learn','speak','grow','listen','dream','smile','think','write','shine','brave','story'];
const PQ_MSGS=['Palanqueta is hard at work gathering your learning…','Picking the best words for you…','Warming up your lesson…','Almost there, hang on…','Teaching the hen a new trick…'];
setInterval(()=>{document.querySelectorAll('.pq-msg').forEach(el=>{if(!el.isConnected)return;const k=((+el.dataset.k||0)+1)%PQ_MSGS.length;el.dataset.k=k;el.style.opacity=0;setTimeout(()=>{el.textContent=PQ_MSGS[k];el.style.opacity=1},220)})},2800);
function pqLoader(size){
  const ws=PQ_WORDS.slice().sort(()=>Math.random()-.5).slice(0,5),xs=[-72,68,-58,60,-66];
  const chips=ws.map((w,i)=>`<i class="pq-w" data-i18n-skip style="--x0:${xs[i]}px;--x1:${xs[i]<0?-34:34}px;--d:${(i*.44).toFixed(2)}s;--r0:${i%2?9:-9}deg">${w}</i>`).join('');
  return `<div class="pq-load${size?' '+size:''}" role="status" aria-label="Loading"><div class="pq-stage"><span class="pq-glow"></span><span class="pq-hen"></span>${chips}<span class="pq-basket"></span><b class="pq-sp s1">✦</b><b class="pq-sp s2">✦</b></div><div class="pq-dots"><u></u><u></u><u></u></div>${size?'':'<p class="pq-msg" data-k="0">'+PQ_MSGS[0]+'</p>'}</div>`;
}
function txtOf(id){const e=$(id);return !e||e.querySelector('.pq-load')?'':e.textContent}
function pqMini(){return '<span class="pq-mini" role="status" aria-label="Loading"></span>'}
window.pqLoader=pqLoader;window.pqMini=pqMini;
function busy(id,on,label){const b=$(id);if(!b)return;if(on){if(!b.dataset.original)b.dataset.original=b.textContent;if(/^(cargando|loading)/i.test(label||''))b.innerHTML=pqMini();else b.textContent=label;b.disabled=true;b.classList.add('loading');setMascotState('pensando')}else{b.disabled=false;b.textContent=b.dataset.original||label;b.classList.remove('loading');setMascotState('idle');if(Math.random()<0.5)setTimeout(showCardPeek,400)}}
function showAuth(){ $('auth-error').style.display='none'; $('auth-modal').style.display='flex'; tsEnsure(); setTimeout(()=>$('auth-email').focus(),50)}
function closeAuth(){ $('auth-modal').style.display='none' }
function authError(msg){$('auth-error').textContent=msg||'';$('auth-error').style.display=msg?'block':'none'}
function resetError(msg){$('reset-error').textContent=msg||'';$('reset-error').style.display=msg?'block':'none'}
async function forgotPassword(){const email=$('auth-email').value.trim();if(Date.now()-(forgotPassword.t||0)<60000)return authError('Wait a minute before requesting another email.');if(!email)return authError('Escribe tu correo arriba primero, luego dale a "¿Olvidaste tu contraseña?".');const cap=tsToken;if(!cap)return authError('Completa la verificación de seguridad antes de continuar.');forgotPassword.t=Date.now();busy('auth-forgot',true,'Enviando...');authError('');try{const r=await sb.auth.resetPasswordForEmail(email,{redirectTo:window.location.origin,captchaToken:cap});if(r.error)throw r.error;toast('Te enviamos un correo para restablecer tu contraseña. Revisa spam si no lo ves.')}catch(e){authError(e.message||'No se pudo enviar el correo.')}finally{tsReset();busy('auth-forgot',false,'¿Olvidaste tu contraseña?')}}
async function resetSubmit(){const pw=$('reset-password').value;if(!pw||!pwStrong(pw))return resetError('La contraseña debe tener al menos 8 caracteres, con letras y números.');busy('reset-submit',true,'Guardando...');resetError('');try{const r=await sb.auth.updateUser({password:pw});if(r.error)throw r.error;$('reset-modal').style.display='none';toast('Contraseña actualizada. Ya puedes usar tu cuenta.');await syncUser(r.data.user)}catch(e){resetError(e.message||'No se pudo guardar la contraseña.')}finally{busy('reset-submit',false,'Guardar nueva contraseña')}}
async function getSession(){const r=await sb.auth.getSession();if(r.error)throw r.error;return r.data.session||null}
async function authFetch(path,options={}){let s=await getSession();if(!s){showAuth();throw new Error('Please sign in to continue.')}const headers=new Headers(options.headers||{});headers.set('Authorization','Bearer '+s.access_token);const wakeT=setTimeout(()=>{if(!state.wakeShown){state.wakeShown=true;toast('Waking up the server… this can take up to a minute the first time.')}},5000);let r;try{r=await fetch(API_URL+path,{...options,headers})}finally{clearTimeout(wakeT)}if(r.status===401){const refreshed=await sb.auth.refreshSession();if(refreshed.data.session){headers.set('Authorization','Bearer '+refreshed.data.session.access_token);r=await fetch(API_URL+path,{...options,headers})}}if(r.status===429){r.clone().json().then(d=>{if(d&&d.limite)showPlanModal(d.limite,d.error)}).catch(()=>{})}return r}
/* ---------- Planes y uso (como Claude: cuota por 5 horas + tope diario) ---------- */
const PLAN_FEATS={gratis:['Para probar la app','Cuota pequeña'],basico:['Práctica diaria tranquila','Todas las actividades'],pro:['Para practicar a diario','Más tutor y pronunciación'],max:['Sin preocuparte por límites','Para uso intensivo']};
function fmtReset(sec){sec=Math.max(60,Math.round(sec||0));const h=Math.floor(sec/3600),m=Math.round((sec%3600)/60);return h?(h+' h'+(m?' '+m+' min':'')):(m+' min')}
function planMeter(label,u,reset){const pct=u.limite?Math.min(100,Math.round(u.usado/u.limite*100)):0;const left=Math.max(0,Math.floor(u.limite-u.usado));return `<div class="pl-m"><div class="pl-mh"><span>${label}</span><b>${left} de ${u.limite} disponibles</b></div><div class="bar"><div class="fill${pct>=85?' warn':''}" style="width:${pct}%"></div></div>${u.usado>0?`<small>Se renueva en ${fmtReset(u.reinicia_seg)}</small>`:'<small>Aún no has usado nada</small>'}</div>`}
function planFeat(p){const f=p.funciones;if(!f)return '';return `<li><b>${f.rutas}</b> rutas personalizadas</li><li>Escenarios de rol: ${f.escenarios==='todos'?'<b>todos</b>':'básicos'}</li>${f.escenario_libre?'<li><b>Situaciones propias</b></li>':''}<li>Traductor hasta <b>${f.traductor_max}</b> caracteres</li><li>Shadowing: <b>${f.shadowing_dia}</b> intentos/día${f.shadowing_tema?' + temas propios':''}</li>${f.reunion?'<li><b>Análisis de reuniones</b></li>':''}<li>Clips: <b>${f.clips_dia}</b> con XP al día${f.clip_tema?' + temas propios':''}</li>${f.presentacion?'<li>Presentaciones de hasta <b>'+f.presentacion_slides+'</b> diapositivas</li>':''}`}
function planGrid(d){return `<div class="pl-grid">${d.planes.map(p=>`<div class="pl-c${p.id===d.plan?' cur':''}${p.id==='pro'?' hot':''}"><b class="pl-n">${p.nombre}</b><div class="pl-p">${p.precio?('$'+p.precio+'<small> MXN/mes</small>'):'Gratis'}</div><ul><li><b>${p.ventana}</b> mensajes cada 5 h</li><li><b>${p.dia}</b> al día</li><li>${(PLAN_FEATS[p.id]||[])[0]||''}</li>${planFeat(p)}</ul>${p.id===d.plan?'<span class="pl-tag">Tu plan</span>':(p.precio?`<button type="button" class="btn${p.id==='pro'?' primary':''}" data-plan-pick="${p.id}">Elegir ${p.nombre}</button>`:'')}</div>`).join('')}</div>`}
async function loadPlanCard(){
  const box=$('plan-card');if(!box)return;
  if(!box.dataset.ready)box.innerHTML=pqLoader('sm');
  try{
    const d=await jsonFetch('/api/uso');box.dataset.ready='1';
    if(d.ilimitado){box.innerHTML='<div class="vb-h"><b>Tu plan</b><span class="badge">Administrador · sin límites</span></div>';return}
    box.innerHTML=`<div class="vb-h"><b>Tu plan</b><span class="badge">${d.plan_nombre}</span></div><p class="pl-note">Cada mensaje al tutor, ejercicio con IA o análisis de voz gasta de tu cuota. Se renueva sola cada 5 horas.</p>${planMeter('Estas 5 horas',d.ventana)}${planMeter('Hoy',d.dia)}<h4 class="pl-h">Planes</h4>${planGrid(d)}`;
  }catch(e){box.innerHTML='<div class="empty">No se pudo cargar tu plan.</div>'}
}
function showPlanModal(info,msg){
  closePlanModal();
  const nxt=info.siguiente_nombre;
  const wrap=document.createElement('div');wrap.className='pl-modal';wrap.id='plan-modal';
  const alta=info.tipo==='alta_demanda',fn=info.tipo==='funcion';
  wrap.innerHTML=`<div class="pl-box" role="dialog" aria-modal="true"><span class="pq-cheer"></span><b class="pl-t">${alta?'Mucha gente practicando ahora':(fn?'Función de un plan superior':'Descansa un momento')}</b><p data-i18n-skip>${esc(msg||'')}</p><small>Tu plan: ${esc(info.plan_nombre||'')}</small><div class="pl-act">${nxt&&!alta?`<button type="button" class="btn primary" id="pl-up">Ver planes${nxt?' · '+esc(nxt):''}</button>`:''}<button type="button" class="btn" id="pl-ok">Entendido</button></div></div>`;
  document.body.appendChild(wrap);
  $('pl-ok').onclick=closePlanModal;wrap.addEventListener('click',e=>{if(e.target===wrap)closePlanModal()});
  const up=$('pl-up');if(up)up.onclick=()=>{closePlanModal();section('cuenta')};
}
function closePlanModal(){const m=$('plan-modal');if(m)m.remove()}
document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('[data-plan-pick]');if(b){toast('Para activar el plan '+b.dataset.planPick.toUpperCase()+' escríbenos en Soporte y te lo activamos.');section('soporte')}});
const OFL=window.TalvoOffline||null;
function offlineErr(){return new Error('No internet connection. This needs to be online.')}
async function jsonFetch(path,options={}){
  if(OFL&&OFL.isOff()){const c=OFL.handle(path,options);if(c!==undefined)return c;throw offlineErr()}
  let r;
  try{r=await authFetch(path,options)}
  catch(e){if(OFL&&OFL.isNetErr(e)){const c=OFL.handle(path,options);if(c!==undefined)return c;throw offlineErr()}throw e}
  const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||('Request failed ('+r.status+')'));
  if(OFL&&r.ok&&(!options.method||String(options.method).toUpperCase()==='GET'))OFL.put(path,d);
  return d}
async function syncUser(user){try{return await syncUserInner(user)}finally{if(window.hideBoot)window.hideBoot()}}
/* Sin internet: entra con la última sesión verificada en este teléfono (solo para ver y practicar). */
function enterOffline(user){
  const sn=OFL&&OFL.snap();if(!sn)return false;
  if(user&&user.id&&user.id!==sn.id)return false;
  const u=user||{id:sn.id,email:sn.email};OFL.setUser(u.id);state.user=u;state.subscribed=true;
  document.querySelector('.app').style.display='';$('welcome-view').style.display='none';closeAuth();
  $('user-display').textContent=u.email||'Signed in';$('side-email').textContent=u.email||'Student';$('login-btn').style.display='none';$('logout-btn').style.display='inline-block';
  $('side-status').textContent='Offline mode';$('app-content').style.display='block';$('locked-view').style.display='none';
  OFL.badge();try{loadDashboard()}catch(e){}return true}
window.addEventListener('online',()=>{if(state.user&&$('side-status')&&$('side-status').textContent==='Offline mode'){setTimeout(()=>{try{syncUser(state.user)}catch(e){}},1500)}});
async function syncUserInner(user){state.user=user;if(user){vfHide();setTimeout(()=>{PUSH.sync().catch(()=>{});pushAskMaybe()},2500)}const content=$('app-content'),locked=$('locked-view');if(!user){document.querySelector('.app').style.display='none';$('welcome-view').style.display='flex';closeAuth();return}document.querySelector('.app').style.display='';$('welcome-view').style.display='none';$('user-display').textContent=user.email||'Signed in';$('side-email').textContent=user.email||'Student';$('login-btn').style.display='none';$('logout-btn').style.display='inline-block';try{const d=await jsonFetch('/api/session');if(!d.authenticated)throw new Error('The session is not recognized by the server.');if(OFL)OFL.snapSave(user,d);state.subscribed=!!d.is_subscribed;renderAccountInfo(user,d);applyProfileIdentity(user,d);if(d.es_admin){$('nav-admin').style.display='flex'}if(d.en_prueba){$('side-status').textContent=`Free trial · ${d.trial_dias_restantes} day(s) left`}else{$('side-status').textContent=state.subscribed?'Practice access active':'Trial ended · subscribe to continue'}content.style.display=state.subscribed?'block':'none';locked.style.display=state.subscribed?'none':'block';if(state.subscribed){if(d.user&&!d.user.onboarded){content.style.display='none';initOnboarding()}else{closeAuth();loadDashboard();}}}catch(e){console.error('[SESSION]',e);if(OFL&&(OFL.isOff()||OFL.isNetErr(e))&&enterOffline(user))return;state.subscribed=false;content.style.display='none';locked.style.display='block';$('side-status').textContent='Access check failed';toast('We could not verify your access. Please sign in again.')}}
function section(name,button){if(!state.user||!state.subscribed){showAuth();return}if(OFL&&OFL.isOff()&&!OFL.allowed(name)){toast('This section needs internet. Lessons in Learning Path work offline.');return}$$('.section').forEach(s=>s.classList.toggle('active',s.id==='sec-'+name));$$('#main-nav button,[data-section-jump]').forEach(b=>b.classList.remove('active'));if(button)button.classList.add('active');const nav=document.querySelector(`#main-nav button[data-section="${name}"]`);if(nav)nav.classList.add('active');if(name==='escritura')loadWritingChallenge();if(name==='lectura')loadReadingLibrary().catch(e=>toast(e.message));if(name==='escucha')loadListeningLibrary().catch(e=>toast(e.message));if(name==='historial')loadProgress().catch(e=>toast(e.message));if(name==='admin')loadAdminActivity();if(name==='home')loadDashboard();if(name==='logros')loadAchievements();if(name==='shop')loadShop();if(name==='notificaciones')loadNotifications();if(name==='vocabulario'){loadVocabDaily()}
  if(name==='pronunciacion')pronAutoload();if(name==='cuenta'){loadPlanCard();pushUI();if(OFL){OFL.check()}}if(window.TalvoStudio)window.TalvoStudio.onSection(name);if(window.TalvoVoice)window.TalvoVoice.onSection(name);if(window.TalvoClips)window.TalvoClips.onSection(name);if(name!=='llamada')callLeave();if(name==='learning-path')(window.loadLearningPath&&window.loadLearningPath());setTimeout(showCardPeek,600)}
let writingLevel='intermediate';
const WRITING_TARGETS={easy:80,intermediate:150,advanced:220};
async function loadWritingChallenge(){$('writing-challenge-card').style.display='block';$('writing-challenge-text').innerHTML=pqLoader('sm');try{const d=await jsonFetch('/api/writing/challenge?nivel='+writingLevel);$('writing-challenge-text').textContent=d.prompt||'';updateWritingWordcount()}catch(e){$('writing-challenge-text').textContent='Could not load a challenge — write about anything you like.'}}
function setWritingLevel(level,btn){writingLevel=level;$$('#writing-level-bar .mode').forEach(b=>b.classList.toggle('active',b.dataset.level===level));loadWritingChallenge()}
function updateWritingWordcount(){const n=$('writing').value.trim().split(/\s+/).filter(Boolean).length;const showTarget=$('writing-challenge-card').style.display!=='none';$('writing-wordcount').textContent=showTarget?`${n}/${WRITING_TARGETS[writingLevel]} words`:n+(n===1?' word':' words')}
async function loadShop(){$('shop-units').innerHTML='<div class="empty">'+pqLoader()+'</div>';$('shop-frames').innerHTML='';try{const d=await jsonFetch('/api/shop');$('shop-gems').textContent=`💎 ${d.gems} gems`;$('shop-freezes').textContent=`🧊 ${d.streak_freezes} streak freeze${d.streak_freezes===1?'':'s'}`;$('shop-buy-freeze').textContent=`Buy — ${d.streak_freeze_price} 💎`;$('shop-units').innerHTML=(d.unit_offers||[]).map(u=>`<div class="card" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:10px"><div><b style="font-size:14px">${esc(u.title)}</b></div><button type="button" class="btn" data-unlock-unit="${u.unit_code}">Unlock — ${u.price} 💎</button></div>`).join('')||'<div class="empty">No units available to unlock right now.</div>';$$('#shop-units [data-unlock-unit]').forEach(b=>b.addEventListener('click',()=>buyItem('unlock_unit:'+b.dataset.unlockUnit)));$('shop-frames').innerHTML=(d.frames||[]).map(f=>`<div class="report" style="text-align:center"><div style="width:52px;height:52px;border-radius:50%;margin:0 auto 8px;background:${f.gradient}"></div><b style="display:block;font-size:13px">${esc(f.name)}</b><button type="button" class="btn${f.id===d.avatar_frame?' primary':''}" style="margin-top:8px;width:100%" data-frame="${f.id}">${f.owned?(f.id===d.avatar_frame?'Equipped':'Equip'):('Buy — '+f.price+' 💎')}</button></div>`).join('');$$('#shop-frames [data-frame]').forEach(b=>b.addEventListener('click',()=>buyItem('frame:'+b.dataset.frame)))}catch(e){$('shop-units').innerHTML='<div class="empty">Could not load the shop.</div>';toast(e.message)}}
async function buyItem(item){try{await jsonFetch('/api/shop/buy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item})});toast('Done!');await loadShop();const s=await jsonFetch('/api/session');applyProfileIdentity(state.user,s)}catch(e){toast(e.message)}}
async function loadNotifications(){$('notif-list').innerHTML='<div class="empty">'+pqLoader()+'</div>';try{const [dash,ach]=await Promise.all([jsonFetch('/api/dashboard'),jsonFetch('/api/achievements')]);const cards=[];
if(dash.streak_days>0)cards.push({icon:'🔥',text:`You're on a ${dash.streak_days}-day streak! Keep it going today.`});
if(dash.daily_goal_pct>=100)cards.push({icon:'✅',text:'You\'ve completed today\'s goal. Great job!'});
else if(dash.daily_goal_pct>0)cards.push({icon:'🎯',text:`Today's goal is at ${dash.daily_goal_pct}% — a bit more and you're done.`});
else cards.push({icon:'🎯',text:'You haven\'t started today\'s goal yet — even a few minutes counts.'});
(ach.achievements||[]).filter(a=>!a.unlocked&&a.progress>=50).slice(0,3).forEach(a=>cards.push({icon:'🏅',text:`Almost there: ${a.title} is ${a.progress}% complete.`}));
(ach.achievements||[]).filter(a=>a.unlocked).slice(-2).forEach(a=>cards.push({icon:a.icon||'🏆',text:`Unlocked: ${a.title}`}));
$('notif-list').innerHTML=cards.length?cards.map(c=>`<div class="card" style="display:flex;gap:12px;align-items:center;margin-bottom:10px"><div style="font-size:22px">${c.icon}</div><div style="font-size:13px">${esc(c.text)}</div></div>`).join(''):'<div class="empty">You\'re all caught up — nothing new right now.</div>'
}catch(e){$('notif-list').innerHTML='<div class="empty">Could not load notifications.</div>';toast(e.message)}}
function pronAutoload(){const B=window.TalvoBank;if(!B)return;const m=state.pron;const emp=id=>{const e=$(id);return !!e&&(!e.textContent.trim()||!!e.querySelector('.pq-w,.pq-mini,[data-pq]')||/^\s*(Loading|Cargando)/i.test(e.textContent))};try{if(m==='lectura'&&emp('phrase')){const b=B.phrase();$('phrase').textContent=b.en;$('translation').textContent=b.es}else if(m==='habla_libre'&&emp('free-topic')){const b=B.topic();$('free-topic').textContent=b.en;$('free-instructions').textContent=b.es}else if(m==='trabalenguas'&&emp('twister')){const b=B.twister();$('twister').textContent=b.en;$('twister-focus').textContent='Focus: '+b.focus}}catch(e){}}
function pronMode(mode){state.pron=mode;$$('.mode[data-pron]').forEach(b=>b.classList.toggle('active',b.dataset.pron===mode));['lectura','habla_libre','trabalenguas'].forEach(x=>{const el=$('panel-'+x);if(el)el.classList.toggle('active',x===mode)});if(mode==='tutor'){section('tutor');return}$('pron-result').style.display='none';pronAutoload()}
let settingsAutoplay=localStorage.getItem('talvo_autoplay')!=='off';
let settingsSpeechRate=localStorage.getItem('talvo_speech_rate')||'normal';
function applySettingsUI(){$$('#setting-autoplay-bar .mode').forEach(b=>b.classList.toggle('active',b.dataset.val===(settingsAutoplay?'on':'off')));$$('#setting-rate-bar .mode').forEach(b=>b.classList.toggle('active',b.dataset.val===settingsSpeechRate))}
function setSettingAutoplay(val){settingsAutoplay=val==='on';localStorage.setItem('talvo_autoplay',val);applySettingsUI()}
function setSettingRate(val){settingsSpeechRate=val;localStorage.setItem('talvo_speech_rate',val);applySettingsUI()}
function speak(text,rate=1){if(!('speechSynthesis'in window))return;speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(String(text||''));u.lang='en-US';{const v=pickVoice();if(v)u.voice=v}u.rate=rate*(settingsSpeechRate==='slow'?0.75:1);speechSynthesis.speak(u)}
/* ---- Audio: voz neuronal del servidor, con respaldo inmediato del navegador ---- */
const audioCache=new Map(),ttsPending=new Map();
const SILENT_WAV='data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAABErAAABAAgAZGF0YQAAAAA=';
let hearEl=null,hearBtn=null;
function getHearEl(){if(!hearEl){hearEl=new Audio();hearEl.preload='auto';hearEl.playsInline=true}return hearEl}
function primeAudio(){try{const a=getHearEl();if(!a.__primed){a.__primed=true;a.src=SILENT_WAV;const p=a.play();if(p&&p.catch)p.catch(()=>{})}}catch(e){}}
function clearPlaying(){$$('.hear.is-playing').forEach(b=>b.classList.remove('is-playing'))}
function stopHearing(){try{if(hearEl)hearEl.pause()}catch(e){}try{window.speechSynthesis&&speechSynthesis.cancel()}catch(e){}clearPlaying()}
let _bestVoice=null,_bestFor=-1;
function pickVoice(){try{const vs=speechSynthesis.getVoices();if(!vs.length)return null;if(_bestVoice&&_bestFor===vs.length)return _bestVoice;
  const score=v=>{let n=0;if(/^en[-_]US/i.test(v.lang))n+=50;else if(/^en/i.test(v.lang))n+=20;else return -1;
    if(/natural|neural|online/i.test(v.name))n+=60;if(/aria|jenny|guy|ava|andrew|emma|brian|samantha|google us english|zoe|allison|premium|enhanced/i.test(v.name))n+=25;
    if(/espeak|compact|novelty|fred|junior|albert|bad news|bells|boing|cellos|good news|organ|trinoids|whisper|zarvox|bubbles|deranged|hysterical|pipe/i.test(v.name))n-=80;
    if(v.localService===false&&!/online|natural/i.test(v.name))n+=5;return n};
  let b=null,bs=-1;vs.forEach(v=>{const x=score(v);if(x>bs){bs=x;b=v}});_bestVoice=b;_bestFor=vs.length;return b}catch(e){return null}}
try{speechSynthesis.addEventListener('voiceschanged',()=>{_bestFor=-1})}catch(e){}
function browserSpeak(text,btn){
  return new Promise(res=>{
    try{
      if(!('speechSynthesis' in window)){res(false);return}
      speechSynthesis.cancel();
      const u=new SpeechSynthesisUtterance(String(text));u.lang='en-US';
      const v=pickVoice();if(v)u.voice=v;
      u.rate=settingsSpeechRate==='slow'?0.75:0.95;
      let done=false;const fin=ok=>{if(done)return;done=true;if(btn)btn.classList.remove('is-playing');res(ok)};
      u.onstart=()=>{if(btn)btn.classList.add('is-playing')};
      u.onend=()=>fin(true);u.onerror=e=>fin(e&&e.error==='canceled'||e&&e.error==='interrupted');
      speechSynthesis.speak(u);
      setTimeout(()=>fin(true),12000);
    }catch(e){res(false)}
  });
}
function fetchTts(text){
  if(audioCache.has(text))return Promise.resolve(audioCache.get(text));
  if(ttsPending.has(text))return ttsPending.get(text);
  if(OFL&&OFL.isOff())return Promise.reject(new Error('offline'));
  const p=(async()=>{
    const ctl=new AbortController(),t=setTimeout(()=>ctl.abort(),45000);
    try{
      const r=await authFetch('/api/sintetizar-audio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto:text}),signal:ctl.signal});
      if(!r.ok)throw new Error('tts '+r.status);
      const blob=await r.blob();if(!blob.size)throw new Error('empty');
      const url=URL.createObjectURL(blob);audioCache.set(text,url);return url;
    }finally{clearTimeout(t);ttsPending.delete(text)}
  })();
  ttsPending.set(text,p);return p;
}
let ttsChain=Promise.resolve();
function prefetchTts(list){(list||[]).forEach(t=>{t=String(t||'').trim();if(!t||audioCache.has(t))return;ttsChain=ttsChain.then(()=>fetchTts(t)).catch(()=>{})})}
function btnLoad(btn,on){if(!btn)return;if(on){if(btn.dataset.html===undefined)btn.dataset.html=btn.innerHTML;btn.innerHTML=pqMini();btn.classList.add('is-loading')}else{if(btn.dataset.html!==undefined){btn.innerHTML=btn.dataset.html;delete btn.dataset.html}btn.classList.remove('is-loading')}}
async function hear(text,btn,quiet){
  text=String(text||'').trim();if(!text)return;
  const a=getHearEl();stopHearing();primeAudio();
  const token=(hear.t=(hear.t||0)+1),cached=audioCache.get(text);
  let url=cached||null;
  if(!url){
    btnLoad(btn,true);
    try{url=await Promise.race([fetchTts(text),new Promise(r=>setTimeout(()=>r(null),3500))])}catch(e){url=null}
    btnLoad(btn,false);
    if(token!==hear.t)return;
  }
  if(url){
    try{
      a.onended=a.onpause=clearPlaying;a.src=url;a.currentTime=0;
      if(btn)btn.classList.add('is-playing');
      await a.play();return;
    }catch(e){clearPlaying()}
  }
  /* servidor lento o audio bloqueado: habla el navegador de inmediato (el servidor sigue guardando la voz buena para la próxima) */
  const ok=await browserSpeak(text,btn);
  if(!ok&&!quiet)toast('No se pudo reproducir el audio. Revisa el volumen de tu teléfono.');
}
async function playGuideAudio(text,btnId){if(!text)return toast('Genera una frase primero.');hear(text,btnId?$(btnId):null)}
document.addEventListener('click',e=>{const h=e.target.closest&&e.target.closest('[data-hear]');if(h){e.preventDefault();hear(h.dataset.hear,h)}});
async function newPhrase(){busy('new-phrase',true,'Generating...');try{const d=await jsonFetch('/nueva-frase');if(!d.frase)throw new Error('empty');$('phrase').textContent=d.frase;$('translation').textContent=d.traduccion||''}catch(e){const b=window.TalvoBank&&TalvoBank.phrase();if(b){$('phrase').textContent=b.en;$('translation').textContent=b.es}else toast(e.message)}finally{busy('new-phrase',false,'New sentence')}}
function customPhrase(){const v=$('custom-phrase').value.trim();if(!v)return toast('Write a sentence first.');$('phrase').textContent=v;$('translation').textContent='Custom sentence';$('custom-phrase').value='';$('pron-result').style.display='none'}
async function newTopic(){busy('new-topic',true,'Generating...');try{const d=await jsonFetch('/nuevo-tema-libre');if(!d.tema)throw new Error('empty');$('free-topic').textContent=d.tema;$('free-instructions').textContent=d.instrucciones||''}catch(e){const b=window.TalvoBank&&TalvoBank.topic();if(b){$('free-topic').textContent=b.en;$('free-instructions').textContent=b.es}else toast(e.message)}finally{busy('new-topic',false,'New topic')}}
async function newTwister(){busy('new-twister',true,'Generating...');try{const d=await jsonFetch('/nuevo-trabalenguas');if(!d.trabalenguas)throw new Error('empty');$('twister').textContent=d.trabalenguas;$('twister-focus').textContent='Focus: '+(d.enfoque||'')}catch(e){const b=window.TalvoBank&&TalvoBank.twister();if(b){$('twister').textContent=b.en;$('twister-focus').textContent='Focus: '+b.focus}else toast(e.message)}finally{busy('new-twister',false,'New challenge')}}
function resetTimer(){clearInterval(state.timer);state.timer=null;state.seconds=0}
function startTimer(){resetTimer();state.timer=setInterval(()=>{state.seconds++;$('record-btn').textContent=`Recording... ${state.seconds}s · Click to stop`},1000)}
let waveformCtx=null,waveformRAF=null,waveformAnalyser=null;
function startWaveform(stream){try{const AudioCtx=window.AudioContext||window.webkitAudioContext;if(!AudioCtx)return;waveformCtx=new AudioCtx();const source=waveformCtx.createMediaStreamSource(stream);waveformAnalyser=waveformCtx.createAnalyser();waveformAnalyser.fftSize=256;source.connect(waveformAnalyser);const canvas=$('pron-waveform');if(!canvas)return;const ctx2d=canvas.getContext('2d');const bufferLength=waveformAnalyser.frequencyBinCount;const dataArray=new Uint8Array(bufferLength);const draw=()=>{waveformRAF=requestAnimationFrame(draw);waveformAnalyser.getByteFrequencyData(dataArray);ctx2d.clearRect(0,0,canvas.width,canvas.height);const barWidth=canvas.width/bufferLength*2.2;let x=0;for(let i=0;i<bufferLength;i++){const v=dataArray[i]/255;const barHeight=v*canvas.height;ctx2d.fillStyle='rgba('+(getComputedStyle(document.documentElement).getPropertyValue('--c1-rgb').trim()||'62,232,255')+','+(0.4+v*0.6)+')';ctx2d.fillRect(x,canvas.height-barHeight,barWidth-2,barHeight);x+=barWidth;if(x>canvas.width)break}};draw()}catch(e){}}
function stopWaveform(){if(waveformRAF)cancelAnimationFrame(waveformRAF);waveformRAF=null;if(waveformCtx){try{waveformCtx.close()}catch(e){}waveformCtx=null}const canvas=$('pron-waveform');if(canvas){const ctx2d=canvas.getContext('2d');ctx2d.clearRect(0,0,canvas.width,canvas.height)}}
async function toggleRecording(){const b=$('record-btn');if(state.recording){resetTimer();state.recording=false;b.classList.remove('recording');b.textContent='Analyzing...';stopWaveform();try{state.recorder.stop();state.recorder.stream?.getTracks().forEach(t=>t.stop())}catch(e){toast('Recording could not be stopped.')}}else{if(!navigator.mediaDevices?.getUserMedia)return toast('Your browser does not support microphone recording.');try{const stream=await navigator.mediaDevices.getUserMedia({audio:true});let mime='audio/webm';if(window.MediaRecorder&&MediaRecorder.isTypeSupported){if(!MediaRecorder.isTypeSupported(mime)){const alternatives=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'];mime=alternatives.find(x=>MediaRecorder.isTypeSupported(x))||''}}state.chunks=[];state.recorder=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);state.recorder.ondataavailable=e=>{if(e.data.size)state.chunks.push(e.data)};state.recorder.onstop=sendRecording;state.recorder.start();state.recording=true;b.classList.add('recording');b.textContent='Recording... 0s · Click to stop';startTimer();startWaveform(stream)}catch(e){toast('Microphone error: '+e.message)}}}
const COACH_TIPS={"Phonetic accuracy":"Focus on individual sounds — try saying tricky words slowly, then at natural speed.","Pronunciation":"Focus on individual sounds — try saying tricky words slowly, then at natural speed.","Fluency":"Practice speaking in longer phrases without stopping. Reading a passage aloud a few times really helps.","Completeness":"Make sure to say every word in the sentence — avoid skipping or rushing through parts.","Prosody":"Work on your intonation — exaggerate the natural rise and fall of the sentence as you practice.","Grammar":"Review the grammar patterns you used, and try rewriting the sentence with correct verb tenses.","Vocabulary":"Try using more specific or varied words — Today's Vocabulary has new words daily.","Coherence":"Organize your ideas with clear connectors like \"first\", \"then\", \"because\".","English quality":"Review your word choice and sentence structure for a more natural flow.","Accuracy":"Reread carefully and double-check the details before answering.","Listening accuracy":"Play it again and focus on one phrase at a time — pausing between words is totally fine while you practice."};
function renderCoachInsight(containerId,metrics,actions){const valid=metrics.filter(m=>m.value!=null&&!isNaN(Number(m.value)));if(!valid.length){$(containerId).innerHTML='';return}const weakest=valid.reduce((a,b)=>Number(b.value)<Number(a.value)?b:a);const tip=COACH_TIPS[weakest.label]||'Keep practicing consistently — small daily sessions add up fast.';const acts=actions||[];const btnsHtml=acts.map((a,i)=>`<button type="button" class="btn${i===0?' primary':''}" id="${containerId}-action-${i}" style="margin:4px 8px 0 0">${esc(a.label)}</button>`).join('');$(containerId).innerHTML=`<div class="card" style="margin-top:14px;background:linear-gradient(135deg,rgba(113,128,255,.14),rgba(113,128,255,.02))"><div style="font-size:11px;color:var(--primary);font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">🧭 Coach insight</div><p style="font-size:13px;margin:0 0 ${acts.length?'2px':'0'}">To sound more fluent, work on your <b>${esc(weakest.label.toLowerCase())}</b> score (${Math.round(weakest.value)}%). ${esc(tip)}</p>${btnsHtml}</div>`;acts.forEach((a,i)=>$(`${containerId}-action-${i}`)?.addEventListener('click',()=>a.fn(weakest.label)))}
function goToLearningPathFor(){section('learning-path')}
function renderPaceGauge(containerId,wpm){if(!wpm){$(containerId).innerHTML='';return}const min=60,max=220;const pct=Math.max(0,Math.min(1,(wpm-min)/(max-min)));const angle=180*pct;const cx=100,cy=100,r=80;const rad=(180-angle)*Math.PI/180;const nx=cx+r*0.78*Math.cos(rad),ny=cy-r*0.78*Math.sin(rad);const label=wpm<100?'Slow':wpm<170?'Good pace':'Fast';const color=wpm<100?'#f5a524':wpm<170?'#22c55e':'#f5a524';const circ=Math.PI*r;$(containerId).innerHTML=`<label class="field-label">Speaking rate</label><svg viewBox="0 0 200 110" style="width:100%;max-width:200px;display:block;margin:0 auto"><path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="var(--line)" stroke-width="10" stroke-linecap="round"/><path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round" stroke-dasharray="${angle/180*circ} ${circ}"/><line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="var(--text)" stroke-width="3" stroke-linecap="round"/><circle cx="${cx}" cy="${cy}" r="5" fill="var(--text)"/></svg><div style="text-align:center;margin-top:-4px"><b style="font-size:18px">${wpm}</b> <small style="color:var(--muted)">wpm</small> · <small style="color:${color};font-weight:700">${label}</small></div>`}
function radarPoints(n,radius,cx,cy,scale){const pts=[];for(let i=0;i<n;i++){const angle=(-90+i*(360/n))*Math.PI/180;pts.push([cx+radius*scale*Math.cos(angle),cy+radius*scale*Math.sin(angle)])}return pts}
function renderRadar(containerId,items){const n=items.length;if(n<3){$(containerId).innerHTML='';return}const cx=100,cy=100,R=72;const gid='radarGrad'+Math.random().toString(36).slice(2,8);let svg=`<svg viewBox="0 0 200 200" style="width:100%;max-width:230px;display:block;margin:0 auto"><defs><radialGradient id="${gid}" cx="50%" cy="50%" r="65%"><stop offset="0%" stop-color="var(--primary)" stop-opacity=".5"/><stop offset="100%" stop-color="var(--primary2)" stop-opacity=".1"/></radialGradient></defs>`;[0.25,0.5,0.75,1].forEach(lv=>{const pts=radarPoints(n,R,cx,cy,lv);svg+=`<polygon points="${pts.map(p=>p.join(',')).join(' ')}" fill="none" stroke="var(--line)" stroke-width="1"/>`});const axisPts=radarPoints(n,R,cx,cy,1);axisPts.forEach(p=>{svg+=`<line x1="${cx}" y1="${cy}" x2="${p[0]}" y2="${p[1]}" stroke="var(--line)" stroke-width="1"/>`});const valPts=items.map((it,i)=>{const v=Math.max(0,Math.min(100,Number(it.value)||0))/100;return radarPoints(n,R,cx,cy,v)[i]});svg+=`<polygon class="radar-fill" points="${valPts.map(p=>p.join(',')).join(' ')}" fill="url(#${gid})" stroke="var(--primary)" stroke-width="2" style="transform-origin:${cx}px ${cy}px;transform:scale(0);transition:transform .6s cubic-bezier(.34,1.56,.64,1)"/>`;valPts.forEach(p=>{svg+=`<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="var(--primary)"/>`});axisPts.forEach((p,i)=>{const lx=cx+(p[0]-cx)*1.32,ly=cy+(p[1]-cy)*1.32;svg+=`<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" font-size="9" fill="var(--muted)">${esc(items[i].label)}</text>`});svg+='</svg>';$(containerId).innerHTML=svg;requestAnimationFrame(()=>requestAnimationFrame(()=>{const el=$(containerId).querySelector('.radar-fill');if(el)el.style.transform='scale(1)'}))}
function renderMetrics(items){$('metric-list').innerHTML=items.map(x=>{const v=Math.max(0,Math.min(100,Number(x.value)||0));return `<div><div class="metric-head"><span>${esc(x.label)}</span><span>${Math.round(v)}%</span></div><div class="bar"><div class="fill" style="width:${v}%"></div></div></div>`}).join('')}
const MOUTH_TIPS={omisiones:{icon:'👄',title:"You're skipping some sounds",tip:"Make sure to pronounce word endings fully, especially -s, -ed and -ing. Try exaggerating the last sound of each word as you practice."},pronunciaciones_incoherentes:{icon:'🗣️',title:'Some sounds need sharpening',tip:"Slow down on the tricky word and isolate the sound — say just that word three times before the full sentence."},inserciones:{icon:'🚫',title:'Extra sounds are sneaking in',tip:"Avoid adding a vowel sound between consonants — try saying the consonant cluster softly, without a pause between letters."},interrupcion_inesperada:{icon:'💨',title:'Unexpected pauses',tip:"Take a breath before you start speaking so you don't run out of air mid-sentence."},falta_un_descanso:{icon:'⏸️',title:'Missing natural pauses',tip:"Pause briefly at commas and periods — it makes your speech sound more natural and gives you time to breathe."},monotona:{icon:'🎵',title:'Try more intonation',tip:"English rises and falls a lot. Exaggerate the pitch on the most important word in the sentence — it will feel strange at first, but that's how natural English sounds."}};
function renderMouthTips(containerId,insp){const active=Object.entries(insp||{}).filter(([k,v])=>v>0&&MOUTH_TIPS[k]);if(!active.length){$(containerId).innerHTML='';return}$(containerId).innerHTML='<label class="field-label">How to improve</label>'+active.map(([k])=>{const t=MOUTH_TIPS[k];return `<div class="card" style="margin-top:8px;padding:12px"><div style="display:flex;gap:10px;align-items:flex-start"><div style="font-size:20px">${t.icon}</div><div><b style="font-size:13px;display:block;margin-bottom:3px">${esc(t.title)}</b><small style="color:var(--muted)">${esc(t.tip)}</small></div></div></div>`}).join('')}
function renderPron(d){const insp=d.inspeccion||{};renderMouthTips('pron-mouth-tips',insp);$('i-omission').textContent=insp.omisiones||0;$('i-mispron').textContent=insp.pronunciaciones_incoherentes||insp.incoherentes||0;$('i-insertion').textContent=insp.inserciones||0;$('i-break').textContent=insp.interrupcion_inesperada||0;$('i-missing').textContent=insp.falta_un_descanso||0;$('i-monotone').textContent=insp.monotona||0;
const strengthMap=[[insp.omisiones,'Complete words'],[insp.pronunciaciones_incoherentes||insp.incoherentes,'Consistent sounds'],[insp.inserciones,'No extra sounds'],[insp.interrupcion_inesperada,'Smooth flow'],[insp.falta_un_descanso,'Natural pauses'],[insp.monotona,'Good intonation']];
const strengths=strengthMap.filter(([count])=>!count).map(([,label])=>label).slice(0,4);
$('pron-strengths').innerHTML=strengths.length?strengths.map(s=>`<span class="badge" style="font-size:11px;padding:6px 10px">✓ ${esc(s)}</span>`).join(''):'';$('global-score').textContent=Math.round(Number(d.puntuacion_global||0));const gscore=Number(d.puntuacion_global||0);$('global-score').className='circle '+(gscore>=80?'good':gscore>=60?'mid':'low');if(state.pron==='habla_libre'&&d.content_assessment){const c=d.content_assessment;const m=[{label:'Pronunciation',value:d.precision},{label:'Fluency',value:d.fluidez},{label:'Grammar',value:d.gramatica||c.grammar_score},{label:'Vocabulary',value:d.vocabulario||c.vocabulary_score}];renderMetrics(m);renderRadar('pron-radar',m);renderCoachInsight('pron-coach',m,[{label:'🎯 Personalized practice',fn:(lb)=>lpFocusFromTool('pronunciation',lb)},{label:'📍 Open Learning Path',fn:()=>goToLearningPathFor()}])}else{const m=[{label:'Phonetic accuracy',value:d.precision},{label:'Fluency',value:d.fluidez},{label:'Completeness',value:d.completitud},{label:'Prosody',value:d.prosodia}];renderMetrics(m);renderRadar('pron-radar',m);renderCoachInsight('pron-coach',m,[{label:'🎯 Personalized practice',fn:(lb)=>lpFocusFromTool('pronunciation',lb)},{label:'📍 Open Learning Path',fn:()=>goToLearningPathFor()}])}$('pron-recording').innerHTML=state.lastRecordingUrl?`<label class="field-label">Your recording</label><audio controls src="${state.lastRecordingUrl}" style="width:100%"></audio>`:'';renderPaceGauge('pron-pace',d.velocidad_wpm);$('words').innerHTML='';(d.palabras||[]).forEach(item=>{const score=Number(item.precision??item.puntuacion??0);const b=document.createElement('button');b.type='button';b.className='word '+(score>=80?'good':score>=60?'mid':'low');b.innerHTML=`<b>${esc(item.palabra)}</b><small>${Math.round(score)}%</small>`;b.addEventListener('click',()=>showPhonemes(item));$('words').appendChild(b)});$('phonemes').style.display='none';$('pron-result').style.display='block';$('pron-result').scrollIntoView({behavior:'smooth',block:'nearest'});reactToScore(d.puntuacion_global);renderPronTrend();try{pronPost(d,gscore)}catch(e){}}
/* --- Pronunciación v2: palabras tocables, veredicto, repetir solo las difíciles --- */
function pronWrap(el){
  if(!el||el.querySelector('.pq-w,.pq-mini,[data-pq],.pw'))return;
  const t=el.textContent;if(!t.trim())return;
  el.innerHTML=t.split(/(\s+)/).map(p=>!p||/^\s+$/.test(p)?p:'<span class="pw" role="button" tabindex="0" data-w="'+esc(p.replace(/[^\w'’-]/g,''))+'">'+esc(p)+'</span>').join('');
}
(function(){
  const ids=['phrase','twister'];
  const mo=new MutationObserver(()=>ids.forEach(i=>pronWrap($(i))));
  ids.forEach(i=>{const el=$(i);if(el){mo.observe(el,{childList:true,characterData:true,subtree:true});pronWrap(el)}});
  document.addEventListener('click',e=>{
    const w=e.target.closest&&e.target.closest('.pw');
    if(w&&w.dataset.w){w.classList.add('say');setTimeout(()=>w.classList.remove('say'),700);speak(w.dataset.w,.8);return}
    const sl=e.target.closest&&e.target.closest('[data-slow]');
    if(sl){const el=$(sl.dataset.slow);if(el)speak(el.textContent.trim(),.6)}
    const fs=e.target.closest&&e.target.closest('[data-fastof]');
    if(fs){const el=$(fs.dataset.fastof);if(el)window.TalvoNative.say(el.textContent)}
  });
  document.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.classList&&e.target.classList.contains('pw')){e.preventDefault();e.target.click()}});
})();
function pronPost(d,score){try{skRecord('pron',Math.round(score||0))}catch(e){}
  const g=$('global-score');g.style.setProperty('--p',Math.max(0,Math.min(100,Math.round(score))));
  const res=$('pron-result');let v=$('pron-verdict');
  if(!v){v=document.createElement('div');v.id='pron-verdict';res.insertBefore(v,res.firstChild)}
  const hi=score>=85,mid=score>=65;
  v.className='pron-verdict '+(hi?'good':mid?'':'low');
  v.innerHTML='<span class="e">'+(hi?'🏆':mid?'👍':'💪')+'</span><div><b>'+T(hi?'Excellent — that sounded natural!':mid?'Good job — a few words to polish.':'Nice try — let\'s work on a few words.')+'</b><small>'+T('Tap any word below to see its sounds.')+'</small></div>';
  const weak=(d.palabras||[]).filter(x=>Number(x.precision??x.puntuacion??0)<75&&x.palabra).map(x=>x.palabra);
  let a=$('pron-actions');
  if(!a){a=document.createElement('div');a.id='pron-actions';$('words').after(a)}
  const scripted=state.pron==='lectura'||state.pron==='trabalenguas';
  const src=state.pron==='trabalenguas'?$('twister'):$('phrase');
  let h='';
  if(scripted)h+='<button type="button" class="btn" id="pa-model">🔊 '+T('Hear the model')+'</button>';
  if(scripted&&weak.length)h+='<button type="button" class="btn primary" id="pa-weak">🎯 '+T('Practice only tricky words')+' ('+weak.length+')</button>';
  h+='<button type="button" class="btn" id="pa-again">🔁 '+T('Try again')+'</button>';
  a.innerHTML=h;
  const up=()=>{res.style.display='none';const tgt=state.pron==='trabalenguas'?'panel-trabalenguas':'panel-lectura';const el=$(tgt);if(el)el.scrollIntoView({behavior:'smooth',block:'center'})};
  $('pa-model')&&($('pa-model').onclick=()=>speak(src.textContent.trim(),.9));
  $('pa-again').onclick=up;
  $('pa-weak')&&($('pa-weak').onclick=()=>{const txt=[...new Set(weak)].join(', ');src.textContent=txt;const tr=state.pron==='lectura'?$('translation'):null;if(tr)tr.textContent=T('Practice your tricky words');up()});
}
function showPhonemes(item){state.phWord=item.palabra||'';$('phonemes').style.display='block';$('phoneme-title').textContent=`${item.palabra||'Word'} · ${item.precision??item.puntuacion??0}%`;$('chips').innerHTML=(item.fonemas||[]).map(p=>`<span class="chip">/${esc(p.fonema)}/ · ${p.precision??0}%</span>`).join('')||'<span style="color:var(--muted);font-size:11px">No phoneme detail available.</span>'}
async function sendRecording(){const blob=new Blob(state.chunks,{type:state.chunks[0]?.type||'audio/webm'});if(state.lastRecordingUrl)URL.revokeObjectURL(state.lastRecordingUrl);state.lastRecordingUrl=URL.createObjectURL(blob);const fd=new FormData();fd.append('audio',blob,'recording.webm');let path='/analizar-audio-real';if(state.pron==='lectura'){fd.append('frase_esperada',$('phrase').textContent.trim());fd.append('modo','lectura')}else if(state.pron==='trabalenguas'){fd.append('frase_esperada',$('twister').textContent.trim());fd.append('modo','trabalenguas')}else{path='/api/assess-unscripted';fd.append('topic',$('free-topic').textContent.trim());fd.append('modo','habla_libre')}try{const d=await jsonFetch(path,{method:'POST',body:fd});renderPron(d)}catch(e){toast(e.message)}finally{$('record-btn').textContent='Start recording';$('record-btn').classList.remove('recording');state.chunks=[]}}
/* --- Skill hero --- */
const SK_CFG={pronunciacion:{k:'pron',ic:'🎙️'},escritura:{k:'write',ic:'✍️'},lectura:{k:'read',ic:'📖'},escucha:{k:'listen',ic:'🎧'},
tutor:{k:'tutor',ic:'🤖',tiles:[['⚡','Instant feedback'],['🗣️','Voice or text']]},
llamada:{k:'call',ic:'📞',tiles:[['🎧','Hands-free'],['⏱️','Live call']]},
vocabulario:{k:'vocab',ic:'🧠',tiles:[['📚','Daily words'],['🔁','Spaced review']]},
traductor:{k:'trans',ic:'🌐',tiles:[['⚡','Instant'],['🔊','Hear it']]},
escenarios:{k:'role',ic:'🎭',tiles:[['🎤','Real roles'],['🧭','Coach tips']]},
voz:{k:'voice',ic:'🎚️',tiles:[['🔬','Analyze'],['🪞','Shadowing']]},
clips:{k:'clips',ic:'🎬',tiles:[['📝','Live subtitles'],['✅','Quick quiz']]},
presentacion:{k:'pres',ic:'📊',tiles:[['📜','Script'],['🎙️','Practice aloud']]},
rutas:{k:'routes',ic:'🧭',tiles:[['🎯','Your goal'],['🛣️','Custom path']]},
historial:{k:'prog',ic:'📈'},logros:{k:'ach',ic:'🏆'},
shop:{k:'shop',ic:'💎',tiles:[['💎','Earn gems'],['🎁','Rewards']]},
notificaciones:{k:'notif',ic:'🔔',tiles:[['🔥','Streak'],['🎯','Goals']]},
configuracion:{k:'set',ic:'⚙️'},
soporte:{k:'help',ic:'💬',tiles:[['⚡','Fast replies'],['💡','Ideas welcome']]},
admin:{k:'admin',ic:'🛰️',tiles:[['👥','Usuarios'],['📈','En vivo']]},
cuenta:{k:'acct',ic:'👤',tiles:[['🛡️','Secure'],['🔔','Reminders']]}};
function skGet(k){try{return JSON.parse(localStorage.getItem('talvo_sk_'+k))||{n:0,best:0,sum:0}}catch(e){return{n:0,best:0,sum:0}}}
function skStats(k){const el=document.querySelector('.sk-hero[data-k="'+k+'"] .sk-stats');if(!el)return;const d=skGet(k);el.innerHTML=[[d.n,'Sessions'],[d.best||'—','Best score'],[d.n?Math.round(d.sum/d.n):'—','Average']].map(([v,l])=>'<div><b>'+v+'</b><small>'+T(l)+'</small></div>').join('')}
function skRecord(k,score){const d=skGet(k);d.n++;d.sum+=score||0;d.best=Math.max(d.best,score||0);try{localStorage.setItem('talvo_sk_'+k,JSON.stringify(d))}catch(e){}skStats(k)}
function skHero(id){
  const sec=$('sec-'+id),c=SK_CFG[id];if(!sec||sec.querySelector('.sk-hero'))return;
  const h=document.createElement('div');h.className='sk-hero';h.dataset.k=c.k;
  h.innerHTML='<i class="sk-scan"></i><div class="sk-ico">'+c.ic+'</div><div class="sk-main"></div><div class="sk-stats"></div>';if(c.tiles){h.querySelector('.sk-stats').innerHTML=c.tiles.map(t=>'<div><b>'+t[0]+'</b><small data-t="'+t[1]+'">'+T(t[1])+'</small></div>').join('')}else if(!['pron','write','read','listen'].includes(c.k))h.querySelector('.sk-stats').remove();
  const m=h.querySelector('.sk-main');
  ['.eyebrow','.page-title','.page-desc'].forEach(q=>{const e=sec.querySelector(':scope>'+q);if(e)m.appendChild(e)});
  sec.insertBefore(h,sec.firstChild);if(['pron','write','read','listen'].includes(c.k))skStats(c.k);
}
setTimeout(function(){Object.keys(SK_CFG).forEach(skHero);skEntryWriting()},0);
const W_IC={easy:'🌱',intermediate:'⚡',advanced:'🚀'};
function skWLevels(){document.querySelectorAll('#writing-level-bar .mode').forEach(b=>{b.dataset.ic=W_IC[b.dataset.level]||'✍️';b.dataset.w='≈ '+WRITING_TARGETS[b.dataset.level]+' '+T('words')})}
function skWProg(){const ta=$('writing'),pr=$('w-prog');if(!ta||!pr)return;const n=ta.value.trim().split(/\s+/).filter(Boolean).length,t=$('writing-challenge-card').style.display!=='none'?WRITING_TARGETS[writingLevel]:100;pr.firstChild.style.width=Math.min(100,Math.round(n/t*100))+'%';pr.classList.toggle('ok',n>=t);const b=$('w-cb-n');if(b)b.textContent=n+(t&&$('writing-challenge-card').style.display!=='none'?' / '+t:'')+' '+T('words')}
function skEntryWriting(){
  skWLevels();
  const mis=$('writing-challenge-text')?.parentElement;if(mis)mis.classList.add('w-mis');
  const ta=$('writing');if(!ta)return;const card=ta.closest('.card');if(!card||card.classList.contains('w-console'))return;
  card.classList.add('w-console');
  const bar=document.createElement('div');bar.className='w-cbar';bar.innerHTML='<i></i><i></i><i></i><span data-i18n-skip>draft.txt</span><b id="w-cb-n" data-i18n-skip></b>';card.insertBefore(bar,card.firstChild);
  const pr=document.createElement('div');pr.className='w-prog';pr.id='w-prog';pr.innerHTML='<i></i>';ta.after(pr);
  ta.addEventListener('input',skWProg);$('writing-level-bar')?.addEventListener('click',()=>setTimeout(()=>{skWLevels();skWProg()},60));
  $('writing-skip-challenge')?.addEventListener('click',()=>setTimeout(skWProg,60));$('writing-new-challenge')?.addEventListener('click',()=>setTimeout(skWProg,60));
  skWProg();
}
/* --- Escritura v2 --- */
const W_CHIPS={easy:['I like','Because','For example,','Every day I','My favorite'],intermediate:['In my opinion,','On the other hand,','For example,','As a result,','I used to'],advanced:['Nevertheless,','Having said that,','It could be argued that','Not only … but also','In the long run,']};
function wDraftSave(){try{localStorage.setItem('talvo_write_draft',$('writing').value)}catch(e){}}
function wToolsRender(){
  const box=$('w-tools');if(!box)return;
  const lvl=(typeof writingLevel!=='undefined'&&W_CHIPS[writingLevel])?writingLevel:'intermediate';
  box.innerHTML='<div class="w-chips" data-i18n-skip>'+W_CHIPS[lvl].map(c=>'<button type="button" class="w-chip" data-ins="'+esc(c)+'">+ '+esc(c)+'</button>').join('')+'</div>'
   +'<div class="w-row"><button type="button" class="btn" id="w-listen">🔊 '+T('Listen to my text')+'</button><button type="button" class="btn" id="w-clear">🗑 '+T('Clear')+'</button><small id="w-saved"></small></div>';
}
setTimeout(function(){
  const ta=$('writing');if(!ta)return;
  wToolsRender();
  try{const d=localStorage.getItem('talvo_write_draft');if(d&&!ta.value.trim()){ta.value=d;if(typeof updateWritingWordcount==='function')updateWritingWordcount()}}catch(e){}
  let t=0;ta.addEventListener('input',()=>{clearTimeout(t);t=setTimeout(()=>{wDraftSave();const s=$('w-saved');if(s)s.textContent=T('Draft saved ✓')},500)});
  ta.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();analyzeWriting()}});
  $('writing-level-bar')?.addEventListener('click',()=>setTimeout(wToolsRender,50));
  document.addEventListener('click',e=>{
    const c=e.target.closest&&e.target.closest('.w-chip');
    if(c){const v=c.dataset.ins+' ',s=ta.selectionStart??ta.value.length;ta.value=ta.value.slice(0,s)+v+ta.value.slice(ta.selectionEnd??s);ta.focus();ta.selectionStart=ta.selectionEnd=s+v.length;ta.dispatchEvent(new Event('input'));return}
    if(e.target.closest&&e.target.closest('#w-listen')){const x=ta.value.trim();if(x)speak(x,.95);else toast(T('Write something first.'));return}
    if(e.target.closest&&e.target.closest('#w-clear')){if(ta.value.trim()&&!confirm(T('Clear your text?')))return;ta.value='';ta.dispatchEvent(new Event('input'));wDraftSave();return}
  });
},0);
function wNorm(x){return x.toLowerCase().replace(/[^\p{L}\p{N}']/gu,'')}
function wDiffHTML(orig,better){
  const a=orig.split(/\s+/).filter(Boolean).map(wNorm),b=better.split(/\s+/).filter(Boolean),bn=b.map(wNorm);
  if(a.length*bn.length>600000)return esc(better);
  const n=a.length,m=bn.length,L=Array.from({length:n+1},()=>new Uint16Array(m+1));
  for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)L[i][j]=a[i]===bn[j]?L[i+1][j+1]+1:Math.max(L[i+1][j],L[i][j+1]);
  const keep=new Set();let i=0,j=0;
  while(i<n&&j<m){if(a[i]===bn[j]){keep.add(j);i++;j++}else if(L[i+1][j]>=L[i][j+1])i++;else j++}
  return b.map((w,k)=>keep.has(k)?esc(w):'<ins>'+esc(w)+'</ins>').join(' ');
}
function writePost(d,text){
  const sc=Math.round(d.puntuacion||0),res=$('writing-result');
  let v=$('w-verdict');if(!v){v=document.createElement('div');v.id='w-verdict';res.insertBefore(v,res.firstChild)}
  const cls=sc>=80?'good':sc>=60?'mid':'low';
  const msg=sc>=85?'Excellent writing!':sc>=70?'Good work — a few fixes will make it shine.':sc>=50?'Nice effort — let\'s fix the key points.':'Good start — every text makes you better.';
  const bars=[['Grammar',d.gramatica],['Vocabulary',d.vocabulario],['Coherence',d.coherencia]].map(([l,x])=>'<div class="wv-bar"><span>'+T(l)+'</span><i><em style="width:'+Math.round(x||0)+'%"></em></i><b>'+Math.round(x||0)+'</b></div>').join('');
  v.innerHTML='<div class="circle '+cls+'" style="--p:'+sc+'">'+sc+'</div><div class="wv-txt"><b>'+T(msg)+'</b><small>'+esc(d.resumen||'')+'</small><div class="wv-bars">'+bars+'</div></div>';
  const better=d.version_mejorada||'';
  if(better){
    $('w-better').innerHTML=wDiffHTML(text,better);
    let a=$('wb-actions');if(!a){a=document.createElement('div');a.id='wb-actions';a.className='wb-actions';$('w-better').after(a)}
    a.innerHTML='<button type="button" class="btn" id="wb-listen">🔊 '+T('Listen')+'</button><button type="button" class="btn" id="wb-copy">📋 '+T('Copy')+'</button><button type="button" class="btn primary" id="wb-use">✨ '+T('Use this version')+'</button>';
    $('wb-listen').onclick=()=>speak(better,.95);
    $('wb-copy').onclick=async()=>{try{await navigator.clipboard.writeText(better);toast(T('Copied'))}catch(e){toast(T('Could not copy'))}};
    $('wb-use').onclick=()=>{$('writing').value=better;$('writing').dispatchEvent(new Event('input'));if(typeof updateWritingWordcount==='function')updateWritingWordcount();$('writing').scrollIntoView({behavior:'smooth',block:'center'});toast(T('Improved version loaded. Edit it and analyze again!'))};
  }
}
async function analyzeWriting(){const text=$('writing').value.trim();if(!text)return toast('Write something first.');busy('writing-submit',true,'Analyzing...');try{const d=await jsonFetch('/analizar-escritura',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto:text})});$('w-score').textContent=Math.round(d.puntuacion||0);$('w-grammar').textContent=Math.round(d.gramatica||0);$('w-vocab').textContent=Math.round(d.vocabulario||0);$('w-coherence').textContent=Math.round(d.coherencia||0);$('w-summary').textContent=d.resumen||'';$('w-corrections').innerHTML=(d.correcciones||[]).map(x=>`<li>${esc(typeof x==='string'?x:JSON.stringify(x))}</li>`).join('')||'<li>No corrections.</li>';$('w-better').textContent=d.version_mejorada||'';try{writePost(d,text);skRecord('write',Math.round(d.puntuacion||0))}catch(e){console.error(e)}$('writing-result').style.display='block';reactToScore(d.puntuacion);renderCoachInsight('writing-coach',[{label:'Grammar',value:d.gramatica},{label:'Vocabulary',value:d.vocabulario},{label:'Coherence',value:d.coherencia}],[{label:'🔄 Try a new challenge',fn:loadWritingChallenge},{label:'🎯 Personalized practice',fn:(lb)=>lpFocusFromTool('writing',lb)},{label:'📍 Open Learning Path',fn:()=>goToLearningPathFor()}])}catch(e){toast(e.message)}finally{busy('writing-submit',false,'Analyze writing')}}
let readingLibraryItems=[];
let readingLibraryFilter='all';
async function loadReadingLibrary(){$('reading-library-view').style.display='block';$('reading-practice-view').style.display='none';$('reading-library-list').innerHTML='<div class="empty">'+pqLoader()+'</div>';try{const d=await jsonFetch('/api/reading/library');readingLibraryItems=d.items||[];renderReadingLibraryList()}catch(e){$('reading-library-list').innerHTML='<div class="empty">Could not load the library.</div>';toast(e.message)}}
function renderReadingLibraryList(){const items=readingLibraryItems.filter(x=>readingLibraryFilter==='all'||x.level===readingLibraryFilter);$('reading-library-list').innerHTML=items.map(x=>`<button type="button" class="lib-card ${esc(x.level)}" data-reading-id="${x.id}"><div class="lib-cov"><span class="rl-lv ${esc(x.level)}" data-i18n-skip>${esc(x.level)}</span><span class="lib-ic">📖</span></div><b class="rl-t">${esc(x.title)}</b><small>⏱ ${x.minutes} min</small><span class="lib-go">Start reading →</span></button>`).join('')||'<div class="empty">No readings for this level.</div>';$$('#reading-library-list [data-reading-id]').forEach(b=>b.addEventListener('click',()=>openReadingEntry(b.dataset.readingId)))}
function setReadingFilter(level){readingLibraryFilter=level;$$('#reading-filter-bar .mode').forEach(b=>b.classList.toggle('active',b.dataset.level===level));renderReadingLibraryList()}
async function openReadingEntry(entryId){state.readingEntryId=entryId;$('reading-library-view').style.display='none';$('reading-practice-view').style.display='block';$('reading-text').innerHTML=pqLoader('sm');$('reading-time').textContent='';$('reading-answer').value='';$('reading-result').style.display='none';try{const d=await jsonFetch('/api/reading/library/'+entryId);state.reading=d;$('reading-text').textContent=d.texto||'';const words=(d.texto||'').trim().split(/\s+/).filter(Boolean).length;$('reading-time').textContent=words?`⏱ ${Math.max(1,Math.round(words/200))} min read`:''}catch(e){toast(e.message)}}
function regenerateReading(){if(state.readingEntryId)openReadingEntry(state.readingEntryId);else loadReading()}
async function loadReading(){try{const d=await jsonFetch('/nuevo-texto-lectura');state.reading=d;$('reading-text').textContent=d.texto||'';const words=(d.texto||'').trim().split(/\s+/).filter(Boolean).length;$('reading-time').textContent=words?`⏱ ${Math.max(1,Math.round(words/200))} min read`:'';$('reading-answer').value='';$('reading-result').style.display='none'}catch(e){toast(e.message)}}
/* --- Entrada Lectura / Escucha --- */
function skShuffle(listId,getItems,filterKey,openFn){
  const list=$(listId);if(!list||list.previousElementSibling&&list.previousElementSibling.classList.contains('lib-tools'))return;
  const t=document.createElement('div');t.className='lib-tools';t.innerHTML='<button type="button" class="btn">🎲 '+T('Surprise me')+'</button>';
  list.before(t);
  t.firstChild.onclick=()=>{const it=getItems().filter(x=>filterKey()==='all'||x.level===filterKey());if(!it.length)return toast(T('No items for this level.'));openFn(it[Math.floor(Math.random()*it.length)].id)};
}
function skEntryReading(){
  skShuffle('reading-library-list',()=>readingLibraryItems,()=>readingLibraryFilter,openReadingEntry);
  const t=$('reading-text');if(!t)return;const card=t.closest('.card');if(!card||card.classList.contains('r-card'))return;
  card.classList.add('r-card');
  const bar=document.createElement('div');bar.className='w-cbar';bar.innerHTML='<i></i><i></i><i></i><span data-i18n-skip>article.txt</span><b id="r-cb-t"></b>';card.insertBefore(bar,card.firstChild);
  const rt=$('reading-time');new MutationObserver(()=>{const b=$('r-cb-t');if(b)b.textContent=rt.textContent}).observe(rt,{childList:true,characterData:true,subtree:true});
  const ans=$('reading-answer').closest('.card');ans.classList.add('w-console');
  const b2=document.createElement('div');b2.className='w-cbar';b2.innerHTML='<i></i><i></i><i></i><span data-i18n-skip>answer.txt</span><b id="r-cb-n" data-i18n-skip></b>';ans.insertBefore(b2,ans.firstChild);
  const upd=()=>{const n=$('reading-answer').value.trim()?$('reading-answer').value.trim().split(/\s+/).length:0;$('r-cb-n').textContent=n+' '+T('words')};
  $('reading-answer').addEventListener('input',upd);upd();
  $('r-wc').style.display='none';
}
function skEntryListening(){
  skShuffle('listening-library-list',()=>listeningLibraryItems,()=>listeningLibraryFilter,openListeningEntry);
  const card=$('dictation-answer')?.closest('.card');if(!card||card.querySelector('.l-player'))return;
  const pl=document.createElement('div');pl.className='l-player';
  pl.innerHTML='<button type="button" class="l-big" id="l-big" aria-label="Play audio">▶</button><div class="l-wave" aria-hidden="true">'+Array.from({length:34},(_,i)=>'<i style="--h:'+(30+Math.round(Math.abs(Math.sin(i*1.7))*65))+'%;animation-delay:'+((i%9)*.08).toFixed(2)+'s"></i>').join('')+'</div><div class="l-ctl"><button type="button" class="btn on" id="l-fast">▶ 1×</button><button type="button" class="btn" id="l-slow">🐢 0.7×</button><button type="button" class="btn lp-fastbtn" id="l-native">⚡ '+T('Native speed')+'</button><button type="button" class="btn" id="l-new">🔄 '+T('New audio')+'</button><span class="badge" id="l-plays">🎧 0 plays</span></div>';
  card.insertBefore(pl,card.firstChild);
  $('listen-play').parentElement.classList.add('l-hide');$('listen-playcount').parentElement.classList.add('l-hide');
  card.classList.add('w-console');const cb=document.createElement('div');cb.className='w-cbar';cb.innerHTML='<i></i><i></i><i></i><span data-i18n-skip>what-i-heard.txt</span><b id="l-cb-n" data-i18n-skip></b>';card.insertBefore(cb,card.firstChild);
  const ta=$('dictation-answer'),upd=()=>{const n=ta.value.trim()?ta.value.trim().split(/\s+/).length:0;$('l-cb-n').textContent=n+' '+T('words')};ta.addEventListener('input',upd);upd();
  $('l-big').onclick=()=>$('listen-play').click();$('l-new').onclick=()=>$('listen-new').click();
  const sp=slow=>{state.lslow=slow;$('l-fast').classList.toggle('on',!slow);$('l-slow').classList.toggle('on',slow)};
  $('l-fast').onclick=()=>sp(false);$('l-slow').onclick=()=>sp(true);$('l-native').onclick=()=>{if(!state.dictation)return toast('Load a dictation first.');window.TalvoNative.say(state.dictation);if(window.lPlayFx)lPlayFx();state.playCount=(state.playCount||0)+1;$('listen-playcount').textContent=`🎧 ${state.playCount} play${state.playCount===1?'':'s'}`};
  new MutationObserver(()=>{$('l-plays').textContent=$('listen-playcount').textContent}).observe($('listen-playcount'),{childList:true,characterData:true,subtree:true});
  let iv=0;window.lPlayFx=()=>{pl.classList.add('playing');clearInterval(iv);let t0=Date.now();iv=setInterval(()=>{const sp=window.speechSynthesis&&(speechSynthesis.speaking||speechSynthesis.pending);if((!sp&&Date.now()-t0>900)||Date.now()-t0>90000){pl.classList.remove('playing');clearInterval(iv)}},250)};
}
setTimeout(function(){skEntryReading();skEntryListening()},0);
/* --- Lectura v2 --- */
const R_CHIPS=['The main idea is','The author says that','One important detail is','I learned that','This is important because'];
let rSize=0;
function rWrap(){
  const el=$('reading-text');if(!el||el.querySelector('.rw')||el.querySelector('[data-pq]'))return;
  const t=el.textContent;if(!t.trim())return;
  rObs.disconnect();
  el.innerHTML=t.split(/(\s+)/).map(w=>/^\s+$/.test(w)||!w?esc(w):'<span class="rw">'+esc(w)+'</span>').join('');
  rObs.observe(el,{childList:true});
}
const rObs=new MutationObserver(rWrap);
function readPost(d){
  const sc=Math.round(d.puntuacion||0),res=$('reading-result');
  let v=$('r-verdict');if(!v){v=document.createElement('div');v.id='r-verdict';res.insertBefore(v,res.firstChild)}
  const cls=sc>=80?'good':sc>=60?'mid':'low';
  const msg=sc>=85?'Excellent understanding!':sc>=70?'Good comprehension — a few details to add.':sc>=50?'Nice effort — read once more and look for details.':'Good start — try reading again, slowly.';
  const bars=[['Accuracy',d.precision],['English quality',d.calidad_ingles||d.gramatica],['Vocabulary',d.vocabulario]].map(([l,x])=>'<div class="wv-bar"><span>'+T(l)+'</span><i><em style="width:'+Math.round(x||0)+'%"></em></i><b>'+Math.round(x||0)+'</b></div>').join('');
  v.innerHTML='<div class="circle '+cls+'" style="--p:'+sc+'">'+sc+'</div><div class="wv-txt"><b>'+T(msg)+'</b><small>'+esc(d.resumen||'')+'</small><div class="wv-bars">'+bars+'</div></div>';
  res.scrollIntoView({behavior:'smooth',block:'start'});
}
setTimeout(function(){
  const el=$('reading-text'),ta=$('reading-answer');if(!el||!ta)return;
  rObs.observe(el,{childList:true});
  $('r-chips').innerHTML=R_CHIPS.map(c=>'<button type="button" class="w-chip" data-rins="'+esc(c)+'">+ '+esc(c)+'</button>').join('');
  const wc=()=>{const n=ta.value.trim()?ta.value.trim().split(/\s+/).length:0;$('r-wc').textContent=n+' '+T(n===1?'word':'words')};
  ta.addEventListener('input',wc);
  ta.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();evaluateReading()}});
  document.addEventListener('click',e=>{
    const t=e.target;if(!t.closest)return;
    const w=t.closest('.rw');
    if(w){el.querySelectorAll('.rw.on').forEach(x=>x.classList.remove('on'));w.classList.add('on');speak(w.textContent.replace(/[^\p{L}'-]/gu,''),.8);return}
    const c=t.closest('[data-rins]');
    if(c){const v=c.dataset.rins+' ',s=ta.selectionStart??ta.value.length;ta.value=ta.value.slice(0,s)+v+ta.value.slice(ta.selectionEnd??s);ta.focus();ta.selectionStart=ta.selectionEnd=s+v.length;wc();return}
    if(t.closest('#r-listen')){speak(el.textContent,.92);return}
    if(t.closest('#r-slow')){speak(el.textContent,.65);return}
    if(t.closest('#r-native')){window.TalvoNative.say(el.textContent);return}
    if(t.closest('#r-minus')){rSize=Math.max(-2,rSize-1);el.style.fontSize=(17+rSize*2)+'px';return}
    if(t.closest('#r-plus')){rSize=Math.min(4,rSize+1);el.style.fontSize=(17+rSize*2)+'px';return}
    if(t.closest('#r-hide')){const h=el.classList.toggle('hid');t.closest('#r-hide').textContent=h?'👁 '+T('Show text'):'🙈 '+T('Hide text');return}
  });
  rWrap();
},0);
async function evaluateReading(){if(!state.reading)return toast('Load a reading first.');const answer=$('reading-answer').value.trim();if(!answer)return toast('Explain what you understood first.');busy('reading-submit',true,'Analyzing...');try{const d=await jsonFetch('/evaluar-lectura',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto_original:state.reading.texto,respuesta:answer})});$('r-score').textContent=Math.round(d.puntuacion||0);$('r-accuracy').textContent=Math.round(d.precision||0);$('r-language').textContent=Math.round(d.calidad_ingles||d.gramatica||0);$('r-vocab').textContent=Math.round(d.vocabulario||0);$('r-summary').textContent=d.resumen||'';$('r-good').innerHTML=(d.aciertos||[]).map(x=>`<li>${esc(x)}</li>`).join('');$('r-improve').innerHTML=(d.mejoras||[]).map(x=>`<li>${esc(x)}</li>`).join('');$('r-vocab-list').innerHTML=(d.vocabulario_sugerido||[]).map(x=>`<div class="vocab-item"><b>${esc(x.palabra||x.term||'')}</b><p>${esc(x.significado||x.meaning||'')}</p><button type="button" class="btn vocab-save-btn" style="margin-top:6px;padding:0 8px;min-height:26px;font-size:10px" data-word="${esc(x.palabra||x.term||'')}" data-meaning="${esc(x.significado||x.meaning||'')}">+ Save</button></div>`).join('');$('reading-result').style.display='block';try{readPost(d);skRecord('read',Math.round(d.puntuacion||0))}catch(e){console.error(e)}reactToScore(d.puntuacion);renderCoachInsight('reading-coach',[{label:'Accuracy',value:d.precision},{label:'English quality',value:d.calidad_ingles||d.gramatica},{label:'Vocabulary',value:d.vocabulario}],[{label:'🔄 Try a new reading',fn:regenerateReading},{label:'🎯 Personalized practice',fn:(lb)=>lpFocusFromTool('reading',lb)},{label:'📍 Open Learning Path',fn:()=>goToLearningPathFor()}])}catch(e){toast(e.message)}finally{busy('reading-submit',false,'Analyze comprehension')}}
let listeningLibraryItems=[];
let listeningLibraryFilter='all';
async function loadListeningLibrary(){$('listening-library-view').style.display='block';$('listening-practice-view').style.display='none';$('listening-library-list').innerHTML='<div class="empty">'+pqLoader()+'</div>';try{const d=await jsonFetch('/api/listening/library');listeningLibraryItems=d.items||[];renderListeningLibraryList()}catch(e){$('listening-library-list').innerHTML='<div class="empty">Could not load the library.</div>';toast(e.message)}}
function renderListeningLibraryList(){const items=listeningLibraryItems.filter(x=>listeningLibraryFilter==='all'||x.level===listeningLibraryFilter);$('listening-library-list').innerHTML=items.map(x=>`<button type="button" class="lib-card ${esc(x.level)}" data-listening-id="${x.id}"><div class="lib-cov"><span class="rl-lv ${esc(x.level)}" data-i18n-skip>${esc(x.level)}</span><span class="lib-ic">🎧</span></div><b class="rl-t">${esc(x.title)}</b><span class="lib-go">Start →</span></button>`).join('')||'<div class="empty">No audios for this level.</div>';$$('#listening-library-list [data-listening-id]').forEach(b=>b.addEventListener('click',()=>openListeningEntry(b.dataset.listeningId)))}
function setListeningFilter(level){listeningLibraryFilter=level;$$('#listening-filter-bar .mode').forEach(b=>b.classList.toggle('active',b.dataset.level===level));renderListeningLibraryList()}
async function openListeningEntry(entryId){state.listeningEntryId=entryId;$('listening-library-view').style.display='none';$('listening-practice-view').style.display='block';state.playCount=0;$('listen-playcount').textContent='🎧 0 plays';$('dictation-hint').textContent='Press play, then write what you heard.';$('dictation-answer').value='';$('dictation-result').style.display='none';try{const d=await jsonFetch('/api/listening/library/'+entryId);state.dictation=d.texto||''}catch(e){toast(e.message)}}
function regenerateListening(){if(state.listeningEntryId)openListeningEntry(state.listeningEntryId);else loadDictation()}
async function loadDictation(){try{const d=await jsonFetch('/nuevo-dictado');state.dictation=d.texto||'';state.playCount=0;$('listen-playcount').textContent='🎧 0 plays';$('dictation-hint').textContent='Press play, then write what you heard.';$('dictation-answer').value='';$('dictation-result').style.display='none'}catch(e){toast(e.message)}}
function playDictation(){if(!state.dictation)return toast('Load a dictation first.');speak(state.dictation,state.lslow?.65:.9);if(window.lPlayFx)lPlayFx();state.playCount=(state.playCount||0)+1;$('listen-playcount').textContent=`🎧 ${state.playCount} play${state.playCount===1?'':'s'}`}
async function evaluateDictation(){const answer=$('dictation-answer').value.trim();if(!answer)return toast('Write what you heard first.');busy('dictation-submit',true,'Evaluating...');try{const d=await jsonFetch('/evaluar-dictado',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto_original:state.dictation,respuesta:answer})});$('d-score').textContent=Math.round(d.puntuacion||0);$('d-words').textContent=d.palabras_correctas??0;$('d-errors').textContent=d.diferencias??0;$('d-level').textContent=d.nivel||'—';$('d-feedback').textContent=d.feedback||'';$('dictation-result').style.display='block';try{skRecord('listen',Math.round(d.puntuacion||0))}catch(e){}reactToScore(d.puntuacion);renderCoachInsight('dictation-coach',[{label:'Listening accuracy',value:d.puntuacion}],[{label:'🔄 Try a new audio',fn:regenerateListening},{label:'🎯 Personalized practice',fn:(lb)=>lpFocusFromTool('dictado',lb)},{label:'📍 Open Learning Path',fn:()=>goToLearningPathFor()}])}catch(e){toast(e.message)}finally{busy('dictation-submit',false,'Evaluate listening')}}
/* --- Talvo · llamada v2: micrófono abierto, turnos en streaming y voz frase por frase --- */
const CALL={mic:null,live:false,muted:false,t0:0,timer:0,abort:null,queue:[],playing:false,audio:null,unlocked:false,skip:false,aiEl:null};
const CALL_SILENT='data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';
const CALL_HELLO="Hi! It's Palanqueta. I'm so happy you called. What would you like to talk about today?";
const EXAM_HELLO="Hi! I'm Palanqueta, and today I'll check your English level. I'll ask you eight questions, from easy to harder. Just answer naturally, there are no wrong answers. Ready? Let's start. What's your name, and where are you from?";
const TEACHER_HELLO='¡Hola! Soy la maestra Palanqueta. Hoy vamos a aprender inglés juntas, paso a paso, y yo te explico todo en español. Para empezar, dime: ¿para qué quieres el inglés, trabajo, viajes o platicar con gente? Puedes contestarme en español.';
function callMode(){try{return localStorage.getItem('talvo_callmode')||(localStorage.getItem('talvo_maestro')==='1'?'teacher':'talk')}catch(e){return 'talk'}}
async function teacherHello(){try{const d=await jsonFetch('/api/maestro/ficha');if(d.nombre&&d.clases>0){return `¡Hola, ${d.nombre}! Qué gusto escucharte otra vez. ¿Cómo estás hoy? En inglés se dice "How are you doing today?". Cuéntame, ${d.ultimo_tema?'la última vez hablamos de '+d.ultimo_tema+', ¿cómo te fue con eso?':'¿cómo te fue desde la última clase?'}`}}catch(e){}return '¡Hola! Qué gusto conocerte, soy tu maestra Palanqueta. Aquí vamos a aprender inglés juntas, poquito a poquito, y yo te explico todo en español. Antes de empezar quiero conocerte. ¿Cómo te llamas?'}
function teacherOn(){return callMode()==='teacher'}
function examOn(){return callMode()==='exam'}
function callModeSet(m){if(m===callMode())return;try{localStorage.setItem('talvo_callmode',m)}catch(e){}state.callMessages=[];CALL.examN=0;const w=$('call-messages');if(w)w.innerHTML='';teacherRender()}
async function teacherMap(){const box=$('teacher-map');if(!box)return;if(!teacherOn()){box.style.display='none';return}
  try{const d=await jsonFetch('/api/maestro/temario');const pct=Math.round(((d.actual-1)/d.total)*100);
  box.style.display='';box.innerHTML=`<div class="tm-head"><div><div class="eyebrow">Tu temario</div><h3>${d.nombre?esc(d.nombre)+', vas':'Vas'} en la unidad ${d.actual} de ${d.total}</h3><small>${d.clases} clase${d.clases===1?'':'s'} con tu maestra</small></div><div class="tm-ring" style="--p:${pct}"><b>${pct}%</b></div></div>
  <ol class="tm-list">${d.unidades.map(u=>`<li class="${u.estado}"><span class="tm-dot">${u.estado==='hecha'?'✓':u.n}</span><div><b>${esc(u.tema)}</b>${u.estado==='actual'?`<small>En la calle: ${esc(u.real)}</small>`:''}</div>${u.estado==='actual'&&u.ruta?`<button type="button" class="btn tm-go" data-u="${esc(u.ruta.unit)}" data-l="${esc(u.ruta.lesson)}">Practicar en las rutas</button>`:''}</li>`).join('')}</ol>
  ${d.dominadas.length?`<h4>Frases que ya dominas</h4><div class="tm-chips">${d.dominadas.map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}
  ${d.rutas&&d.rutas.length?`<h4>Hecho en tus rutas</h4><div class="tm-chips">${d.rutas.map(x=>`<span>${esc(x.leccion)} · ${x.puntos}</span>`).join('')}</div>`:''}
  ${d.repasar.length?`<h4>Para repasar</h4><div class="tm-chips warn">${d.repasar.map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}`;box.querySelectorAll('.tm-go').forEach(b=>b.addEventListener('click',()=>{if(window.lpStart)window.lpStart(b.dataset.u,b.dataset.l,'','open')}))}catch(e){box.style.display='none'}}
function teacherRender(){const on=teacherOn(),ex=examOn();const ui=callEl('call-ui');if(ui){ui.dataset.teacher=on?'1':'0';ui.dataset.exam=ex?'1':'0'}$$('#call-mode-bar .mode').forEach(b=>b.classList.toggle('active',b.dataset.m===callMode()));const h=$('call-title');if(h)h.textContent=ex?'Examen de nivel por llamada.':on?'Aprende con tu maestra bilingüe.':'Practice like a real phone call.';const d=document.querySelector('#sec-llamada .page-desc');if(d){if(!d.dataset.en)d.dataset.en=d.textContent;d.textContent=ex?'Palanqueta te hace 8 preguntas por voz, cada vez más difíciles, y al final te dice tu nivel real (A1 a C1) y qué estudiar. Respira, habla con calma y no te preocupes por equivocarte.':on?'Tu maestra Palanqueta te explica en español, te enseña frases reales en inglés y te hace repetirlas, como un maestro particular. Toca Start call y habla.':d.dataset.en};teacherMap()}
async function teacherSpeak(text){try{const r=await authFetch('/api/sintetizar-audio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto:text,bilingual:true})});if(!r.ok)throw new Error('tts');const url=URL.createObjectURL(await r.blob());const a=new Audio(url);a.onended=()=>URL.revokeObjectURL(url);await a.play()}catch(e){try{speak(String(text).replace(/"/g,''))}catch(_){}}}
function callEl(id){return document.getElementById(id)}
function callSetState(s){const ui=callEl('call-ui');if(ui)ui.dataset.state=s}
function callStatus(t){const n=callEl('call-status');if(n)n.textContent=t}
function callCaption(who,text){const n=callEl('call-caption');if(!n)return;n.className='call-caption '+who;const t=teacherOn();n.textContent=text?(who==='user'?(t?'Tú: ':'You: '):(t?'Maestra: ':'Palanqueta: '))+text:''}
function addCallMessage(text,who){const wrap=$('call-messages');const div=document.createElement('div');div.className='msg '+(who==='user'?'user':'ai');div.textContent=text;wrap.appendChild(div);wrap.scrollTop=wrap.scrollHeight;return div}
function callHelpText(){return CALL.live?(vad.on?'Listening… speak and pause when you are done.':'Hold the button to talk'):'Tap Start call and just talk.'}
function callIdle(){if(state.callBusy||CALL.playing)return;callSetState(CALL.muted?'muted':(CALL.live&&vad.on?'listening':'idle'));callStatus(CALL.muted?'Muted':callHelpText())}
function callUnlockAudio(){if(!CALL.audio){CALL.audio=new Audio();CALL.audio.preload='auto';CALL.audio.setAttribute('playsinline','')}if(CALL.unlocked)return;try{CALL.audio.src=CALL_SILENT;const p=CALL.audio.play();if(p&&p.then)p.then(()=>{CALL.unlocked=true}).catch(()=>{})}catch(e){}}
async function callGetMic(){if(CALL.mic&&CALL.mic.getTracks().some(t=>t.readyState==='live'))return CALL.mic;CALL.mic=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});CALL.mic.getAudioTracks().forEach(t=>{t.enabled=!CALL.muted});return CALL.mic}
function callReleaseMic(){try{CALL.mic&&CALL.mic.getTracks().forEach(t=>t.stop())}catch(e){}CALL.mic=null}
function callFmt(ms){const s=Math.floor(ms/1000);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}

/* --- reproducción: cola de frases; la 1.ª suena mientras llegan las demás --- */
function callB64Url(b64){const bin=atob(b64),u8=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u8[i]=bin.charCodeAt(i);return URL.createObjectURL(new Blob([u8],{type:'audio/mpeg'}))}
function callPlayUrl(url){return new Promise(res=>{const a=CALL.audio;let done=false;const fin=()=>{if(done)return;done=true;CALL.resolveNow=null;res()};CALL.resolveNow=fin;a.onended=fin;a.onerror=fin;a.src=url;const p=a.play();if(p&&p.catch)p.catch(fin)})}
function callSpeakFallback(text){return new Promise(res=>{try{if(!('speechSynthesis' in window))return res();speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang='en-US';u.rate=settingsSpeechRate==='slow'?0.75:1;u.onend=u.onerror=()=>res();CALL.resolveNow=res;speechSynthesis.speak(u)}catch(e){res()}})}
function callEnqueue(text,b64){CALL.queue.push({text,b64});if(!CALL.playing)callPump()}
async function callPump(){
  CALL.playing=true;callUnlockAudio();callSetState('speaking');startMascotTalking();
  try{
    while(CALL.queue.length&&!CALL.skip){
      const it=CALL.queue.shift();callStatus('Palanqueta is speaking…');
      if(it.b64){let url=null;try{url=callB64Url(it.b64);await callPlayUrl(url)}catch(e){await callSpeakFallback(it.text)}finally{if(url)URL.revokeObjectURL(url)}}
      else await callSpeakFallback(it.text)
    }
  }finally{CALL.playing=false;CALL.skip=false;stopMascotTalking();if(!state.callBusy)callIdle()}
}
function callSkip(){
  CALL.queue.length=0;CALL.skip=true;
  try{CALL.abort&&CALL.abort.abort()}catch(e){}
  try{CALL.audio&&CALL.audio.pause()}catch(e){}
  try{speechSynthesis.cancel()}catch(e){}
  if(CALL.resolveNow)CALL.resolveNow();
  if(!CALL.playing)CALL.skip=false
}
async function callWaitPlayback(){while(CALL.playing||CALL.queue.length)await new Promise(r=>setTimeout(r,70))}

/* --- un turno: audio -> /api/llamada/turno (NDJSON en streaming) --- */
async function callStartTalk(){
  if(state.callRecorder&&state.callRecorder.state==='recording')return;
  if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)return toast('Tu navegador no soporta grabación de audio.');
  if(CALL.muted)return toast('Unmute first to talk.');
  callUnlockAudio();
  if(state.callBusy){if(CALL.playing||CALL.abort){callSkip();await new Promise(r=>setTimeout(r,150))}if(state.callBusy)return}
  try{
    const stream=await callGetMic();let mime='audio/webm';
    if(MediaRecorder.isTypeSupported&&!MediaRecorder.isTypeSupported(mime)){mime=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(x=>MediaRecorder.isTypeSupported(x))||''}
    state.callChunks=[];state.callRecorder=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);
    state.callRecorder.ondataavailable=e=>{if(e.data.size)state.callChunks.push(e.data)};
    state.callRecorder.onstop=callSendTurn;state.callRecorder.start();CALL.tTalk=performance.now();
    $('call-talk-btn').classList.add('recording');callSetState('hearing');callStatus('Listening… let go when you are done.')
  }catch(e){toast('Error de micrófono: '+e.message);callIdle()}
}
function callSendTyped(){const inp=$('call-type-input');if(!inp)return;const t=inp.value.trim();if(!t)return;if(state.callBusy){if(CALL.playing||CALL.abort){callSkip()}}inp.value='';callSendTurn(null,t)}
function callPronChips(ev){(CALL.pronAll=CALL.pronAll||[]).push(ev);const el=CALL.userEl;if(!el||!ev.words||!ev.words.length)return;
  const c=document.createElement('div');c.className='cp-pron';
  c.innerHTML=`<div class="cp-t">Tu pronunciación de "${esc(ev.target)}": <b>${ev.score}</b>/100</div><div class="cp-w">${ev.words.map(w=>`<span class="${w.a>=80?'g':w.a>=60?'m':'b'}" data-i18n-skip>${esc(w.w)}<i>${w.a}</i></span>`).join('')}</div>`;
  el.appendChild(c);const wrap=$('call-messages');if(wrap)wrap.scrollTop=wrap.scrollHeight}
/* palabras que Azure midió flojas durante la llamada, para oírlas bien y practicarlas */
function callRenderPronSummary(){
  const box=$('call-summary-pron');if(!box)return;
  const best={};(CALL.pronAll||[]).forEach(ev=>(ev.words||[]).forEach(w=>{const k=String(w.w||'').toLowerCase();if(!/[a-z]/.test(k))return;if(!best[k]||w.a<best[k].a)best[k]={w:w.w,a:w.a}}));
  const weak=Object.values(best).filter(x=>x.a<75).sort((a,b)=>a.a-b.a).slice(0,8);
  const att=(CALL.pronAll||[]).length;
  if(!att){box.style.display='none';CALL.pronAll=[];return}
  const avg=Math.round(CALL.pronAll.reduce((n,e)=>n+(e.score||0),0)/att);
  box.style.display='';
  box.innerHTML=`<h3>Tu pronunciación medida</h3><div class="notice">${att} frase${att===1?'':'s'} medida${att===1?'':'s'} con Azure · promedio <b>${avg}</b>/100.${weak.length?' Las palabras más flojas quedaron guardadas para tu próxima clase.':' ¡Ninguna palabra floja esta vez!'}</div>${weak.length?`<div class="cp-w cp-sum">${weak.map(x=>`<button type="button" class="${x.a>=60?'m':'b'}" data-w="${esc(x.w)}" data-i18n-skip>🔊 ${esc(x.w)}<i>${x.a}</i></button>`).join('')}</div><small style="color:var(--muted)">Toca una palabra para escucharla bien dicha.</small>`:''}`;
  box.querySelectorAll('button[data-w]').forEach(b=>b.addEventListener('click',()=>speak(b.dataset.w,.8)));
  CALL.pronAll=[]
}

/* Espejo de fluidez: velocidad al hablar inglés y muletillas, calculado en tu navegador (sin costo) */
const MIRROR_ES=new Set('el la los las un una unos unas que de del en es y o no si yo me mi tu su se lo le les como por para con pero muy está estoy soy eres somos son hay más mas ya sí bien hola gracias porque cuando donde qué cómo quién dos tres hoy ayer también tambien aquí aqui eso esto esta este'.split(' '));
const MIRROR_FILL=[['you know',/\byou know\b/g],['I mean',/\bi mean\b/g],['like',/\blike\b/g],['basically',/\bbasically\b/g],['actually',/\bactually\b/g],['literally',/\bliterally\b/g],['um / uh',/\b(?:um+|uh+|erm|ehh?|hmm+)\b/g]];
function callMirrorAdd(text){
  try{
    const m=CALL.mirror=CALL.mirror||{words:0,secs:0,turns:0,fill:{}};
    const low=String(text||'').toLowerCase();
    const toks=low.match(/[a-záéíóúñ']+/g)||[];
    const en=toks.filter(w=>/^[a-z']+$/.test(w)&&!MIRROR_ES.has(w));
    if(en.length<toks.length*0.6||en.length<3){CALL.talkSecs=0;return}
    if(!CALL.talkSecs)return;
    m.words+=en.length;m.turns++;m.secs+=Math.max(1,CALL.talkSecs-1.2);
    MIRROR_FILL.forEach(([k,re])=>{const n=(low.match(re)||[]).length;if(n)m.fill[k]=(m.fill[k]||0)+n});
    CALL.talkSecs=0;
  }catch(e){}
}
function callRenderMirror(){
  const box=$('call-summary-mirror');if(!box)return;const m=CALL.mirror;CALL.mirror=null;
  if(!m||m.turns<2||m.secs<6){box.style.display='none';return}
  const wpm=Math.round(m.words/(m.secs/60));
  const lvl=wpm<80?'Vas despacio y seguro: lo siguiente es soltarte un poco más.':wpm<120?'Buen ritmo para conversar. Un nativo promedio habla cerca de 130–150.':'¡Ritmo natural, como el de un nativo!';
  const fills=Object.entries(m.fill).sort((a,b)=>b[1]-a[1]).slice(0,4);
  box.style.display='';
  box.innerHTML=`<h3>Tu espejo de fluidez</h3><div class="notice">Hablaste inglés a unas <b>${wpm}</b> palabras por minuto (${m.words} palabras en ${m.turns} turnos). ${lvl}${fills.length?`<br>Muletillas que más usaste: ${fills.map(([k,n])=>`<b>${esc(k)}</b> ×${n}`).join(', ')}. Son normales; solo cuida que no llenen todo.`:''}<br><small>Estimación a partir de tu transcripción y de cuánto tiempo grabaste.</small></div>`;
}
function callStopTalk(){
  if(CALL.tTalk){CALL.talkSecs=(performance.now()-CALL.tTalk)/1000;CALL.tTalk=0}
  $('call-talk-btn').classList.remove('recording');
  if(state.callRecorder&&state.callRecorder.state!=='inactive')state.callRecorder.stop()
}
async function callSendTurn(ev,typed){
  const isTyped=typeof typed==='string'&&typed.trim().length>0;
  const blob=isTyped?null:new Blob(state.callChunks,{type:state.callChunks[0]?.type||'audio/webm'});
  if(!isTyped&&blob.size<2500){callIdle();return}
  state.callBusy=true;callSetState('thinking');callStatus(isTyped?'Thinking…':'Transcribing…');CALL.aiEl=null;
  const fd=new FormData();if(isTyped)fd.append('texto',typed.trim());else fd.append('audio',blob,'call.webm');fd.append('history',JSON.stringify(state.callMessages.slice(-12)));if(teacherOn()){fd.append('maestro','1');fd.append('clase_n',String(state.callMessages.filter(m=>m.role==='user').length+1))}if(examOn()){fd.append('examen','1');fd.append('turno_n',String((CALL.examN||0)+1))}
  CALL.abort=new AbortController();
  try{
    const r=await authFetch('/api/llamada/turno',{method:'POST',body:fd,signal:CALL.abort.signal});
    if((r.status===404||r.status===405)&&blob){await callTurnLegacy(blob)}
    else{
      if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.error||('Request failed ('+r.status+')'))}
      await callReadStream(r)
    }
    if(examOn()&&CALL.aiEl&&CALL.aiEl.textContent)CALL.examN=(CALL.examN||0)+1;
    await callWaitPlayback();
    if(examOn()&&(CALL.examN||0)>=8){setTimeout(()=>examFinish(),400)}
  }catch(e){if(e.name!=='AbortError')toast(e.message)}
  finally{
    if(CALL.aiEl&&CALL.aiEl.textContent&&!CALL.aiPushed){state.callMessages.push({role:'assistant',content:CALL.aiEl.textContent})}
    CALL.aiPushed=false;CALL.abort=null;state.callBusy=false;
    if(!CALL.live)callReleaseMic();
    callIdle()
  }
}
async function callReadStream(r){
  CALL.aiPushed=false;
  const handle=ev=>{
    if(ev.type==='user'){callMirrorAdd(ev.text);CALL.userEl=addCallMessage(ev.text,'user');state.callMessages.push({role:'user',content:ev.text});callCaption('user',ev.text);callStatus('Palanqueta is thinking…')}
    else if(ev.type==='ai'){if(!CALL.aiEl)CALL.aiEl=addCallMessage('','ai');CALL.aiEl.textContent=(CALL.aiEl.textContent+' '+ev.text).trim();callCaption('ai',CALL.aiEl.textContent);callEnqueue(ev.text,ev.audio)}
    else if(ev.type==='pron'){callPronChips(ev)}
    else if(ev.type==='empty'){callStatus('I did not catch that, try again.')}
    else if(ev.type==='error'){throw new Error(ev.message)}
    else if(ev.type==='done'){if(CALL.aiEl){state.callMessages.push({role:'assistant',content:ev.reply||CALL.aiEl.textContent});CALL.aiPushed=true}}
  };
  const feed=text=>{for(const line of text.split('\n')){const t=line.trim();if(!t)continue;let ev;try{ev=JSON.parse(t)}catch(e){continue}handle(ev)}};
  if(!r.body||!r.body.getReader){feed(await r.text());return}
  const reader=r.body.getReader(),dec=new TextDecoder();let buf='';
  for(;;){
    const {value,done}=await reader.read();if(done)break;
    buf+=dec.decode(value,{stream:true});const cut=buf.lastIndexOf('\n');
    if(cut>=0){feed(buf.slice(0,cut));buf=buf.slice(cut+1)}
  }
  if(buf.trim())feed(buf)
}
/* respaldo: si el servidor todavía no tiene la ruta nueva, se usa el camino de 3 pasos de siempre */
async function callTurnLegacy(blob){
  const fd=new FormData();fd.append('audio',blob,'call.webm');
  const t=await jsonFetch('/api/transcribir-audio',{method:'POST',body:fd});const said=(t.texto||'').trim();
  if(!said){callStatus('I did not catch that, try again.');return}
  addCallMessage(said,'user');state.callMessages.push({role:'user',content:said});callCaption('user',said);callStatus('Palanqueta is thinking…');
  const d=await jsonFetch('/api/tutor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mensaje:said,history:state.callMessages.slice(-14),modo:'llamada'})});
  const reply=d.respuesta||'';CALL.aiEl=addCallMessage(reply,'ai');state.callMessages.push({role:'assistant',content:reply});CALL.aiPushed=true;callCaption('ai',reply);
  let b64=null;try{const r=await authFetch('/api/sintetizar-audio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto:reply,voz:'en-US-AvaMultilingualNeural'})});if(r.ok){const buf=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<buf.length;i+=8192)s+=String.fromCharCode.apply(null,buf.subarray(i,i+8192));b64=btoa(s)}}catch(e){}
  callEnqueue(reply,b64)
}

/* --- ciclo de la llamada --- */
function callRenderLive(on){const ui=callEl('call-ui');if(ui)ui.dataset.live=on?'1':'0'}
async function callStart(){
  if(CALL.live)return;
  if(!navigator.mediaDevices?.getUserMedia)return toast('Your browser does not support microphone recording.');
  callUnlockAudio();
  try{await callGetMic()}catch(e){return toast('Microphone error: '+e.message)}
  if(!state.callMessages.length)CALL.examN=0;CALL.live=true;CALL.muted=false;CALL.t0=Date.now();callRenderLive(true);callEl('call-mute').textContent='🎙️ Mute';
  clearInterval(CALL.timer);CALL.timer=setInterval(()=>{const t=callEl('call-timer');if(t)t.textContent=callFmt(Date.now()-CALL.t0)},500);
  await vadStart();
  if(!state.callMessages.length){
    state.callBusy=true;callSetState('speaking');callStatus('Palanqueta is speaking…');
    try{
      if(teacherOn())CALL.hello=await teacherHello();
      const r=await authFetch('/api/sintetizar-audio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(teacherOn()?{texto:CALL.hello||TEACHER_HELLO,bilingual:true}:{texto:examOn()?EXAM_HELLO:CALL_HELLO,voz:'en-US-AvaMultilingualNeural'})});
      let b64=null;if(r.ok){const buf=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<buf.length;i+=8192)s+=String.fromCharCode.apply(null,buf.subarray(i,i+8192));b64=btoa(s)}
      {const hi=teacherOn()?(CALL.hello||TEACHER_HELLO):examOn()?EXAM_HELLO:CALL_HELLO;if(examOn())CALL.examN=1;addCallMessage(hi,'ai');state.callMessages.push({role:'assistant',content:hi});callCaption('ai',hi);callEnqueue(hi,b64)}await callWaitPlayback()
    }catch(e){}finally{state.callBusy=false;callIdle()}
  }else callIdle()
}
function callToggleMute(){
  CALL.muted=!CALL.muted;if(CALL.mic)CALL.mic.getAudioTracks().forEach(t=>{t.enabled=!CALL.muted});
  callEl('call-mute').textContent=CALL.muted?'🔇 Unmute':'🎙️ Mute';callIdle()
}
function callLeave(){if(CALL.live||vad.on||CALL.playing||CALL.mic||state.callBusy)callTeardown()}
function callTeardown(){
  vadStop();callSkip();
  try{if(state.callRecorder&&state.callRecorder.state!=='inactive'){state.callRecorder.onstop=null;state.callRecorder.stop()}}catch(e){}
  $('call-talk-btn')&&$('call-talk-btn').classList.remove('recording');
  callReleaseMic();clearInterval(CALL.timer);CALL.live=false;CALL.muted=false;state.callBusy=false;
  callRenderLive(false);callSetState('idle');callStatus('Tap Start call and just talk.');callCaption('','');
}
async function examFinish(){
  if(!examOn()||CALL.examBusy)return;CALL.examBusy=true;
  const hist=state.callMessages.slice();callTeardown();callStatus('Calificando tu examen…');callSetState('thinking');
  try{
    const d=await jsonFetch('/api/examen/fin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({history:hist})});
    const box=$('exam-result');if(!box)return;
    box.innerHTML=`<div class="ex-badge">${esc(d.cefr)}</div><div class="ex-lvl">${esc(d.level_label||'')}</div><div class="ex-score">${Math.round(d.puntuacion||0)}<small>/100</small></div><p>${esc(d.resumen||'')}</p><h3>Lo que haces bien</h3><ul class="list">${(d.fortalezas||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h3>A mejorar</h3><ul class="list">${(d.a_mejorar||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h3>Tu plan</h3><ol class="list">${(d.plan||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ol><div class="notice">Practica esta frase: <b>${esc(d.frase_para_practicar||'')}</b></div><div class="ex-actions"><button type="button" class="btn primary" id="exam-apply">Usar este nivel en mi app</button><button type="button" class="btn" id="exam-again">Cerrar</button></div>`;
    box.style.display='block';box.scrollIntoView({behavior:'smooth',block:'start'});
    $('exam-apply').onclick=async()=>{try{await jsonFetch('/api/examen/fin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({history:hist,aplicar:true})});toast('Nivel actualizado: '+(d.level_label||d.cefr));$('exam-apply').disabled=true}catch(e){toast(e.message)}};
    $('exam-again').onclick=()=>{box.style.display='none'};
    state.callMessages=[];CALL.examN=0;$('call-messages').innerHTML=''
  }catch(e){toast(e.message)}finally{CALL.examBusy=false;callSetState('idle');callStatus('Toca Iniciar llamada y habla.')}
}
async function endCall(){
  if(examOn()&&(CALL.examN||0)>=3){return examFinish()}
  const dur=CALL.live?callFmt(Date.now()-CALL.t0):'';
  callTeardown();
  if(!state.callMessages||!state.callMessages.length)return toast('Todavía no has hablado con Palanqueta.');
  callStatus('Generando resumen...');callSetState('thinking');
  try{
    const d=await jsonFetch('/api/resumen-llamada',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({history:state.callMessages})});
    $('call-score-general').textContent=Math.round(d.puntuacion_general||0);$('call-score-fluency').textContent=Math.round(d.fluidez||0);$('call-score-grammar').textContent=Math.round(d.gramatica||0);$('call-score-vocab').textContent=Math.round(d.vocabulario||0);$('call-score-pron').textContent=Math.round(d.pronunciacion_estimada||0);
    $('call-summary-general').textContent=(dur&&dur!=='00:00'?'['+dur+'] ':'')+(d.resumen_general||'');
    $('call-summary-strengths').innerHTML=(d.fortalezas||[]).map(x=>`<li>${esc(x)}</li>`).join('');
    $('call-summary-errors').innerHTML=(d.errores_comunes||[]).map(x=>`<li>${esc(x)}</li>`).join('');
    $('call-summary-vocab').innerHTML=(d.vocabulario_recomendado||[]).map(v=>`<div class="vocab-item"><b>${esc(v.palabra||'')}</b><p>${esc(v.significado||'')}</p></div>`).join('');
    callRenderPronSummary();callRenderMirror();
    $('call-summary-next').textContent=d.siguiente_paso||'';$('call-summary').style.display='block';
    state.callMessages=[];$('call-messages').innerHTML='<div class="msg ai">Hi! I\'m Palanqueta. Tap Start call and let\'s talk. I\'ll answer out loud.</div>';
    const t=callEl('call-timer');if(t)t.textContent='00:00';
    $('call-summary').scrollIntoView({behavior:'smooth',block:'start'})
  }catch(e){toast(e.message)}finally{callCaption('','');callIdle()}
}

async function homeReto(){
  const box=$('home-reto');if(!box)return;
  const rail=$('home-rail');if(rail&&!$('home-more')){const b=document.createElement('button');b.type='button';b.id='home-more';b.className='btn home-more';b.textContent='Show all tools';b.onclick=()=>{const c=rail.classList.toggle('collapsed');b.textContent=c?'Show all tools':'Show fewer tools'};rail.insertAdjacentElement('afterend',b)}
  let reto=null;try{const d=await jsonFetch('/api/rutas');reto=d.reto}catch(e){}
  const day=reto?Math.min(21,reto.dia_hoy||1):0,pc=reto?Math.round(reto.completadas/21*100):0;
  box.innerHTML='<button type="button" class="home-reto" id="home-reto-b"><span class="hr-pq"><img src="palanqueta-asoma.webp" alt="" draggable="false"></span><span class="hr-t"><small>🔥 21-day challenge</small><b>'+(reto?'Day '+day+' of 21 · keep your streak':'Speak real English in 3 weeks')+'</b><em>'+(reto?'Your plan adapts to your level and mistakes.':'A fixed plan built around your goal. It adapts to you.')+'</em>'+(reto?'<i class="hr-bar"><u style="width:'+pc+'%"></u></i>':'')+'</span><span class="hr-go">'+(reto?'Continue':'Start')+' →</span></button>';
  $('home-reto-b').onclick=()=>{if(window.TalvoStudio&&TalvoStudio.goTab)TalvoStudio.goTab('reto');else section('rutas')};
}
async function loadDashboard(){(window.loadNextStep&&window.loadNextStep());try{homeReto()}catch(e){}try{const email=(state.user&&state.user.email)||'';const name=state.username||email.split('@')[0]||'there';const hour=new Date().getHours();const greet=hour<12?'Good morning':hour<19?'Good afternoon':'Good evening';$('home-greeting').textContent=`${greet}, ${esc(name)}! 👋`;const _pa=jsonFetch('/api/achievements').catch(()=>null);const d=await jsonFetch('/api/dashboard');$('home-streak').textContent=`🔥 ${d.streak_days} day streak`;$('home-xp').textContent=`⭐ ${d.xp} XP · Level ${d.level}`;$('home-goal-pct').textContent=d.daily_goal_pct+'%';$('home-goal-fill').style.width=d.daily_goal_pct+'%';$('home-week').innerHTML=(d.week||[]).map(w=>`<div class="day-chip${w.active?' active':''}${w.is_today?' today':''}"><div class="dot">${w.active?'🔥':''}</div><small>${esc(w.weekday)}</small></div>`).join('');const labels={speaking:'🗣️ Speaking',listening:'🎧 Listening',reading:'📖 Reading',writing:'✍️ Writing'};$('home-skills').innerHTML=Object.entries(d.skills||{}).map(([k,v])=>`<div class="report" style="--v:${v}%"><b>${v}%</b><small>${labels[k]||k}</small></div>`).join('');try{const a=await _pa;if(!a)throw 0;$('home-achievements').innerHTML=a.achievements.slice(0,4).map(x=>`<div class="report ach-card${x.unlocked?' unlocked':''}"><div class="ach-icon">${x.icon}</div><small style="display:block;margin-top:4px">${esc(x.title)}</small></div>`).join('')}catch(e){}
try{const vd=await jsonFetch('/api/vocabulario/diario');const w=(vd.palabras||[])[0];$('home-vocab-word').innerHTML=w?`<b style="font-size:16px">${esc(w.palabra)}</b><p style="margin:4px 0;color:var(--muted);font-size:12px">${esc(w.significado||'')}</p>${w.ejemplo?`<p style="font-style:italic;font-size:12px">"${esc(w.ejemplo)}"</p>`:''}`:'<div class="empty">No words yet.</div>'}catch(e){$('home-vocab-word').innerHTML='<div class="empty">Could not load today\'s word.</div>'}
try{const vl=await jsonFetch('/api/vocabulario');const pct=vl.total?Math.round(vl.aprendidas/vl.total*100):0;$('home-vocab-stats').innerHTML=`<small style="color:var(--muted)">Your vocabulary</small><div style="font-weight:700;font-size:15px;margin:2px 0">${vl.aprendidas} / ${vl.total} learned</div><div class="bar" style="margin-top:6px"><div class="fill" style="width:${pct}%"></div></div><button type="button" class="btn" id="home-vocab-review-btn" style="margin-top:8px">Review words →</button>`;$('home-vocab-review-btn')?.addEventListener('click',()=>{section('vocabulario');closeSidebar()})}catch(e){}}catch(e){console.error('[DASHBOARD]',e)}}
async function loadAchievements(){try{const d=await jsonFetch('/api/achievements');$('ach-count').textContent=`🏆 ${d.unlocked_count} / ${d.achievements.length} unlocked`;$('ach-list').innerHTML=d.achievements.map(a=>`<div class="report ach-card${a.unlocked?' unlocked':''}"><div class="ach-icon">${a.icon}</div><b style="display:block;margin-top:6px;font-size:13px">${esc(a.title)}</b>${a.unlocked?'<small style="color:var(--success)">✓ Completed</small>':`<div class="bar"><div class="fill" style="width:${a.progress}%"></div></div><small>${a.progress}%</small>`}</div>`).join('')}catch(e){toast(e.message)}}
/* ---------- Vocabulario ---------- */
const VOC={all:[],daily:[],filter:'all',q:'',shown:12};
const vocNorm=w=>String(w||'').trim().toLowerCase();
function vocUnique(rows){
  const m=new Map();
  (rows||[]).forEach(w=>{
    const k=vocNorm(w.palabra);if(!k)return;
    const p=m.get(k);
    if(!p){m.set(k,{...w,dupIds:[]});return}
    if(w.aprendida)p.aprendida=true;
    if(!p.ejemplo&&w.ejemplo)p.ejemplo=w.ejemplo;
    if(!p.significado&&w.significado)p.significado=w.significado;
    p.dupIds.push(w.id);
  });
  return [...m.values()];
}
function vocIds(w){
  const hit=VOC.all.find(x=>vocNorm(x.palabra)===vocNorm(w.palabra));
  return [...new Set([w.id].concat(hit?[hit.id].concat(hit.dupIds||[]):[]).filter(x=>x!==undefined&&x!==null).map(String))];
}
function vocMark(sentence,word){
  const s=esc(sentence);
  try{const re=new RegExp('\\b('+String(word||'').replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'[a-z]*)','i');return s.replace(re,'<mark>$1</mark>')}catch(e){return s}
}
function vdCard(w,i){
  const ids=vocIds(w).join(',');
  return `<article class="vd-card${w.aprendida?' done':''}"><span class="vd-n">${String(i+1).padStart(2,'0')}</span>`
   +`<div class="vd-top"><button type="button" class="hear" data-hear="${esc(w.palabra)}" aria-label="Hear it">🔊</button><h3 class="vd-word" data-i18n-skip>${esc(w.palabra)}</h3></div>`
   +`<p class="vd-mean" data-i18n-skip>${esc(w.significado||'')}</p>`
   +(w.ejemplo?`<div class="vd-ex" data-i18n-skip><span>${vocMark(w.ejemplo,w.palabra)}</span><button type="button" class="hear sm" data-hear="${esc(w.ejemplo)}" aria-label="Hear it">🔊</button></div>`:'')
   +`<button type="button" class="btn vocab-toggle-btn vd-learn${w.aprendida?' on':''}" data-id="${esc(ids)}" data-state="${!!w.aprendida}">${w.aprendida?'✓ Learned':'Mark learned'}</button></article>`;
}
function vocRenderDaily(){
  const box=$('vocab-daily');if(!box)return;
  const keep=(box.querySelector('.vd-track')||{}).scrollLeft||0;
  box.innerHTML=VOC.daily.length?`<div class="vd-track">${VOC.daily.map(vdCard).join('')}</div>`:'<div class="empty">No words yet.</div>';
  const t=box.querySelector('.vd-track');if(t)t.scrollLeft=keep;
}
async function loadVocabDaily(more){
  const box=$('vocab-daily');
  if(more===true||!VOC.daily.length)box.innerHTML=pqLoader('sm');
  try{
    const d=await jsonFetch('/api/vocabulario/diario'+(more===true?'?mas=1':''));
    const before=VOC.daily.length;
    VOC.daily=d.palabras||[];vocRenderDaily();
    if(more===true&&d.limite)toast("That's plenty for today — review these first!");
    else if(more===true&&VOC.daily.length>before){const t=box.querySelector('.vd-track');if(t)setTimeout(()=>t.scrollTo({left:t.scrollWidth,behavior:'smooth'}),200)}
    prefetchTts(VOC.daily.map(w=>w.palabra));
  }catch(e){box.innerHTML='<div class="empty">Could not load today\'s words.</div>'}
  loadVocabList();
}
function vocRenderHero(){
  const rows=VOC.all,tot=rows.length,lrn=rows.filter(w=>w.aprendida).length,pct=tot?Math.round(lrn/tot*100):0;
  $('vocab-total').textContent=`📚 ${tot} words saved`;$('vocab-learned').textContent=`✅ ${lrn} learned`;
  $('vb-pct').textContent=pct+'%';$('vb-ring').style.setProperty('--p',pct);
}
function vocRow(w){
  const ids=[w.id].concat(w.dupIds||[]).join(',');
  return `<div class="vl-row"><button type="button" class="hear sm" data-hear="${esc(w.palabra)}" aria-label="Hear it">🔊</button>`
   +`<div class="vl-main" data-i18n-skip><b>${esc(w.palabra)}</b><span>${esc(w.significado||'')}</span></div>`
   +`<button type="button" class="btn vocab-toggle-btn${w.aprendida?' on':''}" data-id="${esc(ids)}" data-state="${!!w.aprendida}">${w.aprendida?'✓ Learned':'Mark learned'}</button></div>`;
}
function vocRenderList(){
  const q=VOC.q.trim().toLowerCase();
  let rows=VOC.all.filter(w=>VOC.filter==='all'||(VOC.filter==='learned'?w.aprendida:!w.aprendida))
    .filter(w=>!q||vocNorm(w.palabra).includes(q)||String(w.significado||'').toLowerCase().includes(q));
  const total=rows.length;rows=rows.slice(0,VOC.shown);
  $('vocab-list').innerHTML=rows.map(vocRow).join('')||'<div class="empty">No saved words yet.</div>';
  $('vocab-more').style.display=total>rows.length?'':'none';
}
async function loadVocabList(){
  try{const d=await jsonFetch('/api/vocabulario');VOC.all=vocUnique(d.palabras||[])}
  catch(e){toast(e.message);return}
  vocRenderHero();vocRenderList();refreshSrs();
}
async function saveVocabWord(palabra,significado,origen){try{await jsonFetch('/api/vocabulario/guardar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({palabra,significado,origen})});toast('Saved to your vocabulary.');loadVocabList()}catch(e){toast(e.message)}}
async function toggleVocabLearned(ids,current){
  const list=String(ids).split(',').filter(Boolean),val=!current;
  const hit=VOC.all.concat(VOC.daily).find(w=>list.includes(String(w.id)));
  const key=hit?vocNorm(hit.palabra):null;
  const apply=v=>{VOC.all.concat(VOC.daily).forEach(w=>{if(key&&vocNorm(w.palabra)===key)w.aprendida=v});vocRenderHero();vocRenderList();vocRenderDaily();refreshSrs()};
  apply(val);
  try{await Promise.all(list.map(id=>jsonFetch('/api/vocabulario/marcar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,aprendida:val})})))}
  catch(e){apply(current);toast(e.message)}
}
const FRAME_GRADIENTS={gold:'linear-gradient(135deg,#f5c542,#ffb37a)',fire:'linear-gradient(135deg,#ff6b4a,#ff3d6e)',ocean:'linear-gradient(135deg,#4ad0ff,#7180ff)'};
function avatarMarkup(url,initials,frameGradient){const inner=url?`<img src="${esc(url)}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`:esc(initials);if(!frameGradient)return inner;return `<div style="width:100%;height:100%;border-radius:50%;padding:3px;background:${frameGradient};display:flex;align-items:center;justify-content:center;box-sizing:border-box"><div style="width:100%;height:100%;border-radius:50%;overflow:hidden;background:var(--bg);display:flex;align-items:center;justify-content:center">${inner}</div></div>`}
function applyProfileIdentity(user,d){const u=(d&&d.user)||{};state.username=u.username||'';state.avatarFrame=u.avatar_frame||'';const name=u.username||user.email||'Signed in';const initials=(u.username||user.email||'T').trim().slice(0,2).toUpperCase();const frameGrad=FRAME_GRADIENTS[u.avatar_frame]||null;$('user-display').textContent=name;$('side-email').textContent=u.username||user.email||'Student';$('side-avatar').innerHTML=avatarMarkup(u.avatar_url,initials,frameGrad);$('profile-avatar-preview').innerHTML=avatarMarkup(u.avatar_url,initials,frameGrad);$('profile-username').value=u.username||''}
async function saveUsername(){const name=$('profile-username').value.trim();if(name.length<2)return toast('Escribe al menos 2 caracteres.');busy('profile-username-save',true,'Saving...');try{await jsonFetch('/api/perfil',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:name})});$('user-display').textContent=name;$('side-email').textContent=name;toast('Nombre actualizado.')}catch(e){toast(e.message)}finally{busy('profile-username-save',false,'Save')}}
async function uploadAvatar(file){if(!file)return;if(file.size>4*1024*1024)return toast('La imagen no debe pesar más de 4 MB.');const fd=new FormData();fd.append('avatar',file);busy('profile-avatar-btn',true,'Uploading...');try{const d=await jsonFetch('/api/perfil/avatar',{method:'POST',body:fd});const frameGrad=FRAME_GRADIENTS[state.avatarFrame]||null;$('profile-avatar-preview').innerHTML=avatarMarkup(d.avatar_url,'T',frameGrad);$('side-avatar').innerHTML=avatarMarkup(d.avatar_url,'T',frameGrad);toast('Foto actualizada.')}catch(e){toast(e.message)}finally{busy('profile-avatar-btn',false,'Upload photo')}}
function renderAccountInfo(user,d){$('acc-email').textContent=user.email||'-';const miembro=d.user&&d.user.miembro_desde?new Date(d.user.miembro_desde).toLocaleDateString():'-';$('acc-miembro').textContent=miembro;if(d.en_prueba){$('acc-plan').textContent='Prueba gratis';$('acc-plan').style.color='var(--warning)';$('acc-dias').textContent=d.trial_dias_restantes+' día(s)';$('acc-detalle').textContent='Estás en tu período de prueba gratuita. Al terminar, renueva para seguir practicando.';$('acc-renovar').style.display='none'}else if(d.is_subscribed){$('acc-plan').textContent='Activa';$('acc-plan').style.color='var(--success)';$('acc-dias').textContent='—';$('acc-detalle').textContent='Tu suscripción está activa. ¡Sigue practicando!';$('acc-renovar').style.display='none'}else{$('acc-plan').textContent='Vencida';$('acc-plan').style.color='var(--danger)';$('acc-dias').textContent='0 días';$('acc-detalle').textContent='Tu prueba o suscripción terminó. Renueva por $79 MXN/mes para seguir con acceso.';$('acc-renovar').style.display='inline-block';$('acc-renovar').href='https://wa.me/529911093870?text=Hola%2C%20ya%20hice%20mi%20pago%20de%20%2479%20MXN%2C%20aqui%20esta%20mi%20comprobante%3A'}}
async function enviarSoporte(){const tipo=$('soporte-tipo').value;const texto=$('soporte-texto').value.trim();if(!texto)return toast('Escribe tu mensaje antes de enviar.');busy('soporte-enviar',true,'Enviando...');try{await jsonFetch('/api/soporte',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tipo,mensaje:texto})});$('soporte-texto').value='';$('soporte-confirmacion').style.display='block';setTimeout(()=>$('soporte-confirmacion').style.display='none',5000)}catch(e){toast(e.message)}finally{busy('soporte-enviar',false,'Enviar mensaje')}}
function tutorAudio(div,text){const r=document.createElement('span');r.className='msg-ac';r.innerHTML='<button type="button" class="st-ic sm" aria-label="Listen">🔊</button><button type="button" class="st-ic sm" aria-label="Native speed" title="Native speed">⚡</button>';const bs=r.querySelectorAll('button');const mae=tutorCategory==='maestro';
  if(mae){const en=englishSpans(text);bs[0].onclick=()=>teacherSpeak(text);if(en)bs[1].onclick=()=>window.TalvoNative.say(en);else bs[1].style.display='none'}
  else{bs[0].onclick=()=>speak(text,.95);bs[1].onclick=()=>window.TalvoNative.say(text)}
  div.appendChild(r)}
/* solo lo que va entre comillas Y es inglés (las traducciones al español no se leen con voz inglesa) */
function englishSpans(t){const m=String(t||'').match(/"([^"\n]{2,160})"|“([^”\n]{2,160})”/g)||[];return m.map(x=>x.replace(/^["“]|["”]$/g,'')).filter(x=>!/[¿¡áéíóúñÁÉÍÓÚÑ]/.test(x)&&/[A-Za-z]/.test(x)).join('. ')}
function addTutorMessage(text,who){const wrap=$('tutor-messages');const div=document.createElement('div');div.className='msg '+(who==='user'?'user':'ai');div.textContent=text;if(who!=='user')tutorAudio(div,text);wrap.appendChild(div);wrap.scrollTop=wrap.scrollHeight}
let tutorCategory='conversation';
const TUTOR_OPENERS={conversation:'Hi! I\'m Palanqueta, your English tutor. Tell me something about your day.',grammar:'Let\'s work on grammar today! Tell me about something you did last weekend — I\'ll help you get the tenses just right.',vocabulary:'Let\'s grow your vocabulary! Tell me about a hobby you enjoy, and I\'ll introduce some useful new words as we talk.',pronunciation:'Let\'s focus on pronunciation. Try saying a short sentence about yourself, and I\'ll give you tips on how it should sound.',free:'Free talk! Tell me about anything on your mind — no particular topic, just practice speaking freely.',maestro:'¡Hola! Qué gusto conocerte, soy tu maestra Palanqueta. Te explico en español y practicamos inglés juntas, poquito a poquito. Antes de empezar quiero conocerte: ¿cómo te llamas?'};
function setTutorCategory(cat){tutorCategory=cat;{const inp=$('tutor-input');if(inp)inp.placeholder=cat==='maestro'?'Escribe tu respuesta…':'Write in English...'}$$('#tutor-category-bar .mode').forEach(b=>b.classList.toggle('active',b.dataset.cat===cat));$('tutor-messages').innerHTML=`<div class="msg ai">${esc(TUTOR_OPENERS[cat]||TUTOR_OPENERS.conversation)}</div>`;const f=$('tutor-messages').firstElementChild;if(f&&cat!=='maestro')tutorAudio(f,TUTOR_OPENERS[cat]||TUTOR_OPENERS.conversation);if(cat==='maestro'){teacherHello().then(h=>{if(tutorCategory==='maestro'&&$('tutor-messages').querySelectorAll('.msg').length===1){const f=$('tutor-messages').firstElementChild;if(f&&f.firstChild){f.firstChild.textContent=h}}})}}
async function tutorSend(text){const value=(text??$('tutor-input').value).trim();if(!value)return;addTutorMessage(value,'user');$('tutor-input').value='';busy('tutor-send',true,'Thinking...');try{const d=await jsonFetch('/api/tutor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mensaje:value,categoria:tutorCategory,modo:tutorCategory==='maestro'?'maestro':'',clase_n:$('tutor-messages').querySelectorAll('.msg.user').length,history:Array.from($('tutor-messages').querySelectorAll('.msg')).slice(-8).map(m=>({role:m.classList.contains('user')?'user':'assistant',content:(m.firstChild&&m.firstChild.nodeType===3?m.firstChild.textContent:m.textContent)}))})});addTutorMessage(d.respuesta||'Let’s keep practicing.','ai');state.lastTutor=d.respuesta||'';if(settingsAutoplay){if(tutorCategory==='maestro')teacherSpeak(d.respuesta||'');else speak(d.respuesta||'')}}catch(e){toast(e.message)}finally{busy('tutor-send',false,'Send')}}
function tutorMic(){const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR)return toast('Voice input is not available in this browser.');const r=new SR();r.lang=tutorCategory==='maestro'?'es-MX':'en-US';r.interimResults=false;r.maxAlternatives=1;r.onstart=()=>toast('Listening...');r.onerror=e=>toast('Voice input: '+e.error);r.onresult=e=>tutorSend(e.results[0][0].transcript);r.start()}
async function loadProgress(){try{const d=await jsonFetch('/api/progreso');$('p-total').textContent=d.total_actividades??0;$('p-pron').textContent=d.pronunciacion??0;$('p-writing').textContent=d.escritura??0;$('p-reading').textContent=d.lectura??0;const scores=d.puntuaciones_recientes||[];$('progress-bars').innerHTML=scores.map(x=>`<div class="barcol" title="${Math.round(x)}"><i style="height:${Math.max(4,Math.min(100,Number(x)||0))}%"></i></div>`).join('')||'<div class="empty">No scores yet.</div>';const h=await jsonFetch('/obtener-historial');renderHistory(h)}catch(e){toast(e.message)}}
async function renderPronTrend(){const box=$('pron-trend');if(!box)return;try{const h=await jsonFetch('/obtener-historial');const items=Array.isArray(h)?h:(h.historial||[]);const rows=items.filter(x=>(x.tipo||x.type)==='pronunciation'&&(x.puntuacion??x.score)!=null);const todayStr=new Date().toDateString();const yestStr=new Date(Date.now()-86400000).toDateString();let today='—',yesterday='—',best=0;rows.forEach(r=>{const val=Math.round(Number(r.puntuacion??r.score));const d=new Date(r.created_at||r.fecha||'');const dStr=isNaN(d)?'':d.toDateString();if(dStr===todayStr&&today==='—')today=val;if(dStr===yestStr&&yesterday==='—')yesterday=val;if(val>best)best=val});box.innerHTML=`<div class="pbox"><strong>${today}${today!=='—'?'%':''}</strong><small>Today</small></div><div class="pbox"><strong>${yesterday}${yesterday!=='—'?'%':''}</strong><small>Yesterday</small></div><div class="pbox"><strong>${best}%</strong><small>Best</small></div>`}catch(e){box.innerHTML=''}}
function renderHistory(data){const list=$('history-list');const items=Array.isArray(data)?data:(data.historial||[]);list.innerHTML=items.slice(0,30).map(x=>`<div class="history-card"><div class="history-head"><span>${esc(x.tipo||x.type||'Practice')}</span><span>${esc(x.puntuacion??x.score??'—')}</span></div><div class="history-meta"><span>${esc(x.created_at||x.fecha||'')}</span><span>${esc(x.frase||x.tema||x.resumen||'')}</span></div></div>`).join('')||'<div class="empty">Your practice history will appear here.</div>'}
async function loadAdminActivity(){admBoot();admLoadTab(adm.tab,false)}
const AUTHG={fails:0,until:0};
try{const z=JSON.parse(localStorage.getItem('talvo_auth_lock')||'{}');AUTHG.fails=+z.f||0;AUTHG.until=+z.u||0}catch(e){}
function authLockSave(){try{localStorage.setItem('talvo_auth_lock',JSON.stringify({f:AUTHG.fails,u:AUTHG.until}))}catch(e){}}
const pwStrong=p=>p.length>=8&&/[A-Za-z]/.test(p)&&/\d/.test(p);
function authMsg(e){const m=String(e&&e.message||'');if(/invalid login|invalid credentials/i.test(m))return 'Email or password incorrect.';if(/not confirmed/i.test(m))return 'Please confirm your email first (check your inbox and spam).';if(/rate limit|too many|over_/i.test(m))return 'Too many attempts. Wait a few minutes and try again.';if(/already registered|already been registered/i.test(m))return 'We could not create that account. Try signing in or reset your password.';if(/password/i.test(m)&&/weak|least|short/i.test(m))return 'Use at least 8 characters with letters and numbers.';if(/captcha/i.test(m))return 'La verificación de seguridad falló. Inténtalo de nuevo.';return 'Could not complete that. Please try again.'}
/* --- pantalla de verificación de correo --- */
const VF={email:'',poll:0,cool:0,tick:0,tsId:null,tsTok:''};
function vfProvider(email){const d=(email.split('@')[1]||'').toLowerCase();
  if(/^(gmail|googlemail)\./.test(d))return['Gmail','https://mail.google.com/mail/u/0/#search/from%3Asupabase+OR+from%3Atalvo'];
  if(/^(outlook|hotmail|live|msn)\./.test(d))return['Outlook','https://outlook.live.com/mail/0/'];
  if(/^yahoo\./.test(d))return['Yahoo Mail','https://mail.yahoo.com/'];
  if(/^(icloud|me|mac)\./.test(d))return['iCloud Mail','https://www.icloud.com/mail'];
  return null}
function vfShow(email){setTimeout(vfPushInit,50);
  VF.email=email;
  try{localStorage.setItem('talvo_pending_verify',JSON.stringify({email,t:Date.now()}))}catch(e){}
  $('vf-email').textContent=email;$('vf-err').className='vf-err';$('vf-code').value='';
  const pr=vfProvider(email);
  $('vf-open').innerHTML=pr?'<a href="'+pr[1]+'" target="_blank" rel="noopener">📬 Abrir '+pr[0]+'</a>':'';
  const v=$('verify-view');v.classList.remove('ok');v.classList.add('show');document.body.style.overflow='hidden';
  vfCooldown(60);
  clearInterval(VF.poll);VF.poll=setInterval(async()=>{try{const {data}=await sb.auth.getSession();if(data&&data.session){$('verify-view').classList.add('ok');syncUser(data.session.user)}}catch(e){}},3500);
  vfTs();
}
function vfHide(){
  const v=$('verify-view');if(!v||!v.classList.contains('show'))return;
  v.classList.remove('show','ok');document.body.style.overflow='';clearInterval(VF.poll);clearInterval(VF.tick);
  try{localStorage.removeItem('talvo_pending_verify')}catch(e){}
}
function vfCooldown(sec){
  clearInterval(VF.tick);VF.cool=Date.now()+sec*1000;
  const b=$('vf-resend');
  const upd=()=>{const left=Math.ceil((VF.cool-Date.now())/1000);if(left>0){b.disabled=true;b.textContent='Reenviar correo ('+left+' s)'}else{clearInterval(VF.tick);b.disabled=false;b.textContent='Reenviar correo'}};
  upd();VF.tick=setInterval(upd,500);
}
function vfTs(){
  if(VF.tsId!==null||!window.turnstile){if(VF.tsId===null)setTimeout(vfTs,600);return}
  try{VF.tsId=turnstile.render('#vf-ts',{sitekey:TURNSTILE_SITE_KEY,theme:'auto',callback:t=>{VF.tsTok=t},'expired-callback':()=>{VF.tsTok=''},'error-callback':()=>{VF.tsTok=''}})}catch(e){}
}
function vfErr(m){const e=$('vf-err');e.textContent=m;e.className='vf-err'+(m?' show':'')}
async function vfResend(){
  if(!VF.tsTok)return vfErr('Espera un segundo a que termine la verificación de seguridad y vuelve a intentar. / Wait a second for the security check.');
  const b=$('vf-resend');b.disabled=true;vfErr('');
  try{
    const r=await sb.auth.resend({type:'signup',email:VF.email,options:{captchaToken:VF.tsTok}});
    if(r.error)throw r.error;
    toast('Listo, te enviamos otro correo. Revisa también Spam. / Email sent again.');
  }catch(e){vfErr(/rate|too many|seconds|over_/i.test(String(e.message))?'Pediste demasiados correos. Espera unos minutos e inténtalo otra vez.':'No se pudo reenviar. Inténtalo en un momento.');console.error('[VERIFY RESEND]',e)}
  VF.tsTok='';try{if(VF.tsId!==null)turnstile.reset(VF.tsId)}catch(e){}
  vfCooldown(60);
}
async function vfVerify(){
  const code=$('vf-code').value.replace(/\D/g,'');
  if(code.length<6)return vfErr('Escribe los 6 dígitos del código que viene en tu correo.');
  busy('vf-verify',true,'Verificando...');vfErr('');
  try{
    const r=await sb.auth.verifyOtp({email:VF.email,token:code,type:'signup'});
    if(r.error)throw r.error;
    $('verify-view').classList.add('ok');
    if(r.data&&r.data.user)syncUser(r.data.user);
  }catch(e){vfErr('Ese código no es válido o ya venció. Revisa los dígitos o pide otro correo.');console.error('[VERIFY]',e)}
  finally{busy('vf-verify',false)}
}
/* --- Notificaciones push --- */
const PUSH_KEY_FALLBACK='BEhBs6czLuPG8oTe25H-lOFDJ8mIr6ZrzCUAeB6ZpoU8VAL6-iaz6SISP35U5a0a4wfWm_3pv3xTMrQGosudhe4';
const PUSH={
  supported(){return 'serviceWorker' in navigator&&'PushManager' in window&&'Notification' in window},
  ios(){return /iphone|ipad|ipod/i.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1)},
  standalone(){try{return matchMedia('(display-mode: standalone)').matches||navigator.standalone===true}catch(e){return false}},
  need(){/* motivo por el que no se puede pedir ahora */if(this.supported())return '';return this.ios()&&!this.standalone()?'ios':'unsupported'},
  hour(){const h=parseInt(localStorage.getItem('talvo_push_hour'),10);return h>=0&&h<=23?h:19},
  flag(){try{return localStorage.getItem('talvo_push')||''}catch(e){return ''}},
  setFlag(v){try{localStorage.setItem('talvo_push',v)}catch(e){}},
  u8(b){const p='='.repeat((4-b.length%4)%4),r=atob((b+p).replace(/-/g,'+').replace(/_/g,'/')),o=new Uint8Array(r.length);for(let i=0;i<r.length;i++)o[i]=r.charCodeAt(i);return o},
  async reg(){try{await navigator.serviceWorker.register('sw.js')}catch(e){}return navigator.serviceWorker.ready},
  async sub(){try{const r=await navigator.serviceWorker.getRegistration();return r?await r.pushManager.getSubscription():null}catch(e){return null}},
  async key(){try{const r=await fetch(API_URL+'/api/push/key',{cache:'no-store'});const d=await r.json();if(d&&d.ready&&d.key)return d.key}catch(e){}return ''},
  async send(sub,email){
    const body={subscription:sub.toJSON(),hour:this.hour(),tz:(Intl.DateTimeFormat().resolvedOptions().timeZone||''),lang:(window.TalvoI18n&&TalvoI18n.get&&TalvoI18n.get()==='en')?'en':'es'};
    const s=await getSession();
    if(s){const r=await fetch(API_URL+'/api/push/subscribe',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+s.access_token},body:JSON.stringify(body)});if(!r.ok)throw new Error('sub '+r.status)}
    else if(email){body.email=email;const r=await fetch(API_URL+'/api/push/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error('sub '+r.status)}
  },
  /* debe llamarse directamente desde un clic (el permiso exige un gesto del usuario) */
  async enable(email){
    const need=this.need();if(need)return {ok:false,reason:need};
    let perm=Notification.permission;
    if(perm==='default')perm=await Notification.requestPermission();
    if(perm!=='granted')return {ok:false,reason:perm};
    const key=(await this.key())||'';if(!key)return {ok:false,reason:'server'};
    const reg=await this.reg();
    let sub=await reg.pushManager.getSubscription();
    if(!sub){try{sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:this.u8(key)})}catch(e){return {ok:false,reason:'error'}}}
    try{await this.send(sub,email)}catch(e){return {ok:false,reason:'server'}}
    this.setFlag('on');return {ok:true};
  },
  async disable(){
    const sub=await this.sub();this.setFlag('off');
    if(sub){const ep=sub.endpoint;try{await sub.unsubscribe()}catch(e){}try{await fetch(API_URL+'/api/push/unsubscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({endpoint:ep})})}catch(e){}}
  },
  /* al iniciar sesión: liga este dispositivo a la cuenta si ya había dado permiso */
  async sync(){
    if(!this.supported()||Notification.permission!=='granted'||this.flag()==='off')return;
    const sub=await this.sub();if(!sub)return;
    try{await this.send(sub)}catch(e){}
  }
};
window.TalvoPush=PUSH;
const PUSH_MSG={denied:'Notifications are blocked. Enable them in your browser or phone settings for this site.',ios:'On iPhone: tap Share → Add to Home Screen, open Talvo from there and turn on reminders.',unsupported:'This browser does not support notifications.',server:'We could not connect reminders right now. Try again in a moment.',error:'We could not turn on reminders on this device.'};
function pushMsg(r){return T(PUSH_MSG[r]||PUSH_MSG.error)}
/* A) pantalla de verificación (justo al crear la cuenta) */
async function vfPushInit(){
  const box=$('vf-push');if(!box)return;
  const need=PUSH.need();
  if(need==='unsupported'){box.style.display='none';return}
  box.style.display='flex';
  const on=PUSH.supported()&&Notification.permission==='granted'&&PUSH.flag()!=='off'&&!!(await PUSH.sub());
  box.classList.toggle('ok',on);$('vf-push-btn').style.display=on?'none':'';
  $('vf-push-msg').textContent=on?'✅ Recordatorios activados · Reminders on':(need==='ios'?pushMsg('ios'):'');
  if(need==='ios')$('vf-push-btn').style.display='none';
}
$('vf-push-btn')?.addEventListener('click',async()=>{
  const b=$('vf-push-btn');b.disabled=true;
  const r=await PUSH.enable(VF.email);b.disabled=false;
  if(r.ok){$('vf-push').classList.add('ok');b.style.display='none';$('vf-push-msg').style.color='var(--success)';$('vf-push-msg').textContent='✅ Recordatorios activados · Reminders on'}
  else{$('vf-push-msg').style.color='var(--warning)';$('vf-push-msg').textContent=r.reason==='denied'?'Bloqueadas: actívalas en los ajustes del navegador.':pushMsg(r.reason)}
});
/* B) tarjeta flotante dentro de la app */
function pushAskMaybe(){
  try{
    if(!PUSH.supported()||Notification.permission!=='default'||PUSH.flag()==='off')return;
    const t=parseInt(localStorage.getItem('talvo_push_ask')||'0',10);if(Date.now()-t<5*86400000)return;
    if(!state.user||$('verify-view').classList.contains('show'))return;
    const go=n=>{
      if(Notification.permission!=='default'||!state.user)return;
      const busyTour=document.getElementById('tour-offer')||document.querySelector('.tour-root,.tour-card')||(()=>{try{return localStorage.getItem('talvo_tour_seen')!=='1'}catch(e){return false}})();
      if(busyTour&&n<8)return setTimeout(()=>go(n+1),9000);
      $('push-ask').classList.add('show');
    };
    setTimeout(()=>go(0),6000);
  }catch(e){}
}
function pushAskHide(){$('push-ask').classList.remove('show');try{localStorage.setItem('talvo_push_ask',String(Date.now()))}catch(e){}}
$('pa-no')?.addEventListener('click',pushAskHide);
$('pa-yes')?.addEventListener('click',async()=>{pushAskHide();const r=await PUSH.enable();toast(r.ok?T('Reminders on! 🔔'):pushMsg(r.reason));pushUI()});
/* C) Mi cuenta */
function pushHours(){const sel=$('push-hour');if(!sel||sel.options.length)return;for(let h=0;h<24;h++){const o=document.createElement('option');o.value=h;o.textContent=(h%12||12)+':00 '+(h<12?'AM':'PM');sel.appendChild(o)}}
async function pushUI(){
  const tg=$('push-toggle');if(!tg)return;pushHours();
  const st=$('push-state'),need=PUSH.need();
  const on=!need&&Notification.permission==='granted'&&PUSH.flag()!=='off'&&!!(await PUSH.sub());
  tg.checked=on;tg.disabled=!!need;$('push-opts').style.display=on?'flex':'none';$('push-hour').value=PUSH.hour();
  st.textContent=need?pushMsg(need):(Notification.permission==='denied'?pushMsg('denied'):(on?T('On — Palanqueta will remind you to practice.'):T('Off — turn on to get a daily practice reminder.')));
}
$('push-toggle')?.addEventListener('change',async e=>{
  const tg=e.target;tg.disabled=true;
  if(tg.checked){const r=await PUSH.enable();if(!r.ok){tg.checked=false;toast(pushMsg(r.reason))}else toast(T('Reminders on! 🔔'))}
  else{await PUSH.disable();toast(T('Reminders off.'))}
  tg.disabled=false;pushUI();
});
$('push-hour')?.addEventListener('change',async e=>{
  const h=parseInt(e.target.value,10);try{localStorage.setItem('talvo_push_hour',String(h))}catch(_){}
  const sub=await PUSH.sub();if(!sub)return;
  try{await jsonFetch('/api/push/prefs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({endpoint:sub.endpoint,hour:h,tz:Intl.DateTimeFormat().resolvedOptions().timeZone||''})});toast(T('Saved'))}catch(err){toast(err.message)}
});
(function(){
  let tm;
  const ICONS={streak:['🔥','✨','🔥'],miss:['💤','🌙','💤'],verify:['✉️','✨','⭐'],cheer:['⭐','✨','⭐']};
  const LAND={streak:['🔥 Your streak needs you!','A quick lesson keeps your flame alive.'],miss:['I missed you! 🥺','Come back with a short lesson.'],cheer:['Time to practice!','Your goal for today is ready.'],verify:['Almost there! ✉️','Confirm your email to start your free trial.']};
  function hide(){const b=$('push-banner');if(b)b.classList.remove('show')}
  function pqSound(force){try{if(!force&&localStorage.getItem('talvo_pqsound')==='0')return;const a=new Audio('icons/pq-cluck.mp3');a.volume=.8;const p=a.play();if(p&&p.catch)p.catch(()=>{})}catch(e){}}
  try{const sw=$('push-sound');if(sw){sw.checked=localStorage.getItem('talvo_pqsound')!=='0';sw.addEventListener('change',()=>{try{localStorage.setItem('talvo_pqsound',sw.checked?'1':'0')}catch(e){}if(sw.checked)pqSound(true)})}}catch(e){}
  function show(d){const b=$('push-banner');if(!b)return;pqSound();const m=ICONS[d.mood]?d.mood:'cheer';b.dataset.mood=m;b.querySelectorAll('.pb-st').forEach((e,i)=>e.textContent=ICONS[m][i]);$('pb-title').textContent=d.title||'Palanqueta';$('pb-body').textContent=d.body||'';b.classList.remove('show');void b.offsetWidth;b.classList.add('show');clearTimeout(tm);tm=setTimeout(hide,6500)}
  if('serviceWorker' in navigator)navigator.serviceWorker.addEventListener('message',e=>{if(e.data&&e.data.type==='talvo-push')show(e.data)});
  $('push-banner')?.addEventListener('click',hide);
  /* al tocar la notificación con la app cerrada: Palanqueta saluda con animación */
  try{const q=new URLSearchParams(location.search).get('pq');if(q){history.replaceState(null,'',location.pathname);const L=LAND[q]||LAND.cheer;setTimeout(()=>show({mood:q,title:T(L[0]),body:T(L[1])}),1800)}}catch(e){}
  /* enlaces de los correos: ?verify=<correo> abre la pantalla de confirmación; ?go=cuenta lleva a Mi cuenta */
  try{const u=new URLSearchParams(location.search),v=u.get('verify'),g=u.get('go');if(v||g){history.replaceState(null,'',location.pathname);setTimeout(async()=>{try{const ss=await getSession();if(ss&&ss.access_token){if(g==='cuenta')section('cuenta')}else if(v&&/^[^@\s]+@[^@\s]+$/.test(v))vfShow(v.toLowerCase())}catch(e){}},1500)}}catch(e){}
})();
setInterval(()=>{const n=$('nav-admin'),b=$('email-test');if(b&&n)b.style.display=(n.style.display&&n.style.display!=='none')?'':'none'},3000);
$('email-test')?.addEventListener('click',async()=>{
  const to=prompt('¿A qué correo mando la prueba?',(state.user&&state.user.email)||'');if(!to)return;busy('email-test',true,'Enviando...');
  try{const d=await jsonFetch('/api/email/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to:to.trim()})});toast('Enviados '+d.enviados+' de '+d.de+'. Revisa tu correo (y Spam).')}catch(e){toast(e.message)}finally{busy('email-test',false,'✉️ Enviarme correos de prueba (admin)')}
});
$('push-test')?.addEventListener('click',async()=>{
  busy('push-test',true,'Sending...');
  try{const d=await jsonFetch('/api/push/test',{method:'POST'});toast(d.enviadas?T('Sent! Check your notifications.'):T('No active device found. Turn reminders off and on again.'))}catch(e){toast(e.message)}finally{busy('push-test',false,'🔔 Send a test notification')}
});
async function authSubmit(){const email=$('auth-email').value.trim().toLowerCase();const password=$('auth-password').value;if(!email||!password)return authError('Enter your email and password.');if(!/^[^\s@]{1,64}@[^\s@]{1,255}\.[^\s@]{2,}$/.test(email))return authError('Enter a valid email address.');if(password.length>128)return authError('That password is too long.');const wait=Math.ceil((AUTHG.until-Date.now())/1000);if(wait>0)return authError('Too many attempts. Try again in '+(wait>90?Math.ceil(wait/60)+' minutes':wait+' seconds')+'.');if(state.authRegister&&!pwStrong(password))return authError('Use at least 8 characters with letters and numbers.');const cap=tsToken;if(!cap)return authError('Completa la verificación de seguridad antes de continuar.');busy('auth-submit',true,state.authRegister?'Creating...':'Signing in...');authError('');try{let r;if(state.authRegister){r=await sb.auth.signUp({email,password,options:{captchaToken:cap}});if(r.error)throw r.error;if(r.data.session){toast('Account created.')}else if(r.data.user&&Array.isArray(r.data.user.identities)&&r.data.user.identities.length===0){authError('Ese correo ya tiene una cuenta. Inicia sesión o recupera tu contraseña. / That email already has an account.')}else{closeAuth();vfShow(email)}}else{r=await sb.auth.signInWithPassword({email,password,options:{captchaToken:cap}});if(r.error)throw r.error;AUTHG.fails=0;AUTHG.until=0;authLockSave();closeAuth();await syncUser(r.data.user)} }catch(e){console.error('[AUTH]',e);if(!state.authRegister&&/not confirmed/i.test(String(e&&e.message||''))){closeAuth();vfShow(email);return}if(!state.authRegister){AUTHG.fails++;if(AUTHG.fails>=5){AUTHG.until=Date.now()+Math.min(900000,30000*Math.pow(2,AUTHG.fails-5));}authLockSave()}authError(authMsg(e))}finally{tsReset();busy('auth-submit',false,state.authRegister?'Create account':'Sign in')}}
let obAnswers={learning_goal:null,daily_goal_minutes:null,cefr_level:null};
function initOnboarding(){obAnswers={learning_goal:null,daily_goal_minutes:null,cefr_level:null};$('onboarding-view').style.display='flex';showObStep(1)}
function showObStep(n){[1,2,3,4,5].forEach(i=>{const el=$('ob-step-'+i);if(el)el.style.display=i===n?'block':'none'})}
function selectObOption(groupId,key,value,btn){$$('#'+groupId+' .ob-option').forEach(b=>b.classList.remove('selected'));btn.classList.add('selected');obAnswers[key]=value;setTimeout(()=>{if(key==='learning_goal')showObStep(2);else if(key==='daily_goal_minutes')showObStep(3);else if(key==='cefr_level')finishOnboarding()},300)}
async function finishOnboarding(){try{await jsonFetch('/api/onboarding',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obAnswers)})}catch(e){toast(e.message)}$('onboarding-view').style.display='none';$('app-content').style.display='block';closeAuth();loadDashboard()}
function openAuthAs(register){state.authRegister=register;$('auth-title').textContent=register?'Create account':'Sign in';$('auth-submit').textContent=register?'Create account':'Sign in';$('auth-toggle').textContent=register?'Back to sign in':'Create an account';authError('');showAuth()}
function toggleAuthMode(){state.authRegister=!state.authRegister;$('auth-title').textContent=state.authRegister?'Create account':'Sign in';$('auth-submit').textContent=state.authRegister?'Create account':'Sign in';$('auth-toggle').textContent=state.authRegister?'Back to sign in':'Create an account';authError('')}
async function signOut(){try{if(OFL)OFL.clearUser()}catch(e){}await sb.auth.signOut();state.user=null;state.subscribed=false;syncUser(null)}
function openSidebar(){document.querySelector('.sidebar')?.classList.add('open');$('sidebar-overlay')?.classList.add('show');document.body.style.overflow='hidden'}
function closeSidebar(){document.querySelector('.sidebar')?.classList.remove('open');$('sidebar-overlay')?.classList.remove('show');document.body.style.overflow=''}
function bind(){
$$('#main-nav button').forEach(b=>b.addEventListener('click',()=>{section(b.dataset.section,b);closeSidebar()}));
$$('[data-section-jump]').forEach(b=>b.addEventListener('click',()=>{section(b.dataset.sectionJump);closeSidebar()}));
$('nav-toggle')?.addEventListener('click',openSidebar);
$$('#tabbar button').forEach(b=>b.addEventListener('click',()=>{const t=b.dataset.tab;if(t==='menu')openSidebar();else section(t)}));
let lastSec='';const TAB_IDS=['home','learning-path','pronunciacion','tutor'];
const syncTabs=()=>{const a=document.querySelector('.section.active');const id=a?a.id.replace('sec-',''):'home';$$('#tabbar button').forEach(b=>b.classList.toggle('active',TAB_IDS.includes(id)?b.dataset.tab===id:b.dataset.tab==='menu'));if(id!==lastSec){lastSec=id;const pg=$('app-content');if(pg)pg.scrollTop=0;window.scrollTo(0,0)}};
const secObs=new MutationObserver(syncTabs);$$('.section').forEach(sc=>secObs.observe(sc,{attributes:true,attributeFilter:['class']}));syncTabs();
$('sidebar-close')?.addEventListener('click',closeSidebar);
$('sidebar-overlay')?.addEventListener('click',closeSidebar);
$$('.mode[data-pron]').forEach(b=>b.addEventListener('click',()=>pronMode(b.dataset.pron)));
$$('#writing-level-bar .mode').forEach(b=>b.addEventListener('click',()=>setWritingLevel(b.dataset.level,b)));
$$('#tutor-category-bar .mode').forEach(b=>b.addEventListener('click',()=>setTutorCategory(b.dataset.cat)));$$('#call-mode-bar .mode').forEach(b=>b.addEventListener('click',()=>{if(CALL.live)return toast('Cuelga primero para cambiar de modo.');callModeSet(b.dataset.m)}));teacherRender();
{const f0=document.querySelector('#tutor-messages .msg.ai');if(f0&&!f0.querySelector('.msg-ac'))tutorAudio(f0,f0.textContent)}
$$('#setting-autoplay-bar .mode').forEach(b=>b.addEventListener('click',()=>setSettingAutoplay(b.dataset.val)));
$$('#setting-rate-bar .mode').forEach(b=>b.addEventListener('click',()=>setSettingRate(b.dataset.val)));
applySettingsUI();
$('writing-new-challenge').addEventListener('click',loadWritingChallenge);
$('writing-skip-challenge').addEventListener('click',()=>{$('writing-challenge-card').style.display='none';updateWritingWordcount()});
$('login-btn').addEventListener('click',showAuth);
$('welcome-start').addEventListener('click',()=>openAuthAs(true));
$('welcome-login').addEventListener('click',()=>openAuthAs(false));
$$('#ob-goal-options .ob-option').forEach(b=>b.addEventListener('click',()=>selectObOption('ob-goal-options','learning_goal',b.dataset.val,b)));
$$('#ob-time-options .ob-option').forEach(b=>b.addEventListener('click',()=>selectObOption('ob-time-options','daily_goal_minutes',parseInt(b.dataset.val,10),b)));
$$('#ob-level-options .ob-option').forEach(b=>b.addEventListener('click',()=>selectObOption('ob-level-options','cefr_level',b.dataset.val,b)));
$('profile-username-save').addEventListener('click',saveUsername);
$('shop-buy-freeze').addEventListener('click',()=>buyItem('streak_freeze'));
$('profile-avatar-btn').addEventListener('click',()=>$('profile-avatar-input').click());
$('vf-resend').addEventListener('click',vfResend);$('vf-verify').addEventListener('click',vfVerify);$('vf-code').addEventListener('keydown',e=>{if(e.key==='Enter')vfVerify()});$('vf-done').addEventListener('click',()=>{const em=VF.email;vfHide();openAuthAs(false);$('auth-email').value=em;setTimeout(()=>$('auth-password').focus(),80)});$('vf-change').addEventListener('click',()=>{vfHide();openAuthAs(true);$('auth-email').value='';$('auth-password').value=''});$('profile-avatar-input').addEventListener('change',e=>uploadAvatar(e.target.files[0]));$('logout-btn').addEventListener('click',signOut);$('locked-login').addEventListener('click',showAuth);$('auth-close').addEventListener('click',closeAuth);$('auth-submit').addEventListener('click',authSubmit);$('auth-forgot').addEventListener('click',forgotPassword);$('reset-submit').addEventListener('click',resetSubmit);$('reset-password').addEventListener('keydown',e=>{if(e.key==='Enter')resetSubmit()});$('auth-toggle').addEventListener('click',toggleAuthMode);$('auth-password').addEventListener('keydown',e=>{if(e.key==='Enter')authSubmit()});$('use-custom').addEventListener('click',customPhrase);$('new-phrase').addEventListener('click',newPhrase);$('listen-phrase').addEventListener('click',()=>playGuideAudio(txtOf('phrase').trim(),'listen-phrase'));$('new-topic').addEventListener('click',newTopic);$('new-twister').addEventListener('click',newTwister);$('listen-twister').addEventListener('click',()=>playGuideAudio(txtOf('twister').trim(),'listen-twister'));$('record-btn').addEventListener('click',toggleRecording);$('writing-submit').addEventListener('click',analyzeWriting);$('writing').addEventListener('input',updateWritingWordcount);$('reading-new').addEventListener('click',regenerateReading);$('reading-submit').addEventListener('click',evaluateReading);
$$('#reading-filter-bar .mode').forEach(b=>b.addEventListener('click',()=>setReadingFilter(b.dataset.level)));
$('reading-back-to-library').addEventListener('click',loadReadingLibrary);
$$('#listening-filter-bar .mode').forEach(b=>b.addEventListener('click',()=>setListeningFilter(b.dataset.level)));
$('listening-back-to-library').addEventListener('click',loadListeningLibrary);$('listen-play').addEventListener('click',playDictation);$('listen-new').addEventListener('click',regenerateListening);$('dictation-submit').addEventListener('click',evaluateDictation);$('tutor-send').addEventListener('click',()=>tutorSend());$('tutor-input').addEventListener('keydown',e=>{if(e.key==='Enter')tutorSend()});$('tutor-mic').addEventListener('click',tutorMic);$('tutor-speak').addEventListener('click',()=>{if(tutorCategory==='maestro')teacherSpeak(state.lastTutor||'Sigamos practicando.');else speak(state.lastTutor||'Keep practicing.')});$('call-talk-btn').addEventListener('mousedown',callStartTalk);$('call-talk-btn').addEventListener('touchstart',e=>{e.preventDefault();callStartTalk()});$('call-talk-btn').addEventListener('mouseup',callStopTalk);$('call-talk-btn').addEventListener('mouseleave',callStopTalk);$('call-talk-btn').addEventListener('touchend',e=>{e.preventDefault();callStopTalk()});$('call-hangup').addEventListener('click',endCall);$('soporte-enviar').addEventListener('click',enviarSoporte);$('mascot').addEventListener('click',mascotClicked);document.addEventListener('click',e=>{const save=e.target.closest('.vocab-save-btn');if(save){saveVocabWord(save.dataset.word,save.dataset.meaning,'lectura');return}const tog=e.target.closest('.vocab-toggle-btn');if(tog){toggleVocabLearned(tog.dataset.id,tog.dataset.state==='true')}});window.addEventListener('keydown',e=>{if(e.key==='Escape')closeAuth()})}

/* ===== Talvo extras: siguiente paso, repaso, manos libres, prueba de nivel ===== */
try{fetch(API_URL+'/health',{cache:'no-store'}).catch(()=>{})}catch(e){}



/* --- repaso espaciado (se guarda en este dispositivo) --- */
const SRS_DAYS=[0,1,3,7,14,30];
function srsKey(){return 'talvo_srs_'+((state.user&&state.user.id)||'anon')}
function srsLoad(){try{return JSON.parse(localStorage.getItem(srsKey())||'{}')}catch(e){return {}}}
function srsSave(m){try{localStorage.setItem(srsKey(),JSON.stringify(m))}catch(e){}}
const SRS_BATCH=10;
let srsWords=[],srsQueue=[],srsIdx=0,srsStat={again:0,good:0,easy:0};
const srsK=w=>vocNorm(w.palabra);
const srsRec=(m,w)=>m[srsK(w)]||m[w.id];
function srsBuild(){
  const m=srsLoad(),now=Date.now(),rows=vocUnique(srsWords);
  const seen=rows.filter(w=>{const r=srsRec(m,w);return r&&r.due<=now}).sort((a,b)=>srsRec(m,a).due-srsRec(m,b).due);
  const fresh=rows.filter(w=>!srsRec(m,w));
  return seen.concat(fresh);
}
function srsDueText(n){return n+(n===1?' word due today':' words due today')}
function refreshSrs(){
  const cnt=$('srs-count'),btn=$('srs-start');if(!cnt)return;
  srsWords=VOC.all;
  if($('srs-session').style.display==='block'||$('srs-done').style.display==='block')return;
  const all=srsBuild();
  if(all.length){cnt.textContent=srsDueText(all.length);btn.style.display=''}
  else{cnt.textContent=srsWords.length?'Nothing to review right now':'Save words from your readings and daily list to review them here.';btn.style.display='none'}
}
function srsStart(){
  const all=srsBuild();srsQueue=all.slice(0,SRS_BATCH);srsIdx=0;srsStat={again:0,good:0,easy:0};
  if(!srsQueue.length)return;
  $('srs-done').style.display='none';$('srs-session').style.display='block';$('srs-start').style.display='none';
  prefetchTts(srsQueue.slice(0,3).map(w=>w.palabra));
  srsShow();
}
function srsShow(){
  const w=srsQueue[srsIdx];if(!w){srsFinish();return}
  $('srs-flip').classList.remove('flipped');
  $('srs-word').textContent=w.palabra||'';
  $('srs-meaning').textContent=w.significado||'';
  $('srs-example').innerHTML=w.ejemplo?vocMark(w.ejemplo,w.palabra):'';
  $('srs-ex-row').style.display=w.ejemplo?'flex':'none';
  $('srs-hear').dataset.hear=w.palabra||'';$('srs-hear-ex').dataset.hear=w.ejemplo||'';
  $('srs-reveal-row').style.display='flex';$('srs-grade-row').style.display='none';
  $('srs-pos').textContent=(srsIdx+1)+' / '+srsQueue.length;
  $('srs-fill').style.width=Math.round(srsIdx/srsQueue.length*100)+'%';
  prefetchTts(srsQueue.slice(srsIdx+1,srsIdx+3).map(x=>x.palabra));
  if(settingsAutoplay&&w.palabra)setTimeout(()=>{if(srsQueue[srsIdx]===w&&audioCache.has(w.palabra))hear(w.palabra,$('srs-hear'),true)},400);
}
function srsFlip(){
  if(!srsQueue[srsIdx])return;
  const fc=$('srs-flip'),on=!fc.classList.contains('flipped');
  fc.classList.toggle('flipped',on);
  $('srs-reveal-row').style.display=on?'none':'flex';$('srs-grade-row').style.display=on?'flex':'none';
}
function srsFinish(){
  $('srs-session').style.display='none';
  const left=srsBuild().length;
  $('srs-s-again').textContent=srsStat.again;$('srs-s-good').textContent=srsStat.good;$('srs-s-easy').textContent=srsStat.easy;
  $('srs-more').style.display=left?'':'none';
  $('srs-done-note').textContent=left?srsDueText(left):'Come back tomorrow for more.';
  $('srs-done').style.display='block';
  $('srs-count').textContent=left?srsDueText(left):'Review done!';$('srs-start').style.display='none';
  try{setMascotState('feliz',2600);spawnConfetti()}catch(e){}
}
function srsGrade(g){
  const w=srsQueue[srsIdx];if(!w)return;
  const m=srsLoad(),r=srsRec(m,w)||{box:w.aprendida?2:0};
  const box=g==='again'?0:Math.min(5,r.box+(g==='easy'?2:1));
  m[srsK(w)]={box,due:g==='again'?Date.now()+10*60*1000:Date.now()+SRS_DAYS[box]*86400000};
  srsSave(m);srsStat[g]++;
  if(g==='again'&&!w._rq){w._rq=1;srsQueue.push(w)}
  srsIdx++;srsShow();
}
$('srs-start')?.addEventListener('click',()=>{primeAudio();srsStart()});
$('srs-more')?.addEventListener('click',()=>{primeAudio();srsStart()});
$('srs-reveal')?.addEventListener('click',srsFlip);
$('srs-flip')?.addEventListener('click',e=>{if(e.target.closest('[data-hear]'))return;srsFlip()});
$('srs-flip')?.addEventListener('keydown',e=>{if(e.key===' '||e.key==='Enter'){e.preventDefault();srsFlip()}});
$$('#srs-grade-row [data-grade]').forEach(b=>b.addEventListener('click',()=>srsGrade(b.dataset.grade)));
$('vocab-refresh')?.addEventListener('click',async()=>{primeAudio();busy('vocab-refresh',true,'Cargando...');try{await loadVocabDaily(true)}finally{busy('vocab-refresh',false,'🔄 New words')}});
$$('.vl-tab').forEach(b=>b.addEventListener('click',()=>{VOC.filter=b.dataset.f;VOC.shown=12;$$('.vl-tab').forEach(x=>x.classList.toggle('active',x===b));vocRenderList()}));
$('vocab-search')?.addEventListener('input',e=>{VOC.q=e.target.value;VOC.shown=12;vocRenderList()});
$('vocab-more')?.addEventListener('click',()=>{VOC.shown+=12;vocRenderList()});

/* --- practicar una palabra suelta --- */
$('phoneme-hear')?.addEventListener('click',()=>{if(state.phWord)speak(state.phWord)});
$('phoneme-practice')?.addEventListener('click',()=>{
  if(!state.phWord)return;
  pronMode('lectura');
  $('phrase').textContent=state.phWord;$('translation').textContent='';
  $('pron-result').style.display='none';
  $('panel-lectura')?.scrollIntoView({behavior:'smooth',block:'center'});
  toast('Say it, then press record.');
});

/* --- llamada manos libres (detecta cuándo hablas y cuándo haces pausa) --- */
const vad={on:false,ctx:null,an:null,raf:0,buf:null,floor:0.01,calib:[],voice:0,last:0,started:0,rec:false,starting:false,cool:0,wasBusy:false};
function setHF(on){const b=$('call-handsfree');if(!b)return;b.setAttribute('aria-pressed',on?'true':'false');b.textContent=on?'Hands-free: On':'Hands-free: Off';b.classList.toggle('primary',on);const m=callEl('call-mode-badge');if(m)m.textContent=on?'Hands-free':'Push to talk';callIdle()}
async function vadStart(){
  if(vad.on)return;
  if(!navigator.mediaDevices?.getUserMedia)return toast('Your browser does not support microphone recording.');
  let stream;try{stream=await callGetMic()}catch(e){return toast('Microphone error: '+e.message)}
  const AC=window.AudioContext||window.webkitAudioContext;
  vad.ctx=new AC();if(vad.ctx.state==='suspended')vad.ctx.resume().catch(()=>{});
  vad.an=vad.ctx.createAnalyser();vad.an.fftSize=1024;
  vad.ctx.createMediaStreamSource(stream).connect(vad.an);vad.buf=new Float32Array(vad.an.fftSize);
  vad.on=true;vad.calib=[];vad.voice=0;vad.rec=false;vad.starting=false;vad.cool=performance.now()+600;
  setHF(true);vadLoop();
}
function vadStop(){
  if(!vad.on)return;
  vad.on=false;cancelAnimationFrame(vad.raf);
  try{vad.ctx&&vad.ctx.close()}catch(e){}
  vad.ctx=null;const o=callEl('call-orb');if(o)o.style.setProperty('--lvl','0');setHF(false);
}
function vadLoop(){
  if(!vad.on)return;
  vad.raf=requestAnimationFrame(vadLoop);
  vad.an.getFloatTimeDomainData(vad.buf);
  let sum=0;for(let i=0;i<vad.buf.length;i++)sum+=vad.buf[i]*vad.buf[i];
  const rms=Math.sqrt(sum/vad.buf.length),now=performance.now();
  const orb=callEl('call-orb');if(orb&&!CALL.muted)orb.style.setProperty('--lvl',Math.min(1,rms*9).toFixed(2));
  if(state.callBusy){vad.voice=0;vad.wasBusy=true;return}
  if(vad.wasBusy){vad.wasBusy=false;vad.cool=now+900}
  if(vad.calib.length<40){vad.calib.push(rms);if(vad.calib.length===40)vad.floor=vad.calib.reduce((a,b)=>a+b,0)/40;return}
  const thr=Math.max(vad.floor*3,0.025),talking=$('call-talk-btn').classList.contains('recording');
  if(rms>thr){
    vad.voice++;vad.last=now;
    if(!talking&&!vad.rec&&!vad.starting&&now>vad.cool&&vad.voice>=8&&!CALL.muted){
      vad.rec=true;vad.starting=true;vad.started=now;
      callStartTalk().finally(()=>{vad.starting=false});
    }
  }else if(talking){
    if(vad.rec&&now-vad.last>((teacherOn()||examOn())?2100:1500)&&now-vad.started>900){vad.rec=false;vad.voice=0;vad.cool=now+1200;callStopTalk()}
  }else if(!vad.starting){vad.voice=0;vad.rec=false}
}
$('call-type-send')?.addEventListener('click',callSendTyped);$('call-type-input')?.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();callSendTyped()}});
/* Botón "No sé qué decir": 3 frases para seguir la conversación */
$('call-hint-btn')?.addEventListener('click',async()=>{
  const btn=$('call-hint-btn'),box=$('call-hint-list');if(!btn||!box||btn.disabled)return;
  btn.disabled=true;const old=btn.textContent;btn.textContent='Pensando…';
  try{
    const d=await jsonFetch('/api/llamada/pistas',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({history:state.callMessages.slice(-6)})});
    box.innerHTML=(d.pistas||[]).map((p,i)=>`<div class="ch-item"><div><b data-i18n-skip>${esc(p.en)}</b><small data-i18n-skip>${esc(p.es||'')}</small></div><button type="button" class="btn" data-i="${i}" aria-label="Escuchar">🔊</button></div>`).join('')+'<small class="ch-note">Escucha una, y dila tú en voz alta.</small>';
    box.querySelectorAll('button[data-i]').forEach(b=>b.addEventListener('click',()=>speak(d.pistas[+b.dataset.i].en,.9)));
  }catch(e){toast(e.message||'No pude generar pistas.')}
  finally{btn.disabled=false;btn.textContent=old}
});
$('call-handsfree')?.addEventListener('click',()=>{if(vad.on)vadStop();else vadStart()});
$('call-start')?.addEventListener('click',callStart);
$('call-mute')?.addEventListener('click',callToggleMute);
$('call-skip')?.addEventListener('click',()=>{callSkip();callIdle()});

/* --- prueba de nivel en el onboarding --- */
/* Diagnóstico adaptativo (modelo: tests de colocación reales como Oxford/Cambridge): banco de preguntas por nivel CEFR (0=A1 … 4=C1),
   4 habilidades (gramática, vocabulario, lectura, escucha). La dificultad sube o baja según tus respuestas y termina cuando tu nivel se estabiliza. */
const LV_BANK=[
 /* A1 */
 {l:0,t:'g',q:'My name ___ Carlos.',o:['is','are','am'],a:0},
 {l:0,t:'g',q:'There ___ two books on the table.',o:['are','is','am'],a:0},
 {l:0,t:'g',q:'___ you speak English?',o:['Do','Does','Is'],a:0},
 {l:0,t:'g',q:'He ___ to school by bus.',o:['goes','go','going'],a:0},
 {l:0,t:'v',q:'A person who teaches students is a ___.',o:['teacher','doctor','driver'],a:0},
 {l:0,t:'v',q:'The opposite of "big" is ___.',o:['small','tall','old'],a:0},
 {l:0,t:'v',q:'What day comes after Monday?',o:['Tuesday','Sunday','Friday'],a:0},
 {l:0,t:'r',p:"Hi! I'm Ana. I'm 20 years old. I live in Mexico City with my family. I like music and pizza.",q:'Where does Ana live?',o:['In Mexico City','With friends in Madrid','In a small village'],a:0},
 {l:0,t:'l',s:'My brother is twelve years old and he plays football every Saturday.',q:'How old is the brother?',o:['Twelve','Twenty','Two'],a:0},
 {l:0,t:'l',s:'The shop opens at nine o\'clock in the morning.',q:'When does the shop open?',o:['At nine','At five','At noon'],a:0},
 /* A2 */
 {l:1,t:'g',q:'Yesterday we ___ to the market.',o:['go','went','gone'],a:1},
 {l:1,t:'g',q:"There isn't ___ milk left.",o:['any','some','a'],a:0},
 {l:1,t:'g',q:"I'm ___ than my brother.",o:['taller','more tall','tallest'],a:0},
 {l:1,t:'g',q:'What ___ you doing right now?',o:['are','do','did'],a:0},
 {l:1,t:'v',q:'If you are very tired, you need to ___.',o:['rest','rent','run'],a:0},
 {l:1,t:'v',q:'A place where you can borrow books is a ___.',o:['library','bakery','pharmacy'],a:0},
 {l:1,t:'v',q:'Can you ___ me the way to the station?',o:['show','say','look'],a:0},
 {l:1,t:'r',p:'Tom usually walks to work, but today it is raining, so he is taking the bus. The bus is late, so he will probably arrive at the office after nine.',q:'Why is Tom taking the bus today?',o:['Because it is raining','Because he is late for work','Because he lost his shoes'],a:0},
 {l:1,t:'l',s:'Excuse me, does this train stop at Central Station? No, you need the next one, from platform four.',q:'Where should the man go?',o:['To platform four','To Central Station by bus','To the ticket office'],a:0},
 {l:1,t:'l',s:"I was going to go to the beach on Sunday, but the forecast says it will rain, so I'll visit my grandmother instead.",q:'What will the speaker do on Sunday?',o:['Visit her grandmother','Go to the beach','Watch the rain at home'],a:0},
 /* B1 */
 {l:2,t:'g',q:'She has lived here ___ 2019.',o:['for','since','from'],a:1},
 {l:2,t:'g',q:'If I ___ more time, I would travel more.',o:['have','had','will have'],a:1},
 {l:2,t:'g',q:'I used to ___ football when I was a kid.',o:['play','playing','played'],a:0},
 {l:2,t:'g',q:'The report ___ by the team yesterday.',o:['was finished','finished','has finish'],a:0},
 {l:2,t:'g',q:'He asked me where ___.',o:['I lived','did I live','I did live'],a:0},
 {l:2,t:'v',q:'The flight was ___ because of the storm, so we left the next day.',o:['delayed','delivered','delighted'],a:0},
 {l:2,t:'v',q:'He is very ___: he always arrives on time and finishes his tasks.',o:['reliable','relevant','relative'],a:0},
 {l:2,t:'v',q:'It all ___ on the weather.',o:['depends','decides','deals'],a:0},
 {l:2,t:'r',p:'Many people think working from home is easier, but it can be hard to separate work from free time. Some workers say they end up answering emails late at night. Experts recommend setting a fixed schedule and a dedicated workspace.',q:'What do experts recommend?',o:['A fixed schedule and a dedicated workspace','Answering emails at night','Working only on weekends'],a:0},
 {l:2,t:'l',s:"I'd love to come to your party, but I've got an exam on Monday, so I need to study all weekend. Maybe next time?",q:"Why can't the speaker come?",o:['They need to study for an exam','They are travelling','They are not invited'],a:0},
 {l:2,t:'l',s:'We were going to take the early train, but it was cancelled, so we had to wait nearly two hours for the next one.',q:'What happened to the early train?',o:['It was cancelled','It was full','It was very slow'],a:0},
 /* B2 */
 {l:3,t:'g',q:'By the time we arrived, the movie ___.',o:['already started','has already started','had already started'],a:2},
 {l:3,t:'g',q:'I wish I ___ that job offer last year.',o:['accepted','had accepted','would accept'],a:1},
 {l:3,t:'g',q:'Not only ___ late, but he also forgot the files.',o:['was he','he was','he is'],a:0},
 {l:3,t:'g',q:'She suggested ___ the meeting until Monday.',o:['postponing','to postpone','postpone'],a:0},
 {l:3,t:'g',q:'The project, ___ was due last week, is still unfinished.',o:['which','what','who'],a:0},
 {l:3,t:'v',q:'Her argument was so ___ that nobody could disagree.',o:['convincing','convenient','confident'],a:0},
 {l:3,t:'v',q:'We need to ___ the problem before it gets worse.',o:['tackle','tickle','track'],a:0},
 {l:3,t:'v',q:'He turned down the offer, which means he ___ it.',o:['rejected','accepted','expected'],a:0},
 {l:3,t:'r',p:'Although renewable energy has become cheaper, critics argue that the transition will be slow unless governments remove subsidies for fossil fuels. Supporters counter that abrupt changes could harm workers in traditional industries.',q:"What is the supporters' concern?",o:['Sudden changes could hurt workers in traditional industries','Renewable energy is too expensive','Governments ignore climate change'],a:0},
 {l:3,t:'l',s:"I'd have called you earlier, but my phone died just as I was leaving the office, and I couldn't find a charger anywhere.",q:"Why didn't the speaker call earlier?",o:['Their phone ran out of battery','They forgot the number','They were in a meeting'],a:0},
 {l:3,t:'l',s:'Despite the heavy traffic, we managed to get there on time, which was a relief since the presentation started at nine sharp.',q:'How did the speaker feel?',o:['Relieved','Angry','Bored'],a:0},
 /* C1 */
 {l:4,t:'g',q:'Hardly ___ the door when the phone rang.',o:['had she opened','she had opened','did she open'],a:0},
 {l:4,t:'g',q:"I'd rather you ___ anyone about this.",o:["didn't tell",'don\'t tell',"wouldn't tell"],a:0},
 {l:4,t:'g',q:'Were it not for your help, we ___ the deadline.',o:['would have missed','will miss','had missed'],a:0},
 {l:4,t:'g',q:'The more you practise, ___ you become.',o:['the more confident','more confident','the most confident'],a:0},
 {l:4,t:'v',q:'His speech was full of ___ remarks that offended several guests.',o:['disparaging','dispassionate','disposable'],a:0},
 {l:4,t:'v',q:'The new policy will ___ a significant change in how we work.',o:['entail','entitle','entice'],a:0},
 {l:4,t:'v',q:'She is known for her ___ attention to detail; nothing escapes her.',o:['meticulous','mediocre','malicious'],a:0},
 {l:4,t:'r',p:"The study's findings, while intriguing, should be interpreted with caution: the sample was small, participants were self-selected, and the effect, though statistically significant, was modest in size.",q:'What does the writer suggest about the study?',o:['Its conclusions should not be overstated','Its sample was unusually large','Its effect was dramatic'],a:0},
 {l:4,t:'l',s:"It's not that I disagree with the proposal as such; I just feel we haven't thought through its long-term implications.",q:"What is the speaker's attitude?",o:['Cautious but not opposed','Strongly against','Fully enthusiastic'],a:0},
 {l:4,t:'l',s:'Had the committee consulted the staff beforehand, the backlash might well have been avoided.',q:'What does the speaker imply?',o:['The committee did not consult the staff','The staff were consulted','There was no backlash'],a:0}
];
const LV_NAMES=['beginner','elementary','intermediate','advanced'];
const LV_LABEL={beginner:'Beginner (A1)',elementary:'Elementary (A2)',intermediate:'Intermediate (B1)',advanced:'Advanced (B2+)'};
const LV_CEFR=['A1','A2','B1','B2','C1'];
const LV_SKILL={g:'Grammar',v:'Vocabulary',r:'Reading',l:'Listening'};
const T=x=>window.TalvoI18n?TalvoI18n.tr(x):x;
const LV_MIN=14,LV_MAX=24;
const lv={c:2,n:0,dk:0,seen:new Set(),log:[],cs:[],best:{},cur:null,plays:0,order:['g','v','l','r']};
function lvCanSpeak(){return 'speechSynthesis' in window}
function lvPickItem(){
  const skills=lv.order.filter(s=>s!=='l'||lvCanSpeak());
  const skill=skills[lv.n%skills.length];
  const mid=lv.c-.5;
  const pool=LV_BANK.map((it,i)=>({it,i})).filter(x=>!lv.seen.has(x.i)&&x.it.t===skill);
  pool.sort((a,b)=>Math.abs(a.it.l-mid)-Math.abs(b.it.l-mid)||Math.random()-.5);
  const hit=pool[0]||LV_BANK.map((it,i)=>({it,i})).filter(x=>!lv.seen.has(x.i)&&(x.it.t!=='l'||lvCanSpeak())).sort((a,b)=>Math.abs(a.it.l-mid)-Math.abs(b.it.l-mid))[0];
  return hit||null;
}
function lvShow(){
  const hit=lvPickItem();if(!hit)return lvFinish();
  lv.seen.add(hit.i);const it=hit.it;lv.cur=it;lv.plays=0;
  $('ob-test-count').textContent=T('Question ')+(lv.n+1)+' · '+T(LV_SKILL[it.t]);
  $('ob-test-fill').style.width=Math.min(96,Math.round(lv.n/LV_MIN*100))+'%';
  $('ob-test-q').textContent=it.q;
  let extra='';
  if(it.t==='r')extra='<div class="ob-passage" data-i18n-skip>'+esc(it.p)+'</div>';
  if(it.t==='l')extra='<div class="ob-listen"><button type="button" class="btn" id="ob-play">🔊 Listen</button><small id="ob-plays">You can listen twice.</small></div>';
  $('ob-test-extra').innerHTML=extra;
  const opts=it.o.map((t,i)=>({t,i})).sort(()=>Math.random()-.5);
  $('ob-test-options').innerHTML=opts.map(x=>'<button type="button" class="ob-option" data-i="'+x.i+'" data-i18n-skip>'+esc(x.t)+'</button>').join('')
   +'<button type="button" class="ob-option ob-dk" data-i="-1">🤷 I don\'t know</button>';
  if(it.t==='l')setTimeout(()=>lvPlay(),350);
}
function lvPlay(){
  if(!lv.cur||lv.cur.t!=='l'||lv.plays>=2)return;
  lv.plays++;try{speak(lv.cur.s,.9)}catch(e){}
  const b=$('ob-plays');if(b)b.textContent=lv.plays>=2?T('No more plays for this question.'):T('You can listen once more.');
  if(lv.plays>=2){const p=$('ob-play');if(p)p.disabled=true}
}
/* Estimación por máxima verosimilitud: c = cuántos niveles dominas (0…5). Si l<c aciertas casi siempre (90%); si l>=c solo por azar (30%). "No sé" casi nunca es acierto. */
function lvMLE(){
  let bestC=0,bestLL=-1e9;
  for(let c=0;c<=5;c++){
    let ll=0;
    lv.log.forEach(r=>{const know=r.l<c,p=r.dk?(know?.15:.02):(know?.9:.3);ll+=Math.log(r.ok?p:1-p)});
    ll+=Math.log(c===lv.c?1.001:1);   // desempate: conserva la estimación anterior
    if(ll>bestLL+1e-9){bestLL=ll;bestC=c}
  }
  return bestC;
}
function lvAnswer(i){
  const it=lv.cur,ok=i===it.a;
  if(i===-1)lv.dk++;
  lv.n++;lv.log.push({l:it.l,ok,dk:i===-1});
  if(ok)lv.best[it.t]=Math.max(lv.best[it.t]??-1,it.l);
  lv.c=lvMLE();lv.cs.push(lv.c);
  if(lv.n>=LV_MAX||lvStable())return lvFinish();
  lvShow();
}
function lvStable(){
  if(lv.n<LV_MIN)return false;
  const last=lv.cs.slice(-5);
  return last.every(x=>x===last[0]);
}
function lvFinish(){
  const c=lv.c,rank=Math.min(3,c),cefr=LV_CEFR[Math.min(4,c)];
  const lvl=LV_NAMES[rank];
  obAnswers.cefr_level=lvl;
  $('ob-result-title').textContent=T('Your level: ')+LV_LABEL[lvl];
  $('ob-result-text').textContent=T('Estimated CEFR level: ')+cefr+'. '+(rank===0?T('We will start from the very beginning, step by step.'):T('Your path starts at ')+LV_CEFR[rank]+T(' and the earlier sections are marked as already known.'))+(lv.dk?' '+T('You answered "I don\'t know" ')+lv.dk+'x — '+T('that helps us place you accurately.'):'')+' '+T('It keeps adapting to your results as you practice.');
  $('ob-result-tiers').innerHTML=Object.keys(LV_SKILL).filter(k=>lv.best[k]!=null||LV_BANK.some(x=>x.t===k&&lv.seen.has(LV_BANK.indexOf(x)))).map(k=>'<span class="ob-tier '+(lv.best[k]!=null?'ok':'no')+'" data-i18n-skip>'+T(LV_SKILL[k])+' · '+(lv.best[k]!=null?LV_CEFR[lv.best[k]]:'&lt;A1')+'</span>').join('');
  $('ob-result-adjust').innerHTML='<small>'+T('Doesn\'t look right? Choose another level:')+'</small><div class="ob-adj">'+LV_NAMES.map(n=>'<button type="button" class="ob-option'+(n===lvl?' selected':'')+'" data-lv="'+n+'" data-i18n-skip>'+LV_LABEL[n]+'</button>').join('')+'</div>';
  showObStep(5);
}
$('ob-start-test')?.addEventListener('click',()=>{Object.assign(lv,{c:2,n:0,dk:0,seen:new Set(),log:[],cs:[],best:{},cur:null});showObStep(4);lvShow()});
$('ob-test-extra')?.addEventListener('click',e=>{if(e.target.closest('#ob-play'))lvPlay()});
$('ob-test-options')?.addEventListener('click',e=>{
  const b=e.target.closest('.ob-option');if(!b||!lv.cur)return;
  lvAnswer(Number(b.dataset.i));
});
$('ob-result-adjust')?.addEventListener('click',e=>{
  const b=e.target.closest('[data-lv]');if(!b)return;
  obAnswers.cefr_level=b.dataset.lv;
  $$('#ob-result-adjust .ob-option').forEach(x=>x.classList.toggle('selected',x===b));
  $('ob-result-title').textContent=T('Your level: ')+LV_LABEL[b.dataset.lv];
});
$('ob-result-continue')?.addEventListener('click',()=>finishOnboarding());


/* ===== Panel de administración ===== */
const adm={tab:'resumen',loaded:{},filter:'todos',evf:'',q:'',sort:'reciente',offset:0,t:0,init:false,users:{}};
const ADM_T={pronunciacion:['🗣️','Pronunciación'],escritura:['✍️','Escritura'],lectura:['📖','Lectura'],dictado:['🎧','Dictado'],tutor:['🤖','Tutor'],llamada:['📞','Llamada'],leccion:['📚','Lección (ruta)'],ruta:['🧭','Mis rutas'],traductor:['🌐','Traductor'],diccionario:['📘','Diccionario'],escenario:['🎭','Rol'],ruta_nueva:['✨','Ruta creada'],reunion:['🗣️','Reunión'],shadowing_tema:['🔁','Shadowing tema'],clip:['🎬','Clips'],presentacion:['🎤','Presentación']};
const ADM_E={pagado:['Pagado','st-pagado'],prueba:['En prueba','st-prueba'],vencido:['Vencido','st-vencido']};
const ADM_GOAL={work:'Trabajo',travel:'Viajes',study:'Estudios',exams:'Exámenes',growth:'Crecimiento personal'};
function admAgo(iso){if(!iso)return 'nunca';const s=(Date.now()-new Date(iso).getTime())/1000;if(isNaN(s))return '—';if(s<60)return 'hace un momento';if(s<3600)return 'hace '+Math.floor(s/60)+' min';if(s<86400)return 'hace '+Math.floor(s/3600)+' h';if(s<2592000)return 'hace '+Math.floor(s/86400)+' d';return 'hace '+Math.floor(s/2592000)+' mes(es)'}
function admDate(iso){if(!iso)return '—';const d=new Date(iso);if(isNaN(d))return '—';return d.toLocaleString('es-MX',{timeZone:'America/Mexico_City',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})}
function admShort(iso){const d=new Date(iso+'T12:00:00');return isNaN(d)?'':d.toLocaleDateString('es-MX',{day:'2-digit',month:'short'})}
function admFetch(path,fresh){const sep=path.includes('?')?'&':'?';return Promise.race([jsonFetch(path+(fresh?sep+'fresh=1':'')),new Promise((_,rej)=>setTimeout(()=>rej(new Error('El servidor tardó demasiado en responder.')),45000))])}
function admErr(el,msg){el.innerHTML='<div class="notice adm-err">⚠ '+esc(msg)+' <button type="button" class="btn" data-adm-retry="1">Reintentar</button></div>'}
function admWarn(list){const box=$('admin-warn');const w=(list||[]).filter(Boolean);box.style.display=w.length?'block':'none';box.innerHTML=w.length?'<b>⚠ Datos parciales o con problemas</b><ul class="list" style="margin:6px 0 0">'+w.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':''}
function admStamp(){adm.t=Date.now();admTick()}
function admTick(){const el=$('admin-updated');if(el)el.textContent=adm.t?'Actualizado '+admAgo(new Date(adm.t).toISOString()):''}
function admScoreCls(v){return v>=80?'good':v>=60?'mid':'low'}
function admRow(label,n,max,extra){const pct=max?Math.round(n/max*100):0;return '<div class="adm-row"><span>'+label+'</span><div class="bar"><div class="fill" style="width:'+pct+'%"></div></div><b>'+n+(extra?' <small>'+extra+'</small>':'')+'</b></div>'}
function admUserLink(id,email,right){return '<button type="button" class="adm-list-item" data-adm-user="'+esc(email)+'"><span>'+esc(email||id.slice(0,8))+'</span><span>'+right+'</span></button>'}

function admPagos(d){
  const p=d.pagos||{},s=d.soporte;
  const k=(v,l,sub,c)=>'<div class="report '+(c||'')+'"><b>'+v+'</b><small>'+l+'</small>'+(sub?'<em>'+sub+'</em>':'')+'</div>';
  const ren=(p.por_renovar||[]).map(x=>admUserLink(x.id,x.email,x.dias>=0?'renueva en '+x.dias+' d':'venció hace '+Math.abs(x.dias)+' d')).join('')||'<div class="empty">'+(p.registro_activo?'Ningún pago vence en los próximos 5 días.':'Activa el registro de pagos para ver vencimientos.')+'</div>';
  let sup='';
  if(s){sup=(s.recientes||[]).map(m=>'<button type="button" class="adm-list-item" data-adm-user="'+esc(m.email||'')+'"><span><b>'+esc(m.tipo||'')+'</b> · '+esc(m.mensaje)+'</span><span>'+admAgo(m.fecha)+'</span></button>').join('')||'<div class="empty">Sin mensajes en 7 días.</div>'}
  return '<h2 class="sec-h">Pagos y soporte</h2><div class="adm-kpis">'+k((p.por_renovar||[]).length,'Pagos por renovar','Vencen en ≤5 días o ya vencieron',(p.por_renovar||[]).length?'warn':'')+k(p.sin_fecha==null?'—':p.sin_fecha,'Pagados sin fecha de vencimiento',p.registro_activo?'Actívalos de nuevo con el botón para registrar su fecha':'Falta crear la tabla admin_acciones (pestaña Sistema)',p.sin_fecha?'warn':'')+(s?k(s.total_7d,'Mensajes de soporte (7 d)','De pagos: '+s.pago_7d,s.pago_7d?'warn':''):'')+'</div>'+
   '<div class="adm-two"><div><h3>Pagos por renovar</h3>'+ren+'</div>'+(s?'<div><h3>Soporte reciente</h3>'+sup+'</div>':'<div></div>')+'</div>';
}
async function admResumen(fresh){
  const box=$('admin-resumen');if(!adm.loaded.resumen)box.innerHTML='<div class="empty">'+pqLoader('sm')+'</div>';
  try{
    const d=await admFetch('/api/admin/resumen',fresh);admWarn(d.warnings);admStamp();adm.loaded.resumen=Date.now();
    const u=d.usuarios,a=d.actividad,e=d.estados;adm.price=d.precio_mxn;
    const k=(v,l,sub,c)=>'<div class="report '+(c||'')+'"><b>'+v+'</b><small>'+l+'</small>'+(sub?'<em>'+sub+'</em>':'')+'</div>';
    const maxEv=Math.max(1,...d.serie_14d.map(x=>x.eventos));
    const days=d.serie_14d.map(x=>'<div class="adm-col" title="'+esc(admShort(x.fecha))+': '+x.eventos+' actividades, '+x.usuarios+' usuarios, '+x.registros+' registros"><b>'+x.eventos+'</b><div class="adm-bar" style="height:'+Math.round(x.eventos/maxEv*100)+'px"></div><small>'+esc(admShort(x.fecha).slice(0,2))+'</small><em>👤'+x.usuarios+'</em></div>').join('');
    const tipos=Object.keys(ADM_T);const maxT=Math.max(1,...tipos.map(t=>d.tipos_7d[t]||0));
    const tipoRows=tipos.map(t=>admRow(ADM_T[t][0]+' '+ADM_T[t][1],d.tipos_7d[t]||0,maxT,'hoy '+(d.tipos_24h[t]||0))).join('');
    const top0=d.embudo[0].n||0;
    const funnel=d.embudo.map((p,i)=>admRow(esc(p.paso),p.n,top0,top0?Math.round(p.n/top0*100)+'%':'')).join('');
    const lv=Object.entries(d.niveles).sort((x,y)=>y[1]-x[1]);const maxL=Math.max(1,...lv.map(x=>x[1]));
    const lvRows=lv.map(x=>admRow(esc(x[0]),x[1],maxL)).join('');
    const go=Object.entries(d.objetivos).sort((x,y)=>y[1]-x[1]);const maxG=Math.max(1,...go.map(x=>x[1]));
    const goRows=go.map(x=>admRow(esc(ADM_GOAL[x[0]]||x[0]),x[1],maxG)).join('');
    const venc=(d.por_vencer||[]).map(x=>admUserLink(x.id,x.email,'quedan '+x.dias+' d')).join('')||'<div class="empty">Nadie vence en los próximos 3 días.</div>';
    const top=(d.top_7d||[]).map(x=>admUserLink(x.id,x.email,x.act_7d+' act. · '+x.total+' total')).join('')||'<div class="empty">Sin actividad en 7 días.</div>';
    const ret=d.retencion_7d;
    const H=d.hoy||{usuarios:0,eventos:0,minutos:0,xp:0,tipos:{},lista:[],por_hora:[]};const CR=d.creditos||{por_funcion_7d:{},top_24h:[],total_24h:0,total_7d:0};
    const maxH=Math.max(1,...(H.por_hora||[0]));
    const hrs=(H.por_hora||[]).map((n,i)=>'<div class="adm-col" title="'+i+':00 · '+n+' actividades"><div class="adm-bar" style="height:'+Math.round(n/maxH*60)+'px"></div><small>'+(i%3===0?i:'')+'</small></div>').join('');
    const hoyTipos=Object.entries(H.tipos||{}).sort((a,b)=>b[1]-a[1]).map(([t,n])=>'<span class="badge">'+(ADM_T[t]?ADM_T[t][0]+' '+ADM_T[t][1]:esc(t))+' ×'+n+'</span>').join(' ')||'<span class="admin-updated">Todavía nadie ha practicado hoy.</span>';
    const hoyLista=(H.lista||[]).map(x=>admUserLink(x.id,x.email,x.n+' act. · '+x.min+' min · '+admAgo(x.ultima))).join('')||'<div class="empty">Nadie ha practicado hoy (hora de México).</div>';
    const crF=Object.entries(CR.por_funcion_7d||{});const maxC=Math.max(1,...crF.map(x=>x[1]));
    const crRows=crF.map(x=>admRow(esc(x[0]),x[1],maxC,'créditos')).join('')||'<div class="empty">Sin consumo registrado (crea la tabla con admin_mejoras.sql).</div>';
    const crTop=(CR.top_24h||[]).map(x=>admUserLink(x.id,x.email,x.creditos+' créd.')).join('')||'<div class="empty">Sin consumo en 24 h.</div>';
    const hoyHtml='<h2 class="sec-h">Hoy ('+esc(admShort(H.fecha||new Date().toISOString().slice(0,10)))+', hora de México)</h2><div class="adm-kpis">'+k(H.usuarios,'Usuarios que practicaron hoy','Nuevos hoy: '+(H.nuevos||0),H.usuarios?'good':'')+k(H.eventos,'Actividades hoy','Lecciones, rutas, voz, tutor y más')+k(H.minutos,'Minutos de práctica','Medidos en lecciones')+k(H.xp,'XP ganado hoy')+'</div><div class="adm-chips" style="flex-wrap:wrap;overflow:visible;margin:8px 0">'+hoyTipos+'</div><div class="adm-days" style="height:auto">'+hrs+'</div><p class="adm-legend">Actividad de hoy por hora (0–23).</p><div class="adm-two"><div><h3>Quién practicó hoy</h3>'+hoyLista+'</div><div><h3>Créditos de IA</h3><div class="adm-kpis">'+k(CR.total_24h,'Créditos 24 h')+k(CR.total_7d,'Créditos 7 días')+'</div>'+crRows+'<h3>Mayor consumo (24 h)</h3>'+crTop+'</div></div>';
    box.innerHTML=hoyHtml+
     '<h2 class="sec-h">Usuarios</h2><div class="adm-kpis">'+k(u.total,'Usuarios totales','Confirmados: '+u.confirmados)+k(u.nuevos_7d,'Nuevos (7 días)','24 h: '+u.nuevos_24h+' · 30 d: '+u.nuevos_30d)+k(d.sin_actividad_3d,'Sin ninguna práctica','Registrados hace más de 3 días',d.sin_actividad_3d?'warn':'')+k(ret.pct==null?'—':ret.pct+'%','Retención a 7 días',ret.retenidos+' de '+ret.elegibles+' practicaron esta semana')+'</div>'+
     '<h2 class="sec-h">Actividad</h2><div class="adm-kpis">'+k(a.ahora_15min,'Practicando ahora','Últimos 15 min',a.ahora_15min?'good':'')+k(a.activos_24h,'Activos 24 h',a.eventos_24h+' actividades')+k(a.activos_7d,'Activos 7 días',a.eventos_7d+' actividades')+k(a.activos_30d,'Activos 30 días')+'</div>'+
     '<h2 class="sec-h">Suscripciones</h2><div class="adm-kpis">'+k(e.pagado,'Pagando','',e.pagado?'good':'')+k(e.prueba,'En prueba')+k(e.vencido,'Prueba vencida','Sin acceso hasta que paguen',e.vencido?'warn':'')+k('$'+d.mrr_estimado,'Ingreso mensual estimado','Pagando × $'+d.precio_mxn+' MXN (no son pagos registrados)')+'</div>'+
     admPagos(d)+
     '<h2 class="sec-h">Actividades por día (14 días)</h2><div class="adm-days">'+days+'</div><p class="adm-legend">Número grande = actividades · 👤 = usuarios distintos que practicaron ese día.</p>'+
     '<div class="adm-two"><div><h2 class="sec-h">Qué practican (7 días)</h2>'+tipoRows+'</div><div><h2 class="sec-h">Embudo</h2>'+funnel+'</div></div>'+
     '<div class="adm-two"><div><h2 class="sec-h">Pruebas que vencen pronto</h2>'+venc+'</div><div><h2 class="sec-h">Más activos (7 días)</h2>'+top+'</div></div>'+
     '<div class="adm-two"><div><h2 class="sec-h">Nivel declarado</h2>'+lvRows+'</div><div><h2 class="sec-h">Objetivo</h2>'+goRows+'</div></div>'+
     '<p class="adm-legend">'+esc(d.nota||'')+'</p>';
  }catch(err){admErr(box,err.message)}
}

function admRowHead(u){
  const [lbl,cls]=ADM_E[u.estado]||['—',''];
  let extra='';
  if(u.estado==='prueba')extra=' · '+u.dias_restantes+' d';
  else if(u.estado==='pagado'&&u.dias_renovar!=null)extra=u.dias_renovar>=0?' · renueva en '+u.dias_renovar+' d':' · venció hace '+Math.abs(u.dias_renovar)+' d';
  return '<div class="ur-main"><b>'+esc(u.email||u.id.slice(0,8))+(u.es_admin?' <span class="estado st-admin">admin</span>':'')+'</b><small>'+esc(u.username||'sin nombre')+' · '+esc(u.cefr_level||'nivel sin definir')+'</small></div><span class="estado '+cls+'">'+lbl+extra+'</span><div class="ur-meta"><span>Última práctica: '+admAgo(u.last_activity)+'</span><span>'+u.total+' act. · '+u.act_7d+' en 7 d · 🔥 '+u.racha+'</span><span>Registro: '+admDate(u.created_at)+'</span></div>';
}
function admUserRow(u){adm.users[u.id]=u;return '<div class="user-item" id="ui-'+esc(u.id)+'"><button type="button" class="user-row" data-uid="'+esc(u.id)+'">'+admRowHead(u)+'</button><div class="user-detail" id="ud-'+esc(u.id)+'" style="display:none"></div></div>'}
async function admUsuarios(reset,fresh){
  const list=$('admin-users');
  if(reset){adm.offset=0;list.innerHTML='<div class="empty">'+pqLoader('sm')+'</div>'}
  try{
    const d=await admFetch('/api/admin/usuarios?q='+encodeURIComponent(adm.q)+'&estado='+adm.filter+'&orden='+adm.sort+'&limit=30&offset='+adm.offset,fresh);
    admWarn(d.warnings);admStamp();adm.loaded.usuarios=Date.now();
    const html=d.usuarios.map(admUserRow).join('');
    if(reset)list.innerHTML=html||'<div class="empty">Sin resultados con esos filtros.</div>';else list.insertAdjacentHTML('beforeend',html);
    adm.offset+=d.usuarios.length;
    $('admin-count').textContent=d.total+(d.total===1?' usuario':' usuarios');
    $('admin-more').style.display=adm.offset<d.total?'':'none';
  }catch(err){if(reset)admErr(list,err.message);else toast(err.message)}
}
function admCopy(text){
  if(navigator.clipboard&&navigator.clipboard.writeText)return navigator.clipboard.writeText(text);
  const t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();try{document.execCommand('copy')}catch(e){}t.remove();return Promise.resolve();
}
function admReminder(u){
  const precio=adm.price||79;
  if(u.estado==='prueba')return 'Hola 👋 Tu prueba gratis de Talvo English termina en '+u.dias_restantes+' día(s). Si quieres seguir practicando, la suscripción cuesta $'+precio+' MXN al mes. ¿Te comparto los datos para activarla?';
  if(u.estado==='vencido')return 'Hola 👋 Tu prueba de Talvo English ya terminó. Si quieres seguir practicando, la suscripción cuesta $'+precio+' MXN al mes. ¿Te comparto los datos de pago?';
  if(u.estado==='pagado'&&u.dias_renovar!=null&&u.dias_renovar<=5)return 'Hola 👋 Tu suscripción de Talvo English '+(u.dias_renovar<=0?'ya venció':'vence en '+u.dias_renovar+' día(s)')+'. ¿Quieres renovarla por $'+precio+' MXN? Te comparto los datos de pago.';
  return '';
}
function admAccessPanel(u,d){
  const id=esc(u.id),paid=u.estado==='pagado';
  let estado;
  if(paid)estado=u.dias_renovar==null?'Acceso de pago activo (sin fecha de vencimiento registrada).':(u.dias_renovar>=0?'Pago activo · cubre hasta '+admDate(u.vence_pago):'Según el registro, el pago venció el '+admDate(u.vence_pago)+' · el acceso sigue activo hasta que lo quites');
  else if(u.estado==='prueba')estado='En prueba hasta '+admDate(u.trial_ends_at);
  else estado='Sin acceso · la prueba terminó el '+admDate(u.trial_ends_at);
  const dias='<select class="input" id="acc-dias-'+id+'"><option value="30">30 días</option><option value="60">60 días</option><option value="90">90 días</option><option value="365">1 año</option></select>';
  const prueba='<select class="input" id="acc-prueba-'+id+'"><option value="3">+3 días</option><option value="7" selected>+7 días</option><option value="14">+14 días</option></select>';
  const rem=admReminder(u);
  const curPlan=(d&&d.plan&&d.plan!=='gratis')?d.plan:'basico';
  const planSel='<select class="input" id="acc-plan-'+id+'">'+['basico','pro','max'].map(p=>'<option value="'+p+'"'+(curPlan===p?' selected':'')+'>Plan '+ADM_PLAN[p]+'</option>').join('')+'</select>';
  const uso=d&&d.uso?'<small>Plan actual: <b>'+esc(d.uso.plan_nombre)+'</b> · últimas 5 h: '+d.uso.ventana.usado+' / '+d.uso.ventana.limite+' · hoy: '+d.uso.dia.usado+' / '+d.uso.dia.limite+'</small>':'';
  const planRow='<div class="adm-acts">'+planSel+(paid?'<button type="button" class="btn" data-acc="cambiar_plan" data-uid="'+id+'">🔀 Cambiar plan</button>':'')+'<button type="button" class="btn" data-acc="reiniciar_uso" data-uid="'+id+'">♻ Reiniciar su cuota</button></div>';
  return '<div class="adm-access"><b>Acceso y pagos</b><small>'+esc(estado)+'</small>'+uso+planRow+
   '<div class="adm-acts">'+dias+'<button type="button" class="btn primary" data-acc="'+(paid?'renovar':'activar')+'" data-uid="'+id+'">'+(paid?'🔁 Renovar pago':'✅ Activar pago')+'</button>'+(paid?'<button type="button" class="btn danger" data-acc="desactivar" data-uid="'+id+'">⛔ Quitar acceso de pago</button>':'')+'</div>'+
   (paid?'':'<div class="adm-acts">'+prueba+'<button type="button" class="btn" data-acc="extender_prueba" data-uid="'+id+'">⏱ Extender prueba</button></div>')+
   (rem?'<div class="adm-acts"><button type="button" class="btn" data-copy="'+id+'">📋 Copiar recordatorio</button></div>':'')+
   (d&&d.registro_activo===false?'<small style="color:var(--warning)">⚠ Los cambios se aplican, pero no queda registro ni fecha de vencimiento. Crea la tabla con admin_acciones.sql (pestaña Sistema).</small>':'')+'</div>';
}
async function admLoadDetail(id){
  const box=$('ud-'+id);if(!box)return;
  box.innerHTML='<div class="empty">'+pqLoader('sm')+'</div>';
  try{
    const d=await admFetch('/api/admin/usuario/'+encodeURIComponent(id));const u=d.usuario;adm.users[id]=u;
    const cell=(v,l)=>'<div><b>'+v+'</b><small>'+l+'</small></div>';
    const tipos=Object.entries(u.tipos||{}).map(([t,n])=>'<span class="badge">'+(ADM_T[t]?ADM_T[t][0]+' '+ADM_T[t][1]:esc(t))+' ×'+n+'</span>').join('')||'<span class="admin-updated">Todavía no ha practicado.</span>';
    const ev=(d.recientes||[]).map(x=>'<div class="ud-ev"><span>'+(ADM_T[x.tipo]?ADM_T[x.tipo][0]:'•')+'</span><span>'+(ADM_T[x.tipo]?ADM_T[x.tipo][1]:esc(x.tipo))+' <small>· '+admAgo(x.fecha)+'</small></span>'+(x.score!=null?'<span class="adm-score '+admScoreCls(x.score)+'">'+Math.round(x.score)+'</span>':'<span></span>')+(x.detalle?'<span class="adm-d">'+esc(x.detalle)+(x.seg?' · '+Math.round(x.seg/60*10)/10+' min':'')+(x.xp?' · +'+x.xp+' XP':'')+'</span>':'')+'</div>').join('')||'<div class="admin-updated">Sin actividad.</div>';
    const words=(d.palabras||[]).map(w=>'<span class="chip">'+esc(w.palabra)+'</span>').join('');
    const sup=(d.soporte||[]).map(m=>'<div class="adm-sup"><b>'+esc(m.tipo||'mensaje')+'</b> · '+admDate(m.created_at)+'<small>'+esc(m.mensaje||'')+'</small></div>').join('');
    const NA={activar:'Activó pago',renovar:'Renovó pago',desactivar:'Quitó acceso de pago',extender_prueba:'Extendió prueba'};
    const hist=(d.acciones||[]).map(a=>'<div class="adm-hist"><span>'+(NA[a.accion]||esc(a.accion))+(a.dias&&a.accion!=='desactivar'?' · '+a.dias+' d':'')+'</span><span>'+admDate(a.created_at)+'</span>'+(a.nota?'<small>'+esc(a.nota)+'</small>':'')+'</div>').join('');
    box.innerHTML=admAccessPanel(u,d)+
     '<div class="ud-grid">'+cell(admDate(u.created_at),'Registro')+cell(admDate(u.last_sign_in),'Último acceso')+cell(admDate(u.last_activity),'Última práctica')+cell(u.estado==='prueba'?admDate(u.trial_ends_at):u.estado==='pagado'?'Suscripción activa':'Venció '+admDate(u.trial_ends_at),u.estado==='prueba'?'La prueba termina':'Acceso')+
     cell(u.act_hoy+' · '+u.min_hoy+' min','Hoy: actividades · minutos')+cell(u.total+' / '+u.act_7d+' / '+u.act_30d,'Actividades: total / 7 d / 30 d')+cell(u.min_7d+' min · '+u.xp_7d+' XP','Últimos 7 días')+cell(u.creditos_24h+' / '+u.creditos_7d,'Créditos IA: 24 h / 7 d')+cell(u.prom_score==null?'—':u.prom_score,'Calificación promedio')+cell('🔥 '+u.racha+' d','Racha actual')+cell(u.palabras,'Palabras guardadas')+
     cell(esc(ADM_GOAL[u.learning_goal]||u.learning_goal||'—'),'Objetivo')+cell(u.daily_goal_minutes?u.daily_goal_minutes+' min':'—','Meta diaria')+cell('💎 '+u.gems,'Gemas')+cell(u.onboarded?'Sí':'No',u.confirmado?'Onboarding · correo confirmado':'Onboarding · correo SIN confirmar')+'</div>'+
     '<div class="adm-chips" style="flex-wrap:wrap;overflow:visible;margin:8px 0">'+tipos+'</div>'+
     udDias(d)+udFunc(u)+(hist?'<h3>Historial de cambios de acceso</h3>'+hist:'')+
     '<h3>Últimas actividades</h3>'+ev+(words?'<h3>Palabras guardadas</h3><div class="chips">'+words+'</div>':'')+(sup?'<h3>Mensajes de soporte</h3>'+sup:'')+
     '<p class="admin-updated" style="margin-top:12px">ID: '+esc(u.id)+'</p>';
    box.dataset.ready='1';
  }catch(err){admErr(box,err.message)}
}
function udDias(d){const a=d.dias14||[];if(!a.length)return '';const m=Math.max(1,...a.map(x=>x.n));return '<h3>Últimos 14 días</h3><div class="adm-days">'+a.map(x=>'<div class="adm-col" title="'+esc(admShort(x.fecha))+': '+x.n+'"><b>'+x.n+'</b><div class="adm-bar" style="height:'+Math.round(x.n/m*60)+'px"></div><small>'+esc(admShort(x.fecha).slice(0,2))+'</small></div>').join('')+'</div>'}
function udFunc(u){const f=Object.entries(u.por_funcion_7d||{});if(!f.length)return '';const m=Math.max(1,...f.map(x=>x[1]));return '<h3>Consumo de IA por función (7 d)</h3>'+f.map(x=>admRow(esc(x[0]),x[1],m,'créditos')).join('')}
async function admToggleUser(id){
  const box=$('ud-'+id);if(!box)return;
  if(box.style.display==='block'){box.style.display='none';return}
  box.style.display='block';
  if(!box.dataset.ready)await admLoadDetail(id);
}
async function admAcceso(btn){
  const id=btn.dataset.uid,accion=btn.dataset.acc,u=adm.users[id]||{};
  let dias=30;
  if(accion==='extender_prueba')dias=Number(($('acc-prueba-'+id)||{}).value||7);
  else if(accion!=='desactivar')dias=Number(($('acc-dias-'+id)||{}).value||30);
  const quien=u.email||id,plan=(($('acc-plan-'+id)||{}).value)||'basico';
  const pregunta={activar:'¿Activar el acceso de pago de '+quien+' por '+dias+' días?',renovar:'¿Renovar el pago de '+quien+' por '+dias+' días más?',desactivar:'¿QUITAR el acceso de pago de '+quien+'? Dejará de poder practicar.',extender_prueba:'¿Extender la prueba de '+quien+' por '+dias+' días?',cambiar_plan:'¿Cambiar el plan de '+quien+' a '+ADM_PLAN[plan]+'?',reiniciar_uso:'¿Reiniciar la cuota de '+quien+'? Volverá a tener todos sus mensajes.'}[accion];
  if(!window.confirm(pregunta))return;
  btn.disabled=true;
  try{
    const d=await jsonFetch('/api/admin/usuario/'+encodeURIComponent(id)+'/acceso',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({accion:accion,dias:dias,plan:plan,confirmar:true})});
    toast(d.mensaje);
    if(d.aviso)setTimeout(()=>toast(d.aviso),3400);
    if(d.usuario){adm.users[id]=d.usuario;const row=document.querySelector('#ui-'+CSS.escape(id)+' .user-row');if(row)row.innerHTML=admRowHead(d.usuario)}
    adm.loaded.resumen=0;adm.loaded.usuarios=0;
    await admLoadDetail(id);
  }catch(err){toast(err.message);btn.disabled=false}
}
async function admExport(){
  const btn=$('admin-export');btn.disabled=true;toast('Preparando el archivo…');
  try{
    let off=0,total=1,rows=[];
    while(off<total){const d=await admFetch('/api/admin/usuarios?q='+encodeURIComponent(adm.q)+'&estado='+adm.filter+'&orden='+adm.sort+'&limit=100&offset='+off,off===0);total=d.total;rows=rows.concat(d.usuarios);off+=d.usuarios.length;if(!d.usuarios.length)break}
    const cols=[['Correo','email'],['Nombre','username'],['Estado','estado'],['Días de prueba restantes','dias_restantes'],['Pago vence','vence_pago'],['Registro','created_at'],['Último acceso','last_sign_in'],['Última práctica','last_activity'],['Actividades totales','total'],['Actividades 7 d','act_7d'],['Actividades 30 d','act_30d'],['Calificación promedio','prom_score'],['Racha','racha'],['Palabras guardadas','palabras'],['Nivel','cefr_level'],['Objetivo','learning_goal'],['ID','id']];
    const q=v=>'"'+String(v==null?'':v).replace(/"/g,'""')+'"';
    const csv='\ufeff'+[cols.map(c=>q(c[0])).join(',')].concat(rows.map(r=>cols.map(c=>q(r[c[1]])).join(','))).join('\r\n');
    const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='talvo-usuarios-'+new Date().toISOString().slice(0,10)+'.csv';document.body.appendChild(a);a.click();a.remove();
    toast('Listo: '+rows.length+' usuarios exportados.');
  }catch(err){toast(err.message)}finally{btn.disabled=false}
}

async function admActividad(fresh){
  const box=$('admin-eventos');if(!adm.loaded.actividad)box.innerHTML='<div class="empty">'+pqLoader('sm')+'</div>';
  try{
    const d=await admFetch('/api/admin/actividad?limit=100'+(adm.evf?'&tipo='+adm.evf:''),fresh);admWarn(d.warnings);admStamp();adm.loaded.actividad=Date.now();
    box.innerHTML=(d.eventos||[]).map(x=>{const t=ADM_T[x.tipo]||['•',x.tipo];return '<div class="history-card"><div class="history-head"><span>'+t[0]+' '+t[1]+'</span>'+(x.score!=null?'<span class="adm-score '+admScoreCls(x.score)+'">'+Math.round(x.score)+'</span>':'')+'</div><div class="history-meta"><span>'+esc(x.email||'')+'</span><span>'+admDate(x.fecha)+' · '+admAgo(x.fecha)+'</span></div>'+(x.detalle?'<div class="adm-detail">'+esc(x.detalle)+'</div>':'')+'</div>'}).join('')||'<div class="empty">Sin actividad de este tipo todavía.</div>';
  }catch(err){admErr(box,err.message)}
  try{
    const s=await admFetch('/api/admin/soporte');
    $('admin-soporte').innerHTML=(s.mensajes||[]).map(m=>'<div class="adm-sup"><b>'+esc(m.tipo||'mensaje')+'</b> · '+esc(m.email||'')+' · '+admDate(m.created_at)+'<small>'+esc(m.mensaje||'')+'</small></div>').join('')||'<div class="empty">No hay mensajes de soporte.</div>';
  }catch(err){admErr($('admin-soporte'),err.message)}
}
async function admSistema(fresh){
  const box=$('admin-sistema');if(!adm.loaded.sistema)box.innerHTML='<div class="empty">Revisando el servidor…</div>';
  try{
    const d=await admFetch('/api/admin/sistema');admStamp();adm.loaded.sistema=Date.now();
    const s=d.servidor;const h=Math.floor(s.uptime_seg/3600),m=Math.floor(s.uptime_seg%3600/60);
    box.innerHTML='<h2 class="sec-h">Revisión de servicios</h2>'+d.checks.map(c=>'<div class="adm-check"><span class="ico">'+(c.ok?'✅':'❌')+'</span><div><b>'+esc(c.nombre)+'</b><small>'+esc(c.detalle)+'</small></div></div>').join('')+
     '<h2 class="sec-h">Servidor</h2><div class="adm-kpis">'+
     '<div class="report"><b>'+h+' h '+m+' min</b><small>Encendido desde '+admAgo(s.encendido_desde)+'</small><em>Si es muy poco, el servidor se había dormido</em></div>'+
     '<div class="report"><b>'+s.limite_ia_diario+'</b><small>Límite diario de IA por usuario</small><em>General: '+s.limite_general_min+' peticiones/min</em></div>'+
     '<div class="report"><b>'+s.audios_en_cache+'</b><small>Audios en caché</small><em>Ahorran cobros de voz repetidos</em></div>'+
     '<div class="report"><b>$'+s.precio_mxn+'</b><small>Precio mensual (MXN)</small><em>Zona horaria: '+esc(s.zona_horaria)+' · Python '+esc(s.python)+'</em></div></div>';
  }catch(err){admErr(box,err.message)}
}
/* ---------- Admin: planes, límites y consumo ---------- */
const ADM_PLAN={gratis:'Prueba gratis',basico:'Básico',pro:'Pro',max:'Max'};
const ADM_COST_L={'/api/tutor':'Mensaje al tutor','/api/sintetizar-audio':'Audio de una palabra/frase','/api/transcribir-audio':'Transcribir voz','/api/resumen-llamada':'Resumen de llamada','/api/llamada/turno':'Turno de llamada','/analizar-escritura':'Análisis de escritura','/evaluar-lectura':'Evaluar lectura','/evaluar-dictado':'Evaluar dictado','/analizar-audio-real':'Análisis de pronunciación','/api/assess-reading':'Evaluación de lectura (voz)','/api/assess-unscripted':'Evaluación de habla libre','/nueva-frase':'Frase nueva','/nuevo-tema-libre':'Tema libre','/nuevo-trabalenguas':'Trabalenguas','/nuevo-texto-lectura':'Texto de lectura','/nuevo-dictado':'Dictado nuevo','/api/writing/challenge':'Reto de escritura','/api/vocabulario/diario':'Palabras del día'};
function admMeter(l,u,lim){const pct=lim?Math.min(100,Math.round(u/lim*100)):0;return '<div class="pl-m"><div class="pl-mh"><span>'+l+'</span><b>'+u+' / '+lim+'</b></div><div class="bar"><div class="fill'+(pct>=85?' warn':'')+'" style="width:'+pct+'%"></div></div></div>'}
function admPlanesHtml(d){
  const c=d.config,h=d.hoy,inp=(k,v,st)=>'<input class="input" type="number" min="0" step="'+(st||1)+'" data-cfg="'+k+'" value="'+v+'">';
  let html='';
  if(d.guardado_permanente===false)html+='<div class="notice">⚠ Todavía no existe la tabla <b>config_app</b>: lo que cambies aquí funciona, pero se pierde si Render reinicia. Ejecuta <b>planes_y_uso.sql</b> en Supabase.</div>';
  html+='<h2 class="sec-h">Consumo de las últimas 24 h</h2><div class="card">'+admMeter('Créditos de todos los alumnos',h.total,h.tope_total)+admMeter('Créditos de pruebas gratis',h.gratis,h.tope_gratis)+
    '<small class="admin-updated">'+(h.pausa_gratis?'⛔ Las pruebas gratis están PAUSADAS por el tope diario.':'✅ Todo normal: las pruebas gratis siguen activas.')+' 1 crédito ≈ 1 mensaje al tutor. Es el consumo desde que el servidor arrancó (o las últimas 24 h si ya creaste la tabla).</small></div>';
  html+='<h2 class="sec-h">Planes (mensajes por cada '+d.ventana_horas+' h y por día)</h2><div class="card"><div class="apl-row apl-head"><span>Plan</span><span>Precio MXN/mes</span><span>Cada '+d.ventana_horas+' h</span><span>Por día</span></div>';
  Object.keys(c.planes).forEach(k=>{const p=c.planes[k];html+='<div class="apl-row"><b>'+esc(d.nombres[k]||k)+'</b>'+(k==='gratis'?'<span class="admin-updated">—</span>':inp('planes.'+k+'.precio',p.precio))+inp('planes.'+k+'.ventana',p.ventana)+inp('planes.'+k+'.dia',p.dia)+'</div>'});
  html+='</div><h2 class="sec-h">Interruptores de emergencia (protegen tu saldo de Azure)</h2><div class="card"><div class="apl-row apl-2"><span>Tope diario de créditos de TODOS (pausa las pruebas gratis; frena a todos al 150%)</span>'+inp('global_dia',c.global_dia)+'</div><div class="apl-row apl-2"><span>Tope diario de créditos solo de pruebas gratis</span>'+inp('gratis_global_dia',c.gratis_global_dia)+'</div></div>';
  html+='<h2 class="sec-h">Cuántos créditos gasta cada cosa</h2><div class="card">'+Object.keys(c.costos).map(p=>'<div class="apl-row apl-2"><span>'+esc(ADM_COST_L[p]||p)+'</span>'+inp('costos.'+p,c.costos[p],0.05)+'</div>').join('')+'</div>';
  html+='<div class="actions" style="margin:14px 0"><button type="button" class="btn primary" data-plan-save="1">💾 Guardar cambios</button><button type="button" class="btn danger" data-plan-reset="1">↺ Restaurar valores originales</button></div>';
  html+='<h2 class="sec-h">Quién más gasta (24 h)</h2><div class="card">'+((d.top||[]).map(t=>'<div class="adm-hist"><span><a href="#" data-adm-user="'+esc(t.email)+'">'+esc(t.email)+'</a></span><span>'+t.creditos+' créditos</span></div>').join('')||'<span class="admin-updated">Todavía nadie ha usado la IA.</span>')+'</div>';
  return html;
}
async function admPlanes(fresh){
  const box=$('admin-planes');if(!box)return;
  if(!adm.loaded.planes)box.innerHTML='<div class="empty">'+pqLoader('sm')+'</div>';
  try{const d=await admFetch('/api/admin/planes',fresh);admStamp();adm.loaded.planes=Date.now();box.innerHTML=admPlanesHtml(d)}
  catch(err){admErr(box,err.message)}
}
async function admPlanesSave(restore){
  if(restore&&!window.confirm('¿Volver a los valores originales de planes y límites?'))return;
  const cfg={planes:{},costos:{}};
  $$('#admin-planes [data-cfg]').forEach(i=>{const p=i.dataset.cfg.split('.'),v=Number(i.value);if(p[0]==='planes'){(cfg.planes[p[1]]=cfg.planes[p[1]]||{})[p[2]]=v}else if(p[0]==='costos'){cfg.costos[p.slice(1).join('.')]=v}else cfg[p[0]]=v});
  try{
    const d=await jsonFetch('/api/admin/planes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(restore?{restaurar:true}:{config:cfg})});
    toast(d.mensaje);if(d.aviso)setTimeout(()=>toast(d.aviso),3200);
    adm.loaded.planes=0;admPlanes(true);
  }catch(err){toast(err.message)}
}

function admLoadTab(tab,fresh){
  if(tab==='planes')return admPlanes(fresh);
  if(tab==='resumen')return admResumen(fresh);
  if(tab==='usuarios')return admUsuarios(true,fresh);
  if(tab==='actividad')return admActividad(fresh);
  return admSistema(fresh);
}
function admTab(tab){
  adm.tab=tab;
  $$('#admin-tabs .mode').forEach(b=>b.classList.toggle('active',b.dataset.atab===tab));
  ['resumen','usuarios','actividad','sistema','planes'].forEach(t=>$('atab-'+t).classList.toggle('active',t===tab));
  if(!adm.loaded[tab]||Date.now()-adm.loaded[tab]>60000)admLoadTab(tab,false);
}
function admBoot(){
  if(adm.init)return;adm.init=true;
  $('sec-admin').addEventListener('click',e=>{
    const t=e.target;let n;
    if(n=t.closest('[data-atab]'))return admTab(n.dataset.atab);
    if(t.closest('[data-plan-save]'))return admPlanesSave(false);
    if(t.closest('[data-plan-reset]'))return admPlanesSave(true);
    if(t.closest('#admin-refresh')){adm.loaded={};return admLoadTab(adm.tab,true)}
    if(t.closest('[data-adm-retry]')){adm.loaded[adm.tab]=0;return admLoadTab(adm.tab,true)}
    if(n=t.closest('[data-aflt]')){adm.filter=n.dataset.aflt;$$('#admin-filters button').forEach(b=>b.classList.toggle('active',b===n));return admUsuarios(true)}
    if(n=t.closest('[data-aevf]')){adm.evf=n.dataset.aevf;$$('#admin-evfilters button').forEach(b=>b.classList.toggle('active',b===n));adm.loaded.actividad=0;return admActividad()}
    if(t.closest('#admin-more'))return admUsuarios(false);
    if(t.closest('#admin-export'))return admExport();
    if(n=t.closest('[data-acc]'))return admAcceso(n);
    if(n=t.closest('[data-copy]')){const u=adm.users[n.dataset.copy];if(u)admCopy(admReminder(u)).then(()=>toast('Recordatorio copiado. Pégalo en WhatsApp.'));return}
    if(n=t.closest('.user-row'))return admToggleUser(n.dataset.uid);
    if(n=t.closest('[data-adm-user]')){adm.q=n.dataset.admUser;$('admin-q').value=adm.q;adm.filter='todos';$$('#admin-filters button').forEach(b=>b.classList.toggle('active',b.dataset.aflt==='todos'));admTab('usuarios');return admUsuarios(true)}
  });
  let qt=null;
  $('admin-q').addEventListener('input',e=>{clearTimeout(qt);qt=setTimeout(()=>{adm.q=e.target.value.trim();admUsuarios(true)},350)});
  $('admin-sort').addEventListener('change',e=>{adm.sort=e.target.value;admUsuarios(true)});
  setInterval(admTick,15000);
  setInterval(()=>{if(document.visibilityState==='visible'&&document.querySelector('#sec-admin.active')&&adm.tab!=='usuarios')admLoadTab(adm.tab,false)},90000);
}

Object.assign(window,{cambiarPestana:(n,b)=>section(n,b),cambiarModoPronunciacion:pronMode,obtenerNuevaFrase:newPhrase,obtenerNuevoTemaHablaLibre:newTopic,obtenerNuevoTrabalenguas:newTwister,alternarGrabacion:toggleRecording,evaluarEscritura:analyzeWriting,cargarLectura:loadReading,evaluarLectura:evaluateReading,cargarDictado:loadDictation,evaluarDictado:evaluateDictation,cargarHistorial:loadProgress,procesarAuth:authSubmit,abrirModalAuth:showAuth,cerrarModalAuth:closeAuth,cerrarSesion:signOut,hablarNativo:t=>speak(t),hablarTrabalenguasNativo:t=>speak(t,.85)});
document.addEventListener('DOMContentLoaded',async()=>{bind();try{const s=await getSession();if(!recoveryMode)await syncUser(s?.user||null)}catch(e){console.error('[INIT]',e);if(!recoveryMode){if(OFL&&OFL.isOff()&&enterOffline(null)){if(window.hideBoot)window.hideBoot()}else syncUser(null)}}if(OFL&&!OFL.isOff())setTimeout(()=>OFL.flush(),3000)});
Object.assign(window,{playGuideAudio,speak});
document.querySelectorAll('#home-maestra .hm-card').forEach(b=>b.addEventListener('click',()=>{callModeSet(b.dataset.m);section('llamada')}));
window.TalvoCore={$,$$,jsonFetch,authFetch,state,toast,section,speak,esc,teacherSpeak,setMascotState,reactToScore,loadDashboard};
$$('[data-pq]').forEach(el=>{el.innerHTML=pqLoader(el.dataset.pq||'')});
})();
