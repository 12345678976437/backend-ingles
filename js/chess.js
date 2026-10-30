/* Talvo · Ajedrez: jugar contra la computadora, lecciones guiadas, problemas de mate y repaso de partidas.
   Todo corre en el navegador (reglas con chess.js, rival con chess-engine.js en un Worker): sin costo y sin internet.
   Solo el entrenador con IA usa el servidor. */
(function(){
'use strict';
const C=window.TalvoCore||{};
const $=C.$||(id=>document.getElementById(id));
const esc=C.esc||(s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])));
const lang=()=>{try{return window.TalvoI18n?TalvoI18n.get():'en'}catch(e){return 'en'}};
const T=(en,es)=>lang()==='es'?es:en;
const L2=a=>lang()==='es'?a[1]:a[0];
const lsGet=(k,d)=>{try{const v=localStorage.getItem(k);return v==null?d:JSON.parse(v)}catch(e){return d}};
const lsSet=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}};
const START='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const GLYPH={k:'♚',q:'♛',r:'♜',b:'♝',n:'♞',p:'♟'};
const LEVELS=[null,['Beginner','Principiante'],['Rookie','Novato'],['Casual','Casual'],['Club player','De club'],['Strong','Fuerte'],['Expert','Experto'],['Hardest','Máximo']];
const PIECE_NAME={p:['pawn','peón'],n:['knight','caballo'],b:['bishop','alfil'],r:['rook','torre'],q:['queen','dama'],k:['king','rey']};

/* ---------- motor (Worker; si no se puede, en el hilo principal) ---------- */
let worker=null,wid=0,pend={},local=null,workerBad=false;
function startWorker(){
  if(worker||workerBad)return;
  try{
    worker=new Worker('js/chess-engine.js');
    worker.onmessage=e=>{const d=e.data||{},p=pend[d.id];if(!p)return;if(d.cmd==='progress'){p.prog&&p.prog(d.i,d.n);return}delete pend[d.id];d.cmd==='error'?p.rej(new Error(d.error)):p.res(d)};
    worker.onerror=()=>{workerBad=true;try{worker.terminate()}catch(e){}worker=null;Object.values(pend).forEach(p=>p.rej(new Error('worker')));pend={}};
  }catch(e){workerBad=true;worker=null}
}
function ask(msg,prog){
  startWorker();
  if(worker){return new Promise((res,rej)=>{const id=++wid;pend[id]={res,rej,prog};worker.postMessage(Object.assign({id},msg))}).catch(()=>askLocal(msg,prog))}
  return askLocal(msg,prog);
}
function askLocal(msg,prog){
  return new Promise(res=>{setTimeout(()=>{
    if(!window.Engine){res({best:null,score:0});return}
    local=local||new window.Engine();local.setFen(msg.fen||START);
    for(const u of (msg.moves||[])){const m=local.fromUci(u);if(!m)break;local.make(m)}
    if(msg.cmd==='move'){const r=local.chooseMove(msg.level);res({best:r?local.uci(r.m):null,score:r?r.s:0})}
    else if(msg.cmd==='analyze'){const r=local.analyze(msg.depth||3,msg.ms||800);res({best:r&&r.best,score:r?r.score:0})}
    else if(msg.cmd==='batch'){const out=[];(msg.fens||[]).forEach((f,i)=>{local.setFen(f);const r=local.analyze(msg.depth||3,msg.ms||400);out.push(r?{best:r.best,score:r.score}:null);prog&&prog(i+1,msg.fens.length)});res({out})}
  },20)});
}

/* ---------- tablero ---------- */
function boardHTML(){
  let h='<div class="cb" data-i18n-skip>';
  for(let i=0;i<64;i++)h+='<div class="cb-sq" data-i="'+i+'"></div>';
  return h+'</div>';
}
class Board{
  constructor(el,onClick){this.el=el;this.flip=false;this.onClick=onClick;this.st={};el.innerHTML=boardHTML();
    el.querySelector('.cb').addEventListener('click',e=>{const sq=e.target.closest('.cb-sq');if(sq&&this.onClick)this.onClick(sq.dataset.sq)})}
  draw(chess,st){
    this.st=st=st||this.st;const cells=this.el.querySelectorAll('.cb-sq'),board=chess.board();
    cells.forEach((c,i)=>{
      const r=Math.floor(i/8),f=i%8,rank=this.flip?r:7-r,file=this.flip?7-f:f;
      const name='abcdefgh'[file]+(rank+1),p=board[7-rank][file];
      const cls=['cb-sq',(rank+file)%2===0?'dk':'lt'];
      if(st.sel===name)cls.push('sel');
      if(st.last&&(st.last[0]===name||st.last[1]===name))cls.push('last');
      if(st.tgt&&st.tgt.includes(name))cls.push(p?'cap':'tgt');
      if(st.hint&&st.hint.includes(name))cls.push('hint');
      if(st.check===name)cls.push('chk');
      if(st.bad===name)cls.push('bad');
      c.className=cls.join(' ');c.dataset.sq=name;
      let inner=p?'<span class="cb-p '+(p.color==='w'?'w':'b')+'">'+GLYPH[p.type]+'︎</span>':'';
      if(f===0)inner+='<i class="cb-r">'+(rank+1)+'</i>';
      if(r===7)inner+='<i class="cb-f">'+'abcdefgh'[file]+'</i>';
      c.innerHTML=inner;
    });
  }
}
function kingSq(chess){if(!chess.inCheck())return null;const t=chess.turn();const b=chess.board();for(let r=0;r<8;r++)for(let f=0;f<8;f++){const p=b[r][f];if(p&&p.type==='k'&&p.color===t)return 'abcdefgh'[f]+(8-r)}return null}
function uciOf(m){return m.from+m.to+(m.promotion||'')}
function say(msg,kind){const el=$('ch-msg');if(!el)return;el.className='ch-msg'+(kind?' '+kind:'');el.textContent=msg}

/* ---------- estado ---------- */
const S={tab:'play',level:lsGet('talvo_chess_level',3),color:lsGet('talvo_chess_color','w'),g:null,bd:null,busy:false,hintStage:0,mine:'w',over:false,reviewing:false,
  lesson:null,pz:null,pzMode:lsGet('talvo_chess_pzmode','m1')};
const done=()=>lsGet('talvo_chess_lessons',{});
const pzProg=()=>lsGet('talvo_chess_puzzles',{m1:0,m2:0});

function open(){
  const root=$('chess-root');if(!root)return;
  if(!window.Chess){root.innerHTML='<div class="empty">'+T('Chess is loading…','Cargando el ajedrez…')+'</div>';return}
  render();
}
function tabs(){
  const t=[['play',T('♟️ Play','♟️ Jugar')],['learn',T('📚 Learn','📚 Aprender')],['puzzles',T('🧩 Puzzles','🧩 Problemas')]];
  return '<div class="modebar ch-tabs">'+t.map(x=>'<button type="button" class="mode'+(S.tab===x[0]?' active':'')+'" data-ch-tab="'+x[0]+'">'+x[1]+'</button>').join('')+'</div>';
}
function render(){
  const root=$('chess-root');if(!root)return;
  root.innerHTML=tabs()+'<div id="ch-body"></div>';
  root.querySelectorAll('[data-ch-tab]').forEach(b=>b.onclick=()=>{S.tab=b.dataset.chTab;if(S.tab!=='play'&&S.g&&!S.over){/* la partida sigue guardada en memoria */}render()});
  if(S.tab==='play')S.g&&!S.reviewing?playView():(S.reviewing?reviewView():playSetup());
  else if(S.tab==='learn')S.lesson?lessonView():learnList();
  else puzzlesView();
}

/* =================== JUGAR =================== */
function playSetup(){
  const body=$('ch-body');
  body.innerHTML='<div class="card ch-setup" data-i18n-skip><h3>'+T('Play against the computer','Juega contra la computadora')+'</h3>'
   +'<p class="ch-sub">'+T('Pick a level. Level 1 makes mistakes on purpose; level 7 does not forgive them.','Elige un nivel. El 1 se equivoca a propósito; el 7 no perdona errores.')+'</p>'
   +'<div class="ch-levels">'+LEVELS.slice(1).map((n,i)=>'<button type="button" class="mode'+(S.level===i+1?' active':'')+'" data-lv="'+(i+1)+'"><b>'+(i+1)+'</b><small>'+esc(L2(n))+'</small></button>').join('')+'</div>'
   +'<div class="ch-sub" style="margin-top:12px">'+T('Your color','Tu color')+'</div>'
   +'<div class="modebar" style="grid-template-columns:repeat(3,1fr)">'+[['w',T('⚪ White','⚪ Blancas')],['b',T('⚫ Black','⚫ Negras')],['r',T('🎲 Random','🎲 Al azar')]].map(x=>'<button type="button" class="mode'+(S.color===x[0]?' active':'')+'" data-col="'+x[0]+'">'+x[1]+'</button>').join('')+'</div>'
   +'<button type="button" class="btn primary" id="ch-start" style="margin-top:14px;width:100%">'+T('Start game','Empezar partida')+'</button></div>';
  body.querySelectorAll('[data-lv]').forEach(b=>b.onclick=()=>{S.level=+b.dataset.lv;lsSet('talvo_chess_level',S.level);playSetup()});
  body.querySelectorAll('[data-col]').forEach(b=>b.onclick=()=>{S.color=b.dataset.col;lsSet('talvo_chess_color',S.color);playSetup()});
  $('ch-start').onclick=newGame;
}
function newGame(){
  S.g=new window.Chess();S.over=false;S.hintStage=0;S.busy=false;S.reviewing=false;S.sel=null;S.last=null;S.tgt=null;S.hint=null;S.result='';S.hist=[];
  S.mine=S.color==='r'?(Math.random()<.5?'w':'b'):S.color;
  playView();
  if(S.g.turn()!==S.mine)engineTurn();
}
function playView(){
  const body=$('ch-body');
  body.innerHTML='<div class="ch-game" data-i18n-skip><div class="ch-top"><b id="ch-status"></b><span class="ch-lv">'+T('Level','Nivel')+' '+S.level+' · '+esc(L2(LEVELS[S.level]))+'</span></div>'
   +'<div id="ch-board"></div><div class="ch-msg" id="ch-msg"></div>'
   +'<div class="ch-ctl"><button type="button" class="btn" id="ch-undo">↩ '+T('Undo','Deshacer')+'</button><button type="button" class="btn" id="ch-hint">💡 '+T('Hint','Pista')+'</button><button type="button" class="btn" id="ch-flip">🔄 '+T('Flip','Girar')+'</button><button type="button" class="btn" id="ch-resign">🏳️ '+T('Resign','Rendirse')+'</button></div>'
   +'<div class="ch-moves" id="ch-moves"></div><div id="ch-end"></div></div>';
  S.bd=new Board($('ch-board'),playClick);S.bd.flip=S.mine==='b';
  $('ch-undo').onclick=undo;$('ch-hint').onclick=hint;$('ch-flip').onclick=()=>{S.bd.flip=!S.bd.flip;refresh()};
  $('ch-resign').onclick=()=>{if(S.over)return;if(confirm(T('Resign this game?','¿Rendirte en esta partida?')))finish('resign')};
  refresh();if(S.over)showEnd();
}
function statusText(){
  const g=S.g;if(S.over)return S.result;
  if(S.busy)return T('Computer is thinking…','La computadora está pensando…');
  return (g.turn()===S.mine?T('Your move','Te toca'):T('Computer to move','Mueve la computadora'))+(g.inCheck()?T(' · CHECK!',' · ¡JAQUE!'):'');
}
function refresh(){
  if(!S.bd)return;
  S.bd.draw(S.g,{sel:S.sel,last:S.last,tgt:S.tgt,hint:S.hint,check:kingSq(S.g)});
  const st=$('ch-status');if(st)st.textContent=statusText();
  const mv=S.g.history();let h='';for(let i=0;i<mv.length;i+=2)h+='<span class="n">'+(i/2+1)+'.</span><span>'+esc(mv[i])+'</span><span>'+esc(mv[i+1]||'')+'</span>';
  const m=$('ch-moves');if(m){m.innerHTML=h||'<small>'+T('Moves will appear here.','Aquí aparecerán las jugadas.')+'</small>';m.scrollTop=m.scrollHeight}
}
function playClick(sq){
  if(S.over||S.busy||S.g.turn()!==S.mine)return;
  const g=S.g;
  if(S.sel&&S.tgt&&S.tgt.includes(sq)){tryMove(S.sel,sq);return}
  const p=g.get(sq);
  if(p&&p.color===S.mine){S.sel=sq;S.tgt=g.moves({square:sq,verbose:true}).map(m=>m.to);S.hint=null}else{S.sel=null;S.tgt=null}
  refresh();
}
function tryMove(from,to){
  const g=S.g,mv=g.moves({square:from,verbose:true}).filter(m=>m.to===to);
  if(!mv.length)return;
  if(mv.length>1||mv[0].promotion){promoChoose(ch=>doMove(from,to,ch));return}
  doMove(from,to);
}
function promoChoose(cb){
  const el=document.createElement('div');el.className='ch-promo';
  el.innerHTML='<div class="ch-promo-in"><b>'+T('Promote to…','Corona a…')+'</b><div>'+['q','r','b','n'].map(p=>'<button type="button" data-p="'+p+'"><span class="cb-p '+(S.mine==='w'||S.tab!=='play'?'w':'b')+'">'+GLYPH[p]+'︎</span></button>').join('')+'</div></div>';
  document.body.appendChild(el);
  el.addEventListener('click',e=>{const b=e.target.closest('[data-p]');if(!b)return;el.remove();cb(b.dataset.p)});
}
function doMove(from,to,promo){
  const g=S.g;let m;try{m=g.move({from,to,promotion:promo||'q'})}catch(e){return}
  if(!m)return;S.last=[m.from,m.to];S.sel=null;S.tgt=null;S.hint=null;S.hintStage=0;say('');
  refresh();
  if(g.isGameOver())return finish();
  engineTurn();
}
async function engineTurn(){
  S.busy=true;refresh();
  const t0=Date.now();
  const moves=S.g.history({verbose:true}).map(uciOf);
  let r;try{r=await ask({cmd:'move',fen:START,moves,level:S.level})}catch(e){r=null}
  const wait=Math.max(0,450-(Date.now()-t0));if(wait)await new Promise(x=>setTimeout(x,wait));
  if(!S.g||S.over||S.reviewing){S.busy=false;return}
  S.busy=false;
  let ok=null;
  if(r&&r.best){try{ok=S.g.move({from:r.best.slice(0,2),to:r.best.slice(2,4),promotion:r.best[4]})}catch(e){ok=null}}
  if(!ok){const all=S.g.moves({verbose:true});if(all.length)ok=S.g.move(all[Math.floor(Math.random()*all.length)])}
  if(ok)S.last=[ok.from,ok.to];
  refresh();
  if(S.g.isGameOver())finish();
}
function undo(){
  if(S.busy||!S.g)return;
  if(S.over){return}
  const g=S.g;let n=0;
  while(g.history().length&&n<2){g.undo();n++;if(g.turn()===S.mine)break}
  S.sel=null;S.tgt=null;S.hint=null;S.last=null;const h=g.history({verbose:true});if(h.length){const l=h[h.length-1];S.last=[l.from,l.to]}
  refresh();
  if(g.turn()!==S.mine)engineTurn();
}
async function hint(){
  if(S.over||S.busy||S.g.turn()!==S.mine)return;
  if(S.hint&&S.hintStage===1&&S.hintMove){S.hint=[S.hintMove.slice(0,2),S.hintMove.slice(2,4)];S.hintStage=2;refresh();say(T('Move that piece to the highlighted square.','Mueve esa pieza a la casilla marcada.'),'info');return}
  $('ch-hint').disabled=true;say(T('Thinking…','Pensando…'),'info');
  let r=null;try{r=await ask({cmd:'analyze',fen:S.g.fen(),depth:4,ms:1500})}catch(e){}
  $('ch-hint')&&($('ch-hint').disabled=false);
  if(!r||!r.best){say(T('No idea this time, sorry.','Esta vez no se me ocurre nada.'),'info');return}
  S.hintMove=r.best;S.hint=[r.best.slice(0,2)];S.hintStage=1;refresh();
  const p=S.g.get(r.best.slice(0,2));
  say(T('Look at your '+(p?PIECE_NAME[p.type][0]:'piece')+'. Press Hint again to see where.','Mira tu '+(p?PIECE_NAME[p.type][1]:'pieza')+'. Pulsa Pista otra vez para ver adónde.'),'info');
}
function finish(why){
  const g=S.g;S.over=true;S.busy=false;S.sel=null;S.tgt=null;S.hint=null;
  let txt;
  if(why==='resign')txt=T('You resigned.','Te rendiste.');
  else if(g.isCheckmate())txt=g.turn()===S.mine?T('Checkmate. The computer wins.','Jaque mate. Gana la computadora.'):T('Checkmate! You win! 🎉','¡Jaque mate! ¡Ganaste! 🎉');
  else if(g.isStalemate())txt=T('Draw by stalemate.','Tablas por rey ahogado.');
  else if(g.isThreefoldRepetition())txt=T('Draw by repetition.','Tablas por repetición.');
  else if(g.isInsufficientMaterial())txt=T('Draw: not enough pieces to mate.','Tablas: no hay material para dar mate.');
  else txt=T('Draw.','Tablas.');
  S.result=txt;refresh();showEnd();
  try{window.track&&window.track('ajedrez_fin','ajedrez',{nivel:S.level,res:g.isCheckmate()?(g.turn()===S.mine?'perdio':'gano'):(why||'tablas')})}catch(e){}
}
function showEnd(){
  const el=$('ch-end');if(!el)return;
  el.innerHTML='<div class="card ch-endcard"><h3>'+esc(S.result)+'</h3><div class="ch-ctl"><button type="button" class="btn primary" id="ch-review">'+T('🔍 Review my game','🔍 Revisar mi partida')+'</button><button type="button" class="btn" id="ch-again">'+T('Play again','Jugar otra vez')+'</button></div></div>';
  $('ch-again').onclick=()=>{S.g=null;S.over=false;playSetup()};
  $('ch-review').onclick=startReview;
}

/* =================== REVISAR PARTIDA =================== */
const clampS=s=>Math.max(-1000,Math.min(1000,s));
async function startReview(){
  const hist=S.g.history({verbose:true});
  if(hist.length<2){say(T('Play a few more moves first.','Juega algunas jugadas más primero.'),'info');return}
  S.reviewing=true;S.rv={items:[],pgn:hist.map(m=>m.san),res:S.result,lost:S.result.indexOf('resigned')>-1||S.result.indexOf('rendiste')>-1||(S.g.isCheckmate()&&S.g.turn()===S.mine),few:hist.length<12};
  const body=$('ch-body');
  body.innerHTML='<div class="card" data-i18n-skip><h3>'+T('Reviewing your game…','Revisando tu partida…')+'</h3><div class="bar"><div class="fill" id="rv-bar" style="width:0%"></div></div><p class="ch-sub" id="rv-txt">0%</p></div>';
  const fens=[START];const tmp=new window.Chess();hist.forEach(m=>{tmp.move(m.san);fens.push(tmp.fen())});
  const lim=Math.min(fens.length,90);
  let res;
  try{res=await ask({cmd:'batch',fens:fens.slice(0,lim),depth:3,ms:450},(i,n)=>{const b=$('rv-bar');if(b){b.style.width=Math.round(i/n*100)+'%';$('rv-txt').textContent=i+' / '+n}})}catch(e){res=null}
  const out=res&&res.out||[];
  const items=[];
  hist.forEach((m,i)=>{
    if(m.color!==S.mine||i+1>=lim)return;
    const a=out[i],b=out[i+1];if(!a)return;
    const sBefore=clampS(a.score);
    let sAfter;const after=new window.Chess(fens[i+1]);
    if(after.isCheckmate())sAfter=1000;else if(after.isDraw()||after.isStalemate())sAfter=0;else sAfter=b?clampS(-b.score):null;
    if(sAfter==null)return;
    const best=a.best&&a.best!==uciOf(m)?a.best:null;
    let loss=Math.max(0,sBefore-sAfter);
    if(!best)loss=0;
    const label=loss>=300?'blunder':loss>=150?'mistake':loss>=70?'inaccuracy':(best?'ok':'best');
    let bestSan='';if(best){try{const t=new window.Chess(fens[i]);bestSan=t.move({from:best.slice(0,2),to:best.slice(2,4),promotion:best[4]}).san}catch(e){}}
    items.push({ply:i,n:Math.floor(i/2)+1,san:m.san,best:bestSan,bestUci:best,loss,label,fen:fens[i]});
  });
  S.rv.items=items;S.reviewing=true;reviewView();
}
const LAB={blunder:['??','Blunder','Error grave','#ff5c7a'],mistake:['?','Mistake','Error','#ff9f43'],inaccuracy:['?!','Inaccuracy','Imprecisión','#ffd166'],ok:['✓','Fine','Bien','#5ee6a8'],best:['★','Best move','Mejor jugada','#5ec8ff']};
function reviewView(){
  const body=$('ch-body'),rv=S.rv;if(!rv){S.reviewing=false;playSetup();return}
  const cnt={blunder:0,mistake:0,inaccuracy:0,best:0,ok:0};rv.items.forEach(i=>cnt[i.label]++);
  const bad=rv.items.filter(i=>i.loss>=70).sort((a,b)=>b.loss-a.loss).slice(0,6).sort((a,b)=>a.ply-b.ply);
  body.innerHTML='<div class="card ch-review" data-i18n-skip><h3>'+T('Your game review','Repaso de tu partida')+'</h3><p class="ch-sub">'+esc(rv.res)+'</p>'
   +'<div class="ch-rvsum">'+['best','ok','inaccuracy','mistake','blunder'].map(k=>'<div style="--c:'+LAB[k][3]+'"><b>'+cnt[k]+'</b><small>'+esc(lang()==='es'?LAB[k][2]:LAB[k][1])+'</small></div>').join('')+'</div>'
   +(bad.length?'<h4>'+T('Moments to learn from','Momentos para aprender')+'</h4>'+bad.map((x,i)=>'<div class="ch-rvitem" style="--c:'+LAB[x.label][3]+'"><div><b>'+x.n+'. '+esc(x.san)+' <em>'+LAB[x.label][0]+'</em></b><small>'+(x.best?T('Better was ','Era mejor ')+'<b>'+esc(x.best)+'</b>':'')+'</small></div><button type="button" class="btn" data-show="'+x.ply+'">'+T('Show','Ver')+'</button></div>').join(''):'<div class="notice">'+(rv.few?T('The game was too short to judge your play. Play a few more moves next time.','La partida fue muy corta para juzgar tu juego. La próxima juega algunas jugadas más.'):rv.lost?T('The analysis found no single big blunder, so the loss came from many small things. Try the coach below.','El análisis no encontró un error enorme: la derrota vino de varias cosas pequeñas. Prueba el entrenador de abajo.'):T('No big mistakes found. Nice game!','No encontré errores grandes. ¡Buena partida!'))+'</div>')
   +'<div id="ch-rvboard" style="display:none"></div><div class="ch-msg" id="ch-msg"></div>'
   +'<div class="ch-ctl"><button type="button" class="btn primary" id="ch-coach">🎓 '+T('Ask the AI coach','Pedir al entrenador IA')+'</button><button type="button" class="btn" id="ch-rvdone">'+T('Done','Listo')+'</button></div><div id="ch-coachbox"></div></div>';
  body.querySelectorAll('[data-show]').forEach(b=>b.onclick=()=>{
    const it=rv.items.find(x=>x.ply===+b.dataset.show),box=$('ch-rvboard');box.style.display='';box.innerHTML='<div id="ch-rvb"></div><p class="ch-sub">'+T('Your move was ','Tu jugada fue ')+'<b>'+esc(it.san)+'</b>'+(it.best?T(' · the arrow marks the better one: ',' · se marca la mejor: ')+'<b>'+esc(it.best)+'</b>':'')+'</p>';
    const bd=new Board($('ch-rvb'));bd.flip=S.mine==='b';const ch=new window.Chess(it.fen);bd.draw(ch,{hint:it.bestUci?[it.bestUci.slice(0,2),it.bestUci.slice(2,4)]:null,check:kingSq(ch)});box.scrollIntoView({behavior:'smooth',block:'nearest'})});
  $('ch-rvdone').onclick=()=>{S.reviewing=false;S.rv=null;S.g=null;S.over=false;playSetup()};
  $('ch-coach').onclick=()=>askCoach(bad);
}
async function askCoach(bad){
  const btn=$('ch-coach'),box=$('ch-coachbox');if(!btn||!window.TalvoCore||!TalvoCore.jsonFetch)return;
  btn.disabled=true;btn.textContent=T('Thinking…','Pensando…');
  try{
    const d=await TalvoCore.jsonFetch('/api/ajedrez/entrenador',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      moves:S.rv.pgn.join(' ').slice(0,1800),result:S.rv.res,level:S.level,color:S.mine,lang:lang(),
      mistakes:bad.map(x=>({n:x.n,played:x.san,better:x.best,kind:x.label,loss:Math.round(x.loss)}))})});
    box.innerHTML='<div class="card ch-coachcard" data-i18n-skip><h4>🎓 '+T('Your coach says','Tu entrenador dice')+'</h4><p>'+esc(d.resumen||'')+'</p>'
      +((d.consejos||[]).length?'<ul>'+d.consejos.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'')+(d.ejercicio?'<p class="ch-sub"><b>'+T('Try this: ','Prueba esto: ')+'</b>'+esc(d.ejercicio)+'</p>':'')+'</div>';
    btn.style.display='none';
  }catch(e){btn.disabled=false;btn.textContent='🎓 '+T('Ask the AI coach','Pedir al entrenador IA');say(e.message||T('The coach is not available right now.','El entrenador no está disponible ahora.'),'bad')}
}

/* =================== APRENDER =================== */
function learnList(){
  const body=$('ch-body'),dn=done(),cats=window.CHESS_CATS||{},ls=window.CHESS_LESSONS||[];
  const total=ls.length,n=ls.filter(l=>dn[l.id]).length;
  let h='<div class="card" data-i18n-skip><div class="eyebrow">'+T('Chess school','Escuela de ajedrez')+'</div><h3>'+T('From zero to your first checkmate','De cero a tu primer jaque mate')+'</h3><div class="bar"><div class="fill" style="width:'+Math.round(n/Math.max(1,total)*100)+'%"></div></div><p class="ch-sub">'+n+' / '+total+' '+T('lessons done','lecciones hechas')+'</p></div>';
  Object.keys(cats).forEach(k=>{
    const group=ls.filter(l=>l.cat===k);if(!group.length)return;
    h+='<div class="card" data-i18n-skip><h4>'+esc(L2(cats[k]))+'</h4>'+group.map(l=>'<button type="button" class="ch-les'+(dn[l.id]?' ok':'')+'" data-les="'+l.id+'"><span>'+(dn[l.id]?'✓':'♟')+'</span><b>'+esc(L2(l.t))+'</b></button>').join('')+'</div>';
  });
  body.innerHTML=h;
  body.querySelectorAll('[data-les]').forEach(b=>b.onclick=()=>openLesson(b.dataset.les));
}
function openLesson(id){
  const l=(window.CHESS_LESSONS||[]).find(x=>x.id===id);if(!l)return;
  S.lesson={l,g:new window.Chess(l.fen),tries:0,sel:null,tgt:null,solved:false};lessonView();
}
function lessonView(){
  const body=$('ch-body'),s=S.lesson,l=s.l;
  body.innerHTML='<div class="ch-game" data-i18n-skip><button type="button" class="rt-back" id="ls-back">← '+T('Lessons','Lecciones')+'</button><div class="card"><h3>'+esc(L2(l.t))+'</h3><p>'+esc(L2(l.x))+'</p></div><div id="ch-board"></div><div class="ch-msg" id="ch-msg"></div><div class="ch-ctl" id="ls-ctl"></div></div>';
  $('ls-back').onclick=()=>{S.lesson=null;learnList()};
  s.bd=new Board($('ch-board'),lessonClick);s.bd.flip=s.g.turn()==='b';lessonDraw();lessonCtl();
}
function lessonDraw(){const s=S.lesson;s.bd.draw(s.g,{sel:s.sel,tgt:s.tgt,hint:s.hint,check:kingSq(s.g),last:s.last})}
function lessonCtl(){
  const s=S.lesson,el=$('ls-ctl');if(!el)return;
  const ls=window.CHESS_LESSONS,i=ls.findIndex(x=>x.id===s.l.id),nxt=ls[i+1];
  el.innerHTML=s.solved?(nxt?'<button type="button" class="btn primary" id="ls-next">'+T('Next lesson →','Siguiente lección →')+'</button>':'<button type="button" class="btn primary" id="ls-end">'+T('Back to lessons','Volver a las lecciones')+'</button>')
    :'<button type="button" class="btn" id="ls-hint">💡 '+T('Hint','Pista')+'</button><button type="button" class="btn" id="ls-reset">↩ '+T('Reset','Reiniciar')+'</button>';
  if($('ls-next'))$('ls-next').onclick=()=>openLesson(nxt.id);
  if($('ls-end'))$('ls-end').onclick=()=>{S.lesson=null;learnList()};
  if($('ls-hint'))$('ls-hint').onclick=()=>{const a=s.l.ans==='any'?null:s.l.ans[0];if(!a){say(T('Move the king to a square the rook does not attack.','Mueve el rey a una casilla que la torre no ataque.'),'info');return}s.hint=[a.slice(0,2),a.slice(2,4)];lessonDraw();say(T('The highlighted squares show the move.','Las casillas marcadas muestran la jugada.'),'info')};
  if($('ls-reset'))$('ls-reset').onclick=()=>{s.g=new window.Chess(s.l.fen);s.sel=null;s.tgt=null;s.hint=null;s.last=null;say('');lessonDraw()};
}
function lessonClick(sq){
  const s=S.lesson;if(!s||s.solved)return;const g=s.g;
  if(s.sel&&s.tgt&&s.tgt.includes(sq)){
    const mv=g.moves({square:s.sel,verbose:true}).filter(m=>m.to===sq);
    const go=promo=>lessonMove(s.sel,sq,promo);
    if(mv.length>1||mv[0].promotion)promoChoose(go);else go();return}
  const p=g.get(sq);
  if(p&&p.color===g.turn()){s.sel=sq;s.tgt=g.moves({square:sq,verbose:true}).map(m=>m.to);s.hint=null}else{s.sel=null;s.tgt=null}
  lessonDraw();
}
function lessonMove(from,to,promo){
  const s=S.lesson,l=s.l,g=s.g;
  const m=g.move({from,to,promotion:promo||'q'});if(!m)return;
  const u=uciOf(m);const ok=l.ans==='any'||l.ans.includes(u);
  s.sel=null;s.tgt=null;s.hint=null;s.last=[m.from,m.to];lessonDraw();
  if(ok){
    s.solved=true;const dn=done();dn[l.id]=1;lsSet('talvo_chess_lessons',dn);
    say('✅ '+L2(l.ok),'good');lessonCtl();
    try{window.track&&window.track('leccion_fin','ajedrez',{id:l.id})}catch(e){}
  }else{
    s.tries++;
    setTimeout(()=>{g.undo();s.last=null;lessonDraw()},650);
    say(s.tries>=2?T('Not that one. Press Hint if you want help.','Esa no es. Pulsa Pista si quieres ayuda.'):T('Not quite. Read the goal and try again.','Casi. Lee el objetivo e inténtalo de nuevo.'),'bad');
  }
}

/* =================== PROBLEMAS =================== */
function puzzlesView(){
  const body=$('ch-body'),P=window.CHESS_PUZZLES||{m1:[],m2:[]},pr=pzProg();
  const modes=[['m1',T('Mate in 1','Mate en 1')],['m2',T('Mate in 2','Mate en 2')]];
  body.innerHTML='<div class="modebar ch-tabs" style="margin-bottom:10px">'+modes.map(m=>'<button type="button" class="mode'+(S.pzMode===m[0]?' active':'')+'" data-pzm="'+m[0]+'">'+m[1]+' <small>'+Math.min(pr[m[0]]||0,P[m[0]].length)+'/'+P[m[0]].length+'</small></button>').join('')+'</div><div id="pz-body"></div>';
  body.querySelectorAll('[data-pzm]').forEach(b=>b.onclick=()=>{S.pzMode=b.dataset.pzm;lsSet('talvo_chess_pzmode',S.pzMode);S.pz=null;puzzlesView()});
  openPuzzle();
}
function openPuzzle(){
  const P=window.CHESS_PUZZLES||{m1:[],m2:[]},list=P[S.pzMode],pr=pzProg(),el=$('pz-body');
  const i=pr[S.pzMode]||0;
  if(i>=list.length){el.innerHTML='<div class="card" data-i18n-skip><h3>'+T('You solved them all! 🏆','¡Resolviste todos! 🏆')+'</h3><button type="button" class="btn" id="pz-reset">'+T('Start over','Empezar de nuevo')+'</button></div>';$('pz-reset').onclick=()=>{pr[S.pzMode]=0;lsSet('talvo_chess_puzzles',pr);openPuzzle()};return}
  const g=new window.Chess(list[i]);
  S.pz={g,i,mode:S.pzMode,first:true,tries:0,sel:null,tgt:null,solved:false,busy:false};
  el.innerHTML='<div class="ch-game" data-i18n-skip><div class="ch-top"><b>'+(S.pzMode==='m1'?T('Mate in 1','Mate en 1'):T('Mate in 2','Mate en 2'))+' · #'+(i+1)+'</b><span class="ch-lv">'+(g.turn()==='w'?T('White to move','Mueven blancas'):T('Black to move','Mueven negras'))+'</span></div><div id="ch-board"></div><div class="ch-msg" id="ch-msg"></div>'
   +'<div class="ch-ctl" id="pz-ctl"><button type="button" class="btn" id="pz-hint">💡 '+T('Hint','Pista')+'</button><button type="button" class="btn" id="pz-skip">'+T('Skip','Saltar')+'</button></div></div>';
  S.pz.bd=new Board($('ch-board'),pzClick);S.pz.bd.flip=g.turn()==='b';pzDraw();
  say(T('Find the move that wins by force.','Encuentra la jugada que gana por la fuerza.'),'info');
  $('pz-hint').onclick=pzHint;$('pz-skip').onclick=()=>pzNext(false);
}
function pzDraw(){const p=S.pz;p.bd.draw(p.g,{sel:p.sel,tgt:p.tgt,hint:p.hint,last:p.last,check:kingSq(p.g)})}
function pzClick(sq){
  const p=S.pz;if(!p||p.solved||p.busy)return;const g=p.g;
  if(p.sel&&p.tgt&&p.tgt.includes(sq)){
    const mv=g.moves({square:p.sel,verbose:true}).filter(m=>m.to===sq);const go=pr=>pzMove(p.sel,sq,pr);
    if(mv.length>1||mv[0].promotion)promoChoose(go);else go();return}
  const pc=g.get(sq);
  if(pc&&pc.color===p.g.turn()&&!p.replyPending){p.sel=sq;p.tgt=g.moves({square:sq,verbose:true}).map(m=>m.to);p.hint=null}else{p.sel=null;p.tgt=null}
  pzDraw();
}
async function pzMove(from,to,promo){
  const p=S.pz,g=p.g;const fenBefore=g.fen();
  const m=g.move({from,to,promotion:promo||'q'});if(!m)return;
  p.sel=null;p.tgt=null;p.hint=null;p.last=[m.from,m.to];pzDraw();
  if(g.isCheckmate())return pzWin();
  if(p.mode==='m1'||!p.first){return pzWrong(fenBefore)}
  /* mate en 2: la primera jugada vale si, hagan lo que hagan, el mate llega en la siguiente */
  p.busy=true;say(T('Checking…','Comprobando…'),'info');
  let r=null;try{r=await ask({cmd:'analyze',fen:g.fen(),depth:3,ms:900})}catch(e){}
  p.busy=false;
  if(r&&r.best&&r.score<=-29990){
    p.first=false;
    try{const o=g.move({from:r.best.slice(0,2),to:r.best.slice(2,4),promotion:r.best[4]});p.last=[o.from,o.to]}catch(e){}
    pzDraw();say(T('Good! Now deliver checkmate.','¡Bien! Ahora da el jaque mate.'),'good');
  }else pzWrong(fenBefore);
}
function pzWrong(fenBefore){
  const p=S.pz;p.tries++;
  say(p.tries>=2?T('Not that. Press Hint if you are stuck.','Esa no es. Pulsa Pista si estás atorado.'):T('That is not it. Look for checks first!','Esa no es. ¡Busca primero los jaques!'),'bad');
  setTimeout(()=>{if(!S.pz||S.pz!==p)return;p.g=new window.Chess(p.first?fenBefore:fenBefore);p.last=null;p.first=p.mode==='m2'&&p.first;pzDraw()},700);
}
function pzWin(){
  const p=S.pz;p.solved=true;say(T('Checkmate! Well done. ✅','¡Jaque mate! Muy bien. ✅'),'good');
  const pr=pzProg();if((pr[p.mode]||0)<=p.i)pr[p.mode]=p.i+1;lsSet('talvo_chess_puzzles',pr);
  try{window.track&&window.track('leccion_fin','ajedrez',{id:'pz_'+p.mode})}catch(e){}
  $('pz-ctl').innerHTML='<button type="button" class="btn primary" id="pz-next">'+T('Next puzzle →','Siguiente problema →')+'</button>';$('pz-next').onclick=()=>{puzzlesView()};
}
function pzNext(){const pr=pzProg();const p=S.pz;if(p&&(pr[p.mode]||0)<=p.i)pr[p.mode]=p.i+1;lsSet('talvo_chess_puzzles',pr);puzzlesView()}
async function pzHint(){
  const p=S.pz;if(!p||p.solved||p.busy)return;
  const g=p.g;let mv=null;
  const mates=g.moves({verbose:true}).filter(m=>{const t=new window.Chess(g.fen());t.move(m.san);return t.isCheckmate()});
  if(mates.length)mv=mates[0];
  else{p.busy=true;let r=null;try{r=await ask({cmd:'analyze',fen:g.fen(),depth:4,ms:1200})}catch(e){}p.busy=false;if(r&&r.best)mv={from:r.best.slice(0,2),to:r.best.slice(2,4)}}
  if(!mv)return;
  const pc=g.get(mv.from);p.hint=[mv.from];pzDraw();
  say(T('Look at this '+(pc?PIECE_NAME[pc.type][0]:'piece')+'.','Mira esta pieza: '+(pc?PIECE_NAME[pc.type][1]:'pieza')+'.'),'info');
}

window.TalvoChess={open,onSection(name){if(name==='ajedrez')open()}};
})();
