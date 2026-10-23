/* Talvo · Tutorial guiado con Palanqueta */
(function(){
'use strict';
const C=()=>window.TalvoCore||{};
const STEPS=[
 {t:'Hi, I\'m Palanqueta!',p:'I\'ll show you around Talvo in one minute. You can leave the tour at any time.',s:'home'},
 {t:'Home',p:'Your daily goal, streak and shortcuts live here. Start here every day.',s:'home'},
 {t:'Learning Path',p:'Short lessons that adapt to your level and goal. Finish them to earn stars and XP and unlock the next steps.',s:'learning-path'},
 {t:'Pronunciation',p:'Say a phrase out loud and get a score, word by word. Pick a new phrase, a free topic or a tongue twister.',s:'pronunciacion'},
 {t:'Tutor chat',p:'Chat with your AI tutor in English. Ask anything and get gentle corrections.',s:'tutor'},
 {t:'Voice call',p:'Talk to the tutor like a real phone call. It listens and answers out loud.',s:'llamada'},
 {t:'Writing, Reading, Listening',p:'Write with feedback, read short texts and train your ear with dictation.',s:'escritura'},
 {t:'Vocabulary',p:'Save new words from anywhere and review them so they stick.',s:'vocabulario'},
 {t:'Translator',p:'Type or speak in Spanish or English and get a natural translation, with better ways to say it.',s:'traductor'},
 {t:'Role-play',p:'Rehearse interviews, sales calls, travel and more with an AI partner who coaches you.',s:'escenarios'},
 {t:'My Routes',p:'Tell me what you want to achieve, like selling cheese in English, and I\'ll build a course just for you.',s:'rutas'},
 {t:'Short Clips',p:'Watch short everyday scenes with live subtitles and test what you understood.',s:'clips'},
 {t:'Presentations',p:'Paste your slides or upload a .pptx, get a spoken script and rehearse each slide.',s:'presentacion'},
 {t:'Voice Lab',p:'Analyze your speaking, repeat phrases like a native, look words up and review real meetings.',s:'voz'},
 {t:'Progress and rewards',p:'See your history, unlock achievements and spend the gems you earn in the shop.',s:'historial'},
 {t:'Your plan',p:'Each plan has credits that renew every 5 hours. Check your usage and upgrade whenever you want.',s:'cuenta'},
 {t:'You\'re ready! 🎉',p:'Practice a little every day and I\'ll be cheering for you. You can open this tutorial again from the menu.',s:'home'}
];
let i=0,root=null,hl=null;
const avatar=()=>{const im=document.querySelector('.topbar-brand img');return im?im.src:''};
function clear(){if(hl){hl.classList.remove('tour-hl');hl=null}}
function close(done){clear();if(root){root.remove();root=null}document.body.classList.remove('tour-on');try{localStorage.setItem('talvo_tour_seen','1')}catch(e){}}
function show(){
  if(!root)return;const st=STEPS[i];clear();
  try{C().section&&C().section(st.s)}catch(e){}
  const btn=document.querySelector('#main-nav [data-section="'+st.s+'"],.sidebar [data-section="'+st.s+'"]');
  if(btn&&btn.offsetParent!==null&&innerWidth>900){btn.classList.add('tour-hl');hl=btn;try{btn.scrollIntoView({block:'center'})}catch(e){}}
  const last=i===STEPS.length-1;
  root.querySelector('.tour-card').innerHTML='<div class="tour-top"><img src="'+avatar()+'" alt="" class="tour-pq"><div><b class="tour-t">'+st.t+'</b><span class="tour-n">'+(i+1)+' / '+STEPS.length+'</span></div></div><p class="tour-p">'+st.p+'</p><div class="tour-bar"><i style="width:'+Math.round((i+1)/STEPS.length*100)+'%"></i></div><div class="tour-btns">'+(last?'':'<button type="button" class="btn" data-a="skip">Skip tour</button>')+(i>0?'<button type="button" class="btn" data-a="back">Back</button>':'')+'<button type="button" class="btn primary" data-a="next">'+(last?'Let\'s go!':'Next')+'</button></div>';
  root.querySelectorAll('[data-a]').forEach(b=>b.onclick=()=>{const a=b.dataset.a;if(a==='skip')close();else if(a==='back'){i=Math.max(0,i-1);show()}else if(i>=STEPS.length-1)close(true);else{i++;show()}});
  if(window.TalvoI18n&&TalvoI18n.refresh)try{TalvoI18n.refresh(root)}catch(e){}
}
function start(){
  if(root)return;const of=document.getElementById('tour-offer');if(of)of.remove();i=0;root=document.createElement('div');root.className='tour';root.setAttribute('role','dialog');root.setAttribute('aria-label','Tutorial');
  root.innerHTML='<div class="tour-card"></div>';document.body.appendChild(root);document.body.classList.add('tour-on');
  const sb=document.getElementById('sidebar-close');
  show();
}
function seen(){try{return localStorage.getItem('talvo_tour_seen')==='1'}catch(e){return true}}
function offer(){
  if(seen()||root||document.getElementById('tour-offer'))return;const act=document.querySelector('.section.active');if(!act||act.id!=='sec-home')return;
  const el=document.createElement('div');el.id='tour-offer';el.className='tour-offer';
  el.innerHTML='<img src="'+avatar()+'" alt="" class="tour-pq"><div><b>New here?</b><p>Let me show you around in one minute.</p><div class="tour-btns"><button type="button" class="btn" data-o="no">Not now</button><button type="button" class="btn primary" data-o="go">Show me</button></div></div>';
  document.body.appendChild(el);setTimeout(()=>{if(el.isConnected){el.remove();try{localStorage.setItem('talvo_tour_seen','1')}catch(e){}}},14000);
  el.querySelector('[data-o=no]').onclick=()=>{try{localStorage.setItem('talvo_tour_seen','1')}catch(e){}el.remove()};
  el.querySelector('[data-o=go]').onclick=()=>{el.remove();start()};
  if(window.TalvoI18n&&TalvoI18n.refresh)try{TalvoI18n.refresh(el)}catch(e){}
}
document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('[data-tour]');if(b){e.preventDefault();const sb=document.querySelector('.sidebar.open');if(sb){const x=document.getElementById('sidebar-close');x&&x.click()}start()}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&root)close()});
window.TalvoTour={start,offer,close};
let tries=0;const iv=setInterval(()=>{tries++;const app=document.getElementById('app-content');if(app&&app.style.display!=='none'&&C().state&&C().state.user){clearInterval(iv);setTimeout(offer,2500)}else if(tries>120)clearInterval(iv)},1000);
})();
