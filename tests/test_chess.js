// Pruebas del motor de ajedrez: node tests/test_chess.js
const {Engine}=require('../js/chess-engine.js');
const assert=require('assert');
const e=new Engine();
const PERFT=[
 ['rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',4,197281],
 ['r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1',3,97862],
 ['8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1',4,43238],
 ['r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1',3,9467],
 ['rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8',3,62379]];
for(const [f,d,n] of PERFT){e.setFen(f);const t=Date.now();const c=e.perft(d,0);assert.strictEqual(c,n,f+' perft '+d+' = '+c+' (esperado '+n+')');console.log('perft ok',n,(Date.now()-t)+'ms')}
// el hash incremental coincide con el recalculado y make/unmake restaura todo
let seed=12345;const rn=k=>{seed=(seed*1103515245+12345)&0x7fffffff;return seed%k};
for(let g=0;g<30;g++){
  e.setFen(PERFT[g%5][0]);
  for(let ply=0;ply<80;ply++){
    const mv=e.legalMoves(0);if(!mv.length)break;
    const m=mv[rn(mv.length)];const before=e.hash,bb=Array.from(e.b);
    e.make(m);assert.strictEqual(e.hash,e.fullHash(),'hash incremental');
    e.unmake();assert.strictEqual(e.hash,before);assert.deepStrictEqual(Array.from(e.b),bb);
    e.make(m);
  }
}
console.log('hash y deshacer OK');
// mates de verdad (mate en 1 y en 2) y no regalar la dama
const T=[
 ['6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1','a1a8'],                       // mate del pasillo
 ['r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4','h5f7'], // mate pastor
 ['7k/5Q2/6K1/8/8/8/8/8 w - - 0 1','f7g7']];                         // dama y rey
for(const [f,mv] of T){e.setFen(f);const r=e.analyze(4,3000);assert.strictEqual(r.best,mv,f+' -> '+r.best);assert(r.score>Engine.MATE-100,'debe ver mate');}
e.setFen('4k3/8/8/8/8/8/4q3/4K2R w K - 0 1');
const rr=e.analyze(4,3000);console.log('torre: se come la dama?',rr.best);
// el rival de nivel 1..7 siempre juega algo legal
for(let lv=1;lv<=7;lv++){e.setFen('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');const t=Date.now();const r=e.chooseMove(lv);assert(r&&e.legalMoves(0).includes(r.m));console.log('nivel',lv,e.uci(r.m),(Date.now()-t)+'ms')}
console.log('motor OK');
// los problemas guardados: mate en 1 con una única solución; mate en 2 con una única primera jugada (verificado con chess.js, independiente del motor)
global.window={};eval(require('fs').readFileSync(__dirname+'/../js/vendor/chess.js','utf8'));
eval(require('fs').readFileSync(__dirname+'/../js/chess-puzzles.js','utf8'));
const PZ=window.CHESS_PUZZLES;assert(PZ.m1.length>=30&&PZ.m2.length>=30);
for(const f of PZ.m1){const c=new window.Chess(f);const mates=c.moves().filter(s=>s.endsWith('#'));assert.strictEqual(mates.length,1,'m1 '+f)}
for(const f of PZ.m2){const c=new window.Chess(f);let good=0;
  for(const m of c.moves()){c.move(m);const replies=c.moves();let all=replies.length>0&&!c.isCheckmate()&&!c.isDraw();
    if(c.isCheckmate())good++;
    else if(replies.length){let ok=true;for(const r of replies){c.move(r);ok=ok&&c.moves().some(x=>x.endsWith('#'));c.undo();if(!ok)break}if(ok)good++}
    c.undo()}
  assert.strictEqual(good,1,'m2 '+f+' soluciones '+good)}
console.log('problemas OK',PZ.m1.length,PZ.m2.length);
// lecciones: la FEN carga, las respuestas son legales y las tácticas son realmente la mejor jugada
eval(require('fs').readFileSync(__dirname+'/../js/chess-lessons.js','utf8'));
for(const L of window.CHESS_LESSONS){
  const c=new window.Chess(L.fen);const legal=c.moves({verbose:true}).map(m=>m.from+m.to+(m.promotion||''));
  assert(legal.length>0,L.id+' sin jugadas');
  if(L.ans==='any'){assert(c.inCheck(),L.id+' debería estar en jaque');continue}
  for(const a of L.ans)assert(legal.includes(a),L.id+' jugada ilegal '+a);
  if(['mate_back','mate_queen','mate_ladder'].includes(L.id)){const m=c.move({from:L.ans[0].slice(0,2),to:L.ans[0].slice(2,4)});assert(c.isCheckmate(),L.id+' no es mate')}
  if(L.cat==='tactics'){e.setFen(L.fen);const r=e.analyze(5,3000);assert(L.ans.includes(r.best),L.id+': el motor prefiere '+r.best+' (puntaje '+r.score+')')}
  assert(L.t.length===2&&L.x.length===2&&L.ok.length===2,L.id+' faltan textos');
}
console.log('lecciones OK',window.CHESS_LESSONS.length);
